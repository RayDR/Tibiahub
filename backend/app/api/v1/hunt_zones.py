"""Hunt Zones API endpoints."""
import hashlib
from typing import List, Optional
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
from app.services import media_asset_service as media_svc

router = APIRouter(prefix="/hunt-zones", tags=["hunt-zones"])


def _get_setting(db: Session, key: str, default: str = "") -> str:
    value = db.query(SettingsModel).filter(SettingsModel.key == key).first()
    return value.value if value and value.value is not None else default


def _is_image_autofetch_enabled(db: Session) -> bool:
    return _get_setting(db, "auto_fetch_missing_images_enabled", "0") == "1"


async def _resolve_fandom_image_url(image_url: str) -> str | None:
    return image_url


def _placeholder_map_svg(label: str) -> bytes:
    safe = media_svc.escape_svg_text(label or "Unknown Zone", limit=48)
    return (
        "<svg xmlns='http://www.w3.org/2000/svg' width='640' height='360' viewBox='0 0 640 360'>"
        "<defs><linearGradient id='bg' x1='0' y1='0' x2='1' y2='1'>"
        "<stop offset='0%' stop-color='#0f172a'/><stop offset='100%' stop-color='#1e293b'/></linearGradient></defs>"
        "<rect width='640' height='360' fill='url(#bg)'/>"
        "<path d='M0 280 L160 220 L280 260 L410 210 L640 260 L640 360 L0 360 Z' fill='#334155'/>"
        "<circle cx='320' cy='162' r='22' fill='#f59e0b'/><circle cx='320' cy='162' r='8' fill='#111827'/>"
        f"<text x='320' y='324' text-anchor='middle' fill='#cbd5e1' font-size='20' font-family='Arial, sans-serif'>{safe}</text>"
        "</svg>"
    ).encode("utf-8")


@router.get("/highlights", response_model=List[HuntZone])
async def get_hunt_zone_highlights(
    limit: int = Query(12, ge=1, le=50),
    db: Session = Depends(get_db),
):
    try:
        metadata = EntityMetadataService.get_highlights(db, entity_type="hunt_zone", limit=limit)
        if not metadata:
            return []

        zone_ids = [record.entity_id for record in metadata if record.entity_id is not None]
        if not zone_ids:
            return []

        raw_zones = db.query(HuntZoneModel).filter(HuntZoneModel.id.in_(zone_ids)).all()
        by_id = {zone.id: zone for zone in raw_zones}
        return [by_id[zone_id] for zone_id in zone_ids if zone_id in by_id]
    except Exception:
        return []


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
    """Serve hunt-zone map image from local MediaAsset cache (local-first)."""
    zone = db.query(HuntZoneModel).filter(HuntZoneModel.id == zone_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail="Hunt zone not found")

    asset_key = media_svc.build_zone_asset_key(zone)
    source_url = media_svc.build_zone_source_url(zone)
    if not source_url:
        placeholder = _placeholder_map_svg(zone.name)
        return Response(
            content=placeholder,
            media_type="image/svg+xml",
            headers={
                "Cache-Control": "public, max-age=3600",
                "X-Image-Source": "placeholder",
                "X-Asset-Key": asset_key,
            },
        )

    autofetch = _is_image_autofetch_enabled(db)
    asset = await media_svc.get_or_fetch_asset(
        db,
        asset_key=asset_key,
        source_url=source_url,
        autofetch_enabled=autofetch,
    )

    if not asset or asset.status != "cached":
        placeholder = _placeholder_map_svg(zone.name)
        return Response(
            content=placeholder,
            media_type="image/svg+xml",
            headers={
                "Cache-Control": "public, max-age=3600",
                "X-Image-Source": "placeholder",
                "X-Image-Status": getattr(asset, "status", "missing") if asset else "missing",
                "X-Asset-Key": asset_key,
            },
        )

    content = asset.read_bytes()
    if not content:
        placeholder = _placeholder_map_svg(zone.name)
        return Response(
            content=placeholder,
            media_type="image/svg+xml",
            headers={
                "Cache-Control": "public, max-age=3600",
                "X-Image-Source": "placeholder",
                "X-Image-Status": "missing",
                "X-Asset-Key": asset_key,
            },
        )

    etag = asset.sha256_hash[:20] if asset.sha256_hash else hashlib.sha1(content).hexdigest()
    if request.headers.get("if-none-match") == etag:
        return Response(
            status_code=304,
            headers={
                "ETag": etag,
                "Cache-Control": f"public, max-age={settings.IMAGE_CACHE_MAX_AGE_SECONDS}",
            },
        )

    media_type = asset.content_type or "image/png"
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Type": media_type,
            "Content-Length": str(len(content)),
            "Cache-Control": f"public, max-age={settings.IMAGE_CACHE_MAX_AGE_SECONDS}",
            "ETag": etag,
            "X-Image-Source": "local-media-asset",
            "X-Asset-Key": asset_key,
        },
    )


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
