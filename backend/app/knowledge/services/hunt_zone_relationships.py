"""Exact, replay-safe Creature-to-Hunt-Zone relationship normalization."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.knowledge.indexing import normalize_name
from app.knowledge.models import KnowledgeEntity, KnowledgeEntityAlias
from app.knowledge.services.graph import KnowledgeGraphService, RelationshipInput
from app.models import Creature, HuntZone


HUNT_ZONE_LOCATION_SCOPE = "hunt_zone_locations"


@dataclass(frozen=True, slots=True)
class HuntZoneRelationshipNormalizationResult:
    source_references: int = 0
    relationships_created: int = 0
    resolved: int = 0
    unresolved: int = 0
    ambiguous: int = 0
    relationships_retired: int = 0
    bridges_recovered: int = 0


@dataclass(frozen=True, slots=True)
class HuntZoneRelationshipRepairBatch:
    processed_creatures: int
    skipped_creatures: int
    next_creature_id: int | None
    has_more: bool
    metrics: HuntZoneRelationshipNormalizationResult


class ExactHuntZoneIndex:
    """Bounded in-memory exact-name index used by historical batch replay."""

    def __init__(self, values: dict[str, tuple[KnowledgeEntity, ...]]):
        self._values = values

    @classmethod
    def build(cls, db: Session) -> "ExactHuntZoneIndex":
        grouped: dict[str, dict[UUID, KnowledgeEntity]] = defaultdict(dict)
        entities = db.query(KnowledgeEntity).filter(
            KnowledgeEntity.entity_type == "hunt_zone",
        ).all()
        by_id = {entity.uuid: entity for entity in entities}
        for entity in entities:
            normalized = normalize_name(entity.canonical_name)
            if normalized:
                grouped[normalized][entity.uuid] = entity
        if by_id:
            aliases = db.query(KnowledgeEntityAlias).filter(
                KnowledgeEntityAlias.entity_type == "hunt_zone",
                KnowledgeEntityAlias.entity_uuid.in_(by_id),
            ).all()
            for alias in aliases:
                normalized = normalize_name(alias.alias)
                if normalized:
                    grouped[normalized][alias.entity_uuid] = by_id[alias.entity_uuid]
        return cls({key: tuple(values.values()) for key, values in grouped.items()})

    def candidates(self, name: str) -> tuple[KnowledgeEntity, ...]:
        return self._values.get(normalize_name(name), ())


def _recover_domain_bridge(
    db: Session,
    *,
    zone_name: str,
    entity: KnowledgeEntity,
) -> bool:
    """Attach an exact unique legacy domain row without creating a new row."""
    normalized = normalize_name(zone_name)
    rows = db.query(HuntZone).filter(HuntZone.normalized_name == normalized).all()
    if len(rows) != 1:
        return False
    row = rows[0]
    if row.knowledge_entity_id == entity.uuid:
        return False
    if row.knowledge_entity_id is not None:
        return False
    existing_bridge = db.query(HuntZone).filter(
        HuntZone.knowledge_entity_id == entity.uuid,
    ).first()
    if existing_bridge is not None:
        return False
    row.knowledge_entity_id = entity.uuid
    if not row.slug:
        row.slug = entity.slug
    db.flush()
    return True


def normalize_creature_hunt_zone_relationships(
    db: Session,
    *,
    creature_entity_uuid: UUID,
    creature_name: str,
    locations: tuple[str, ...] | list[str],
    provider_id: str,
    source_document_id: str,
    exact_index: ExactHuntZoneIndex | None = None,
) -> HuntZoneRelationshipNormalizationResult:
    """Normalize provider location strings without treating text as entities."""
    index = exact_index or ExactHuntZoneIndex.build(db)
    current_ids: set[UUID] = set()
    seen: set[str] = set()
    created = resolved = unresolved = ambiguous = recovered = 0

    for raw_name in locations:
        name = str(raw_name or "").strip()
        normalized = normalize_name(name)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        candidates = index.candidates(name)
        target = candidates[0] if len(candidates) == 1 else None
        state = "resolved" if target is not None else "ambiguous" if len(candidates) > 1 else "unresolved"
        reason = (
            "EXACT_CANONICAL_OR_ALIAS"
            if state == "resolved"
            else "MULTIPLE_CANDIDATES"
            if state == "ambiguous"
            else "NO_CANDIDATE"
        )
        mutation = KnowledgeGraphService.upsert(db, RelationshipInput(
            source_entity_id=creature_entity_uuid,
            source_scope=HUNT_ZONE_LOCATION_SCOPE,
            relationship_type="appears_in",
            target_entity_id=target.uuid if target else None,
            target_entity_type="hunt_zone",
            unresolved_name=None if target else name,
            resolution_state=state,
            confidence="high",
            source_provider_id=provider_id,
            source_document_ref=source_document_id,
            source_context={
                "source_field": "locations",
                "source_creature_name": creature_name,
                "resolution_policy": "exact_name_or_verified_alias_only",
                "resolution_reason": reason,
                "candidate_entity_ids": [str(candidate.uuid) for candidate in candidates],
                "evidence": "explicit_provider_creature_location_reference",
            },
        ))
        current_ids.add(mutation.relationship.id)
        created += int(mutation.created)
        resolved += int(state == "resolved")
        unresolved += int(state == "unresolved")
        ambiguous += int(state == "ambiguous")
        if target is not None:
            recovered += int(_recover_domain_bridge(db, zone_name=name, entity=target))

    retired = KnowledgeGraphService.reconcile_provider(
        db,
        source_entity_id=creature_entity_uuid,
        source_scope=HUNT_ZONE_LOCATION_SCOPE,
        provider_id=provider_id,
        relationship_types={"appears_in"},
        current_ids=current_ids,
    )
    return HuntZoneRelationshipNormalizationResult(
        source_references=len(seen),
        relationships_created=created,
        resolved=resolved,
        unresolved=unresolved,
        ambiguous=ambiguous,
        relationships_retired=retired,
        bridges_recovered=recovered,
    )


def _add_results(
    left: HuntZoneRelationshipNormalizationResult,
    right: HuntZoneRelationshipNormalizationResult,
) -> HuntZoneRelationshipNormalizationResult:
    return HuntZoneRelationshipNormalizationResult(**{
        field_name: getattr(left, field_name) + getattr(right, field_name)
        for field_name in HuntZoneRelationshipNormalizationResult.__dataclass_fields__
    })


class HuntZoneRelationshipRepairService:
    """Replay stored Creature location evidence in bounded resumable batches."""

    @staticmethod
    def run_batch(
        db: Session,
        *,
        after_creature_id: int = 0,
        limit: int = 100,
    ) -> HuntZoneRelationshipRepairBatch:
        if not 1 <= limit <= 500:
            raise ValueError("Hunt Zone relationship repair batches must contain 1 to 500 creatures")
        rows = db.query(Creature).filter(
            Creature.id > after_creature_id,
        ).order_by(Creature.id).limit(limit + 1).all()
        has_more = len(rows) > limit
        rows = rows[:limit]
        index = ExactHuntZoneIndex.build(db)
        total = HuntZoneRelationshipNormalizationResult()
        processed = skipped = 0
        for creature in rows:
            if not creature.knowledge_entity_id or not creature.external_id:
                skipped += 1
                continue
            result = normalize_creature_hunt_zone_relationships(
                db,
                creature_entity_uuid=creature.knowledge_entity_id,
                creature_name=creature.name,
                locations=tuple(creature.locations or ()),
                provider_id=creature.source_name or "tibiawiki",
                source_document_id=f"creature:{creature.external_id}",
                exact_index=index,
            )
            total = _add_results(total, result)
            processed += 1
        return HuntZoneRelationshipRepairBatch(
            processed_creatures=processed,
            skipped_creatures=skipped,
            next_creature_id=rows[-1].id if rows else None,
            has_more=has_more,
            metrics=total,
        )
