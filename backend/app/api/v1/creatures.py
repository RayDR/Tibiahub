"""Creatures API endpoints."""
import hashlib
import logging
from pathlib import Path
import re
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models import Creature as CreatureModel
from app.models.settings import SystemSettings as SettingsModel
from app.schemas import Creature, CreatureCreate, CreatureSimple
from app.services.creature_storage_service import get_cached_creature_by_id, get_cached_creature_by_name, list_cached_creatures, resolve_cached_creature
from app.services.entity_metadata_service import EntityMetadataService
from app.services import media_asset_service as media_svc
from app.core.config import settings

router = APIRouter(prefix="/creatures", tags=["creatures"])
logger = logging.getLogger(__name__)
_CATEGORY_IMAGE_KEY_PREFIX = "cyclopedia_category_image_"
_CATEGORY_IMAGE_DIR = Path("backend/storage/category-images")


def _get_setting(db: Session, key: str, default: str = "") -> str:
    value = db.query(SettingsModel).filter(SettingsModel.key == key).first()
    return value.value if value and value.value is not None else default


def _is_image_autofetch_enabled(db: Session) -> bool:
    return _get_setting(db, "auto_fetch_missing_images_enabled", "0") == "1"


def _placeholder_svg(label: str) -> bytes:
    safe = media_svc.escape_svg_text(label or "Unknown", limit=42)
    return (
        "<svg xmlns='http://www.w3.org/2000/svg' width='320' height='320' viewBox='0 0 320 320'>"
        "<defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'>"
        "<stop offset='0%' stop-color='#0f172a'/><stop offset='100%' stop-color='#1e293b'/></linearGradient></defs>"
        "<rect width='320' height='320' fill='url(#g)'/>"
        "<circle cx='160' cy='118' r='48' fill='#334155'/><rect x='84' y='188' width='152' height='16' rx='8' fill='#475569'/>"
        f"<text x='160' y='278' text-anchor='middle' fill='#cbd5e1' font-size='14' font-family='Arial, sans-serif'>{safe}</text>"
        "</svg>"
    ).encode("utf-8")


def _normalize_category_key(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", (value or "").strip().lower()).strip("_")
    return normalized or "uncategorized"


def _get_category_images(db: Session) -> dict[str, str]:
    rows = (
        db.query(SettingsModel)
        .filter(SettingsModel.key.like(f"{_CATEGORY_IMAGE_KEY_PREFIX}%"), SettingsModel.is_active == True)
        .all()
    )
    mapping: dict[str, str] = {}
    for row in rows:
        key = row.key[len(_CATEGORY_IMAGE_KEY_PREFIX):]
        if key and row.value:
            mapping[key] = row.value
    return mapping


@router.get("/category-images")
async def get_cyclopedia_category_images(db: Session = Depends(get_db)):
    """Public mapping used by Cyclopedia category cards."""
    return _get_category_images(db)


@router.get("/category-images/file/{file_name}")
async def get_cyclopedia_category_image_file(file_name: str):
    """Serve locally uploaded category image files."""
    safe_name = Path(file_name).name
    target = (_CATEGORY_IMAGE_DIR / safe_name).resolve()
    root = _CATEGORY_IMAGE_DIR.resolve()
    if not str(target).startswith(str(root)):
        raise HTTPException(status_code=400, detail="Invalid file path")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="Category image not found")
    return FileResponse(path=str(target))


@router.get("/highlights", response_model=List[CreatureSimple])
async def get_creature_highlights(
    limit: int = Query(18, ge=1, le=50),
    db: Session = Depends(get_db),
):
    try:
        metadata = EntityMetadataService.get_highlights(db, entity_type="creature", limit=limit)
        creature_ids = [record.entity_id for record in metadata if record.entity_id is not None]
        if creature_ids:
            raw_creatures = db.query(CreatureModel).filter(CreatureModel.id.in_(creature_ids)).all()
            by_id = {creature.id: creature for creature in raw_creatures}
            creatures = [by_id[creature_id] for creature_id in creature_ids if creature_id in by_id]
            if creatures:
                return creatures
        return list_cached_creatures(db, search=None, category=None, is_boss=None, skip=0, limit=limit, sort_by="name", sort_order="asc")
    except Exception:
        return []


