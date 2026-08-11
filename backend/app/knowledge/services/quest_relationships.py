"""Conservative, provenance-aware Quest relationship resolution."""

from __future__ import annotations

from hashlib import sha256
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.knowledge.dto import QuestAccessReference
from app.knowledge.indexing import normalize_name
from app.knowledge.models import KnowledgeAccess, KnowledgeEntity, KnowledgeQuestRelation, KnowledgeRelationship
from app.knowledge.schemas import KnowledgeEntityCreate
from app.knowledge.services.entities import KnowledgeEntityService
from app.knowledge.services.item_relationships import exact_entity_candidates
from app.knowledge.services.npc_location_normalization import exact_place_candidates
from app.knowledge.services.graph import KnowledgeGraphService, RelationshipInput
from app.models import Creature
from app.models.external_data import TibiaWikiLocation
from app.services.text_utils import normalize_search_text, slugify


@dataclass(frozen=True, slots=True)
class QuestRelationCounts:
    created: int = 0
    resolved: int = 0
    unresolved: int = 0
    ambiguous: int = 0


def _resolve(db: Session, entity_type: str, name: str) -> tuple[KnowledgeEntity | None, str]:
    matches = (
        exact_place_candidates(db, name)
        if entity_type in {"location", "area", "town"}
        else exact_entity_candidates(db, entity_type, name)
    )
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


def ensure_access_destination_location(
    db: Session,
    *,
    destination_name: str,
    quest_external_id: str,
) -> KnowledgeEntity | None:
    """Create a low-priority place identity from an explicit provider link.

    This is intentionally limited to destination names parsed from an exact
    ``Access to [[Place]]`` claim. It does not invent location attributes. A
    later full location document resolves to and enriches the same entity.
    """
    candidates = exact_place_candidates(db, destination_name)
    if len(candidates) == 1:
        return candidates[0]
    if candidates:
        return None

    normalized = normalize_name(destination_name)
    if not normalized:
        return None
    identity_hash = sha256(normalized.encode("utf-8")).hexdigest()[:20]
    entity = KnowledgeEntityService.create(
        db,
        KnowledgeEntityCreate(
            entity_type="location",
            canonical_name=destination_name,
            language_neutral_id=f"location:tibiawiki-reference:{identity_hash}",
            source_priority=80,
            search_weight=0.5,
        ),
    )
    db.add(
        TibiaWikiLocation(
            name=destination_name,
            normalized_name=normalize_search_text(destination_name),
            slug=entity.slug,
            external_id=f"reference:{identity_hash}",
            source_name="tibiawiki_reference",
            knowledge_entity_id=entity.uuid,
            npcs=[],
            creatures=[],
            quests=[],
            sublocations=[],
            provider_metadata={
                "reference_only": True,
                "source_entity_type": "quest",
                "source_external_id": quest_external_id,
            },
            supplied_fields=["canonical_name", "slug"],
            protected_fields=[],
            data_version=1,
        )
    )
    db.flush()
    return entity


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
) -> tuple[KnowledgeRelationship, bool]:
    normalized = normalize_name(target_name)
    if not normalized:
        raise ValueError("Quest relationships require a target name")
    compatibility = db.query(KnowledgeQuestRelation).filter_by(
        provider_id=provider_id,
        quest_entity_uuid=quest_entity_uuid,
        scope_key=scope_key,
        relation_type=relation_type,
        target_entity_type=target_entity_type,
        normalized_target_name=normalized,
    ).first()
    protected = bool(compatibility and compatibility.protected)
    if protected:
        target_name = compatibility.target_name
        entity = db.get(KnowledgeEntity, compatibility.target_entity_uuid) if compatibility.target_entity_uuid else None
        status = compatibility.resolution_status
    else:
        if explicit_entity_uuid is not None:
            entity, status = db.get(KnowledgeEntity, explicit_entity_uuid), "resolved"
        else:
            entity, status = _resolve(db, target_entity_type, target_name)
    graph_type = {
        "unlocks_quest": "prerequisite_for",
        "involves_npc": "references_npc",
    }.get(relation_type, relation_type)
    if mission_id is not None:
        graph_type = {
            "requires_item": "mission_requires_item",
            "rewards_item": "mission_rewards_item",
            "involves_creature": "mission_involves_creature",
            "involves_npc": "mission_references_npc",
            "occurs_at_location": "mission_occurs_at_location",
        }.get(relation_type, graph_type)
    graph_scope = f"mission:{mission_id}" if mission_id else "quest"
    if protected:
        existing = db.query(KnowledgeRelationship).filter_by(
            source_entity_id=quest_entity_uuid, source_scope=graph_scope,
            relationship_type_code=graph_type, manual_override=True, is_current=True,
        ).first()
        if existing is not None:
            return existing, False
    graph_target_type = entity.entity_type if entity is not None else target_entity_type
    candidate_type = "creature" if target_entity_type == "boss" else target_entity_type
    candidates = (
        exact_place_candidates(db, target_name)
        if status == "ambiguous" and candidate_type in {"location", "area", "town"}
        else exact_entity_candidates(db, candidate_type, target_name) if status == "ambiguous" else []
    )
    mutation = KnowledgeGraphService.upsert(db, RelationshipInput(
        source_entity_id=quest_entity_uuid,
        source_scope=graph_scope,
        relationship_type=graph_type,
        target_entity_id=entity.uuid if entity is not None and status == "resolved" else None,
        target_entity_type=graph_target_type,
        unresolved_name=None if status == "resolved" else target_name,
        resolution_state=status,
        confidence="verified" if protected else "high",
        source_provider_id=provider_id,
        source_document_ref=source_document_id,
        source_context={"context": source_context, "resolution_policy": "exact_name_or_alias_only",
                        "candidate_entity_ids": [str(candidate.uuid) for candidate in candidates]},
        manual_override=protected,
    ))
    return mutation.relationship, mutation.created
