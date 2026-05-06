"""Hunt Zones API endpoints."""
import hashlib
from typing import List, Optional
from urllib.parse import unquote, urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import Request, Response
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.db.database import get_db
from app.models.spawn_location import SpawnLocation
from app.models import HuntZone as HuntZoneModel
from app.models.settings import SystemSettings as SettingsModel
from app.schemas import HuntZone, HuntZoneCreate, HuntRecommendation
from app.services.entity_metadata_service import EntityMetadataService
from app.services.text_utils import normalize_search_text
from app.services.hunt_service import HuntRecommendationService

router = APIRouter(prefix="/hunt-zones", tags=["hunt-zones"])


def _get_setting(db: Session, key: str, default: str = "") -> str:
    value = db.query(SettingsModel).filter(SettingsModel.key == key).first()
    return value.value if value and value.value is not None else default


def _is_image_autofetch_enabled(db: Session) -> bool:
    return _get_setting(db, "auto_fetch_missing_images_enabled", "0") == "1"


async def _resolve_fandom_image_url(image_url: str) -> str | None:
    if "/Special:FilePath/" not in image_url:
        return image_url

    parsed = urlparse(image_url)
    asset_name = unquote(parsed.path.rsplit("/", 1)[-1])
    if not asset_name:
        return None
    file_title = asset_name[0].upper() + asset_name[1:]

    async with httpx.AsyncClient(
        timeout=20.0,
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


@router.get("/highlights", response_model=List[HuntZone])
async def get_hunt_zone_highlights(
    limit: int = Query(12, ge=1, le=50),
    db: Session = Depends(get_db),
):
    metadata = EntityMetadataService.get_highlights(db, entity_type="hunt_zone", limit=limit)
    zones = []
    for record in metadata:
        if record.entity_id is None:
            continue
        zone = (
            db.query(HuntZoneModel)
            .options(selectinload(HuntZoneModel.creature_spawns).selectinload(SpawnLocation.creature))
            .filter(HuntZoneModel.id == record.entity_id)
            .first()
        )
        if zone:
            zones.append(zone)
    return zones


@router.get("/", response_model=List[HuntZone])
async def get_hunt_zones(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    min_level: Optional[int] = None,
    max_level: Optional[int] = None,
    city: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get list of hunt zones with optional filters"""
    query = db.query(HuntZoneModel).options(selectinload(HuntZoneModel.creature_spawns).selectinload(SpawnLocation.creature))
    
    if min_level is not None:
        query = query.filter(HuntZoneModel.min_level >= min_level)
    
    if max_level is not None:
        query = query.filter(
            (HuntZoneModel.max_level.is_(None)) | (HuntZoneModel.max_level <= max_level)
        )
    
    if city:
        query = query.filter(HuntZoneModel.city.ilike(f"%{city}%"))

    if search:
        normalized_search = normalize_search_text(search)
        query = query.filter(
            (HuntZoneModel.name.ilike(f"%{search}%")) |
            (HuntZoneModel.city.ilike(f"%{search}%")) |
            (HuntZoneModel.normalized_name.contains(normalized_search))
        )
    
    zones = query.offset(skip).limit(limit).all()
    if search:
        EntityMetadataService.record_searches(
            db,
            entity_type="hunt_zone",
            matches=[(zone.normalized_name or zone.name, zone.name, zone.id) for zone in zones[: min(len(zones), 5)]],
        )
        db.commit()
    return zones


@router.get("/{zone_id}", response_model=HuntZone)
async def get_hunt_zone(zone_id: int, db: Session = Depends(get_db)):
    """Get detailed information about a specific hunt zone"""
    zone = (
        db.query(HuntZoneModel)
        .options(selectinload(HuntZoneModel.creature_spawns).selectinload(SpawnLocation.creature))
        .filter(HuntZoneModel.id == zone_id)
        .first()
    )
    
    if not zone:
        raise HTTPException(status_code=404, detail="Hunt zone not found")

    EntityMetadataService.record_searches(
        db,
        entity_type="hunt_zone",
        matches=[(zone.normalized_name or zone.name, zone.name, zone.id)],
    )
    db.commit()
    
    return zone


@router.get("/{zone_id}/map-image")
async def get_hunt_zone_map_image(zone_id: int, request: Request, db: Session = Depends(get_db)):
    """Proxy hunt zone map image with fallback resolution and ETag caching."""
    zone = db.query(HuntZoneModel).filter(HuntZoneModel.id == zone_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail="Hunt zone not found")

    map_url = zone.map_image_url
    if not map_url:
        raise HTTPException(status_code=404, detail="Map image not available")
    if not _is_image_autofetch_enabled(db):
        raise HTTPException(status_code=404, detail="Map image not cached locally")

    resolved_url = map_url
    try:
        async with httpx.AsyncClient(
            timeout=20.0,
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

        if zone.map_image_url != resolved_url:
            zone.map_image_url = resolved_url
            db.add(zone)
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

        media_type = upstream.headers.get("content-type", "image/png").split(";")[0]
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
        raise HTTPException(status_code=404, detail=f"Map image source unavailable: {str(exc)}") from exc


@router.get("/recommendations/{vocation}", response_model=List[HuntRecommendation])
async def get_hunt_recommendations(
    vocation: str,
    level: int = Query(..., ge=1, le=2000),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """
    Get hunt zone recommendations for a specific vocation and level
    
    - **vocation**: knight, paladin, sorcerer, druid, or monk
    - **level**: Player level (1-2000)
    - **limit**: Maximum number of recommendations (default: 10)
    """
    try:
        recommendations = HuntRecommendationService.get_recommendations(
            db, vocation, level, limit
        )
        return recommendations
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/", response_model=HuntZone, status_code=201)
async def create_hunt_zone(
    zone: HuntZoneCreate,
    db: Session = Depends(get_db)
):
    """Create a new hunt zone"""
    existing = db.query(HuntZoneModel).filter(
        HuntZoneModel.name == zone.name
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Hunt zone already exists")
    
    db_zone = HuntZoneModel(**zone.dict())
    db.add(db_zone)
    db.commit()
    db.refresh(db_zone)
    
    return db_zone
