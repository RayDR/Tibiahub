"""PostgreSQL-only Quest search and detail endpoints."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.knowledge.services import KnowledgeGraphService
from app.models.creature import Creature
from app.models.external_data import TibiaWikiQuest
from app.schemas import QuestDetail, QuestRelatedCreature, QuestSearchResult
from app.services.entity_metadata_service import EntityMetadataService
from app.services.text_utils import normalize_search_text


router = APIRouter(prefix="/quests", tags=["quests"])


def _summary(row: TibiaWikiQuest) -> QuestSearchResult:
    return QuestSearchResult(
        id=row.id, name=row.name, slug=row.slug, description=row.summary or row.description,
        group_name=row.group_name, parent_page=row.parent_page, is_group=bool(row.is_group),
        min_level=row.min_level, max_level=row.max_level, experience_reward=row.experience_reward,
        location=row.location, npc=row.npc, source_url=row.source_url, category=row.category,
        quest_type=row.quest_type, premium_required=row.premium_required,
        repeatable=row.repeatable, last_synced_at=row.last_synced_at,
    )


@router.get("/highlights", response_model=List[QuestSearchResult])
def get_quest_highlights(limit: int = Query(12, ge=1, le=50), db: Session = Depends(get_db)):
    metadata = EntityMetadataService.get_highlights(db, entity_type="quest", limit=limit)
    ids = [record.entity_id for record in metadata if record.entity_id is not None]
    rows: list[TibiaWikiQuest] = []
    if ids:
        found = db.query(TibiaWikiQuest).filter(TibiaWikiQuest.id.in_(ids)).all()
        by_id = {row.id: row for row in found}
        rows = [by_id[value] for value in ids if value in by_id and not by_id[value].is_group]
    if not rows:
        rows = db.query(TibiaWikiQuest).filter(TibiaWikiQuest.is_group.is_(False)).order_by(
            TibiaWikiQuest.updated_at.desc().nullslast(), TibiaWikiQuest.id.desc()
        ).limit(limit).all()
    return [_summary(row) for row in rows]


@router.get("/", response_model=List[QuestSearchResult])
def search_quests(
    search: str | None = Query(None, min_length=2),
    category: str | None = None,
    level: int | None = Query(None, ge=0),
    premium: bool | None = None,
    repeatable: bool | None = None,
    include_groups: bool = False,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(TibiaWikiQuest)
    if not include_groups:
        query = query.filter(TibiaWikiQuest.is_group.is_(False))
    if search:
        query = query.filter(TibiaWikiQuest.name.ilike(f"%{search}%"))
    if category:
        query = query.filter(TibiaWikiQuest.category == category)
    if level is not None:
        query = query.filter(or_(TibiaWikiQuest.min_level.is_(None), TibiaWikiQuest.min_level <= level))
        query = query.filter(or_(TibiaWikiQuest.max_level.is_(None), TibiaWikiQuest.max_level >= level))
    if premium is not None:
        query = query.filter(TibiaWikiQuest.premium_required == premium)
    if repeatable is not None:
        query = query.filter(TibiaWikiQuest.repeatable == repeatable)
    rows = query.order_by(TibiaWikiQuest.name.asc()).offset(skip).limit(limit).all()
    if rows:
        EntityMetadataService.record_searches(db, entity_type="quest", matches=[
            (normalize_search_text(row.name), row.name, row.id) for row in rows[:5]
        ])
        db.commit()
    return [_summary(row) for row in rows]


def _safe_named(values) -> list[dict]:
    return [value for value in (values or []) if isinstance(value, dict) and isinstance(value.get("name"), str)]


@router.get("/{identifier}", response_model=QuestDetail)
def get_quest_detail(identifier: str, db: Session = Depends(get_db)):
    query = db.query(TibiaWikiQuest)
    if identifier.isdigit():
        quest = query.filter(or_(TibiaWikiQuest.id == int(identifier), TibiaWikiQuest.external_id == identifier)).first()
    else:
        quest = query.filter(or_(TibiaWikiQuest.slug == identifier, TibiaWikiQuest.normalized_name == normalize_search_text(identifier))).first()
    if quest is None:
        raise HTTPException(status_code=404, detail="Quest not found")

    relations = []
    related_creatures = []
    if quest.knowledge_entity_id:
        relation_rows = KnowledgeGraphService.outgoing(db, quest.knowledge_entity_id)
        for relation in relation_rows:
            relation_type = {
                "prerequisite_for": "unlocks_quest",
                "references_npc": "involves_npc",
                "mission_references_npc": "involves_npc",
            }.get(relation.relationship_type, relation.relationship_type.removeprefix("mission_"))
            mission_id = relation.source_scope.removeprefix("mission:") if relation.source_scope.startswith("mission:") else None
            relations.append({
                "relation_type": relation_type,
                "target_entity_type": relation.target_type,
                "target_name": relation.target_name,
                "resolution_status": relation.resolution_state,
                "target_slug": relation.target_slug,
                "mission_id": mission_id,
            })
            if relation.target_entity_id and relation.target_type in {"creature", "boss"}:
                creature = db.query(Creature).filter_by(knowledge_entity_id=relation.target_entity_id).first()
                if creature and all(item.creature_id != creature.id for item in related_creatures):
                    related_creatures.append(QuestRelatedCreature(
                        creature_id=creature.id, creature_name=creature.name, creature_slug=creature.slug,
                        is_boss=bool(creature.is_boss), classification=creature.classification,
                        image_url=creature.image_url,
                    ))
    missions = [{
        "id": mission.id, "external_id": mission.external_id, "title": mission.title,
        "sequence": mission.sequence, "description": mission.description,
        "objectives": list(mission.objectives or []), "required_items": _safe_named(mission.required_items),
        "rewarded_items": _safe_named(mission.rewarded_items), "related_npcs": _safe_named(mission.related_npcs),
        "related_creatures": _safe_named(mission.related_creatures), "locations": _safe_named(mission.locations),
    } for mission in sorted(quest.missions, key=lambda row: row.sequence)]
    required_items = _safe_named(quest.required_items)
    rewarded_items = _safe_named(quest.rewarded_items)
    required_quests = _safe_named(quest.required_quests)
    return QuestDetail(
        **_summary(quest).model_dump(), summary=quest.summary, image_url=quest.image_url,
        difficulty=quest.difficulty, duration=quest.duration, solo_possible=quest.solo_possible,
        data_version=quest.data_version, starting_npcs=_safe_named(quest.starting_npcs),
        related_npcs=_safe_named(quest.related_npcs), required_items=required_items,
        rewarded_items=rewarded_items, required_quests=required_quests,
        unlocked_quests=_safe_named(quest.unlocked_quests), required_creatures=_safe_named(quest.required_creatures),
        bosses=_safe_named(quest.bosses), locations=_safe_named(quest.locations),
        access_unlocks=[value for value in (quest.access_unlocks or []) if isinstance(value, dict)],
        missions=missions, relationships=relations, related_creatures=related_creatures,
        requirements=[value["name"] for value in required_items + required_quests],
        rewards=[value["name"] for value in rewarded_items],
        related_quest_names=[value["name"] for value in required_quests + _safe_named(quest.unlocked_quests)],
    )
