"""Creatures API endpoints."""
import logging
from pathlib import Path
import re
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.database import SessionLocal, get_db
from app.models import Creature as CreatureModel
from app.models.settings import SystemSettings as SettingsModel
from app.schemas import Creature, CreatureCreate, CreatureSimple
from app.services.creature_storage_service import get_cached_creature_by_id, get_cached_creature_by_name, list_cached_creatures, resolve_cached_creature
from app.services.creature_category_service import (
    CANONICAL_CREATURE_CATEGORIES,
    creature_category_expression,
    resolve_creature_category,
)
from app.services.entity_metadata_service import EntityMetadataService
from app.services import media_asset_service as media_svc
from app.api.v1.local_media import (
    LocalMediaDescriptor,
    build_local_media_file_response,
    resolve_local_media_descriptor,
)
from app.core.config import settings

router = APIRouter(prefix="/creatures", tags=["creatures"])
logger = logging.getLogger(__name__)
_CATEGORY_IMAGE_KEY_PREFIX = "cyclopedia_category_image_"
_CATEGORY_IMAGE_DIR = Path("backend/storage/category-images")


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


def _unavailable_creature_image(
    *,
    label: str,
    asset_key: str,
    include_placeholder: bool,
    status: str = "missing",
) -> Response:
    headers = {
        "Cache-Control": "public, max-age=300",
        "X-Image-Source": (
            "placeholder"
            if include_placeholder
            else "unavailable"
        ),
        "X-Image-Status": status,
        "X-Asset-Key": asset_key,
    }

    if not include_placeholder:
        raise HTTPException(
            status_code=404,
            detail="Creature image unavailable",
            headers=headers,
        )

    return Response(
        content=_placeholder_svg(label),
        media_type="image/svg+xml",
        headers=headers,
    )


def _normalize_category_key(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", (value or "").strip().lower()).strip("_")
    return normalized or "uncategorized"


_CANONICAL_CATEGORY_KEYS = {
    _normalize_category_key(category)
    for category in CANONICAL_CREATURE_CATEGORIES
}


def _get_category_images(db: Session) -> dict[str, str]:
    rows = (
        db.query(SettingsModel)
        .filter(SettingsModel.key.like(f"{_CATEGORY_IMAGE_KEY_PREFIX}%"), SettingsModel.is_active == True)
        .all()
    )
    mapping: dict[str, str] = {}
    for row in rows:
        key = row.key[len(_CATEGORY_IMAGE_KEY_PREFIX):]
        if (
            key in _CANONICAL_CATEGORY_KEYS
            and row.value
        ):
            mapping[key] = row.value
    return mapping


@router.get("/category-images")
async def get_cyclopedia_category_images(db: Session = Depends(get_db)):
    """Public mapping used by Cyclopedia category cards."""
    return _get_category_images(db)


@router.get("/category-images/file/{file_name}")
def get_cyclopedia_category_image_file(file_name: str):
    """Serve locally uploaded category image files."""
    safe_name = Path(file_name).name
    target = (_CATEGORY_IMAGE_DIR / safe_name).resolve()
    root = _CATEGORY_IMAGE_DIR.resolve()
    if not str(target).startswith(str(root)):
        raise HTTPException(status_code=400, detail="Invalid file path")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="Category image not found")
    return FileResponse(path=str(target))


@router.get("/category-previews")
async def get_creature_category_previews(
    response: Response,
    db: Session = Depends(get_db),
):
    """Return local creature candidates for GIF-first category cards."""
    creatures = (
        db.query(CreatureModel)
        .filter(
            CreatureModel.is_hidden == False,
            CreatureModel.is_boss == False,
        )
        .all()
    )

    ranked: dict[str, list[tuple[tuple, dict]]] = {}

    for creature in creatures:
        effective_category = resolve_creature_category(
            bestiary_class=creature.bestiary_class,
            creature_class=creature.creature_class,
            classification=creature.classification,
        )
        if effective_category is None:
            continue

        category_key = _normalize_category_key(
            effective_category
        )
        name_key = _normalize_category_key(creature.name or "")

        media_rank = (
            0
            if creature.image_asset_id is not None
            else 1
            if (
                creature.image_url_override
                or creature.image_url
            )
            else 2
        )

        exact_rank = 0 if name_key == category_key else 1

        score = (
            media_rank,
            exact_rank,
            -int(creature.experience or 0),
            len(creature.name or ""),
            (creature.name or "").lower(),
        )

        ranked.setdefault(category_key, []).append(
            (
                score,
                {
                    "id": creature.id,
                    "name": creature.name,
                    "slug": creature.slug,
                },
            )
        )

    result = {
        category_key: [
            payload
            for _, payload in sorted(
                candidates,
                key=lambda candidate: candidate[0],
            )[:6]
        ]
        for category_key, candidates in ranked.items()
    }

    response.headers["Cache-Control"] = (
        "public, max-age=3600, stale-while-revalidate=86400"
    )

    return result


