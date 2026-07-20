"""MediaAsset service — deduplicating local media cache."""
import hashlib
import io
import ipaddress
import logging
import re
import socket
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import unquote, urlparse

import httpx
from PIL import Image, UnidentifiedImageError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.media_asset import MediaAsset

logger = logging.getLogger(__name__)

_MEDIA_DIR = Path("backend/storage/media")
# Don't retry a failed asset for this many seconds (avoid hammering external hosts)
_RETRY_COOLDOWN_SECONDS = 3600
_MAX_IMAGE_BYTES = 5 * 1024 * 1024
_MAX_IMAGE_PIXELS = 16_000_000
_ALLOWED_CONTENT_TYPES = {
    "image/png": ("PNG", ".png"),
    "image/jpeg": ("JPEG", ".jpg"),
    "image/webp": ("WEBP", ".webp"),
}
_MAX_REDIRECTS = 4


class UnsafeMediaError(ValueError):
    """A media source or payload failed a user-safe validation check."""


def escape_svg_text(value: str, *, limit: int) -> str:
    """XML-escape dynamic text before inserting it into an SVG text node."""
    from xml.sax.saxutils import escape

    return escape((value or "")[:limit], {"\"": "&quot;", "'": "&apos;"})


def validate_raster_image(content: bytes, declared_content_type: str | None = None) -> tuple[str, str]:
    """Validate size, declared MIME type, and decoded raster format."""
    if not content:
        raise UnsafeMediaError("The image is empty")
    if len(content) > _MAX_IMAGE_BYTES:
        raise UnsafeMediaError("The image exceeds the maximum allowed size")

    declared = (declared_content_type or "").split(";", 1)[0].strip().lower()
    if declared and declared not in _ALLOWED_CONTENT_TYPES:
        raise UnsafeMediaError("Unsupported image content type")
    try:
        with Image.open(io.BytesIO(content)) as image:
            if image.width * image.height > _MAX_IMAGE_PIXELS:
                raise UnsafeMediaError("The image dimensions are too large")
            image.verify()
            actual_format = (image.format or "").upper()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise UnsafeMediaError("Invalid image data") from exc

    matching = next(
        ((mime, extension) for mime, (fmt, extension) in _ALLOWED_CONTENT_TYPES.items() if fmt == actual_format),
        None,
    )
    if not matching:
        raise UnsafeMediaError("Unsupported image format")
    actual_mime, extension = matching
    if declared and declared != actual_mime:
        raise UnsafeMediaError("Image content type does not match its data")
    return actual_mime, extension


def validate_remote_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise UnsafeMediaError("Only public HTTP and HTTPS image URLs are allowed")
    if parsed.username or parsed.password:
        raise UnsafeMediaError("Authenticated image URLs are not allowed")
    try:
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UnsafeMediaError("The image host could not be resolved") from exc
    if not addresses:
        raise UnsafeMediaError("The image host could not be resolved")
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global:
            raise UnsafeMediaError("The image host is not publicly reachable")


def _validate_connected_peer(response: httpx.Response) -> None:
    """Reject DNS rebinding by checking the address of the established socket."""
    stream = response.extensions.get("network_stream")
    peer = stream.get_extra_info("server_addr") if stream else None
    if not peer:
        raise UnsafeMediaError("The image connection could not be verified")
    try:
        ip = ipaddress.ip_address(peer[0])
    except (ValueError, TypeError, IndexError) as exc:
        raise UnsafeMediaError("The image connection could not be verified") from exc
    if not ip.is_global:
        raise UnsafeMediaError("The image host is not publicly reachable")


# ── key / URL builders ────────────────────────────────────────────────────────

def _normalize_key_part(name: str) -> str:
    """Lowercase name, strip image extension, replace non-alphanum with _."""
    name = name.strip().lower()
    for ext in (".gif", ".png", ".jpg", ".jpeg", ".webp"):
        if name.endswith(ext):
            name = name[: -len(ext)]
            break
    return re.sub(r"[^a-z0-9]+", "_", name).strip("_")


def build_creature_asset_key(creature) -> str:
    alias = (getattr(creature, "image_alias", None) or "").strip()
    if alias:
        return f"creature:{_normalize_key_part(alias)}"
    return f"creature:{_normalize_key_part(creature.name)}"