@router.get("/", response_model=List[CreatureSimple])
async def get_creatures(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    search: Optional[str] = None,
    category: Optional[str] = None,
    is_boss: Optional[bool] = Query(None),
    difficulty: Optional[str] = None,
    sort_by: str = Query("name", pattern="^(name|experience|hitpoints|difficulty)$"),
    sort_order: str = Query("asc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
):
    """Get list of creatures with optional filters"""
    safe_sort_by = sort_by if sort_by in {"name", "experience", "hitpoints", "difficulty"} else "name"
    safe_sort_order = "desc" if sort_order == "desc" else "asc"

    try:
        cached_items = list_cached_creatures(
            db,
            search=search,
            category=category,
            is_boss=is_boss,
            skip=skip,
            limit=limit,
            sort_by=safe_sort_by,
            sort_order=safe_sort_order,
            include_hidden=False,
        )
        if search and cached_items:
            EntityMetadataService.record_searches(
                db,
                entity_type="creature",
                matches=[
                    (item.normalized_name or item.name, item.name, item.id)
                    for item in cached_items[: min(len(cached_items), 5)]
                ],
            )
            db.commit()
        return cached_items
    except Exception as exc:
        db.rollback()
        logger.exception("creatures_search_failed search=%s error=%s", search, exc)
        return []


@router.get("/bosses", response_model=List[CreatureSimple])
async def get_bosses(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    search: Optional[str] = None,
    sort_by: str = Query("name", pattern="^(name|experience|hitpoints|difficulty)$"),
    sort_order: str = Query("asc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
):
    safe_sort_by = sort_by if sort_by in {"name", "experience", "hitpoints", "difficulty"} else "name"
    safe_sort_order = "desc" if sort_order == "desc" else "asc"
    cached = list_cached_creatures(
        db,
        search=search,
        category=None,
        is_boss=True,
        skip=skip,
        limit=limit,
        sort_by=safe_sort_by,
        sort_order=safe_sort_order,
        include_hidden=False,
    )
    return cached


@router.get("/{creature_identifier}", response_model=Creature)
async def get_creature(creature_identifier: str, response: Response, db: Session = Depends(get_db)):
    """Get detailed information about a creature by slug or legacy numeric id."""
    cached = resolve_cached_creature(db, creature_identifier)

    if cached:
        EntityMetadataService.record_searches(
            db,
            entity_type="creature",
            matches=[(cached.normalized_name or cached.name, cached.name, cached.id)],
        )
        db.commit()
        canonical_slug = cached.slug or ""
        if canonical_slug:
            response.headers["X-Canonical-Slug"] = canonical_slug
        response.headers["X-Data-Status"] = "partial" if not cached.loot_items else "complete"
        if cached.last_synced_at:
            response.headers["X-Last-Synced-At"] = cached.last_synced_at.isoformat()
        return cached

    raise HTTPException(status_code=404, detail="We couldn't find this creature.")


@router.get("/name/{creature_name}", response_model=Creature)
async def get_creature_by_name(creature_name: str, db: Session = Depends(get_db)):
    """Get detailed information about a creature by name"""
    cached = get_cached_creature_by_name(db, creature_name)
    if cached:
        EntityMetadataService.record_searches(
            db,
            entity_type="creature",
            matches=[(cached.normalized_name or cached.name, cached.name, cached.id)],
        )
        db.commit()
        return cached
    raise HTTPException(
        status_code=404,
        detail="We couldn't find this creature.",
    )


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
    """Serve creature image from local MediaAsset cache (local-first)."""
    creature = get_cached_creature_by_id(db, creature_id)
    if not creature:
        raise HTTPException(status_code=404, detail="Creature not found in local cache")

    asset_key = media_svc.build_creature_asset_key(creature)
    source_url = media_svc.build_creature_source_url(creature)
    if not source_url:
        placeholder = _placeholder_svg(creature.name)
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
        placeholder = _placeholder_svg(creature.name)
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
        placeholder = _placeholder_svg(creature.name)
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
        return Response(status_code=304, headers={
            "ETag": etag,
            "Cache-Control": f"public, max-age={settings.IMAGE_CACHE_MAX_AGE_SECONDS}",
        })

    media_type = asset.content_type or "image/gif"
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
