"""Items/Loot API endpoints."""
import hashlib
import asyncio
from difflib import SequenceMatcher
from typing import List
from urllib.parse import unquote, urlparse

import httpx
from fastapi import APIRouter, Depends, Query
from fastapi import HTTPException, Request, Response
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.db.database import get_db
from app.models.creature import Creature
from app.models.settings import SystemSettings as SettingsModel
from app.models import Loot as LootModel
from app.models.external_data import Item as ExternalItemModel
from app.models.spawn_location import SpawnLocation
from app.schemas import ItemDetail, ItemDropCreature, ItemSearchResult
from app.services.entity_metadata_service import EntityMetadataService
from app.services.external_apis import get_items
from app.services.text_utils import normalize_search_text

router = APIRouter(prefix="/items", tags=["items"])
DETAIL_FALLBACK_TIMEOUT_SECONDS = 15.0


def _get_setting(db: Session, key: str, default: str = "") -> str:
    value = db.query(SettingsModel).filter(SettingsModel.key == key).first()
    return value.value if value and value.value is not None else default


def _is_external_detail_fallback_enabled(db: Session) -> bool:
    return (
        _get_setting(db, "external_auto_fallback_enabled", "0") == "1"
        or _get_setting(db, "bestiary_allow_external_detail_fallback", "0") == "1"
    )


def _is_image_autofetch_enabled(db: Session) -> bool:
    return _get_setting(db, "auto_fetch_missing_images_enabled", "0") == "1"


def _build_item_special_filepath(item_name: str) -> str:
    safe_name = item_name.replace(" ", "_")
    return f"{settings.TIBIAWIKI_BASE_PAGE_URL}/Special:FilePath/{safe_name}.gif"


async def _resolve_fandom_image_url(image_url: str) -> str | None:
    if "/Special:FilePath/" not in image_url:
        return image_url

    parsed = urlparse(image_url)
    asset_name = unquote(parsed.path.rsplit("/", 1)[-1])
    if not asset_name:
        return None
    file_title = asset_name[0].upper() + asset_name[1:]

    async with httpx.AsyncClient(
        timeout=15.0,
        headers={"User-Agent": settings.TIBIAWIKI_USER_AGENT, "Accept": "application/json"},
    ) as client:
        response = await client.get(
            settings.TIBIAWIKI_API_URL,
            params={
                "action": "query",
                "titles": f"File:{file_title}",
                "prop": "imageinfo",
                "iiprop": "url",
                "format": "json",
            },
        )
        response.raise_for_status()
        pages = ((response.json() or {}).get("query") or {}).get("pages") or {}
        for page in pages.values():
            imageinfo = page.get("imageinfo") or []
            if imageinfo and imageinfo[0].get("url"):
                return imageinfo[0]["url"]
    return None


