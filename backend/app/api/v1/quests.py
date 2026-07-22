"""Quest search endpoints (local-first with controlled external fallback)."""
import asyncio
from difflib import SequenceMatcher
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.creature import Creature
from app.models.external_data import TibiaWikiQuest
from app.models.settings import SystemSettings as SettingsModel
from app.schemas import QuestDetail, QuestRelatedCreature, QuestSearchResult
from app.services.entity_metadata_service import EntityMetadataService
from app.services.external_apis import get_quests
from app.services.text_utils import normalize_search_text

router = APIRouter(prefix="/quests", tags=["quests"])
DETAIL_FALLBACK_TIMEOUT_SECONDS = 15.0


def _get_setting(db: Session, key: str, default: str = "") -> str:
    value = db.query(SettingsModel).filter(SettingsModel.key == key).first()
    return value.value if value and value.value is not None else default


def _is_external_detail_fallback_enabled(db: Session) -> bool:
    return (
        _get_setting(db, "external_auto_fallback_enabled", "0") == "1"
        or _get_setting(db, "bestiary_allow_external_detail_fallback", "0") == "1"
    )


def _rank_quest(query: str, quest_name: str) -> tuple[int, float, str]:
    normalized_query = normalize_search_text(query)
    normalized_name = normalize_search_text(quest_name)
    if normalized_name == normalized_query:
        return (0, -1.0, normalized_name)
    if normalized_name.startswith(normalized_query):
        return (1, -1.0, normalized_name)
    if normalized_query in normalized_name:
        return (2, -1.0, normalized_name)
    return (3, -SequenceMatcher(a=normalized_query, b=normalized_name).ratio(), normalized_name)


