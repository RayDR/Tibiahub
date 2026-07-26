"""Canonical NPC/location normalization and exact graph-reference resolution."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.knowledge.adapters.protocol import KnowledgeNormalizationResult
from app.knowledge.dto import LocationKnowledgeDTO, NpcKnowledgeDTO
from app.knowledge.events import KnowledgeEventType, emit_event
from app.knowledge.indexing import normalize_name
from app.knowledge.metadata import refresh_search_metadata
from app.knowledge.models import (
    KnowledgeEntity, KnowledgeEntityAlias, KnowledgeExternalMapping, KnowledgeRelationship,
)
from app.knowledge.schemas import KnowledgeEntityCreate
from app.knowledge.services.entities import (
    DuplicateKnowledgeAliasError, DuplicateKnowledgeEntityError, KnowledgeEntityService,
)
from app.knowledge.services.failures import InvalidNormalizationContractError
from app.knowledge.services.graph import KnowledgeGraphService, RelationshipInput
from app.knowledge.services.item_relationships import exact_entity_candidates
from app.models.external_data import TibiaWikiLocation, TibiaWikiNpc
from app.services.entity_metadata_service import EntityMetadataService
from app.services.text_utils import normalize_search_text


class NamedEntityIdentityConflictError(InvalidNormalizationContractError):
    code = "named_entity_identity_conflict"
    safe_message = "The provider identity conflicts with an existing canonical record."


PLACE_ENTITY_TYPES = ("location", "area", "town")


@dataclass(frozen=True, slots=True)
class NamedEntityNormalizationApplied:
    status: str
    entity_uuid: UUID
    aliases_created: int
    warnings: int
    metrics: dict[str, int]


def _provider_mapping(db: Session, provider: str, entity_type: str, external_id: str):
    entity_types = PLACE_ENTITY_TYPES if entity_type in PLACE_ENTITY_TYPES else (entity_type,)
    matches = db.query(KnowledgeExternalMapping).filter(
        KnowledgeExternalMapping.provider_id == provider,
        KnowledgeExternalMapping.entity_type_id.in_(entity_types),
        KnowledgeExternalMapping.external_id == external_id,
    ).all()
    if len(matches) > 1:
        raise NamedEntityIdentityConflictError()
    return matches[0] if matches else None


def _entity_mapping(db: Session, provider: str, entity_type: str, entity_uuid: UUID):
    entity_types = PLACE_ENTITY_TYPES if entity_type in PLACE_ENTITY_TYPES else (entity_type,)
    return db.query(KnowledgeExternalMapping).filter(
        KnowledgeExternalMapping.provider_id == provider,
        KnowledgeExternalMapping.entity_type_id.in_(entity_types),
        KnowledgeExternalMapping.entity_uuid == entity_uuid,
    ).first()


def _resolve_entity(db: Session, result: KnowledgeNormalizationResult, dto, entity_type: str):
    if not result.provider_code or not result.external_id or result.candidate is None:
        raise InvalidNormalizationContractError()
    mapping = _provider_mapping(db, result.provider_code, entity_type, result.external_id)
    if mapping:
        return mapping.entity, False
    matches = exact_entity_candidates(db, entity_type, dto.canonical_name)
    available = [row for row in matches if _entity_mapping(db, result.provider_code, entity_type, row.uuid) is None]
    if len(available) > 1:
        raise NamedEntityIdentityConflictError()
    if len(available) == 1:
        return available[0], False
    candidate = result.candidate
    collision = bool(matches)
    return KnowledgeEntityService.create(db, KnowledgeEntityCreate(
        entity_type=entity_type, canonical_name=candidate.canonical_name,
        language_neutral_id=candidate.language_neutral_id, aliases=list(candidate.aliases),
        status=candidate.status, source_priority=candidate.source_priority,
        visibility=candidate.visibility, search_weight=candidate.search_weight,
        allow_name_collision=collision, slug_suffix=result.external_id if collision else None,
    )), True


def _ensure_mapping(db: Session, result: KnowledgeNormalizationResult, entity: KnowledgeEntity, dto, entity_type: str):
    existing = _provider_mapping(db, result.provider_code or "", entity_type, result.external_id or "")
    if existing:
        if existing.entity_uuid != entity.uuid:
            raise NamedEntityIdentityConflictError()
        existing.provider_metadata = dict(dto.provider_metadata)
        return
    try:
        with db.begin_nested():
            db.add(KnowledgeExternalMapping(
                provider_id=result.provider_code, entity_type_id=entity.entity_type,
                external_id=result.external_id, entity_uuid=entity.uuid,
                provider_metadata=dict(dto.provider_metadata),
            ))
            db.flush()
    except IntegrityError as exc:
        raise NamedEntityIdentityConflictError() from exc


def _update_entity(db: Session, entity: KnowledgeEntity, result: KnowledgeNormalizationResult):
    candidate = result.candidate
    if candidate is None:
        raise InvalidNormalizationContractError()
    changed = False
    if candidate.source_priority <= entity.source_priority:
        for field, value in (
            ("canonical_name", candidate.canonical_name), ("source_priority", candidate.source_priority),
            ("status", candidate.status), ("visibility", candidate.visibility),
            ("search_weight", candidate.search_weight),
        ):
            if value not in (None, "") and getattr(entity, field) != value:
                setattr(entity, field, value)
                changed = True
    existing = {row.normalized_alias for row in db.query(KnowledgeEntityAlias).filter_by(entity_uuid=entity.uuid).all()}
    aliases_created = 0
    warnings = len(result.warnings)
    for alias in candidate.aliases:
        normalized = normalize_name(alias)
        if not normalized or normalized in existing:
            continue
        try:
            KnowledgeEntityService.add_alias(db, entity, alias)
            existing.add(normalized)
            aliases_created += 1
        except (DuplicateKnowledgeAliasError, DuplicateKnowledgeEntityError):
            warnings += 1
    refresh_search_metadata(entity)
    return changed or aliases_created > 0, aliases_created, warnings


def _assign_bridge(row, dto, values: tuple[tuple[str, object, str | None], ...], *, created: bool) -> bool:
    changed = False
    protected = set(row.protected_fields or [])
    for field, value, supplied in values:
        if field in protected or value is None or value == "":
            continue
        if supplied and supplied not in dto.supplied_fields:
            continue
        if value in ([], {}) and not created and getattr(row, field) not in (None, "", [], {}):
            continue
        if getattr(row, field) != value:
            setattr(row, field, value)
            changed = True
    return changed


def _bridge_npc(db: Session, entity: KnowledgeEntity, dto: NpcKnowledgeDTO):
    row = db.query(TibiaWikiNpc).filter_by(knowledge_entity_id=entity.uuid).first()
    if row is None:
        row = db.query(TibiaWikiNpc).filter_by(source_name="tibiawiki", external_id=dto.external_id).first()
    if row is not None and row.knowledge_entity_id != entity.uuid:
        raise NamedEntityIdentityConflictError()
    created = row is None
    if row is None:
        row = TibiaWikiNpc(
            name=dto.canonical_name, normalized_name=normalize_search_text(dto.canonical_name),
            slug=entity.slug, external_id=dto.external_id, source_name="tibiawiki",
            knowledge_entity_id=entity.uuid, protected_fields=[], supplied_fields=[], data_version=1,
        )
        db.add(row)
        db.flush()
    changed = _assign_bridge(row, dto, (
        ("name", dto.canonical_name, None), ("normalized_name", normalize_search_text(dto.canonical_name), None),
        ("slug", entity.slug, None), ("external_id", dto.external_id, None), ("source_name", "tibiawiki", None),
        ("source_url", dto.source_reference, "source_reference"), ("image_url", dto.image_reference, "image_reference"),
        ("title", dto.title, "title"), ("occupation", dto.occupation, "occupation"),
        ("sex", dto.sex, "sex"), ("location_name", dto.location_name, "location_name"),
        ("description", dto.description, "description"),
        ("buys", [asdict(value) for value in dto.buys], "buys"),
        ("sells", [asdict(value) for value in dto.sells], "sells"),
        ("destinations", [asdict(value) for value in dto.destinations], "destinations"),
        ("related_quests", [asdict(value) for value in dto.related_quests], "related_quests"),
        ("provider_metadata", dict(dto.provider_metadata), None),
        ("supplied_fields", sorted(dto.supplied_fields), None),
    ), created=created)
    if not created and changed:
        row.data_version = max(1, row.data_version or 1) + 1
    row.last_synced_at = datetime.now(UTC)
    EntityMetadataService.update_sync_timestamp(
        db, entity_type="npc", entity_key=row.normalized_name, display_name=row.name, entity_id=row.id,
    )
    db.flush()
    return created or changed


def _bridge_location(db: Session, entity: KnowledgeEntity, dto: LocationKnowledgeDTO):
    row = db.query(TibiaWikiLocation).filter_by(knowledge_entity_id=entity.uuid).first()
    if row is None:
        row = db.query(TibiaWikiLocation).filter_by(source_name="tibiawiki", external_id=dto.external_id).first()
    if row is not None and row.knowledge_entity_id != entity.uuid:
        raise NamedEntityIdentityConflictError()
    created = row is None
    if row is None:
        row = TibiaWikiLocation(
            name=dto.canonical_name, normalized_name=normalize_search_text(dto.canonical_name),
            slug=entity.slug, external_id=dto.external_id, source_name="tibiawiki",
            knowledge_entity_id=entity.uuid, protected_fields=[], supplied_fields=[], data_version=1,
        )
        db.add(row)
        db.flush()
    changed = _assign_bridge(row, dto, (
        ("name", dto.canonical_name, None), ("normalized_name", normalize_search_text(dto.canonical_name), None),
        ("slug", entity.slug, None), ("external_id", dto.external_id, None), ("source_name", "tibiawiki", None),
        ("source_url", dto.source_reference, "source_reference"), ("image_url", dto.image_reference, "image_reference"),
        ("location_kind", dto.location_kind, "location_kind"), ("region", dto.region, "region"),
        ("parent_location", dto.parent_location, "parent_location"), ("description", dto.description, "description"),
        ("premium_required", dto.premium_required, "premium_required"),
        ("minimum_level", dto.minimum_level, "minimum_level"), ("maximum_level", dto.maximum_level, "maximum_level"),
        ("npcs", [asdict(value) for value in dto.npcs], "npcs"),
        ("creatures", [asdict(value) for value in dto.creatures], "creatures"),
        ("quests", [asdict(value) for value in dto.quests], "quests"),
        ("sublocations", [asdict(value) for value in dto.sublocations], "sublocations"),
        ("access_notes", dto.access_notes, "access_notes"),
        ("provider_metadata", dict(dto.provider_metadata), None),
        ("supplied_fields", sorted(dto.supplied_fields), None),
    ), created=created)
    if not created and changed:
        row.data_version = max(1, row.data_version or 1) + 1
    row.last_synced_at = datetime.now(UTC)
    EntityMetadataService.update_sync_timestamp(
        db, entity_type=entity.entity_type, entity_key=row.normalized_name, display_name=row.name, entity_id=row.id,
    )
    db.flush()
    return created or changed


def exact_place_candidates(db: Session, name: str, entity_types: tuple[str, ...] = PLACE_ENTITY_TYPES) -> list[KnowledgeEntity]:
    matches: dict[UUID, KnowledgeEntity] = {}
    for entity_type in entity_types:
        for entity in exact_entity_candidates(db, entity_type, name):
            matches[entity.uuid] = entity
    return list(matches.values())


def _upsert_named_relationship(
    db: Session,
    *,
    source_entity: KnowledgeEntity,
    relationship_type: str,
    target_name: str,
    candidate_types: tuple[str, ...],
    unresolved_type: str,
    provider_id: str,
    source_document_ref: str | None,
    source_scope: str,
    context: str,
) -> UUID:
    matches = exact_place_candidates(db, target_name, candidate_types)
    target = matches[0] if len(matches) == 1 else None
    state = "resolved" if target is not None else "ambiguous" if len(matches) > 1 else "unresolved"
    mutation = KnowledgeGraphService.upsert(db, RelationshipInput(
        source_entity_id=source_entity.uuid,
        source_scope=source_scope,
        relationship_type=relationship_type,
        target_entity_id=target.uuid if target else None,
        target_entity_type=target.entity_type if target else unresolved_type,
        unresolved_name=None if target else target_name,
        resolution_state=state,
        confidence="high",
        source_provider_id=provider_id,
        source_document_ref=source_document_ref,
        source_context={
            "context": context,
            "resolution_policy": "exact_name_or_alias_only",
            "candidate_entity_ids": [str(match.uuid) for match in matches] if len(matches) > 1 else [],
        },
    ))
    return mutation.relationship.id


def _sync_npc_location_relationships(
    db: Session,
    *,
    entity: KnowledgeEntity,
    dto: NpcKnowledgeDTO | LocationKnowledgeDTO,
    provider_id: str,
) -> int:
    current_ids: set[UUID] = set()
    relationship_types: set[str] = set()
    source_document_ref = f"{'npc' if isinstance(dto, NpcKnowledgeDTO) else 'location'}:{dto.external_id}"
    if isinstance(dto, NpcKnowledgeDTO):
        relationship_types.add("located_at")
        if dto.location_name:
            current_ids.add(_upsert_named_relationship(
                db, source_entity=entity, relationship_type="located_at",
                target_name=dto.location_name, candidate_types=PLACE_ENTITY_TYPES,
                unresolved_type="location", provider_id=provider_id,
                source_document_ref=source_document_ref, source_scope="location",
                context="npc.location_name",
            ))
    elif entity.entity_type == "location":
        relationship_types.add("contained_in")
        parent = dto.parent_location or dto.region
        if parent:
            current_ids.add(_upsert_named_relationship(
                db, source_entity=entity, relationship_type="contained_in",
                target_name=parent, candidate_types=("area",), unresolved_type="area",
                provider_id=provider_id, source_document_ref=source_document_ref,
                source_scope="parent", context="location.parent_location_or_region",
            ))
    elif entity.entity_type == "area":
        relationship_types.add("contained_in")
        parent = dto.parent_location or dto.region
        if parent:
            current_ids.add(_upsert_named_relationship(
                db, source_entity=entity, relationship_type="contained_in",
                target_name=parent, candidate_types=("town",), unresolved_type="town",
                provider_id=provider_id, source_document_ref=source_document_ref,
                source_scope="parent", context="area.parent_location_or_region",
            ))
    if relationship_types:
        KnowledgeGraphService.reconcile_provider(
            db, source_entity_id=entity.uuid, source_scope="location" if isinstance(dto, NpcKnowledgeDTO) else "parent",
            provider_id=provider_id, relationship_types=relationship_types, current_ids=current_ids,
        )
    return len(current_ids)


def sync_access_destination(
    db: Session,
    *,
    access_entity: KnowledgeEntity,
    destination_name: str | None,
    provider_id: str,
    source_document_ref: str | None,
) -> int:
    current_ids: set[UUID] = set()
    if destination_name:
        current_ids.add(_upsert_named_relationship(
            db, source_entity=access_entity, relationship_type="leads_to",
            target_name=destination_name, candidate_types=PLACE_ENTITY_TYPES,
            unresolved_type="location", provider_id=provider_id,
            source_document_ref=source_document_ref, source_scope="destination",
            context="access.destination_name",
        ))
    KnowledgeGraphService.reconcile_provider(
        db, source_entity_id=access_entity.uuid, source_scope="destination",
        provider_id=provider_id, relationship_types={"leads_to"}, current_ids=current_ids,
    )
    return len(current_ids)


def _candidate_types_for_reference(row: KnowledgeRelationship) -> tuple[str, ...]:
    if row.relationship_type_code == "contained_in":
        return ("town",) if row.source_entity.entity_type == "area" else ("area",)
    if row.target_entity_type_id in PLACE_ENTITY_TYPES:
        return PLACE_ENTITY_TYPES
    return (row.target_entity_type_id,)


def _resolve_exact_references(db: Session, entity: KnowledgeEntity) -> int:
    names = {normalize_name(entity.canonical_name)} | {
        row.normalized_alias for row in db.query(KnowledgeEntityAlias).filter_by(entity_uuid=entity.uuid).all()
    }
    names.discard("")
    if not names:
        return 0
    target_types = PLACE_ENTITY_TYPES if entity.entity_type in PLACE_ENTITY_TYPES else (entity.entity_type,)
    rows = db.query(KnowledgeRelationship).filter(
        KnowledgeRelationship.target_entity_type_id.in_(target_types),
        KnowledgeRelationship.normalized_unresolved_name.in_(names),
        KnowledgeRelationship.resolution_state.in_(("unresolved", "ambiguous")),
        KnowledgeRelationship.is_current.is_(True),
        KnowledgeRelationship.manual_override.is_(False),
    ).all()
    resolved = 0
    for row in rows:
        candidate_types = _candidate_types_for_reference(row)
        candidates = (
            exact_place_candidates(db, row.unresolved_name or "", candidate_types)
            if entity.entity_type in PLACE_ENTITY_TYPES
            else exact_entity_candidates(db, entity.entity_type, row.unresolved_name or "")
        )
        if candidates != [entity]:
            continue
        document_ref = row.source_document.provider_document_id if row.source_document is not None else None
        mutation = KnowledgeGraphService.upsert(db, RelationshipInput(
            source_entity_id=row.source_entity_id, source_scope=row.source_scope,
            relationship_type=row.relationship_type_code, target_entity_id=entity.uuid,
            unresolved_name=row.unresolved_name, resolution_state="resolved", confidence="high",
            source_provider_id=row.source_provider_id, source_document_ref=document_ref,
            source_job_id=row.source_job_id,
            source_context={**dict(row.source_context or {}), "resolution_policy": "exact_name_or_alias_only", "resolved_from": str(row.id)},
        ))
        KnowledgeGraphService.supersede(db, row, mutation.relationship)
        resolved += 1
    return resolved


class NpcLocationKnowledgeNormalizationService:
    @staticmethod
    def apply(db: Session, result: KnowledgeNormalizationResult) -> NamedEntityNormalizationApplied:
        if result.canonical_data is None or result.candidate is None:
            raise InvalidNormalizationContractError()
        entity_type = result.candidate.entity_type
        if entity_type == "npc":
            dto = NpcKnowledgeDTO.from_canonical_data(result.canonical_data)
        elif entity_type in PLACE_ENTITY_TYPES:
            dto = LocationKnowledgeDTO.from_canonical_data(result.canonical_data)
        else:
            raise InvalidNormalizationContractError()
        entity, created = _resolve_entity(db, result, dto, entity_type)
        _ensure_mapping(db, result, entity, dto, entity_type)
        entity_changed, aliases, warnings = _update_entity(db, entity, result)
        bridge_changed = _bridge_npc(db, entity, dto) if entity_type == "npc" else _bridge_location(db, entity, dto)
        relationships_synced = _sync_npc_location_relationships(
            db, entity=entity, dto=dto, provider_id=result.provider_code or "tibiawiki",
        )
        references_resolved = _resolve_exact_references(db, entity)
        changed = entity_changed or bridge_changed
        if changed and not created:
            emit_event(db, KnowledgeEventType.ENTITY_UPDATED, entity_uuid=entity.uuid, payload={"source": f"tibiawiki_{entity_type}_normalization"})
        return NamedEntityNormalizationApplied(
            "created" if created else "updated" if changed else "unchanged",
            entity.uuid, aliases, warnings,
            {"references_resolved": references_resolved, "relationships_synced": relationships_synced},
        )
