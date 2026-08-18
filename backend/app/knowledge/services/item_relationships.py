"""Deduplicated Creature-to-Item drop facts with conservative exact resolution."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.knowledge.indexing import normalize_name
from app.knowledge.models import (
    KnowledgeEntity,
    KnowledgeEntityAlias,
    KnowledgeRelationship,
    KnowledgeSearchMetadata,
)
from app.knowledge.services.graph import KnowledgeGraphService, RelationshipInput
from app.models import Loot
from app.services.text_utils import normalize_search_text


@dataclass(frozen=True, slots=True)
class DropRelationshipResult:
    relationship: KnowledgeRelationship
    created: bool
    resolution_status: str


def exact_entity_candidates(db: Session, entity_type: str, name: str) -> list[KnowledgeEntity]:
    normalized = normalize_name(name)
    if not normalized:
        return []
    # Canonical and alias names are both indexed local knowledge. Query them
    # directly instead of lazily loading every entity's alias collection (an
    # N+1 path that made relationship-heavy normalization exceed its lease).
    matches = {
        entity.uuid: entity
        for entity in (
            db.query(KnowledgeEntity)
            .join(
                KnowledgeSearchMetadata,
                KnowledgeSearchMetadata.entity_uuid == KnowledgeEntity.uuid,
            )
            .filter(
                KnowledgeEntity.entity_type == entity_type,
                KnowledgeSearchMetadata.normalized_name == normalized,
            )
        )
    }
    for entity in (
        db.query(KnowledgeEntity)
        .join(KnowledgeEntityAlias, KnowledgeEntityAlias.entity_uuid == KnowledgeEntity.uuid)
        .filter(
            KnowledgeEntity.entity_type == entity_type,
            KnowledgeEntityAlias.entity_type == entity_type,
            KnowledgeEntityAlias.normalized_alias == normalized,
        )
    ):
        matches[entity.uuid] = entity
    return list(matches.values())


def _resolve_exact(db: Session, entity_type: str, name: str) -> tuple[KnowledgeEntity | None, str]:
    matches = exact_entity_candidates(db, entity_type, name)
    if len(matches) == 1:
        return matches[0], "resolved"
    return None, "ambiguous" if len(matches) > 1 else "unresolved"


def upsert_drop_relationship(
    db: Session,
    *,
    provider_id: str,
    creature_name: str,
    item_name: str,
    source_document_id: str,
    source_direction: str,
    creature_entity_uuid: UUID | None = None,
    item_entity_uuid: UUID | None = None,
) -> DropRelationshipResult:
    normalized_creature = normalize_name(creature_name)
    normalized_item = normalize_name(item_name)
    if not normalized_creature or not normalized_item:
        raise ValueError("Drop relationships require nonempty creature and item names")

    identity_conflict = False
    # The adapter's own source UUID is authoritative. The opposite endpoint
    # remains ambiguous when multiple exact-name entities exist.
    if source_direction == "item_dropped_by" and creature_entity_uuid is not None and len(exact_entity_candidates(db, "creature", creature_name)) > 1:
        identity_conflict = True
        creature_entity_uuid = None
    if source_direction != "item_dropped_by" and item_entity_uuid is not None and len(exact_entity_candidates(db, "item", item_name)) > 1:
        identity_conflict = True
        item_entity_uuid = None

    creature_status = "resolved"
    item_status = "resolved"
    if creature_entity_uuid is None:
        creature, creature_status = _resolve_exact(db, "creature", creature_name)
        creature_entity_uuid = creature.uuid if creature else None
    if item_entity_uuid is None:
        item, item_status = _resolve_exact(db, "item", item_name)
        item_entity_uuid = item.uuid if item else None
    if identity_conflict or "ambiguous" in {creature_status, item_status}:
        resolution_status = "ambiguous"
    elif creature_entity_uuid is not None and item_entity_uuid is not None:
        resolution_status = "resolved"
    else:
        resolution_status = "unresolved"

    if creature_entity_uuid is not None:
        item_candidates = exact_entity_candidates(db, "item", item_name) if resolution_status == "ambiguous" else []
        mutation = KnowledgeGraphService.upsert(db, RelationshipInput(
            source_entity_id=creature_entity_uuid,
            relationship_type="drops",
            target_entity_id=item_entity_uuid if resolution_status == "resolved" else None,
            target_entity_type="item",
            unresolved_name=None if resolution_status == "resolved" else item_name,
            resolution_state=resolution_status,
            confidence="high",
            source_provider_id=provider_id,
            source_document_ref=source_document_id,
            source_context={"direction": source_direction, "resolution_policy": "exact_name_or_alias_only",
                            "candidate_entity_ids": [str(candidate.uuid) for candidate in item_candidates]},
        ))
    elif item_entity_uuid is not None:
        creature_candidates = exact_entity_candidates(db, "creature", creature_name) if resolution_status == "ambiguous" else []
        mutation = KnowledgeGraphService.upsert(db, RelationshipInput(
            source_entity_id=item_entity_uuid,
            relationship_type="dropped_by",
            target_entity_type="creature",
            unresolved_name=creature_name,
            resolution_state=resolution_status,
            confidence="high",
            source_provider_id=provider_id,
            source_document_ref=source_document_id,
            source_context={"direction": source_direction, "resolution_policy": "exact_name_or_alias_only",
                            "candidate_entity_ids": [str(candidate.uuid) for candidate in creature_candidates]},
        ))
    else:
        raise ValueError("Drop relationships require one resolved source entity")
    return DropRelationshipResult(mutation.relationship, mutation.created, resolution_status)


def link_item_drops(
    db: Session,
    *,
    item_entity_uuid: UUID,
    item_name: str,
    dropped_by: tuple,
    provider_id: str,
    source_document_id: str,
) -> tuple[int, int]:
    created = 0
    unresolved = 0
    seen: set[str] = set()
    for reference in dropped_by:
        creature_name = str(reference.name).strip()
        normalized = normalize_name(creature_name)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result = upsert_drop_relationship(
            db,
            provider_id=provider_id,
            creature_name=creature_name,
            item_name=item_name,
            item_entity_uuid=item_entity_uuid,
            source_document_id=source_document_id,
            source_direction="item_dropped_by",
        )
        created += int(result.created)
        unresolved += int(result.resolution_status != "resolved")

    legacy_rows = db.query(Loot).filter(Loot.normalized_name == normalize_search_text(item_name)).all()
    for loot in legacy_rows:
        if loot.creature is None:
            continue
        normalized = normalize_name(loot.creature.name)
        if normalized in seen:
            continue
        seen.add(normalized)
        result = upsert_drop_relationship(
            db,
            provider_id=provider_id,
            creature_name=loot.creature.name,
            item_name=item_name,
            creature_entity_uuid=loot.creature.knowledge_entity_id,
            item_entity_uuid=item_entity_uuid,
            source_document_id=source_document_id,
            source_direction="creature_loot_bridge",
        )
        created += int(result.created)
        unresolved += int(result.resolution_status != "resolved")
    return created, unresolved


def link_creature_loot(
    db: Session,
    *,
    creature_entity_uuid: UUID,
    creature_name: str,
    loot_references: tuple,
    provider_id: str,
    source_document_id: str,
) -> tuple[int, int]:
    created = 0
    unresolved = 0
    seen: set[str] = set()
    for reference in loot_references:
        item_name = str(reference.item_name).strip()
        normalized = normalize_name(item_name)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result = upsert_drop_relationship(
            db,
            provider_id=provider_id,
            creature_name=creature_name,
            item_name=item_name,
            creature_entity_uuid=creature_entity_uuid,
            source_document_id=source_document_id,
            source_direction="creature_drops",
        )
        created += int(result.created)
        unresolved += int(result.resolution_status != "resolved")
    return created, unresolved
