"""Hunt Zones API endpoints."""
from collections import defaultdict
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import Request, Response
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import SessionLocal, get_db
from app.models import HuntZone as HuntZoneModel
from app.models.external_data import TibiaWikiLocation, TibiaWikiQuest
from app.models.user import User
from app.models.workspace_audit import WorkspaceAudit
from app.knowledge.models import KnowledgeEntity, KnowledgeEntityAlias
from app.schemas import (
    HuntZone,
    HuntZoneAccess,
    HuntZoneAccessQuest,
    HuntZoneCreate,
    HuntZoneList,
    HuntRecommendation,
)
from app.api.v1.local_media import (
    LocalMediaDescriptor,
    build_local_media_file_response,
    resolve_local_media_descriptor,
)
from app.services.entity_metadata_service import EntityMetadataService
from app.services.text_utils import normalize_search_text
from app.services.hunt_service import HuntRecommendationService
from app.services.hunt_zone_projection_service import HuntZoneProjectionService
from app.services import media_asset_service as media_svc
from app.api.v1.endpoints.auth import get_current_knowledge_editor

router = APIRouter(prefix="/hunt-zones", tags=["hunt-zones"])


def _canonical_zone_slug(zone: HuntZoneModel) -> str:
    return zone.slug or normalize_search_text(zone.name).replace(" ", "-")


def _unique_location_knowledge(db: Session, zones: list[HuntZoneModel]) -> dict[str, TibiaWikiLocation]:
    normalized_names = {zone.normalized_name or normalize_search_text(zone.name) for zone in zones}
    normalized_names.discard("")
    if not normalized_names:
        return {}
    rows = db.query(TibiaWikiLocation).filter(TibiaWikiLocation.normalized_name.in_(normalized_names)).all()
    grouped: dict[str, list[TibiaWikiLocation]] = defaultdict(list)
    for row in rows:
        grouped[row.normalized_name].append(row)
    return {name: matches[0] for name, matches in grouped.items() if len(matches) == 1}


def _access_quest_names(zone: HuntZoneModel, location: TibiaWikiLocation | None) -> list[str]:
    names: list[str] = []
    if zone.quest and zone.quest.name:
        names.append(zone.quest.name)
    metadata = location.provider_metadata if location and isinstance(location.provider_metadata, dict) else {}
    raw_names = metadata.get("access_quest_names") or []
    if isinstance(raw_names, list):
        names.extend(str(value or "").strip() for value in raw_names if str(value or "").strip())
    raw_zone_metadata = getattr(zone, "provider_metadata", None)
    zone_metadata = raw_zone_metadata if isinstance(raw_zone_metadata, dict) else {}
    zone_canonical = zone_metadata.get("canonical") if isinstance(zone_metadata.get("canonical"), dict) else {}
    zone_names = zone_canonical.get("access_quests") or []
    if isinstance(zone_names, list):
        names.extend(str(value or "").strip() for value in zone_names if str(value or "").strip())
    deduped: dict[str, str] = {}
    for name in names:
        normalized = normalize_search_text(name)
        if normalized and normalized not in deduped:
            deduped[normalized] = name
    return list(deduped.values())


def _canonical_quest_index(db: Session, quest_names: list[str]) -> dict[str, TibiaWikiQuest]:
    normalized_names = {normalize_search_text(name) for name in quest_names if normalize_search_text(name)}
    if not normalized_names:
        return {}
    rows = db.query(TibiaWikiQuest).filter(TibiaWikiQuest.normalized_name.in_(normalized_names)).all()
    grouped: dict[str, list[TibiaWikiQuest]] = defaultdict(list)
    for row in rows:
        if row.normalized_name:
            grouped[row.normalized_name].append(row)
    return {name: matches[0] for name, matches in grouped.items() if len(matches) == 1}


def _zone_access(zone: HuntZoneModel, location: TibiaWikiLocation | None, quest_index: dict[str, TibiaWikiQuest]) -> HuntZoneAccess:
    names = _access_quest_names(zone, location)
    quests: list[HuntZoneAccessQuest] = []
    quest_requires_premium = False
    for name in names:
        canonical = quest_index.get(normalize_search_text(name))
        if canonical and canonical.premium_required is True:
            quest_requires_premium = True
        quests.append(HuntZoneAccessQuest(id=canonical.id if canonical else None, name=name, slug=canonical.slug if canonical else None))

    # HuntZone.min_level is a recommendation field, not proof of an access gate.
    minimum_level = location.minimum_level if location else None
    maximum_level = location.maximum_level if location else None

    # Legacy False defaults are not evidence that Premium is not required.
    zone_supplied = set(getattr(zone, "supplied_fields", None) or [])
    if zone.requires_premium or quest_requires_premium:
        premium_required: bool | None = True
    elif "premium_required" in zone_supplied and zone.requires_premium is False:
        premium_required = False
    elif location is not None:
        premium_required = location.premium_required
    else:
        premium_required = None

    quest_required = (
        True if zone.requires_quest is True or quests
        else False if zone.requires_quest is False and "access_quests" in zone_supplied
        else None
    )
    raw_zone_metadata = getattr(zone, "provider_metadata", None)
    zone_metadata = raw_zone_metadata if isinstance(raw_zone_metadata, dict) else {}
    zone_canonical = zone_metadata.get("canonical") if isinstance(zone_metadata.get("canonical"), dict) else {}
    notes = location.access_notes if location else zone_canonical.get("access_notes")
    has_restriction = bool((minimum_level is not None and minimum_level > 0) or premium_required is True or quest_required is True)
    has_evidence = bool(minimum_level is not None or maximum_level is not None or premium_required is not None or quest_required is not None or notes)
    return HuntZoneAccess(
        status="restricted" if has_restriction else "documented" if has_evidence else "unknown",
        minimum_level=minimum_level,
        maximum_level=maximum_level,
        premium_required=premium_required,
        quest_required=quest_required,
        quests=quests,
        notes=notes,
        source_provider=location.source_name if location else zone.source_provider,
        source_url=location.source_url if location else zone.source_url,
    )