@router.get("/highlights", response_model=List[QuestSearchResult])
async def get_quest_highlights(
    limit: int = Query(12, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Return top local quest records ranked by metadata search/highlight signals."""
    metadata = EntityMetadataService.get_highlights(db, entity_type="quest", limit=limit)
    quest_ids = [record.entity_id for record in metadata if record.entity_id is not None]
    rows: list[TibiaWikiQuest] = []
    if quest_ids:
        raw = db.query(TibiaWikiQuest).filter(TibiaWikiQuest.id.in_(quest_ids)).all()
        by_id = {row.id: row for row in raw}
        rows = [by_id[qid] for qid in quest_ids if qid in by_id and not bool(getattr(by_id[qid], "is_group", False))]
    if not rows:
        rows = (
            db.query(TibiaWikiQuest)
            .filter((TibiaWikiQuest.is_group.is_(False)) | (TibiaWikiQuest.is_group.is_(None)))
            .order_by(TibiaWikiQuest.updated_at.desc().nullslast(), TibiaWikiQuest.id.desc())
            .limit(limit)
            .all()
        )

    return [
        QuestSearchResult(
            id=row.id,
            name=row.name,
            slug=row.slug,
            description=row.description,
            group_name=row.group_name,
            parent_page=row.parent_page,
            is_group=bool(row.is_group),
            min_level=row.min_level,
            max_level=row.max_level,
            experience_reward=row.experience_reward,
            location=row.location,
            npc=row.npc,
            source_url=row.source_url or ((row.raw_data or {}).get("source_url") if row.raw_data else None),
        )
        for row in rows
    ]


@router.get("/", response_model=List[QuestSearchResult])
async def search_quests(
    search: str | None = Query(None, min_length=2, description="Search term for quest name"),
    include_groups: bool = Query(False, description="Include group/hub pages in results"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    base_query = db.query(TibiaWikiQuest)
    if not include_groups:
        base_query = base_query.filter((TibiaWikiQuest.is_group.is_(False)) | (TibiaWikiQuest.is_group.is_(None)))

    if search:
        rows = (
            base_query
            .filter(TibiaWikiQuest.name.ilike(f"%{search}%"))
            .offset(skip)
            .limit(limit)
            .all()
        )
    else:
        rows = (
            base_query
            .order_by(TibiaWikiQuest.updated_at.desc().nullslast(), TibiaWikiQuest.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    if not rows and search:
        rows = (
            db.query(TibiaWikiQuest)
            .filter(TibiaWikiQuest.raw_data.isnot(None))
            .limit(300)
            .all()
        )
        rows = sorted(rows, key=lambda item: _rank_quest(search, item.name))[skip: skip + limit]

    if rows:
        EntityMetadataService.record_searches(
            db,
            entity_type="quest",
            matches=[(normalize_search_text(row.name), row.name, row.id) for row in rows[: min(len(rows), 5)]],
        )
        db.commit()

    return [
        QuestSearchResult(
            id=row.id,
            name=row.name,
            slug=row.slug,
            description=row.description,
            group_name=row.group_name,
            parent_page=row.parent_page,
            is_group=bool(row.is_group),
            min_level=row.min_level,
            max_level=row.max_level,
            experience_reward=row.experience_reward,
            location=row.location,
            npc=row.npc,
            source_url=row.source_url or ((row.raw_data or {}).get("source_url") if row.raw_data else None),
        )
        for row in rows
    ]


@router.get("/{quest_id}", response_model=QuestDetail)
async def get_quest_detail(quest_id: int, db: Session = Depends(get_db)):
    quest = db.query(TibiaWikiQuest).filter(TibiaWikiQuest.id == quest_id).first()

    if not quest and _is_external_detail_fallback_enabled(db):
        external_response = await asyncio.wait_for(get_quests(expand=True), timeout=DETAIL_FALLBACK_TIMEOUT_SECONDS)
        if external_response.success() and isinstance(external_response.data, list):
            best = next(
                (
                    entry for entry in external_response.data
                    if entry.get("id") == quest_id or str(entry.get("id") or "") == str(quest_id)
                ),
                None,
            )
            if best and best.get("name"):
                existing = db.query(TibiaWikiQuest).filter(TibiaWikiQuest.name == best["name"]).first()
                if not existing:
                    existing = TibiaWikiQuest(name=best["name"])
                    db.add(existing)
                existing.description = best.get("description")
                existing.min_level = best.get("min_level")
                existing.max_level = best.get("max_level")
                existing.experience_reward = best.get("experience_reward")
                existing.location = best.get("location")
                existing.npc = best.get("npc")
                existing.raw_data = best
                db.commit()
                db.refresh(existing)
                quest = existing

    if not quest:
        raise HTTPException(status_code=404, detail="Quest not found")

    normalized_name = normalize_search_text(quest.name)
    related_creatures_rows = (
        db.query(Creature)
        .filter(Creature.related_tasks.isnot(None))
        .all()
    )
    related_creatures: list[QuestRelatedCreature] = []
    for creature in related_creatures_rows:
        tasks = [task for task in (creature.related_tasks or []) if isinstance(task, str)]
        if any(normalized_name in normalize_search_text(task) for task in tasks):
            related_creatures.append(
                QuestRelatedCreature(
                    creature_id=creature.id,
                    creature_name=creature.name,
                    creature_slug=creature.slug,
                    is_boss=bool(creature.is_boss),
                    classification=creature.classification,
                    image_url=creature.image_url,
                )
            )

    raw_data = quest.raw_data or {}
    requirements = [
        item
        for item in (
            quest.requirements
            or raw_data.get("requirements")
            or raw_data.get("related_tasks")
            or raw_data.get("missions")
            or []
        )
        if isinstance(item, str)
    ]

    if not requirements:
        requirements = [
            task
            for creature in related_creatures_rows
            for task in (creature.related_tasks or [])
            if isinstance(task, str) and normalized_name in normalize_search_text(task)
        ]

    return QuestDetail(
        id=quest.id,
        name=quest.name,
        slug=quest.slug,
        description=quest.description,
        group_name=quest.group_name,
        parent_page=quest.parent_page,
        is_group=bool(quest.is_group),
        min_level=quest.min_level,
        max_level=quest.max_level,
        experience_reward=quest.experience_reward,
        location=quest.location,
        npc=quest.npc,
        source_url=quest.source_url or ((quest.raw_data or {}).get("source_url") if quest.raw_data else None),
        rewards=[item for item in (quest.rewards or []) if isinstance(item, str)],
        requirements=requirements,
        related_quest_names=[item for item in (raw_data.get("related_quests") or []) if isinstance(item, str)],
        related_creatures=related_creatures,
    )
