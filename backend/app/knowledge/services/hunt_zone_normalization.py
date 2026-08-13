"""Canonical Hunt Zone bridge and evidence-scoped relationship reconciliation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.knowledge.adapters.protocol import KnowledgeNormalizationResult
from app.knowledge.dto import HuntZoneKnowledgeDTO
from app.knowledge.indexing import normalize_name
from app.knowledge.models import KnowledgeEntity, KnowledgeExternalMapping
from app.knowledge.services.entities import KnowledgeEntityService
from app.knowledge.schemas import KnowledgeEntityCreate
from app.knowledge.services.graph import KnowledgeGraphService, RelationshipInput
from app.knowledge.services.item_relationships import exact_entity_candidates
from app.knowledge.services.npc_location_normalization import exact_place_candidates
from app.models import HuntZone
from app.services.entity_metadata_service import EntityMetadataService
from app.services.text_utils import normalize_search_text


@dataclass(frozen=True, slots=True)
class HuntZoneNormalizationApplied:
    status: str
    entity_uuid: UUID
    aliases_created: int
    warnings: int
    metrics: dict[str, int]


def _resolve_entity(db: Session, result: KnowledgeNormalizationResult, dto: HuntZoneKnowledgeDTO):
    mapping = db.query(KnowledgeExternalMapping).filter_by(
        provider_id=result.provider_code,
        entity_type_id="hunt_zone",
        external_id=result.external_id,
    ).first()
    if mapping:
        return mapping.entity, False
    matches = exact_entity_candidates(db, "hunt_zone", dto.canonical_name)
    if len(matches) == 1:
        return matches[0], False
    candidate = result.candidate
    if candidate is None:
        raise ValueError("Hunt Zone normalization requires a canonical candidate")
    return KnowledgeEntityService.create(db, KnowledgeEntityCreate(
        entity_type="hunt_zone",
        canonical_name=candidate.canonical_name,
        language_neutral_id=candidate.language_neutral_id,
        aliases=list(candidate.aliases),
        source_priority=candidate.source_priority,
        allow_name_collision=bool(matches),
        slug_suffix=dto.external_id if matches else None,
    )), True


def _ensure_mapping(db: Session, result: KnowledgeNormalizationResult, entity: KnowledgeEntity, dto: HuntZoneKnowledgeDTO):
    mapping = db.query(KnowledgeExternalMapping).filter_by(
        provider_id=result.provider_code,
        entity_type_id="hunt_zone",
        external_id=result.external_id,
    ).first()
    if mapping is None:
        mapping = KnowledgeExternalMapping(
            provider_id=result.provider_code,
            entity_type_id="hunt_zone",
            external_id=result.external_id,
            entity_uuid=entity.uuid,
        )
        db.add(mapping)
    elif mapping.entity_uuid != entity.uuid:
        raise ValueError("Hunt Zone provider identity conflicts with an existing canonical record")
    mapping.provider_metadata = dict(dto.provider_metadata)


def _bridge(db: Session, entity: KnowledgeEntity, dto: HuntZoneKnowledgeDTO) -> tuple[bool, bool, bool]:
    row = db.query(HuntZone).filter_by(knowledge_entity_id=entity.uuid).first()
    if row is None:
        row = db.query(HuntZone).filter_by(source_provider="tibiawiki", external_id=dto.external_id).first()
    if row is None:
        matches = db.query(HuntZone).filter(
            HuntZone.normalized_name == normalize_search_text(dto.canonical_name),
        ).all()
        row = matches[0] if len(matches) == 1 and matches[0].knowledge_entity_id is None else None
    if row is not None and row.knowledge_entity_id not in (None, entity.uuid):
        raise ValueError("Hunt Zone bridge identity conflicts with an existing canonical record")
    created = row is None
    if row is None:
        row = HuntZone(
            name=dto.canonical_name,
            normalized_name=normalize_search_text(dto.canonical_name),
            slug=entity.slug,
            source_provider="tibiawiki",
            source_name="tibiawiki",
            external_id=dto.external_id,
            knowledge_entity_id=entity.uuid,
            data_version=1,
            protected_fields=[],
        )
        db.add(row)
        db.flush()

    prior_supplied = set(row.supplied_fields or [])

    def adds_information(previous, current) -> bool:
        if previous in (None, ""):
            return current not in (None, "", [], {})
        if isinstance(previous, dict) and isinstance(current, dict):
            return any(
                key not in previous or adds_information(previous.get(key), value)
                for key, value in current.items()
            )
        if isinstance(previous, (list, tuple)) and isinstance(current, (list, tuple)):
            return bool(current) and not previous
        return False

    canonical_data = dto.to_canonical_data()
    repaired = bool(
        not created
        and (
            not prior_supplied
            or not dto.supplied_fields.issubset(prior_supplied)
            or adds_information(row.raw_data or {}, canonical_data)
        )
    )
    protected = set(row.protected_fields or [])
    changed = False

    def assign(field_name: str, value, supplied_field: str | None = None) -> None:
        nonlocal changed
        if field_name in protected:
            return
        if supplied_field is not None and supplied_field not in dto.supplied_fields:
            return
        if value in (None, ""):
            return
        if getattr(row, field_name) != value:
            setattr(row, field_name, value)
            changed = True

    assign("knowledge_entity_id", entity.uuid)
    assign("name", dto.canonical_name)
    assign("normalized_name", normalize_search_text(dto.canonical_name))
    assign("slug", entity.slug)
    assign("source_provider", "tibiawiki")
    assign("source_name", "tibiawiki")
    assign("external_id", dto.external_id)
    assign("source_url", dto.source_reference, "source_reference")
    assign("city", dto.city, "city")
    assign("region", dto.location, "location")
    assign("min_level", dto.minimum_recommended_level, "vocation_recommendations")
    assign("exp_rating", str(dto.experience_rating) if dto.experience_rating is not None else None, "experience_rating")
    assign("profit_rating", str(dto.loot_rating) if dto.loot_rating is not None else None, "loot_rating")
    assign("requires_premium", dto.premium_required, "premium_required")
    assign("description", dto.description, "description")
    assign("map_image_url", dto.image_reference, "image_reference")

    assign("raw_data", canonical_data)
    assign("provider_metadata", {**dict(dto.provider_metadata), "canonical": canonical_data})
    assign("supplied_fields", sorted(dto.supplied_fields))
    if not created and changed:
        row.data_version = max(1, row.data_version or 1) + 1
    row.last_synced_at = datetime.now(UTC)
    EntityMetadataService.update_sync_timestamp(
        db,
        entity_type="hunt_zone",
        entity_key=row.normalized_name,
        display_name=row.name,
        entity_id=row.id,
    )
    db.flush()
    return created, changed, repaired


def _named_relationship(
    db: Session,
    *,
    source: KnowledgeEntity,
    relation: str,
    name: str,
    target_types: tuple[str, ...],
    unresolved_type: str,
    scope: str,
    document: str,
) -> tuple[UUID, bool]:
    if set(target_types).issubset({"area", "town", "location"}):
        matches = exact_place_candidates(db, name, target_types)
    else:
        matches = [match for target_type in target_types for match in exact_entity_candidates(db, target_type, name)]
    unique = {match.uuid: match for match in matches}
    target = next(iter(unique.values())) if len(unique) == 1 else None
    state = "resolved" if target else "ambiguous" if len(unique) > 1 else "unresolved"
    mutation = KnowledgeGraphService.upsert(db, RelationshipInput(
        source_entity_id=source.uuid,
        source_scope=scope,
        relationship_type=relation,
        target_entity_id=target.uuid if target else None,
        target_entity_type=target.entity_type if target else unresolved_type,
        unresolved_name=None if target else name,
        resolution_state=state,
        confidence="high",
        source_provider_id="tibiawiki",
        source_document_ref=document,
        source_context={
            "resolution_policy": "exact_name_or_alias_only",
            "candidate_entity_ids": [str(value) for value in unique] if len(unique) > 1 else [],
            "evidence": "explicit_provider_field_or_list",
        },
    ))
    return mutation.relationship.id, state != "resolved"


def _sync_relationships(db: Session, entity: KnowledgeEntity, dto: HuntZoneKnowledgeDTO) -> tuple[int, int, int]:
    document = f"hunt_zone:{dto.external_id}"
    total = unresolved = retired = 0
    specs = (
        ("creatures", "creatures", "has_creature", dto.creatures, ("creature", "boss"), "creature"),
        ("access_quests", "access", "requires_hunt_quest", dto.access_quests, ("quest",), "quest"),
        ("city", "location", "located_at", (dto.city,) if dto.city else (), ("town",), "town"),
        ("location", "location", "located_at", (dto.location,) if dto.location else (), ("area", "location"), "location"),
    )
    by_scope: dict[str, tuple[set[str], set[UUID]]] = {}
    for supplied_field, scope, relation, names, target_types, unresolved_type in specs:
        if supplied_field not in dto.supplied_fields:
            continue
        relation_types, current_ids = by_scope.setdefault(scope, (set(), set()))
        relation_types.add(relation)
        for name in dict.fromkeys(value.strip() for value in names if value.strip()):
            relationship_id, is_unresolved = _named_relationship(
                db,
                source=entity,
                relation=relation,
                name=name,
                target_types=target_types,
                unresolved_type=unresolved_type,
                scope=scope,
                document=document,
            )
            current_ids.add(relationship_id)
            total += 1
            unresolved += int(is_unresolved)
    for scope, (relation_types, current_ids) in by_scope.items():
        retired += KnowledgeGraphService.reconcile_provider(
            db,
            source_entity_id=entity.uuid,
            source_scope=scope,
            provider_id="tibiawiki",
            relationship_types=relation_types,
            current_ids=current_ids,
        )
    return total, unresolved, retired


class HuntZoneKnowledgeNormalizationService:
    @staticmethod
    def apply(db: Session, result: KnowledgeNormalizationResult) -> HuntZoneNormalizationApplied:
        if result.canonical_data is None or result.candidate is None:
            raise ValueError("Hunt Zone normalization requires canonical data")
        dto = HuntZoneKnowledgeDTO.from_canonical_data(result.canonical_data)
        entity, entity_created = _resolve_entity(db, result, dto)
        _ensure_mapping(db, result, entity, dto)
        bridge_created, bridge_changed, repaired = _bridge(db, entity, dto)
        relationships, unresolved, retired = _sync_relationships(db, entity, dto)
        status = "created" if entity_created or bridge_created else "updated" if bridge_changed or retired else "unchanged"
        return HuntZoneNormalizationApplied(
            status=status,
            entity_uuid=entity.uuid,
            aliases_created=len(result.candidate.aliases) + int(entity_created),
            warnings=len(result.warnings),
            metrics={
                "relationships_reconciled": relationships,
                "relationships_retired": retired,
                "unresolved_relationships": unresolved,
                "entities_repaired": int(repaired),
            },
        )
