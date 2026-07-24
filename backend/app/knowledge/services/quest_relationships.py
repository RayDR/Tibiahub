"""Conservative, provenance-aware Quest relationship resolution."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.knowledge.dto import QuestAccessReference
from app.knowledge.indexing import normalize_name
from app.knowledge.models import KnowledgeAccess, KnowledgeEntity, KnowledgeQuestRelation
from app.knowledge.schemas import KnowledgeEntityCreate
from app.knowledge.services.entities import KnowledgeEntityService
from app.knowledge.services.item_relationships import exact_entity_candidates
from app.models import Creature
from app.services.text_utils import slugify


@dataclass(frozen=True, slots=True)
class QuestRelationCounts:
    created: int = 0
    resolved: int = 0
    unresolved: int = 0
    ambiguous: int = 0


def _resolve(db: Session, entity_type: str, name: str) -> tuple[KnowledgeEntity | None, str]:
    matches = exact_entity_candidates(db, entity_type, name)
    if entity_type in {"creature", "boss"}:
        filtered: list[KnowledgeEntity] = []
        for match in matches:
            creature = db.query(Creature).filter(Creature.knowledge_entity_id == match.uuid).first()
            if entity_type == "boss" and creature is not None and creature.is_boss:
                filtered.append(match)
            elif entity_type == "creature" and (creature is None or not creature.is_boss):
                filtered.append(match)
        matches = filtered
        if entity_type == "boss" and not matches:
            matches = [
                candidate for candidate in exact_entity_candidates(db, "creature", name)
                if (db.query(Creature).filter(Creature.knowledge_entity_id == candidate.uuid, Creature.is_boss.is_(True)).first())
            ]
    if len(matches) == 1:
        return matches[0], "resolved"
    return None, "ambiguous" if len(matches) > 1 else "unresolved"


def ensure_access(
    db: Session,
    *,
    quest_entity_uuid: UUID,
    quest_external_id: str,
    access: QuestAccessReference,
    provider_id: str,
) -> KnowledgeEntity:
    code = f"{provider_id}:{quest_external_id}:{slugify(access.name)}"
    record = db.query(KnowledgeAccess).filter(KnowledgeAccess.access_code == code).first()
    if record is not None:
        entity = record.knowledge_entity
    else:
        matches = exact_entity_candidates(db, "access", access.name)
        entity = matches[0] if len(matches) == 1 else KnowledgeEntityService.create(
            db,
            KnowledgeEntityCreate(
                entity_type="access",
                canonical_name=access.name,
                language_neutral_id=f"access:{code}",
                source_priority=20,
            ),
        )
        record = db.query(KnowledgeAccess).filter(KnowledgeAccess.knowledge_entity_id == entity.uuid).first()
        if record is None:
            record = KnowledgeAccess(
                knowledge_entity_id=entity.uuid,
                access_code=code,
                canonical_name=access.name,
                normalized_name=normalize_name(access.name),
                unlocked_by_quest_entity_uuid=quest_entity_uuid,
                required_quests=list(access.required_quests),
                required_items=list(access.required_items),
                description=access.description,
                destination_name=access.destination_name,
                provider_metadata={"provider": provider_id, "quest_external_id": quest_external_id},
            )
            db.add(record)
    protected = set(record.protected_fields or [])
    for field, value in (
        ("description", access.description),
        ("destination_name", access.destination_name),
        ("required_quests", list(access.required_quests)),
        ("required_items", list(access.required_items)),
    ):
        if field not in protected and value not in (None, [], ""):
            setattr(record, field, value)
    if "unlocked_by_quest_entity_uuid" not in protected:
        record.unlocked_by_quest_entity_uuid = quest_entity_uuid
    db.flush()
    return entity


def upsert_quest_relation(
    db: Session,
    *,
    provider_id: str,
    quest_entity_uuid: UUID,
    scope_key: str,
    relation_type: str,
    target_entity_type: str,
    target_name: str,
    source_document_id: str,
    source_context: str,
    mission_id: UUID | None = None,
    explicit_entity_uuid: UUID | None = None,
) -> tuple[KnowledgeQuestRelation, bool]:
    normalized = normalize_name(target_name)
    if not normalized:
        raise ValueError("Quest relationships require a target name")
    row = db.query(KnowledgeQuestRelation).filter_by(
        provider_id=provider_id,
        quest_entity_uuid=quest_entity_uuid,
        scope_key=scope_key,
        relation_type=relation_type,
        target_entity_type=target_entity_type,
        normalized_target_name=normalized,
    ).first()
    created = row is None
    if row is None:
        row = KnowledgeQuestRelation(
            provider_id=provider_id,
            quest_entity_uuid=quest_entity_uuid,
            mission_id=mission_id,
            scope_key=scope_key,
            relation_type=relation_type,
            target_entity_type=target_entity_type,
            target_name=target_name.strip(),
            normalized_target_name=normalized,
        )
        db.add(row)
    if not row.protected:
        if explicit_entity_uuid is not None:
            entity, status = db.get(KnowledgeEntity, explicit_entity_uuid), "resolved"
        elif target_entity_type in {"npc", "location"}:
            entity, status = None, "unresolved"
        else:
            entity, status = _resolve(db, target_entity_type, target_name)
        row.mission_id = mission_id
        row.target_name = target_name.strip()
        row.target_entity_uuid = entity.uuid if entity else None
        row.resolution_status = status
        row.confidence = "exact"
        row.relation_metadata = {"resolution_policy": "exact_name_or_alias_only"}
    documents = list(row.source_document_ids or [])
    if source_document_id not in documents:
        documents.append(source_document_id)
    row.source_document_ids = documents
    contexts = list(row.source_contexts or [])
    if source_context not in contexts:
        contexts.append(source_context)
    row.source_contexts = contexts
    db.flush()
    return row, created
