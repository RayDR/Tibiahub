"""Creatures API endpoints."""
import hashlib
from typing import List, Optional
from urllib.parse import unquote, urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models import Creature as CreatureModel
from app.schemas import Creature, CreatureCreate, CreatureSimple
from app.services.bestiary_source import BestiarySourceError, get_creature_detail_by_id, get_creature_detail_by_name, list_creature_summaries
from app.services.creature_storage_service import get_cached_creature_by_id, get_cached_creature_by_name, list_cached_creatures, upsert_creature_payload
from app.services.entity_metadata_service import EntityMetadataService
from app.services.text_utils import normalize_search_text
from app.core.config import settings

router = APIRouter(prefix="/creatures", tags=["creatures"])


async def _resolve_fandom_image_url(image_url: str) -> Optional[str]:
    if "/Special:FilePath/" not in image_url:
        return image_url

    parsed = urlparse(image_url)
    asset_name = unquote(parsed.path.rsplit("/", 1)[-1])
    if not asset_name:
        return None
    file_title = asset_name[0].upper() + asset_name[1:]

    async with httpx.AsyncClient(timeout=20.0, headers={"User-Agent": settings.TIBIAWIKI_USER_AGENT, "Accept": "application/json"}) as client:
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


@router.get("/highlights", response_model=List[CreatureSimple])
async def get_creature_highlights(
    limit: int = Query(18, ge=1, le=50),
    db: Session = Depends(get_db),
):
    metadata = EntityMetadataService.get_highlights(db, entity_type="creature", limit=limit)
    creatures: list[CreatureSimple] = []
    for record in metadata:
        if record.entity_id is None:
            continue
        creature = db.query(CreatureModel).filter(CreatureModel.id == record.entity_id).first()
        if creature:
            creatures.append(creature)
    if creatures:
        return creatures
    return list_cached_creatures(db, search=None, skip=0, limit=limit, sort_by="name", sort_order="asc")


@router.get("/", response_model=List[CreatureSimple])
async def get_creatures(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    search: Optional[str] = None,
    difficulty: Optional[str] = None,
    sort_by: str = Query("name", pattern="^(name|experience|hitpoints|difficulty)$"),
    sort_order: str = Query("asc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
):
    """Get list of creatures with optional filters"""
    if not search:
        return list_cached_creatures(db, search=None, skip=skip, limit=limit, sort_by=sort_by, sort_order=sort_order)

    try:
        summaries = await list_creature_summaries(
            skip=skip,
            limit=limit,
            search=search,
            difficulty=difficulty,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        for item in summaries[: min(len(summaries), 10)]:
            cached = db.query(CreatureModel).filter(CreatureModel.id == item["id"]).first()
            if cached:
                cached.hitpoints = item.get("hitpoints") or cached.hitpoints
                cached.experience = item.get("experience") or cached.experience
                cached.image_url = item.get("image_url") or cached.image_url
                cached.slug = item.get("slug") or cached.slug
                cached.normalized_name = normalize_search_text(item.get("name"))
            else:
                upsert_creature_payload(db, item)
        EntityMetadataService.record_searches(
            db,
            entity_type="creature",
            matches=[(item["name"], item["name"], item["id"]) for item in summaries[: min(len(summaries), 5)]],
        )
        db.commit()
        return summaries
    except BestiarySourceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/{creature_id}", response_model=Creature)
async def get_creature(creature_id: int, db: Session = Depends(get_db)):
    """Get detailed information about a specific creature"""
    cached = get_cached_creature_by_id(db, creature_id)
    if cached and cached.loot_items:
        EntityMetadataService.record_searches(
            db,
            entity_type="creature",
            matches=[(cached.normalized_name or cached.name, cached.name, cached.id)],
        )
        db.commit()
        return cached
    try:
        payload = await get_creature_detail_by_id(creature_id)
        creature = upsert_creature_payload(db, payload)
        EntityMetadataService.record_searches(
            db,
            entity_type="creature",
            matches=[(creature.normalized_name or creature.name, creature.name, creature.id)],
        )
        db.commit()
        db.refresh(creature)
        return get_cached_creature_by_id(db, creature.id) or creature
    except BestiarySourceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/name/{creature_name}", response_model=Creature)
async def get_creature_by_name(creature_name: str, db: Session = Depends(get_db)):
    """Get detailed information about a creature by name"""
    cached = get_cached_creature_by_name(db, creature_name)
    if cached and cached.loot_items:
        EntityMetadataService.record_searches(
            db,
            entity_type="creature",
            matches=[(cached.normalized_name or cached.name, cached.name, cached.id)],
        )
        db.commit()
        return cached
    try:
        payload = await get_creature_detail_by_name(creature_name)
        creature = upsert_creature_payload(db, payload)
        EntityMetadataService.record_searches(
            db,
            entity_type="creature",
            matches=[(creature.normalized_name or creature.name, creature.name, creature.id)],
        )
        db.commit()
        return get_cached_creature_by_id(db, creature.id) or creature
    except BestiarySourceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/", response_model=Creature, status_code=201)
async def create_creature(
    creature: CreatureCreate,
    db: Session = Depends(get_db),
):
    """Create a new creature in the local cache database"""
    existing = db.query(CreatureModel).filter(CreatureModel.name == creature.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Creature already exists")

    db_creature = CreatureModel(**creature.dict())
    db.add(db_creature)
    db.commit()
    db.refresh(db_creature)
    return db_creature


@router.get("/{creature_id}/image")
async def get_creature_image(creature_id: int, request: Request, db: Session = Depends(get_db)):
    """Proxy creature image as a complete buffered response to avoid HTTP/2 chunk issues."""
    try:
        creature = get_cached_creature_by_id(db, creature_id)
        if not creature:
            payload = await get_creature_detail_by_id(creature_id)
            creature = upsert_creature_payload(db, payload)
            db.commit()
    except BestiarySourceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    image_url = creature.image_url if hasattr(creature, "image_url") else creature.get("image_url")
    if not image_url:
        raise HTTPException(status_code=404, detail="Image not found")

    resolved_url = image_url
    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True, headers={
            "User-Agent": settings.TIBIAWIKI_USER_AGENT,
            "Referer": settings.TIBIAWIKI_BASE_PAGE_URL,
        }) as client:
            upstream = await client.get(resolved_url)
            if upstream.status_code in {403, 404} and "/Special:FilePath/" in resolved_url:
                fallback_url = await _resolve_fandom_image_url(resolved_url)
                if fallback_url:
                    resolved_url = fallback_url
                    if hasattr(creature, "image_url"):
                        creature.image_url = fallback_url
                        db.add(creature)
                        db.commit()
                    upstream = await client.get(resolved_url)
            upstream.raise_for_status()

        content = upstream.content
        etag = hashlib.sha1(content).hexdigest()
        if request.headers.get("if-none-match") == etag:
            return Response(status_code=304, headers={
                "ETag": etag,
                "Cache-Control": f"public, max-age={settings.IMAGE_CACHE_MAX_AGE_SECONDS}",
            })

        media_type = upstream.headers.get("content-type", "image/gif").split(";")[0]
        headers = {
            "Content-Type": media_type,
            "Content-Length": str(len(content)),
            "Cache-Control": f"public, max-age={settings.IMAGE_CACHE_MAX_AGE_SECONDS}",
            "ETag": etag,
        }
        return Response(content=content, media_type=media_type, headers=headers)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Image source unavailable: {str(exc)}") from exc