def _zone_details(db: Session, zones: list[HuntZoneModel], *, detail: bool = True) -> list[dict]:
    return HuntZoneProjectionService.project(db, zones, detail=detail)


def _zone_detail(db: Session, zone: HuntZoneModel) -> dict:
    return _zone_details(db, [zone])[0]


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


@router.get("/highlights", response_model=List[HuntZoneList])
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

        raw_zones = (
            db.query(HuntZoneModel)
            .filter(HuntZoneModel.id.in_(zone_ids))
            .all()
        )
        by_id = {zone.id: zone for zone in raw_zones}
        return _zone_details(
            db,
            [by_id[zone_id] for zone_id in zone_ids if zone_id in by_id],
            detail=False,
        )
    except Exception:
        return []


@router.get("/", response_model=List[HuntZoneList])
async def get_hunt_zones(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    min_level: Optional[int] = None,
    max_level: Optional[int] = None,
    city: Optional[str] = None,
    search: Optional[str] = None,
    canonical_only: bool = Query(False),
    db: Session = Depends(get_db)
):
    """Get list of hunt zones with optional filters"""
    query = db.query(HuntZoneModel)

    if canonical_only:
        query = query.join(
            KnowledgeEntity,
            KnowledgeEntity.uuid == HuntZoneModel.knowledge_entity_id,
        ).filter(
            KnowledgeEntity.entity_type == "hunt_zone",
            KnowledgeEntity.status == "active",
            KnowledgeEntity.visibility == "public",
        )
    
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
        alias_entities = select(KnowledgeEntityAlias.entity_uuid).where(
            KnowledgeEntityAlias.entity_type == "hunt_zone",
            KnowledgeEntityAlias.normalized_alias == normalized_search,
        )
        query = query.filter(
            (HuntZoneModel.name.ilike(f"%{search}%")) |
            (HuntZoneModel.city.ilike(f"%{search}%")) |
            (HuntZoneModel.normalized_name.contains(normalized_search)) |
            (HuntZoneModel.knowledge_entity_id.in_(alias_entities))
        )
    
    zones = query.order_by(HuntZoneModel.name).offset(skip).limit(limit).all()
    if search:
        EntityMetadataService.record_searches(
            db,
            entity_type="hunt_zone",
            matches=[(zone.normalized_name or zone.name, zone.name, zone.id) for zone in zones[: min(len(zones), 5)]],
        )
        db.commit()
    return _zone_details(db, zones, detail=False)


@router.get("/{zone_identifier}", response_model=HuntZone)
async def get_hunt_zone(
    zone_identifier: str,
    response: Response,
    db: Session = Depends(get_db),
):
    """Get detailed information about a specific hunt zone"""
    query = db.query(HuntZoneModel)
    if zone_identifier.isdigit():
        query = query.filter(HuntZoneModel.id == int(zone_identifier))
    else:
        normalized = normalize_search_text(zone_identifier.replace("-", " ").replace("_", " "))
        alias_entities = select(KnowledgeEntityAlias.entity_uuid).where(
            KnowledgeEntityAlias.entity_type == "hunt_zone",
            KnowledgeEntityAlias.normalized_alias == normalized,
        )
        query = query.filter(or_(
            HuntZoneModel.slug == zone_identifier,
            HuntZoneModel.normalized_name == normalized,
            HuntZoneModel.knowledge_entity_id.in_(alias_entities),
        ))
    # A provider-backed bridge and its retained legacy free-text row may share
    # a display name. Stable numeric compatibility lookups remain exact; name
    # and slug discovery prefer the canonical provider row without deleting or
    # mutating the legacy evidence.
    if not zone_identifier.isdigit():
        query = query.order_by(
            HuntZoneModel.knowledge_entity_id.is_(None),
            HuntZoneModel.id,
        )
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
    db_zone = HuntZoneModel(**zone.model_dump(exclude={
        "quest_name", "quest_slug", "vocation_recommendations", "canonical_id",
        "missing_fields", "data_sources", "spatial",
    }))
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
    
    return _zone_detail(db, db_zone)
