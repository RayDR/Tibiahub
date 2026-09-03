"""Canonical Hunt Zone bridge and evidence-scoped relationship reconciliation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session, selectinload
from sqlalchemy.exc import IntegrityError

from app.knowledge.adapters.protocol import KnowledgeNormalizationResult
from app.knowledge.dto import HuntZoneKnowledgeDTO
from app.knowledge.indexing import normalize_name
from app.knowledge.metadata import refresh_search_metadata
from app.knowledge.models import (
    KnowledgeEntity,
    KnowledgeEntityAlias,
    KnowledgeExternalMapping,
    KnowledgeSearchMetadata,
)
from app.knowledge.services.entities import (
    DuplicateKnowledgeAliasError,
    DuplicateKnowledgeEntityError,
    KnowledgeEntityService,
)
from app.knowledge.services.failures import InvalidNormalizationContractError
from app.knowledge.schemas import KnowledgeEntityCreate
from app.knowledge.services.graph import KnowledgeGraphService, RelationshipInput
from app.knowledge.services.item_relationships import exact_entity_candidates
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


class HuntZoneIdentityConflictError(InvalidNormalizationContractError):
    code = "hunt_zone_identity_conflict"
    safe_message = "The Hunting Zone identity conflicts with an existing canonical record."


def _resolve_entity(db: Session, result: KnowledgeNormalizationResult, dto: HuntZoneKnowledgeDTO):
    mapping = db.query(KnowledgeExternalMapping).filter_by(
        provider_id=result.provider_code,
        entity_type_id="hunt_zone",
        external_id=result.external_id,
    ).first()
    if mapping:
        return mapping.entity, False
    matches = exact_entity_candidates(db, "hunt_zone", dto.canonical_name)
    available = [
        entity
        for entity in matches
        if db.query(KnowledgeExternalMapping).filter_by(
            provider_id=result.provider_code,
            entity_type_id="hunt_zone",
            entity_uuid=entity.uuid,
        ).first() is None
    ]
    if len(available) == 1:
        return available[0], False
    if len(available) > 1:
        raise HuntZoneIdentityConflictError()
    candidate = result.candidate
    if candidate is None:
        raise ValueError("Hunt Zone normalization requires a canonical candidate")
    collision = bool(matches)
    return KnowledgeEntityService.create(db, KnowledgeEntityCreate(
        entity_type="hunt_zone",
        canonical_name=candidate.canonical_name,
        language_neutral_id=candidate.language_neutral_id,
        aliases=[],
        source_priority=candidate.source_priority,
        allow_name_collision=collision,
        slug_suffix=result.external_id if collision else None,
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
        try:
            with db.begin_nested():
                db.add(mapping)
                db.flush()
        except IntegrityError as exc:
            existing = db.query(KnowledgeExternalMapping).filter_by(
                provider_id=result.provider_code,
                entity_type_id="hunt_zone",
                external_id=result.external_id,
            ).one_or_none()
            if existing is None or existing.entity_uuid != entity.uuid:
                raise HuntZoneIdentityConflictError() from exc
            mapping = existing
    elif mapping.entity_uuid != entity.uuid:
        raise HuntZoneIdentityConflictError()
    mapping.provider_metadata = dict(dto.provider_metadata)


def _update_aliases(
    db: Session,
    entity: KnowledgeEntity,
    aliases: tuple[str, ...],
) -> tuple[int, int]:
    existing = {
        alias.normalized_alias
        for alias in db.query(KnowledgeEntityAlias).filter(
            KnowledgeEntityAlias.entity_uuid == entity.uuid,
        ).all()
    }
    created = warnings = 0
    for alias in aliases:
        normalized = normalize_name(alias)
        if not normalized or normalized in existing:
            continue
        try:
            KnowledgeEntityService.add_alias(db, entity, alias)
            existing.add(normalized)
            created += 1
        except (DuplicateKnowledgeAliasError, DuplicateKnowledgeEntityError):
            warnings += 1
    if created:
        refresh_search_metadata(entity)
    return created, warnings


def _update_entity(
    db: Session,
    entity: KnowledgeEntity,
    result: KnowledgeNormalizationResult,
    dto: HuntZoneKnowledgeDTO,
) -> tuple[bool, int, int]:
    candidate = result.candidate
    if candidate is None:
        raise InvalidNormalizationContractError()
    if entity.canonical_name != candidate.canonical_name:
        canonical_matches = [
            match
            for match in exact_entity_candidates(db, "hunt_zone", candidate.canonical_name)
            if match.uuid != entity.uuid
        ]
        if canonical_matches:
            raise HuntZoneIdentityConflictError()
    aliases_created, warnings = _update_aliases(
        db,
        entity,
        (candidate.canonical_name, *dto.aliases),
    )
    changed = aliases_created > 0
    if candidate.source_priority <= entity.source_priority:
        if entity.canonical_name != candidate.canonical_name:
            KnowledgeEntityService.update_name(db, entity, candidate.canonical_name)
            changed = True
        for field_name, value in (
            ("source_priority", candidate.source_priority),
            ("status", candidate.status),
            ("visibility", candidate.visibility),
            ("search_weight", candidate.search_weight),
        ):
            if getattr(entity, field_name) != value:
                setattr(entity, field_name, value)
                changed = True
    refresh_search_metadata(entity)
    return changed, aliases_created, warnings


def _bridge(db: Session, entity: KnowledgeEntity, dto: HuntZoneKnowledgeDTO) -> tuple[bool, bool, bool]:
    row = db.query(HuntZone).filter_by(knowledge_entity_id=entity.uuid).first()
    if row is None:
        row = db.query(HuntZone).filter_by(source_provider="tibiawiki", external_id=dto.external_id).first()
    if row is not None and row.knowledge_entity_id not in (None, entity.uuid):
        raise HuntZoneIdentityConflictError()
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

    def clear_unknown(field_name: str) -> None:
        nonlocal changed
        if field_name in protected:
            return
        if getattr(row, field_name) is not None:
            setattr(row, field_name, None)
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
    if "premium_required" not in dto.supplied_fields:
        clear_unknown("requires_premium")
    for legacy_field in (
        "requires_quest",
        "knights_recommended",
        "paladins_recommended",
        "sorcerers_recommended",
        "druids_recommended",
        "monks_recommended",
    ):
        clear_unknown(legacy_field)
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


def _exact_candidate_index(
    db: Session,
    names: tuple[str, ...],
    target_types: tuple[str, ...],
) -> dict[str, list[KnowledgeEntity]]:
    normalized_names = {normalize_name(name) for name in names if normalize_name(name)}
    if not normalized_names:
        return {}
    indexed: dict[str, dict[UUID, KnowledgeEntity]] = {
        normalized: {} for normalized in normalized_names
    }
    canonical_rows = db.query(
        KnowledgeSearchMetadata.normalized_name,
        KnowledgeEntity,
    ).join(
        KnowledgeEntity,
        KnowledgeEntity.uuid == KnowledgeSearchMetadata.entity_uuid,
    ).options(
        selectinload(KnowledgeEntity.aliases),
    ).filter(
        KnowledgeEntity.entity_type.in_(target_types),
        KnowledgeSearchMetadata.normalized_name.in_(normalized_names),
    ).all()
    for normalized, entity in canonical_rows:
        indexed[normalized][entity.uuid] = entity
    alias_rows = db.query(
        KnowledgeEntityAlias.normalized_alias,
        KnowledgeEntity,
    ).join(
        KnowledgeEntity,
        KnowledgeEntity.uuid == KnowledgeEntityAlias.entity_uuid,
    ).options(
        selectinload(KnowledgeEntity.aliases),
    ).filter(
        KnowledgeEntity.entity_type.in_(target_types),
        KnowledgeEntityAlias.entity_type.in_(target_types),
        KnowledgeEntityAlias.normalized_alias.in_(normalized_names),
    ).all()
    for normalized, entity in alias_rows:
        indexed[normalized][entity.uuid] = entity
    return {
        normalized: list(matches.values())
        for normalized, matches in indexed.items()
    }


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
    matches: list[KnowledgeEntity],
    retain_unresolved: bool = True,
) -> tuple[UUID | None, str | None]:
    unique = {match.uuid: match for match in matches}
    target = next(iter(unique.values())) if len(unique) == 1 else None
    if target is None and not retain_unresolved:
        return None, None
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
    return mutation.relationship.id, state


def _sync_relationships(
    db: Session,
    entity: KnowledgeEntity,
    dto: HuntZoneKnowledgeDTO,
) -> tuple[int, int, int, int, int]:
    document = f"hunt_zone:{dto.external_id}"
    total = resolved = unresolved = ambiguous = retired = 0
    specs = (
        ("creatures", "creatures", "has_creature", dto.creatures, ("creature", "boss"), "creature", True),
        ("access_quests", "access", "requires_hunt_quest", dto.access_quests, ("quest",), "quest", True),
        ("city", "location", "located_at", (dto.city,) if dto.city else (), ("town", "location"), "town", True),
        # TibiaWiki's free-form location field often contains prose rather than a
        # canonical place identity. Keep that text on HuntZone.region, but only
        # project a graph edge when the complete value resolves exactly.
        ("location", "location", "located_at", (dto.location,) if dto.location else (), ("area", "location"), "location", False),
    )
    by_scope: dict[str, tuple[set[str], set[UUID]]] = {}
    for supplied_field, scope, relation, names, target_types, unresolved_type, retain_unresolved in specs:
        if supplied_field not in dto.supplied_fields:
            continue
        relation_types, current_ids = by_scope.setdefault(scope, (set(), set()))
        relation_types.add(relation)
        unique_names = tuple(dict.fromkeys(value.strip() for value in names if value.strip()))
        candidate_index = _exact_candidate_index(db, unique_names, target_types)
        for name in unique_names:
            relationship_id, state = _named_relationship(
                db,
                source=entity,
                relation=relation,
                name=name,
                target_types=target_types,
                unresolved_type=unresolved_type,
                scope=scope,
                document=document,
                matches=candidate_index.get(normalize_name(name), []),
                retain_unresolved=retain_unresolved,
            )
            if relationship_id is None:
                continue
            current_ids.add(relationship_id)
            total += 1
            resolved += int(state == "resolved")
            unresolved += int(state == "unresolved")
            ambiguous += int(state == "ambiguous")
    for scope, (relation_types, current_ids) in by_scope.items():
        retired += KnowledgeGraphService.reconcile_provider(
            db,
            source_entity_id=entity.uuid,
            source_scope=scope,
            provider_id="tibiawiki",
            relationship_types=relation_types,
            current_ids=current_ids,
        )
    return total, resolved, unresolved, ambiguous, retired


class HuntZoneKnowledgeNormalizationService:
    @staticmethod
    def apply(db: Session, result: KnowledgeNormalizationResult) -> HuntZoneNormalizationApplied:
        if result.canonical_data is None or result.candidate is None:
            raise ValueError("Hunt Zone normalization requires canonical data")
        dto = HuntZoneKnowledgeDTO.from_canonical_data(result.canonical_data)
        entity, entity_created = _resolve_entity(db, result, dto)
        _ensure_mapping(db, result, entity, dto)
        entity_changed, aliases_created, alias_warnings = _update_entity(db, entity, result, dto)
        bridge_created, bridge_changed, repaired = _bridge(db, entity, dto)
        relationships, resolved, unresolved, ambiguous, retired = _sync_relationships(db, entity, dto)
        status = (
            "created"
            if entity_created or bridge_created
            else "updated"
            if entity_changed or bridge_changed or aliases_created or retired
            else "unchanged"
        )
        return HuntZoneNormalizationApplied(
            status=status,
            entity_uuid=entity.uuid,
            aliases_created=aliases_created,
            warnings=len(result.warnings) + alias_warnings,
            metrics={
                "relationships_reconciled": relationships,
                "resolved_relationships": resolved,
                "relationships_retired": retired,
                "unresolved_relationships": unresolved,
                "ambiguous_relationships": ambiguous,
                "entities_repaired": int(repaired),
            },
        )
