"""Canonical quest browsing helpers for the Cyclopedia quest library."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import asc, desc, func, or_
from sqlalchemy.orm import Session

from app.api.v1.quests import _summary
from app.db.database import get_db
from app.models.external_data import TibiaWikiQuest
from app.services.text_utils import normalize_search_text

router = APIRouter(prefix="/quests", tags=["quests"])

QuestSort = Literal["name", "min_level"]
SortOrder = Literal["asc", "desc"]


def _access_quest_predicate():
    textual = or_(
        func.lower(func.coalesce(TibiaWikiQuest.category, "")).contains("access quest"),
        func.lower(func.coalesce(TibiaWikiQuest.quest_type, "")).contains("access quest"),
        func.lower(func.coalesce(TibiaWikiQuest.group_name, "")).contains("access quest"),
    )
    return or_(textual, TibiaWikiQuest.access_unlocks != [])


def _is_access_quest(row: TibiaWikiQuest) -> bool:
    values = (row.category, row.quest_type, row.group_name)
    return any("access quest" in str(value or "").lower() for value in values) or bool(row.access_unlocks)


def _base_query(db: Session):
    return db.query(TibiaWikiQuest).filter(
        TibiaWikiQuest.knowledge_entity_id.isnot(None),
        TibiaWikiQuest.is_group.is_(False),
    )


def _ordered_query(query, *, sort_by: QuestSort, sort_order: SortOrder):
    direction = desc if sort_order == "desc" else asc
    if sort_by == "min_level":
        return query.order_by(
            direction(TibiaWikiQuest.min_level).nullslast(),
            direction(TibiaWikiQuest.name),
            TibiaWikiQuest.id.asc(),
        )
    return query.order_by(direction(TibiaWikiQuest.name), TibiaWikiQuest.id.asc())


def _browser_result(row: TibiaWikiQuest) -> dict:
    payload = _summary(row).model_dump()
    payload["is_access_quest"] = _is_access_quest(row)
    return payload


@router.get("/facets")
def get_quest_facets(db: Session = Depends(get_db)) -> dict:
    base = _base_query(db)
    total = base.count()
    access_total = base.filter(_access_quest_predicate()).count()
    known_level = base.filter(TibiaWikiQuest.min_level.isnot(None)).count()
    bounds = (
        base.with_entities(func.min(TibiaWikiQuest.min_level), func.max(TibiaWikiQuest.min_level))
        .filter(TibiaWikiQuest.min_level.isnot(None))
        .first()
    )
    return {
        "total": int(total),
        "access_quests": int(access_total),
        "minimum_level_known": int(known_level),
        "minimum_level_min": bounds[0] if bounds else None,
        "minimum_level_max": bounds[1] if bounds else None,
    }


@router.get("/browse")
def browse_quests(
    search: str | None = Query(None, min_length=2, description="Search term for quest name"),
    access_only: bool = Query(False),
    sort_by: QuestSort = Query("name"),
    sort_order: SortOrder = Query("asc"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[dict]:
    query = _base_query(db)
    if search:
        query = query.filter(TibiaWikiQuest.normalized_name.contains(normalize_search_text(search)))
    if access_only:
        query = query.filter(_access_quest_predicate())
    rows = _ordered_query(query, sort_by=sort_by, sort_order=sort_order).offset(skip).limit(limit).all()
    return [_browser_result(row) for row in rows]
