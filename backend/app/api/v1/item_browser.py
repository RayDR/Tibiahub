"""Canonical item browsing helpers for Cyclopedia Loot."""
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import asc, desc, func
from sqlalchemy.orm import Session

from app.api.v1.items import _build_canonical_item_result
from app.db.database import get_db
from app.models.external_data import Item as ExternalItemModel
from app.schemas import ItemSearchResult
from app.services.text_utils import normalize_search_text

router = APIRouter(prefix="/items", tags=["items"])

ItemSort = Literal["name", "category"]
SortOrder = Literal["asc", "desc"]


def _ordered_item_query(query, *, sort_by: ItemSort, sort_order: SortOrder):
    direction = desc if sort_order == "desc" else asc
    primary = ExternalItemModel.category if sort_by == "category" else ExternalItemModel.name
    return query.order_by(
        direction(primary).nullslast(),
        direction(ExternalItemModel.name),
        ExternalItemModel.id.asc(),
    )


@router.get("/facets")
def get_item_facets(db: Session = Depends(get_db)) -> dict:
    """Return local canonical item categories and counts for browse controls."""
    canonical = ExternalItemModel.knowledge_entity_id.isnot(None)
    total = db.query(func.count(ExternalItemModel.id)).filter(canonical).scalar() or 0
    rows = (
        db.query(ExternalItemModel.category, func.count(ExternalItemModel.id))
        .filter(
            canonical,
            ExternalItemModel.category.isnot(None),
            ExternalItemModel.category != "",
        )
        .group_by(ExternalItemModel.category)
        .order_by(ExternalItemModel.category.asc())
        .all()
    )
    return {
        "total": int(total),
        "categories": [
            {"value": category, "count": int(count)}
            for category, count in rows
            if category
        ],
    }


@router.get("/browse", response_model=list[ItemSearchResult])
def browse_items(
    search: str | None = Query(None, min_length=2, description="Search term for item name"),
    category: str | None = Query(None, min_length=1, max_length=100),
    sort_by: ItemSort = Query("name"),
    sort_order: SortOrder = Query("asc"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[ItemSearchResult]:
    """Browse canonical local items with stable pagination, category filtering, and sorting."""
    query = db.query(ExternalItemModel).filter(
        ExternalItemModel.knowledge_entity_id.isnot(None)
    )
    if search:
        query = query.filter(
            ExternalItemModel.normalized_name.contains(normalize_search_text(search))
        )
    if category:
        query = query.filter(ExternalItemModel.category.ilike(category))

    rows = (
        _ordered_item_query(query, sort_by=sort_by, sort_order=sort_order)
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [_build_canonical_item_result(db, item) for item in rows]