def build_creature_source_url(creature) -> Optional[str]:
    """Priority: image_url_override → alias → image_url."""
    override = (getattr(creature, "image_url_override", None) or "").strip()
    if override:
        return override
    alias = (getattr(creature, "image_alias", None) or "").strip()
    if alias:
        safe = alias.replace(" ", "_")
        if not safe.lower().endswith((".gif", ".png", ".jpg", ".jpeg", ".webp")):
            safe = f"{safe}.gif"
        return f"{settings.TIBIAWIKI_BASE_PAGE_URL}/Special:FilePath/{safe}"
    return (getattr(creature, "image_url", None) or None)


def build_loot_asset_key(loot) -> str:
    alias = (getattr(loot, "item_image_alias", None) or "").strip()
    if alias:
        return f"item:{_normalize_key_part(alias)}"
    return f"item:{_normalize_key_part(loot.item_name)}"


def build_loot_source_url(loot) -> Optional[str]:
    override = (getattr(loot, "item_image_url_override", None) or "").strip()
    if override:
        return override
    alias = (getattr(loot, "item_image_alias", None) or "").strip()
    if alias:
        safe = alias.replace(" ", "_")
        if not safe.lower().endswith((".gif", ".png", ".jpg", ".jpeg", ".webp")):
            safe = f"{safe}.gif"
        return f"{settings.TIBIAWIKI_BASE_PAGE_URL}/Special:FilePath/{safe}"
    url = (getattr(loot, "item_image_url", None) or "").strip()
    if url:
        return url
    # fallback: build Special:FilePath from item name
    safe_name = loot.item_name.replace(" ", "_")
    return f"{settings.TIBIAWIKI_BASE_PAGE_URL}/Special:FilePath/{safe_name}.gif"


def build_zone_asset_key(zone) -> str:
    return f"zone:{_normalize_key_part(zone.name)}"


def build_zone_source_url(zone) -> Optional[str]:
    return (getattr(zone, "map_image_url", None) or None)


# ── internal fetch helpers ────────────────────────────────────────────────────

async def _resolve_wiki_special_path(url: str, client: httpx.AsyncClient) -> Optional[str]:
    """Use the MediaWiki API to turn Special:FilePath into a direct CDN URL."""
    parsed = urlparse(url)
    asset_name = unquote(parsed.path.rsplit("/", 1)[-1])
    if not asset_name:
        return None
    file_title = asset_name[0].upper() + asset_name[1:]
    try:
        resp = await client.get(
            settings.TIBIAWIKI_API_URL,
            params={
                "action": "query",
                "titles": f"File:{file_title}",
                "prop": "imageinfo",
                "iiprop": "url",
                "format": "json",
            },
        )
        resp.raise_for_status()
        pages = ((resp.json() or {}).get("query") or {}).get("pages") or {}
        for page in pages.values():
            info = (page.get("imageinfo") or [])
            if info and info[0].get("url"):
                return info[0]["url"]
    except Exception:
        pass
    return None


async def _fetch_image(source_url: str) -> tuple[bytes, str, str]:
    """Fetch image bytes. Resolves Special:FilePath via wiki API if needed.
    Returns (content_bytes, content_type, resolved_url).
    Raises httpx.HTTPStatusError or httpx.RequestError on failure.
    """
    headers = {
        "User-Agent": settings.TIBIAWIKI_USER_AGENT,
        "Referer": settings.TIBIAWIKI_BASE_PAGE_URL,
    }
    timeout = httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0)
    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=False,
        headers=headers,
    ) as client:
        current_url = source_url
        for _ in range(_MAX_REDIRECTS + 1):
            validate_remote_url(current_url)
            async with client.stream("GET", current_url) as resp:
                _validate_connected_peer(resp)
                if resp.is_redirect:
                    location = resp.headers.get("location")
                    if not location:
                        raise UnsafeMediaError("Invalid image redirect")
                    current_url = str(resp.url.join(location))
                    continue
                resp.raise_for_status()
                declared_type = resp.headers.get("content-type")
                declared_length = resp.headers.get("content-length")
                if declared_length and int(declared_length) > _MAX_IMAGE_BYTES:
                    raise UnsafeMediaError("The image exceeds the maximum allowed size")
                chunks: list[bytes] = []
                total = 0
                async for chunk in resp.aiter_bytes():
                    total += len(chunk)
                    if total > _MAX_IMAGE_BYTES:
                        raise UnsafeMediaError("The image exceeds the maximum allowed size")
                    chunks.append(chunk)
                content = b"".join(chunks)
                content_type, _ = validate_raster_image(content, declared_type)
                return content, content_type, str(resp.url)
        raise UnsafeMediaError("Too many image redirects")