@router.get("/category-counts")
async def get_creature_category_counts(
    response: Response,
    db: Session = Depends(get_db),
):
    """Return visible non-boss creature counts by canonical category."""
    category_expression = creature_category_expression()

    filters = (
        CreatureModel.is_hidden == False,
        CreatureModel.is_boss == False,
    )

    total = (
        db.query(func.count(CreatureModel.id))
        .filter(*filters)
        .scalar()
        or 0
    )

    rows = (
        db.query(
            category_expression.label("category"),
            func.count(CreatureModel.id),
        )
        .filter(*filters)
        .group_by(category_expression)
        .all()
    )

    result = {
        "all": int(total),
        **{
            _normalize_category_key(category): 0
            for category in CANONICAL_CREATURE_CATEGORIES
        },
    }

    for category, count in rows:
        if category is None:
            continue

        key = _normalize_category_key(category)

        if key in result:
            result[key] = int(count or 0)

    response.headers["Cache-Control"] = (
        "public, max-age=3600, stale-while-revalidate=86400"
    )

    return result


@router.get("/popular", response_model=List[CreatureSimple])
async def get_popular_creatures(
    response: Response,
    limit: int = Query(12, ge=1, le=30),
    db: Session = Depends(get_db),
):
    """Return non-boss creatures ordered by real search/view activity."""
    metadata = EntityMetadataService.get_popular(
        db,
        entity_type="creature",
        limit=min(limit * 4, 120),
    )

    creature_ids = [
        row.entity_id
        for row in metadata
        if row.entity_id is not None
    ]

    response.headers["Cache-Control"] = (
        "public, max-age=300, stale-while-revalidate=900"
    )

    if not creature_ids:
        return []

    rows = (
        db.query(CreatureModel)
        .filter(
            CreatureModel.id.in_(creature_ids),
            CreatureModel.is_hidden == False,
            CreatureModel.is_boss == False,
        )
        .all()
    )

    by_id = {
        creature.id: creature
        for creature in rows
    }

    return [
        by_id[creature_id]
        for creature_id in creature_ids
        if creature_id in by_id
    ][:limit]


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

    db_creature = CreatureModel(**creature.model_dump())
    db.add(db_creature)
    db.commit()
    db.refresh(db_creature)
    return db_creature


@router.get("/{creature_id}/image")
def get_creature_image(
    creature_id: int,
    request: Request,
    include_placeholder: bool = Query(True, alias="placeholder"),
):
    """Serve creature image from local MediaAsset cache (local-first)."""
    descriptor = _resolve_creature_media_descriptor(creature_id)

    if descriptor.status != "cached":
        return _unavailable_creature_image(
            label=descriptor.fallback_label,
            asset_key=descriptor.asset_key,
            include_placeholder=include_placeholder,
            status=descriptor.status,
        )

    response = build_local_media_file_response(
        request,
        descriptor,
        default_media_type="image/gif",
        cache_max_age_seconds=settings.IMAGE_CACHE_MAX_AGE_SECONDS,
        extra_headers={
            "X-Image-Source": "local-media-asset",
            "X-Image-Status": "cached",
            "X-Asset-Key": descriptor.asset_key,
        },
    )

    if response is None:
        return _unavailable_creature_image(
            label=descriptor.fallback_label,
            asset_key=descriptor.asset_key,
            include_placeholder=include_placeholder,
            status="missing",
        )

    return response


def _resolve_creature_media_descriptor(creature_id: int) -> LocalMediaDescriptor:
    """Resolve creature media metadata in a short-lived DB session."""

    def _resolver(db: Session) -> LocalMediaDescriptor:
        creature = get_cached_creature_by_id(db, creature_id)
        if not creature:
            raise HTTPException(status_code=404, detail="Creature not found in local cache")

        asset_key = media_svc.build_creature_asset_key(creature)
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
            fallback_label=creature.name or "Unknown Creature",
        )

    return resolve_local_media_descriptor(
        _resolver,
        session_factory=SessionLocal,
    )
