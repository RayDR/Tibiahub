"""Quest identity, bridge, mission, access, and relationship normalization."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.knowledge.adapters.protocol import KnowledgeNormalizationResult
from app.knowledge.dto import QuestKnowledgeDTO
from app.knowledge.events import KnowledgeEventType, emit_event
from app.knowledge.indexing import normalize_name
from app.knowledge.metadata import refresh_search_metadata
from app.knowledge.models import KnowledgeEntity, KnowledgeEntityAlias, KnowledgeExternalMapping
from app.knowledge.schemas import KnowledgeEntityCreate
from app.knowledge.services.entities import DuplicateKnowledgeAliasError, DuplicateKnowledgeEntityError, KnowledgeEntityService
from app.knowledge.services.failures import InvalidNormalizationContractError
from app.knowledge.services.graph import KnowledgeGraphService
from app.knowledge.services.item_relationships import exact_entity_candidates
from app.knowledge.services.npc_location_normalization import sync_access_destination
from app.knowledge.services.quest_relationships import (
    ensure_access,
    ensure_access_destination_location,
    upsert_quest_relation,
)
from app.models.external_data import QuestMission, TibiaWikiQuest
from app.services.entity_metadata_service import EntityMetadataService
from app.services.text_utils import normalize_search_text


class QuestIdentityConflictError(InvalidNormalizationContractError):
    code = "quest_identity_conflict"
    safe_message = "The quest identity conflicts with an existing canonical record."


@dataclass(frozen=True, slots=True)
class QuestNormalizationApplied:
    status: str
    entity_uuid: UUID
    aliases_created: int
    warnings: int
    metrics: dict[str, int]


def _provider_mapping(db: Session, provider: str, external_id: str) -> KnowledgeExternalMapping | None:
    return db.query(KnowledgeExternalMapping).filter_by(provider_id=provider, entity_type_id="quest", external_id=external_id).first()


def _entity_mapping(db: Session, provider: str, entity_uuid: UUID) -> KnowledgeExternalMapping | None:
    return db.query(KnowledgeExternalMapping).filter_by(provider_id=provider, entity_type_id="quest", entity_uuid=entity_uuid).first()


def _resolve_entity(db: Session, result: KnowledgeNormalizationResult, dto: QuestKnowledgeDTO) -> tuple[KnowledgeEntity, bool]:
    if not result.provider_code or not result.external_id or result.candidate is None:
        raise InvalidNormalizationContractError()
    mapping = _provider_mapping(db, result.provider_code, result.external_id)
    if mapping:
        return mapping.entity, False
    matches = exact_entity_candidates(db, "quest", dto.canonical_name)
    available = [entity for entity in matches if _entity_mapping(db, result.provider_code, entity.uuid) is None]
    if len(available) > 1:
        raise QuestIdentityConflictError()
    if len(available) == 1:
        return available[0], False
    collision = bool(matches)
    candidate = result.candidate
    return KnowledgeEntityService.create(db, KnowledgeEntityCreate(
        entity_type="quest", canonical_name=candidate.canonical_name,
        language_neutral_id=candidate.language_neutral_id, aliases=list(candidate.aliases),
        status=candidate.status, source_priority=candidate.source_priority,
        visibility=candidate.visibility, search_weight=candidate.search_weight,
        allow_name_collision=collision, slug_suffix=result.external_id if collision else None,
    )), True


def _mapping(db: Session, result: KnowledgeNormalizationResult, entity: KnowledgeEntity, dto: QuestKnowledgeDTO) -> None:
    existing = _provider_mapping(db, result.provider_code or "", result.external_id or "")
    if existing:
        if existing.entity_uuid != entity.uuid:
            raise QuestIdentityConflictError()
        existing.provider_metadata = dict(dto.provider_metadata)
        return
    try:
        with db.begin_nested():
            db.add(KnowledgeExternalMapping(
                provider_id=result.provider_code, entity_type_id="quest", external_id=result.external_id,
                entity_uuid=entity.uuid, provider_metadata=dict(dto.provider_metadata),
            ))
            db.flush()
    except IntegrityError as exc:
        raise QuestIdentityConflictError() from exc


def _entity_update(db: Session, entity: KnowledgeEntity, result: KnowledgeNormalizationResult) -> tuple[bool, int, int]:
    candidate = result.candidate
    if candidate is None:
        raise InvalidNormalizationContractError()
    changed = False
    if candidate.source_priority <= entity.source_priority:
        for field, value in (("canonical_name", candidate.canonical_name), ("source_priority", candidate.source_priority), ("status", candidate.status), ("visibility", candidate.visibility), ("search_weight", candidate.search_weight)):
            if value not in (None, "") and getattr(entity, field) != value:
                setattr(entity, field, value); changed = True
    existing = {alias.normalized_alias for alias in db.query(KnowledgeEntityAlias).filter_by(entity_uuid=entity.uuid).all()}
    added = 0
    warnings = len(result.warnings)
    for alias in candidate.aliases:
        if not normalize_name(alias) or normalize_name(alias) in existing:
            continue
        try:
            KnowledgeEntityService.add_alias(db, entity, alias); added += 1; existing.add(normalize_name(alias))
        except (DuplicateKnowledgeAliasError, DuplicateKnowledgeEntityError):
            warnings += 1
    refresh_search_metadata(entity)
    return changed or bool(added), added, warnings


def _bridge(db: Session, entity: KnowledgeEntity, dto: QuestKnowledgeDTO) -> tuple[TibiaWikiQuest, bool]:
    quest = db.query(TibiaWikiQuest).filter_by(knowledge_entity_id=entity.uuid).first()
    if quest is None:
        quest = db.query(TibiaWikiQuest).filter_by(source_name="tibiawiki", external_id=dto.external_id).first()
    if quest is None:
        legacy = db.query(TibiaWikiQuest).filter(TibiaWikiQuest.knowledge_entity_id.is_(None)).all()
        exact = [row for row in legacy if normalize_search_text(row.name) == normalize_search_text(dto.canonical_name)]
        if len(exact) > 1:
            raise QuestIdentityConflictError()
        quest = exact[0] if exact else None
    if quest is not None and quest.knowledge_entity_id not in (None, entity.uuid):
        raise QuestIdentityConflictError()
    created = quest is None
    if quest is None:
        quest = TibiaWikiQuest(name=dto.canonical_name, knowledge_entity_id=entity.uuid, data_version=1, protected_fields=[])
        db.add(quest); db.flush()
    changed = False
    protected = set(quest.protected_fields or [])
    def assign(field: str, value, supplied: str | None = None) -> None:
        nonlocal changed
        if field in protected or value is None or value == "" or (supplied and supplied not in dto.supplied_fields):
            return
        if value in ([], {}) and getattr(quest, field) not in (None, "", [], {}):
            return
        if getattr(quest, field) != value:
            setattr(quest, field, value); changed = True
    if quest.knowledge_entity_id is None:
        quest.knowledge_entity_id = entity.uuid; changed = True
    for field, value, supplied in (
        ("name", dto.canonical_name, None), ("normalized_name", normalize_search_text(dto.canonical_name), None),
        ("slug", entity.slug, None), ("external_id", dto.external_id, None), ("source_name", "tibiawiki", None),
        ("source_url", dto.source_reference, "source_reference"), ("image_url", dto.image_reference, "image_reference"),
        ("description", dto.description, "description"), ("summary", dto.summary, "summary"),
        ("group_name", dto.group_name, "group_name"), ("parent_page", dto.parent_page, "parent_page"),
        ("is_group", dto.is_group, "is_group"), ("quest_type", dto.quest_type, "quest_type"),
        ("category", dto.category, "category"), ("difficulty", dto.difficulty, "difficulty"),
        ("duration", dto.estimated_duration, "estimated_duration"), ("min_level", dto.minimum_level, "minimum_level"),
        ("max_level", dto.maximum_level, "maximum_level"), ("experience_reward", dto.experience_reward, "experience_reward"),
        ("premium_required", dto.premium_required, "premium_required"), ("repeatable", dto.repeatable, "repeatable"),
        ("solo_possible", dto.solo_possible, "solo_possible"),
        ("starting_npcs", [asdict(x) for x in dto.starting_npcs], "starting_npcs"),
        ("related_npcs", [asdict(x) for x in dto.related_npcs], "related_npcs"),
        ("required_items", [asdict(x) for x in dto.required_items], "required_items"),
        ("rewarded_items", [asdict(x) for x in dto.rewarded_items], "rewarded_items"),
        ("required_quests", [asdict(x) for x in dto.required_quests], "required_quests"),
        ("unlocked_quests", [asdict(x) for x in dto.unlocked_quests], "unlocked_quests"),
        ("required_creatures", [asdict(x) for x in dto.required_creatures], "required_creatures"),
        ("bosses", [asdict(x) for x in dto.bosses], "bosses"),
        ("locations", [asdict(x) for x in dto.locations], "locations"),
        ("access_unlocks", [{
            **asdict(x), "required_quests": list(x.required_quests), "required_items": list(x.required_items),
        } for x in dto.access_unlocks], "access_unlocks"),
        ("parser_metadata", {
            **dict(dto.provider_metadata),
            "supplied_fields": sorted(dto.supplied_fields),
        }, None),
    ):
        assign(field, value, supplied)
    if dto.starting_npcs:
        assign("npc", dto.starting_npcs[0].name)
    if dto.locations:
        assign("location", dto.locations[0].name)
    assign("requirements", [x.name for x in dto.required_items] + [x.name for x in dto.required_quests])
    assign("rewards", [x.name for x in dto.rewarded_items])
    assign("treasure", [asdict(x) for x in dto.rewarded_items])
    quest.raw_data = None
    quest.last_synced_at = datetime.now(UTC)
    if not created and changed:
        quest.data_version = max(1, quest.data_version or 1) + 1
    EntityMetadataService.update_sync_timestamp(db, entity_type="quest", entity_key=quest.normalized_name, display_name=quest.name, entity_id=quest.id)
    db.flush()
    return quest, created or changed


def _missions(db: Session, quest: TibiaWikiQuest, dto: QuestKnowledgeDTO, provider: str) -> tuple[dict[int, QuestMission], int, int]:
    by_identity = {(row.provider_id, row.identity_key): row for row in quest.missions}
    result: dict[int, QuestMission] = {}
    created = changed = 0
    for mission in sorted(dto.missions, key=lambda value: value.sequence):
        key = mission.external_id or f"{normalize_name(mission.title)}:{mission.sequence}"
        row = by_identity.get((provider, key))
        if row is None:
            row = QuestMission(quest_id=quest.id, provider_id=provider, identity_key=key, title=mission.title, normalized_title=normalize_name(mission.title), sequence=mission.sequence)
            db.add(row); created += 1
        protected = set(row.protected_fields or [])
        canonical_changed = False
        for field, value in (
            ("external_id", mission.external_id), ("title", mission.title), ("normalized_title", normalize_name(mission.title)),
            ("sequence", mission.sequence), ("description", mission.description), ("objectives", list(mission.objectives)),
            ("required_items", [asdict(x) for x in mission.required_items]), ("rewarded_items", [asdict(x) for x in mission.rewarded_items]),
            ("related_npcs", [asdict(x) for x in mission.related_npcs]), ("related_creatures", [asdict(x) for x in mission.related_creatures]),
            ("locations", [asdict(x) for x in mission.locations]), ("supplied_fields", sorted(mission.supplied_fields)),
        ):
            if field not in protected and value is not None and value != "" and not (
                value in ([], {}) and getattr(row, field) not in (None, "", [], {})
            ) and getattr(row, field) != value:
                setattr(row, field, value); canonical_changed = True
        changed += int(canonical_changed and row in quest.missions)
        db.flush(); result[mission.sequence] = row
    return result, created, changed


def _relationships(db: Session, entity: KnowledgeEntity, dto: QuestKnowledgeDTO, missions: dict[int, QuestMission], provider: str) -> dict[str, int]:
    counts = {
        "relations_created": 0,
        "relations_resolved": 0,
        "relations_unresolved": 0,
        "relations_ambiguous": 0,
        "relations_superseded": 0,
    }
    document = f"quest:{dto.external_id}"
    for access in dto.access_unlocks:
        if access.destination_name:
            ensure_access_destination_location(
                db,
                destination_name=access.destination_name,
                quest_external_id=dto.external_id,
            )
    references = [
        ("requires_quest", "quest", value.name, "required_quests") for value in dto.required_quests
    ] + [("unlocks_quest", "quest", value.name, "unlocked_quests") for value in dto.unlocked_quests]
    references += [("requires_item", "item", value.name, "required_items") for value in dto.required_items]
    references += [("rewards_item", "item", value.name, "rewarded_items") for value in dto.rewarded_items]
    references += [("involves_creature", "creature", value.name, "required_creatures") for value in dto.required_creatures]
    references += [("involves_boss", "boss", value.name, "bosses") for value in dto.bosses]
    references += [("starts_at_npc", "npc", value.name, "starting_npcs") for value in dto.starting_npcs]
    references += [("involves_npc", "npc", value.name, "related_npcs") for value in dto.related_npcs]
    references += [("occurs_at_location", "location", value.name, "locations") for value in dto.locations]
    for access in dto.access_unlocks:
        access_entity = ensure_access(db, quest_entity_uuid=entity.uuid, quest_external_id=dto.external_id, access=access, provider_id=provider)
        sync_access_destination(
            db,
            access_entity=access_entity,
            destination_name=access.destination_name,
            provider_id=provider,
            source_document_ref=document,
        )
        references.append(("unlocks_access", "access", access.name, "access_unlocks", access_entity.uuid))
    quest_relation_ids: set[UUID] = set()
    for entry in references:
        relation_type, target_type, name, context, *explicit = entry
        row, created = upsert_quest_relation(db, provider_id=provider, quest_entity_uuid=entity.uuid, scope_key="quest", relation_type=relation_type, target_entity_type=target_type, target_name=name, source_document_id=document, source_context=context, explicit_entity_uuid=explicit[0] if explicit else None)
        quest_relation_ids.add(row.id)
        counts["relations_created"] += int(created); counts[f"relations_{row.resolution_state}"] += 1
    counts["relations_superseded"] += KnowledgeGraphService.reconcile_provider(
        db,
        source_entity_id=entity.uuid,
        source_scope="quest",
        provider_id=provider,
        relationship_types={
            "requires_quest", "prerequisite_for", "requires_item", "rewards_item",
            "involves_creature", "involves_boss", "starts_at_npc", "references_npc",
            "occurs_at_location", "unlocks_access",
        },
        current_ids=quest_relation_ids,
    )
    for mission in dto.missions:
        row = missions[mission.sequence]; scope = f"mission:{row.identity_key}"
        mission_refs = [("requires_item", "item", x.name, "required_items") for x in mission.required_items]
        mission_refs += [("rewards_item", "item", x.name, "rewarded_items") for x in mission.rewarded_items]
        mission_refs += [("involves_creature", "creature", x.name, "related_creatures") for x in mission.related_creatures]
        mission_refs += [("involves_npc", "npc", x.name, "related_npcs") for x in mission.related_npcs]
        mission_refs += [("occurs_at_location", "location", x.name, "locations") for x in mission.locations]
        mission_relation_ids: set[UUID] = set()
        for relation_type, target_type, name, context in mission_refs:
            relation, created = upsert_quest_relation(db, provider_id=provider, quest_entity_uuid=entity.uuid, mission_id=row.id, scope_key=scope, relation_type=relation_type, target_entity_type=target_type, target_name=name, source_document_id=document, source_context=f"mission.{context}")
            mission_relation_ids.add(relation.id)
            counts["relations_created"] += int(created); counts[f"relations_{relation.resolution_state}"] += 1
        counts["relations_superseded"] += KnowledgeGraphService.reconcile_provider(
            db,
            source_entity_id=entity.uuid,
            source_scope=f"mission:{row.id}",
            provider_id=provider,
            relationship_types={
                "mission_requires_item", "mission_rewards_item", "mission_involves_creature",
                "mission_references_npc", "mission_occurs_at_location",
            },
            current_ids=mission_relation_ids,
        )
    return counts


class QuestKnowledgeNormalizationService:
    @staticmethod
    def apply(db: Session, result: KnowledgeNormalizationResult) -> QuestNormalizationApplied:
        if result.canonical_data is None:
            raise InvalidNormalizationContractError()
        dto = QuestKnowledgeDTO.from_canonical_data(result.canonical_data)
        entity, created = _resolve_entity(db, result, dto)
        _mapping(db, result, entity, dto)
        entity_changed, aliases, warnings = _entity_update(db, entity, result)
        quest, quest_changed = _bridge(db, entity, dto)
        mission_rows, missions_created, missions_updated = _missions(db, quest, dto, result.provider_code or "tibiawiki")
        relation_metrics = _relationships(db, entity, dto, mission_rows, result.provider_code or "tibiawiki")
        mission_changed = bool(missions_created or missions_updated)
        if mission_changed and not quest_changed and not created:
            quest.data_version = max(1, quest.data_version or 1) + 1
        changed = entity_changed or quest_changed or mission_changed
        if changed and not created:
            emit_event(db, KnowledgeEventType.ENTITY_UPDATED, entity_uuid=entity.uuid, payload={"source": "tibiawiki_quest_normalization"})
        return QuestNormalizationApplied(
            "created" if created else "updated" if changed else "unchanged", entity.uuid, aliases, warnings,
            {"missions_created": missions_created, "missions_updated": missions_updated, "missions_total": len(mission_rows), **relation_metrics},
        )