# ── public API ────────────────────────────────────────────────────────────────

def get_asset(db: Session, asset_key: str) -> Optional[MediaAsset]:
    """Return MediaAsset by key if already in DB (no fetch)."""
    return db.query(MediaAsset).filter(MediaAsset.asset_key == asset_key).first()


def clear_asset(db: Session, *, asset_key: str) -> bool:
    """Delete local cached file and remove MediaAsset row for the given key."""
    asset = db.query(MediaAsset).filter(MediaAsset.asset_key == asset_key).first()
    if not asset:
        return False
    try:
        if asset.local_path:
            path = Path(asset.local_path)
            if path.exists() and path.is_file():
                path.unlink(missing_ok=True)
        db.delete(asset)
        db.commit()
        return True
    except Exception:
        db.rollback()
        return False


async def get_or_fetch_asset(
    db: Session,
    *,
    asset_key: str,
    source_url: str,
    autofetch_enabled: bool = False,
    force_refetch: bool = False,
) -> Optional[MediaAsset]:
    """
    Return a cached MediaAsset if available locally.
    If not cached and (autofetch_enabled or force_refetch), attempt to fetch.
    Returns the asset (may have status='failed') or None.
    """
    asset = db.query(MediaAsset).filter(MediaAsset.asset_key == asset_key).first()

    # Serve from local cache immediately if ready
    if asset and asset.status == "cached" and asset.file_exists():
        return asset

    # Respect retry cooldown for failed assets
    if asset and asset.status == "failed" and not force_refetch:
        if asset.last_fetched_at:
            age = (datetime.utcnow() - asset.last_fetched_at.replace(tzinfo=None)).total_seconds()
            if age < _RETRY_COOLDOWN_SECONDS:
                return asset  # caller should serve placeholder

    if not autofetch_enabled and not force_refetch:
        return asset  # None or stale asset

    # ── attempt fetch ────────────────────────────────────────────────────────
    if not asset:
        asset = MediaAsset(asset_key=asset_key, source_url=source_url, status="pending")
        db.add(asset)
        db.flush()

    try:
        content, content_type, resolved_url = await _fetch_image(source_url)
        _, ext = validate_raster_image(content, content_type)
        safe_key = re.sub(r"[^a-z0-9_]", "_", asset_key).strip("_")
        _MEDIA_DIR.mkdir(parents=True, exist_ok=True)
        local_path = _MEDIA_DIR / f"{safe_key}{ext}"
        local_path.write_bytes(content)

        asset.resolved_url = resolved_url
        asset.local_path = str(local_path)
        asset.content_type = content_type
        asset.size_bytes = len(content)
        asset.sha256_hash = hashlib.sha256(content).hexdigest()
        asset.status = "cached"
        asset.last_fetched_at = datetime.utcnow()
        asset.error_message = None
        db.commit()
        logger.info("media_asset_cached key=%s path=%s size=%d", asset_key, local_path, len(content))
    except Exception as exc:
        db.rollback()
        # Re-query after rollback; asset may or may not exist now
        asset = db.query(MediaAsset).filter(MediaAsset.asset_key == asset_key).first()
        if not asset:
            asset = MediaAsset(asset_key=asset_key, source_url=source_url)
            db.add(asset)
        asset.status = "failed"
        asset.error_message = "Image download failed validation" if isinstance(exc, UnsafeMediaError) else "Image download failed"
        asset.last_fetched_at = datetime.utcnow()
        try:
            db.commit()
        except Exception:
            db.rollback()
        logger.warning("media_asset_fetch_failed key=%s error=%s", asset_key, exc)

    return asset


async def refresh_asset(
    db: Session,
    *,
    asset_key: str,
    source_url: str,
) -> Optional[MediaAsset]:
    """Force-refetch an asset regardless of cooldown or current status."""
    return await get_or_fetch_asset(
        db,
        asset_key=asset_key,
        source_url=source_url,
        autofetch_enabled=True,
        force_refetch=True,
    )
