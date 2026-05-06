"""Creatures API endpoints."""
import hashlib
import logging
import asyncio
from pathlib import Path
from typing import List, Optional
from urllib.parse import unquote, urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models import Creature as CreatureModel
from app.models.settings import SystemSettings as SettingsModel
from app.models.external_data import CachedResource
from app.schemas import Creature, CreatureCreate, CreatureSimple
from app.services.bestiary_source import get_creature_detail_by_name
from app.services.creature_storage_service import get_cached_creature_by_id, get_cached_creature_by_name, list_cached_creatures, resolve_cached_creature, upsert_creature_payload
from app.services.entity_metadata_service import EntityMetadataService
from app.services.external_apis import get_creatures as get_external_creatures
from app.core.config import settings

router = APIRouter(prefix="/creatures", tags=["creatures"])
logger = logging.getLogger(__name__)
_IMAGE_CACHE_DIR = Path("backend/storage/cache/images")
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


def _resource_key(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()


def _ensure_cache_dir() -> None:
    _IMAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _read_cached_image(resource: CachedResource) -> Optional[bytes]:
    if not resource.local_path:
        return None
    path = Path(resource.local_path)
    if not path.exists():
        return None
    return path.read_bytes()


def _write_cached_image(*, key: str, content: bytes) -> str:
    _ensure_cache_dir()
    path = _IMAGE_CACHE_DIR / f"{key}.bin"
    path.write_bytes(content)
    return str(path)


async def _resolve_fandom_image_url(image_url: str) -> Optional[str]:
    if "/Special:FilePath/" not in image_url:
        return image_url

    parsed = urlparse(image_url)
    asset_name = unquote(parsed.path.rsplit("/", 1)[-1])
    if not asset_name:
        return None
    file_title = asset_name[0].upper() + asset_name[1:]

    async with httpx.AsyncClient(timeout=15.0, headers={"User-Agent": settings.TIBIAWIKI_USER_AGENT, "Accept": "application/json"}) as client:
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
    return list_cached_creatures(db, search=None, category=None, is_boss=None, skip=0, limit=limit, sort_by="name", sort_order="asc")


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
    )
    if cached:
        return cached

    if _is_external_detail_fallback_enabled(db):
        try:
            external_response = await asyncio.wait_for(
                get_external_creatures(expand=True),
                timeout=DETAIL_FALLBACK_TIMEOUT_SECONDS,
            )
            if external_response.success() and isinstance(external_response.data, list):
                bosses_payload = [
                    item for item in external_response.data
                    if bool(item.get("is_boss"))
                ]
                # Persist only the needed page window to avoid mass sync behavior.
                page_slice = bosses_payload[skip: skip + limit]
                for payload in page_slice:
                    upsert_creature_payload(db, payload)
                if page_slice:
                    db.commit()
                cached = list_cached_creatures(
                    db,
                    search=search,
                    category=None,
                    is_boss=True,
                    skip=skip,
                    limit=limit,
                    sort_by=safe_sort_by,
                    sort_order=safe_sort_order,
                )
                if cached:
                    return cached
        except Exception as exc:
            db.rollback()
            logger.warning("bosses_fallback_failed search=%s error=%s", search, exc)

    return []


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
        return cached

    if _is_external_detail_fallback_enabled(db):
        guessed_name = creature_identifier.replace("-", " ").replace("_", " ").strip()
        if guessed_name:
            try:
                payload = await asyncio.wait_for(
                    get_creature_detail_by_name(guessed_name),
                    timeout=DETAIL_FALLBACK_TIMEOUT_SECONDS,
                )
                upsert_creature_payload(db, payload)
                db.commit()
                cached = resolve_cached_creature(db, creature_identifier)
                if not cached and payload.get("name"):
                    cached = get_cached_creature_by_name(db, payload["name"])
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
                    response.headers["X-Data-Source"] = "external-fallback"
                    return cached
            except Exception as exc:
                db.rollback()
                logger.warning("creature_fallback_failed identifier=%s error=%s", creature_identifier, exc)

    raise HTTPException(status_code=404, detail="We couldn't find this creature.")


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
    """Proxy creature image as a complete buffered response to avoid HTTP/2 chunk issues."""
    try:
        creature = get_cached_creature_by_id(db, creature_id)
        if not creature:
            raise HTTPException(status_code=404, detail="Creature not found in local cache")
    except HTTPException:
        raise

    image_url = creature.image_url if hasattr(creature, "image_url") else creature.get("image_url")
    if not image_url:
        raise HTTPException(status_code=404, detail="Image not found")

    resource = (
        db.query(CachedResource)
        .filter(CachedResource.resource_type == "creature_image", CachedResource.entity_type == "creature", CachedResource.entity_id == creature_id)
        .first()
    )

    if resource:
        cached_content = _read_cached_image(resource)
        if cached_content:
            etag = resource.etag_hash or hashlib.sha1(cached_content).hexdigest()
            if request.headers.get("if-none-match") == etag:
                return Response(status_code=304, headers={
                    "ETag": etag,
                    "Cache-Control": f"public, max-age={settings.IMAGE_CACHE_MAX_AGE_SECONDS}",
                })
            media_type = resource.content_type or "image/gif"
            return Response(
                content=cached_content,
                media_type=media_type,
                headers={
                    "Content-Type": media_type,
                    "Content-Length": str(len(cached_content)),
                    "Cache-Control": f"public, max-age={settings.IMAGE_CACHE_MAX_AGE_SECONDS}",
                    "ETag": etag,
                    "X-Image-Source": "local-cache",
                },
            )

    if not _is_image_autofetch_enabled(db):
        raise HTTPException(status_code=404, detail="Image not cached locally")

    resolved_url = image_url
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, headers={
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
        cache_key = _resource_key(resolved_url)
        local_path = _write_cached_image(key=cache_key, content=content)

        if not resource:
            resource = CachedResource(
                resource_type="creature_image",
                entity_type="creature",
                entity_id=creature_id,
                source_url=image_url,
            )
            db.add(resource)
        resource.resolved_url = resolved_url
        resource.local_path = local_path
        resource.content_type = media_type
        resource.size_bytes = len(content)
        resource.etag_hash = etag
        resource.status = "ready"
        from datetime import datetime
        resource.last_fetched_at = datetime.utcnow()
        resource.error = None
        db.commit()

        headers = {
            "Content-Type": media_type,
            "Content-Length": str(len(content)),
            "Cache-Control": f"public, max-age={settings.IMAGE_CACHE_MAX_AGE_SECONDS}",
            "ETag": etag,
            "X-Image-Source": "external-fetch",
        }
        return Response(content=content, media_type=media_type, headers=headers)
    except Exception as exc:
        if resource:
            cached_content = _read_cached_image(resource)
            if cached_content:
                media_type = resource.content_type or "image/gif"
                return Response(content=cached_content, media_type=media_type, headers={
                    "Content-Type": media_type,
                    "Content-Length": str(len(cached_content)),
                    "Cache-Control": f"public, max-age={settings.IMAGE_CACHE_MAX_AGE_SECONDS}",
                    "ETag": resource.etag_hash or hashlib.sha1(cached_content).hexdigest(),
                    "X-Image-Source": "stale-cache",
                })
        raise HTTPException(status_code=404, detail="Image source unavailable") from exc
