"""Items/Loot API endpoints."""
from difflib import SequenceMatcher
from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload

from app.db.database import get_db
from app.models.creature import Creature
from app.models import Loot as LootModel
from app.models.spawn_location import SpawnLocation
from app.schemas import ItemDropCreature, ItemSearchResult
from app.services.entity_metadata_service import EntityMetadataService
from app.services.text_utils import normalize_search_text

router = APIRouter(prefix="/items", tags=["items"])


def _rank_item(query: str, item_name: str) -> tuple[int, float, str]:
    normalized_query = normalize_search_text(query)
    normalized_name = normalize_search_text(item_name)
    if normalized_name == normalized_query:
        return (0, -1.0, normalized_name)
    if normalized_name.startswith(normalized_query):
        return (1, -1.0, normalized_name)
    if normalized_query in normalized_name:
        return (2, -1.0, normalized_name)
    return (3, -SequenceMatcher(a=normalized_query, b=normalized_name).ratio(), normalized_name)


@router.get("/highlights", response_model=List[ItemSearchResult])
async def get_item_highlights(
    limit: int = Query(12, ge=1, le=50),
    db: Session = Depends(get_db),
):
    metadata = EntityMetadataService.get_highlights(db, entity_type="item", limit=limit)
    if not metadata:
        return []

    response: list[ItemSearchResult] = []
    for record in metadata:
        drops = (
            db.query(LootModel)
            .options(
                joinedload(LootModel.creature)
                .joinedload(Creature.spawn_locations)
                .joinedload(SpawnLocation.hunt_zone)
            )
            .filter(LootModel.normalized_name == record.entity_key)
            .all()
        )
        if not drops:
            continue
        response.append(_build_item_result(drops[0].item_name, drops))
    return response


@router.get("/", response_model=List[ItemSearchResult])
async def search_items(
    search: str = Query(..., min_length=2, description="Search term for item name"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Search for items/loot by name.
    Returns grouped results sorted by exactness and fuzzy similarity.
    """
    normalized_search = normalize_search_text(search)
    query = (
        db.query(LootModel)
        .options(
            joinedload(LootModel.creature)
            .joinedload(Creature.spawn_locations)
            .joinedload(SpawnLocation.hunt_zone)
        )
        .filter(LootModel.normalized_name.isnot(None))
        .filter(LootModel.normalized_name.contains(normalized_search))
    )
    candidate_rows = query.limit(max(limit * 8, 40)).all()
    if not candidate_rows:
        candidate_rows = (
            db.query(LootModel)
            .options(
                joinedload(LootModel.creature)
                .joinedload(Creature.spawn_locations)
                .joinedload(SpawnLocation.hunt_zone)
            )
            .limit(200)
            .all()
        )

    grouped: dict[str, list[LootModel]] = {}
    for row in candidate_rows:
        key = row.normalized_name or normalize_search_text(row.item_name)
        grouped.setdefault(key, []).append(row)

    ranked_keys = sorted(
        grouped.keys(),
        key=lambda key: _rank_item(search, grouped[key][0].item_name),
    )
    selected_keys = ranked_keys[skip: skip + limit]
    EntityMetadataService.record_searches(
        db,
        entity_type="item",
        matches=[(key, grouped[key][0].item_name, None) for key in selected_keys],
    )
    db.commit()
    return [_build_item_result(grouped[key][0].item_name, grouped[key]) for key in selected_keys]


def _build_item_result(item_name: str, drops: list[LootModel]) -> ItemSearchResult:
    related_drops: list[ItemDropCreature] = []
    seen_creature_ids: set[int] = set()
    for drop in sorted(drops, key=lambda item: (item.percentage is None, -(item.percentage or 0))):
        if not drop.creature or drop.creature.id in seen_creature_ids:
            continue
        seen_creature_ids.add(drop.creature.id)
        hunt_zones = []
        for spawn in drop.creature.spawn_locations or []:
            if spawn.hunt_zone:
                hunt_zones.append({
                    "id": spawn.hunt_zone.id,
                    "name": spawn.hunt_zone.name,
                    "city": spawn.hunt_zone.city,
                    "min_level": None if spawn.hunt_zone.min_level == 0 else spawn.hunt_zone.min_level,
                    "max_level": spawn.hunt_zone.max_level,
                    "difficulty": spawn.hunt_zone.difficulty,
                    "source_url": getattr(spawn.hunt_zone, "source_url", None),
                })
        related_drops.append(ItemDropCreature(
            creature_id=drop.creature.id,
            creature_name=drop.creature.name,
            creature_slug=getattr(drop.creature, "slug", None),
            chance=drop.percentage,
            rarity=drop.rarity,
            hunt_zones=hunt_zones,
        ))
    sample = drops[0]
    return ItemSearchResult(
        item_name=item_name,
        normalized_name=sample.normalized_name or normalize_search_text(item_name),
        item_image_url=sample.item_image_url,
        source_url=sample.source_url,
        drops=related_drops,
    )