@router.get("/{item_id}/image")
async def get_item_image(item_id: int, request: Request, db: Session = Depends(get_db)):
    """Proxy loot image with fallback resolution and ETag caching."""
    loot = db.query(LootModel).filter(LootModel.id == item_id).first()
    if not loot:
        loot = db.query(LootModel).filter(LootModel.external_id == str(item_id)).first()
    if not loot:
        raise HTTPException(status_code=404, detail="Item not found")

    if not _is_image_autofetch_enabled(db):
        raise HTTPException(status_code=404, detail="Image not cached locally")

    resolved_url = loot.item_image_url
    if not resolved_url:
        resolved_url = _build_item_special_filepath(loot.item_name)

    try:
        async with httpx.AsyncClient(
            timeout=15.0,
            follow_redirects=True,
            headers={
                "User-Agent": settings.TIBIAWIKI_USER_AGENT,
                "Referer": settings.TIBIAWIKI_BASE_PAGE_URL,
            },
        ) as client:
            upstream = await client.get(resolved_url)
            if upstream.status_code in {403, 404} and "/Special:FilePath/" in resolved_url:
                fallback_url = await _resolve_fandom_image_url(resolved_url)
                if fallback_url:
                    resolved_url = fallback_url
                    upstream = await client.get(resolved_url)
            upstream.raise_for_status()

        if loot.item_image_url != resolved_url:
            loot.item_image_url = resolved_url
            db.add(loot)
            db.commit()

        content = upstream.content
        etag = hashlib.sha1(content).hexdigest()
        if request.headers.get("if-none-match") == etag:
            return Response(
                status_code=304,
                headers={
                    "ETag": etag,
                    "Cache-Control": f"public, max-age={settings.IMAGE_CACHE_MAX_AGE_SECONDS}",
                },
            )

        media_type = upstream.headers.get("content-type", "image/gif").split(";")[0]
        return Response(
            content=content,
            media_type=media_type,
            headers={
                "Content-Type": media_type,
                "Content-Length": str(len(content)),
                "Cache-Control": f"public, max-age={settings.IMAGE_CACHE_MAX_AGE_SECONDS}",
                "ETag": etag,
            },
        )
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Image source unavailable: {str(exc)}") from exc


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
    search: str | None = Query(None, min_length=2, description="Search term for item name"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Search for items/loot by name.
    Returns grouped results sorted by exactness and fuzzy similarity.
    """
    if not search:
        rows = (
            db.query(LootModel)
            .options(
                joinedload(LootModel.creature)
                .joinedload(Creature.spawn_locations)
                .joinedload(SpawnLocation.hunt_zone)
            )
            .filter(LootModel.normalized_name.isnot(None))
            .limit(500)
            .all()
        )
        if not rows and _is_external_detail_fallback_enabled(db):
            external_response = await asyncio.wait_for(get_items(expand=False), timeout=DETAIL_FALLBACK_TIMEOUT_SECONDS)
            if external_response.success() and isinstance(external_response.data, list):
                # Persist only requested page to avoid mass sync behavior.
                page_slice = external_response.data[skip: skip + limit]
                persisted: list[ItemSearchResult] = []
                for entry in page_slice:
                    name = (entry.get("name") or "").strip()
                    if not name:
                        continue
                    existing = db.query(ExternalItemModel).filter(ExternalItemModel.name == name).first()
                    if not existing:
                        existing = ExternalItemModel(name=name)
                        db.add(existing)
                    existing.item_id = entry.get("item_id")
                    existing.description = entry.get("description")
                    existing.type = entry.get("type")
                    existing.raw_data = entry
                    persisted.append(
                        ItemSearchResult(
                            item_name=name,
                            normalized_name=normalize_search_text(name),
                            item_image_url=entry.get("image_url"),
                            source_url=entry.get("source_url"),
                            drops=[],
                        )
                    )
                if persisted:
                    db.commit()
                    return persisted
        grouped: dict[str, list[LootModel]] = {}
        for row in rows:
            key = row.normalized_name or normalize_search_text(row.item_name)
            grouped.setdefault(key, []).append(row)
        ranked_keys = sorted(grouped.keys(), key=lambda key: _rank_item(grouped[key][0].item_name, grouped[key][0].item_name))
        selected_keys = ranked_keys[skip: skip + limit]
        return [_build_item_result(grouped[key][0].item_name, grouped[key]) for key in selected_keys]

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
    if not selected_keys and _is_external_detail_fallback_enabled(db):
        external_response = await asyncio.wait_for(get_items(expand=False), timeout=DETAIL_FALLBACK_TIMEOUT_SECONDS)
        if external_response.success() and isinstance(external_response.data, list):
            external_items = [entry for entry in external_response.data if entry.get("name")]
            if external_items:
                external_items.sort(key=lambda entry: _rank_item(search, entry.get("name", "")))
                best_match = external_items[0]
                if normalize_search_text(search) in normalize_search_text(best_match.get("name", "")):
                    name = best_match.get("name")
                    normalized_name = normalize_search_text(name)
                    existing = db.query(ExternalItemModel).filter(ExternalItemModel.name == name).first()
                    if not existing:
                        existing = ExternalItemModel(name=name)
                        db.add(existing)
                    existing.description = best_match.get("description")
                    existing.type = best_match.get("type")
                    existing.raw_data = best_match
                    EntityMetadataService.record_searches(
                        db,
                        entity_type="item",
                        matches=[(normalized_name, name, None)],
                    )
                    db.commit()
                    return [
                        ItemSearchResult(
                            item_name=name,
                            normalized_name=normalized_name,
                            item_image_url=best_match.get("image_url"),
                            source_url=best_match.get("source_url"),
                            drops=[],
                        )
                    ]
    EntityMetadataService.record_searches(
        db,
        entity_type="item",
        matches=[(key, grouped[key][0].item_name, None) for key in selected_keys],
    )
    db.commit()
    return [_build_item_result(grouped[key][0].item_name, grouped[key]) for key in selected_keys]


@router.get("/{item_id}", response_model=ItemDetail)
async def get_item_detail(item_id: int, db: Session = Depends(get_db)):
    """Get item detail from local cache first, then controlled external fallback."""
    local_by_id = (
        db.query(LootModel)
        .options(
            joinedload(LootModel.creature)
            .joinedload(Creature.spawn_locations)
            .joinedload(SpawnLocation.hunt_zone)
        )
        .filter(LootModel.id == item_id)
        .first()
    )

    if not local_by_id:
        local_by_id = (
            db.query(LootModel)
            .options(
                joinedload(LootModel.creature)
                .joinedload(Creature.spawn_locations)
                .joinedload(SpawnLocation.hunt_zone)
            )
            .filter(LootModel.external_id == str(item_id))
            .first()
        )

    if local_by_id:
        all_rows = (
            db.query(LootModel)
            .options(
                joinedload(LootModel.creature)
                .joinedload(Creature.spawn_locations)
                .joinedload(SpawnLocation.hunt_zone)
            )
            .filter(LootModel.normalized_name == local_by_id.normalized_name)
            .all()
        )
        mapped = _build_item_result(local_by_id.item_name, all_rows)
        top_drop = max((drop.chance for drop in mapped.drops if drop.chance is not None), default=None)
        rarity = next((drop.rarity for drop in mapped.drops if drop.rarity), None)
        return ItemDetail(
            id=local_by_id.id,
            item_name=mapped.item_name,
            normalized_name=mapped.normalized_name,
            item_image_url=mapped.item_image_url,
            source_url=mapped.source_url,
            rarity=rarity,
            drop_chance=top_drop,
            drops=mapped.drops,
        )

    if _is_external_detail_fallback_enabled(db):
        external_response = await asyncio.wait_for(get_items(expand=True), timeout=DETAIL_FALLBACK_TIMEOUT_SECONDS)
        if external_response.success() and isinstance(external_response.data, list):
            best = next(
                (
                    entry for entry in external_response.data
                    if entry.get("item_id") == item_id
                    or str(entry.get("item_id") or "") == str(item_id)
                ),
                None,
            )
            if best:
                name = (best.get("name") or "").strip()
                if not name:
                    raise HTTPException(status_code=404, detail="Item not found")

                normalized_name = normalize_search_text(name)
                existing = db.query(ExternalItemModel).filter(ExternalItemModel.name == name).first()
                if not existing:
                    existing = ExternalItemModel(name=name)
                    db.add(existing)
                existing.item_id = best.get("item_id")
                existing.description = best.get("description")
                existing.type = best.get("type")
                existing.raw_data = best
                db.commit()

                return ItemDetail(
                    id=existing.id,
                    item_name=name,
                    normalized_name=normalized_name,
                    item_image_url=best.get("image_url"),
                    source_url=best.get("source_url"),
                    rarity=None,
                    drop_chance=None,
                    drops=[],
                )

    raise HTTPException(status_code=404, detail="Item not found")


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
