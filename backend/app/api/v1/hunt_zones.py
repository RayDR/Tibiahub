"""Hunt Zones API endpoints."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import Request, Response
from sqlalchemy import or_
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.db.database import SessionLocal, get_db
from app.models.spawn_location import SpawnLocation
from app.models import HuntZone as HuntZoneModel
from app.models.external_data import TibiaWikiQuest
from app.models.user import User
from app.models.workspace_audit import WorkspaceAudit
from app.schemas import HuntZone, HuntZoneCreate, HuntRecommendation
from app.api.v1.local_media import (
    LocalMediaDescriptor,
    build_local_media_file_response,
    resolve_local_media_descriptor,
)
from app.services.entity_metadata_service import EntityMetadataService
from app.services.text_utils import normalize_search_text
from app.services.hunt_service import HuntRecommendationService
from app.services import media_asset_service as media_svc
from app.api.v1.endpoints.auth import get_current_knowledge_editor

router = APIRouter(prefix="/hunt-zones", tags=["hunt-zones"])


def _canonical_zone_slug(zone: HuntZoneModel) -> str:
    return zone.slug or normalize_search_text(zone.name).replace(" ", "-")


def _zone_detail(db: Session, zone: HuntZoneModel) -> dict:
    canonical_quest = None
    if zone.quest and zone.quest.name:
        canonical_quest = db.query(TibiaWikiQuest).filter(
            TibiaWikiQuest.normalized_name == normalize_search_text(zone.quest.name)
        ).first()
    return {
        **HuntZone.model_validate(zone).model_dump(),
        "slug": _canonical_zone_slug(zone),
        "quest_id": canonical_quest.id if canonical_quest else None,
        "quest_name": zone.quest.name if zone.quest else None,
        "quest_slug": canonical_quest.slug if canonical_quest else None,
    }


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


@router.get("/{zone_identifier}", response_model=HuntZone)
async def get_hunt_zone(
    zone_identifier: str,
    response: Response,
    db: Session = Depends(get_db),
):
    """Get detailed information about a specific hunt zone"""
    query = db.query(HuntZoneModel).options(
        selectinload(HuntZoneModel.creature_spawns).selectinload(SpawnLocation.creature),
        selectinload(HuntZoneModel.quest),
    )
    if zone_identifier.isdigit():
        query = query.filter(HuntZoneModel.id == int(zone_identifier))
    else:
        normalized = normalize_search_text(zone_identifier.replace("-", " ").replace("_", " "))
        query = query.filter(or_(
            HuntZoneModel.slug == zone_identifier,
            HuntZoneModel.normalized_name == normalized,
        ))
    zone = query.first()
    
    if not zone:
        raise HTTPException(status_code=404, detail="Hunt zone not found")

    EntityMetadataService.record_searches(
        db,
        entity_type="hunt_zone",
        matches=[(zone.normalized_name or zone.name, zone.name, zone.id)],
    )
    db.commit()
    response.headers["X-Canonical-Slug"] = _canonical_zone_slug(zone)
    return _zone_detail(db, zone)


@router.get("/{zone_id}/map-image")
def get_hunt_zone_map_image(
    zone_id: int,
    request: Request,
    include_placeholder: bool = Query(True, alias="placeholder"),
):
    """Serve hunt-zone map image from local MediaAsset cache (local-first)."""
    descriptor = _resolve_hunt_zone_media_descriptor(zone_id)

    if descriptor.status != "cached":
        if not include_placeholder:
            raise HTTPException(
                status_code=404,
                detail="Hunt-zone map unavailable",
                headers={
                    "X-Image-Source": "unavailable",
                    "X-Image-Status": descriptor.status,
                    "X-Asset-Key": descriptor.asset_key,
                },
            )
        placeholder = _placeholder_map_svg(descriptor.fallback_label)
        return Response(
            content=placeholder,
            media_type="image/svg+xml",
            headers={
                "Cache-Control": "public, max-age=3600",
                "X-Image-Source": "placeholder",
                "X-Image-Status": descriptor.status,
                "X-Asset-Key": descriptor.asset_key,
            },
        )

    response = build_local_media_file_response(
        request,
        descriptor,
        default_media_type="image/png",
        cache_max_age_seconds=settings.IMAGE_CACHE_MAX_AGE_SECONDS,
        extra_headers={
            "X-Image-Source": "local-media-asset",
            "X-Image-Status": "cached",
            "X-Asset-Key": descriptor.asset_key,
        },
    )

    if response is None:
        if not include_placeholder:
            raise HTTPException(
                status_code=404,
                detail="Hunt-zone map unavailable",
                headers={
                    "X-Image-Source": "unavailable",
                    "X-Image-Status": "missing",
                    "X-Asset-Key": descriptor.asset_key,
                },
            )
        placeholder = _placeholder_map_svg(descriptor.fallback_label)
        return Response(
            content=placeholder,
            media_type="image/svg+xml",
            headers={
                "Cache-Control": "public, max-age=3600",
                "X-Image-Source": "placeholder",
                "X-Image-Status": "missing",
                "X-Asset-Key": descriptor.asset_key,
            },
        )

    return response


def _resolve_hunt_zone_media_descriptor(zone_id: int) -> LocalMediaDescriptor:
    """Resolve hunt-zone map media metadata in a short-lived DB session."""

    def _resolver(db: Session) -> LocalMediaDescriptor:
        zone = db.query(HuntZoneModel).filter(HuntZoneModel.id == zone_id).first()
        if not zone:
            raise HTTPException(status_code=404, detail="Hunt zone not found")

        asset_key = media_svc.build_zone_asset_key(zone)
        # Public requests must never perform provider downloads.
        # Missing assets are populated exclusively by sync/admin workers.
        asset = media_svc.get_asset(db, asset_key)

        return LocalMediaDescriptor(
            local_path=(str(asset.local_path) if asset and asset.local_path else None),
            content_type=(asset.content_type if asset else None),
            size_bytes=(asset.size_bytes if asset else None),
            asset_hash=(asset.sha256_hash if asset else None),
            asset_key=asset_key,
            status=(getattr(asset, "status", "missing") if asset else "missing"),
            fallback_label=zone.name or "Unknown Zone",
        )

    return resolve_local_media_descriptor(
        _resolver,
        session_factory=SessionLocal,
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
    db: Session = Depends(get_db),
    editor: User = Depends(get_current_knowledge_editor),
):
    """Create a new hunt zone"""
    existing = db.query(HuntZoneModel).filter(
        HuntZoneModel.name == zone.name
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Hunt zone already exists")
    
    # ``quest_name`` is a response/display convenience; the persisted relation
    # is ``quest_id`` and is intentionally managed by knowledge workflows.
    db_zone = HuntZoneModel(**zone.model_dump(exclude={"quest_name", "quest_slug"}))
    db.add(db_zone)
    db.flush()
    db.add(WorkspaceAudit(
        actor_id=editor.id,
        workspace_type="knowledge_editor",
        action="knowledge_hunt_zone_created",
        target_type="hunt_zone",
        target_id=str(db_zone.id),
        assisted=False,
        safe_metadata={"name": db_zone.name},
    ))
    db.commit()
    db.refresh(db_zone)
    
    return db_zone
