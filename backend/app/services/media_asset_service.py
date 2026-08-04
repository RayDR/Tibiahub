"""MediaAsset service — deduplicating local media cache."""
import asyncio
import hashlib
import io
import ipaddress
import logging
import os
import re
import socket
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Optional
from urllib.parse import unquote, urlparse

import httpx
from PIL import Image, UnidentifiedImageError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.media_asset import MediaAsset
from app.services.sync_error_service import SAFE_MESSAGES, classify_exception, sanitize_url

logger = logging.getLogger(__name__)

_MEDIA_DIR = Path("backend/storage/media")
# Don't retry a failed asset for this many seconds (avoid hammering external hosts)
_RETRY_COOLDOWN_SECONDS = 3600
_MAX_IMAGE_BYTES = 5 * 1024 * 1024
_MAX_IMAGE_PIXELS = 16_000_000
_ALLOWED_CONTENT_TYPES = {
    "image/gif": ("GIF", ".gif"),
    "image/png": ("PNG", ".png"),
    "image/jpeg": ("JPEG", ".jpg"),
    "image/webp": ("WEBP", ".webp"),
}
_MAX_REDIRECTS = 4
_ALLOWED_MEDIA_HOSTS = frozenset({
    "tibia.fandom.com", "static.wikia.nocookie.net", "tibiamaps.github.io",
})
_MAX_FETCH_ATTEMPTS = 3


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
    # Decoders commonly tolerate arbitrary bytes after a valid image. Reject
    # those payloads so an executable/script cannot be smuggled as a raster.
    if actual_format == "PNG":
        marker = content.rfind(b"\x00\x00\x00\x00IEND\xaeB`\x82")
        logical_size = marker + 12 if marker >= 0 else -1
    elif actual_format == "JPEG":
        marker = content.rfind(b"\xff\xd9")
        logical_size = marker + 2 if marker >= 0 else -1
    elif actual_format == "GIF":
        marker = content.rfind(b"\x3b")
        logical_size = marker + 1 if marker >= 0 else -1
    else:  # WebP RIFF length includes bytes after the first eight-byte header.
        logical_size = int.from_bytes(content[4:8], "little") + 8 if len(content) >= 12 and content[:4] == b"RIFF" else -1
    if logical_size != len(content):
        raise UnsafeMediaError("Image contains unsupported trailing data")
    if declared and declared != actual_mime:
        raise UnsafeMediaError("Image content type does not match its data")
    return actual_mime, extension


def validate_remote_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise UnsafeMediaError("Only allowlisted HTTPS image URLs are allowed")
    if parsed.username or parsed.password:
        raise UnsafeMediaError("Authenticated image URLs are not allowed")
    if parsed.hostname.lower() not in _ALLOWED_MEDIA_HOSTS:
        raise UnsafeMediaError("The image provider host is not allowed")
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
    """Priority: explicit override → stored provider URL → alias fallback."""
    override = (
        getattr(creature, "image_url_override", None) or ""
    ).strip()
    if override:
        return override

    # The provider URL was obtained while synchronizing the creature page and
    # is more reliable than reconstructing a case-sensitive MediaWiki title.
    stored_url = (
        getattr(creature, "image_url", None) or ""
    ).strip()
    if stored_url:
        return stored_url

    alias = (
        getattr(creature, "image_alias", None) or ""
    ).strip()
    if alias:
        safe = alias.replace(" ", "_")
        if not safe.lower().endswith(
            (".gif", ".png", ".jpg", ".jpeg", ".webp")
        ):
            safe = f"{safe}.gif"

        return (
            f"{settings.TIBIAWIKI_BASE_PAGE_URL}"
            f"/Special:FilePath/{safe}"
        )

    return None

def build_loot_asset_key(loot) -> str:
    alias = (getattr(loot, "item_image_alias", None) or "").strip()
    if alias:
        return f"item:{_normalize_key_part(alias)}"
    return f"item:{_normalize_key_part(loot.item_name)}"



def build_loot_source_url(loot) -> Optional[str]:
    """Priority: explicit override → stored provider URL → alias fallback."""
    override = (
        getattr(loot, "item_image_url_override", None) or ""
    ).strip()
    if override:
        return override

    stored_url = (
        getattr(loot, "item_image_url", None) or ""
    ).strip()
    if stored_url:
        return stored_url

    alias = (
        getattr(loot, "item_image_alias", None) or ""
    ).strip()
    if alias:
        safe = alias.replace(" ", "_")
        if not safe.lower().endswith(
            (".gif", ".png", ".jpg", ".jpeg", ".webp")
        ):
            safe = f"{safe}.gif"

        return (
            f"{settings.TIBIAWIKI_BASE_PAGE_URL}"
            f"/Special:FilePath/{safe}"
        )

    safe_name = loot.item_name.replace(" ", "_")

    return (
        f"{settings.TIBIAWIKI_BASE_PAGE_URL}"
        f"/Special:FilePath/{safe_name}.gif"
    )

def build_zone_asset_key(zone) -> str:
    return f"zone:{_normalize_key_part(zone.name)}"


def build_zone_source_url(zone) -> Optional[str]:
    return (getattr(zone, "map_image_url", None) or None)


# ── internal fetch helpers ────────────────────────────────────────────────────

_WIKI_TITLE_LOWER_WORDS = frozenset({
    "a",
    "an",
    "and",
    "as",
    "at",
    "by",
    "for",
    "from",
    "in",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
})


def _normalize_wiki_file_title(value: str) -> str:
    normalized = unquote(value or "").strip()

    if normalized.lower().startswith("file:"):
        normalized = normalized[5:]

    normalized = normalized.replace("_", " ")

    return " ".join(normalized.split()).casefold()


def _wiki_file_title_candidates(asset_name: str) -> list[str]:
    """Build common MediaWiki filename-capitalization variants."""
    decoded = unquote(asset_name or "").replace("_", " ").strip()

    if not decoded:
        return []

    stem, extension = os.path.splitext(decoded)
    extension = extension.lower()

    words = stem.split()

    first_letter = (
        f"{stem[:1].upper()}{stem[1:]}{extension}"
        if stem
        else decoded
    )

    smart_title_words = []
    for index, word in enumerate(words):
        if index > 0 and word.casefold() in _WIKI_TITLE_LOWER_WORDS:
            smart_title_words.append(word.casefold())
        else:
            smart_title_words.append(
                f"{word[:1].upper()}{word[1:]}"
                if word
                else word
            )

    smart_title = f"{' '.join(smart_title_words)}{extension}"

    full_title = (
        f"{' '.join(word[:1].upper() + word[1:] for word in words)}"
        f"{extension}"
    )

    candidates = [
        f"{stem}{extension}",
        first_letter,
        smart_title,
        full_title,
    ]

    result: list[str] = []

    for candidate in candidates:
        if candidate and candidate not in result:
            result.append(candidate)

    return result


def _extract_mediawiki_image_url(
    payload: dict,
    *,
    expected_title: str | None = None,
) -> Optional[str]:
    pages = ((payload.get("query") or {}).get("pages") or [])

    if isinstance(pages, dict):
        page_rows = pages.values()
    else:
        page_rows = pages

    normalized_expected = (
        _normalize_wiki_file_title(expected_title)
        if expected_title
        else None
    )

    for page in page_rows:
        if not isinstance(page, dict):
            continue

        if page.get("missing") is not None:
            continue

        page_title = page.get("title") or ""

        if (
            normalized_expected
            and _normalize_wiki_file_title(page_title)
            != normalized_expected
        ):
            continue

        image_info = page.get("imageinfo") or []

        if not image_info:
            continue

        resolved_url = image_info[0].get("url")

        if not resolved_url:
            continue

        validate_remote_url(resolved_url)

        return resolved_url

    return None


async def _resolve_wiki_special_path(
    url: str,
    client: httpx.AsyncClient,
) -> Optional[str]:
    """Resolve a Fandom Special:FilePath URL through MediaWiki."""
    parsed = urlparse(url)
    asset_name = unquote(parsed.path.rsplit("/", 1)[-1])

    if not asset_name:
        return None

    candidates = _wiki_file_title_candidates(asset_name)

    try:
        validate_remote_url(settings.TIBIAWIKI_API_URL)

        exact_response = await client.get(
            settings.TIBIAWIKI_API_URL,
            params={
                "action": "query",
                "titles": "|".join(
                    f"File:{candidate}"
                    for candidate in candidates
                ),
                "prop": "imageinfo",
                "iiprop": "url",
                "redirects": "1",
                "format": "json",
                "formatversion": "2",
            },
        )

        _validate_connected_peer(exact_response)
        exact_response.raise_for_status()

        if len(exact_response.content) > 1024 * 1024:
            raise UnsafeMediaError(
                "The provider metadata response is too large"
            )

        resolved_url = _extract_mediawiki_image_url(
            exact_response.json() or {},
        )

        if resolved_url:
            return resolved_url

        search_term, _extension = os.path.splitext(
            asset_name.replace("_", " ")
        )
        search_term = search_term.replace('"', " ").strip()

        search_response = await client.get(
            settings.TIBIAWIKI_API_URL,
            params={
                "action": "query",
                "generator": "search",
                "gsrsearch": f'"{search_term}"',
                "gsrnamespace": "6",
                "gsrlimit": "10",
                "prop": "imageinfo",
                "iiprop": "url",
                "format": "json",
                "formatversion": "2",
            },
        )

        _validate_connected_peer(search_response)
        search_response.raise_for_status()

        if len(search_response.content) > 1024 * 1024:
            raise UnsafeMediaError(
                "The provider metadata response is too large"
            )

        return _extract_mediawiki_image_url(
            search_response.json() or {},
            expected_title=asset_name,
        )

    except Exception as exc:
        logger.warning(
            "mediawiki_image_resolution_failed "
            "asset=%s error_type=%s",
            asset_name[:160],
            type(exc).__name__,
        )

        return None


async def _fetch_image_once(source_url: str) -> tuple[bytes, str, str]:
    """Fetch image bytes. Resolves Special:FilePath via wiki API if needed.
    Returns (content_bytes, content_type, resolved_url).
    Raises httpx.HTTPStatusError or httpx.RequestError on failure.
    """
    headers = {
        "User-Agent": settings.TIBIAWIKI_USER_AGENT,
        "Referer": settings.TIBIAWIKI_BASE_PAGE_URL,
        "Accept": "image/avif,image/webp,image/png,image/jpeg,image/gif",
    }
    timeout = httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0)
    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=False,
        headers=headers,
    ) as client:
        current_url = source_url
        parsed_source = urlparse(source_url)
        if parsed_source.hostname == "tibia.fandom.com" and "/Special:FilePath/" in parsed_source.path:
            resolved = await _resolve_wiki_special_path(source_url, client)
            if not resolved:
                raise UnsafeMediaError("The provider could not resolve the image resource")
            current_url = resolved
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


async def _fetch_image(source_url: str) -> tuple[bytes, str, str]:
    """Fetch with bounded backoff for rate limits and provider server errors."""
    for attempt in range(_MAX_FETCH_ATTEMPTS):
        try:
            return await _fetch_image_once(source_url)
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            retryable = status == 429 or 500 <= status < 600
            if not retryable or attempt + 1 >= _MAX_FETCH_ATTEMPTS:
                raise
            retry_after = exc.response.headers.get("Retry-After")
            delay = min(60, max(1, int(retry_after))) if retry_after and retry_after.isdigit() else 2 ** attempt
            await asyncio.sleep(delay)
        except (httpx.TimeoutException, httpx.NetworkError):
            if attempt + 1 >= _MAX_FETCH_ATTEMPTS:
                raise
            await asyncio.sleep(2 ** attempt)
    raise UnsafeMediaError("Image download attempts exhausted")


# ── public API ────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class MediaFetchOutcome:
    asset: MediaAsset | None
    result: str
    error_category: str | None = None
    safe_message: str | None = None
    http_status: int | None = None
    retryable: bool | None = None
    safe_url: str | None = None


def _atomic_image_write(destination: Path, content: bytes) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(prefix=".media-", dir=destination.parent, delete=False) as temporary:
            temporary_name = temporary.name
            temporary.write(content)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_name, destination)
        temporary_name = None
    finally:
        if temporary_name:
            Path(temporary_name).unlink(missing_ok=True)


async def cache_media_asset(
    db: Session,
    *,
    asset_key: str,
    source_url: str,
    force_refetch: bool = False,
    retry_failed: bool = False,
) -> MediaFetchOutcome:
    """Use the canonical downloader and atomically update one served media asset."""
    asset = db.query(MediaAsset).filter(MediaAsset.asset_key == asset_key).first()
    if asset and asset.status == "cached" and asset.file_exists() and not force_refetch:
        return MediaFetchOutcome(asset=asset, result="cached")
    if asset and asset.status == "failed" and not (force_refetch or retry_failed):
        if asset.last_fetched_at:
            fetched_at = asset.last_fetched_at
            if fetched_at.tzinfo is None:
                fetched_at = fetched_at.replace(tzinfo=UTC)
            if (datetime.now(UTC) - fetched_at).total_seconds() < _RETRY_COOLDOWN_SECONDS:
                return MediaFetchOutcome(asset=asset, result="failed", error_category="download_failed", safe_message=asset.error_message)

    database_mutated = False
    try:
        content, content_type, resolved_url = await _fetch_image(source_url)
        _, extension = validate_raster_image(content, content_type)
        safe_key = re.sub(r"[^a-z0-9_]", "_", asset_key).strip("_")
        destination = _MEDIA_DIR / f"{safe_key}{extension}"
        _atomic_image_write(destination, content)
        created = asset is None
        if asset is None:
            asset = MediaAsset(asset_key=asset_key)
            db.add(asset)
        database_mutated = True
        asset.source_url = sanitize_url(source_url)
        asset.resolved_url = sanitize_url(resolved_url)
        asset.local_path = str(destination)
        asset.content_type = content_type
        asset.size_bytes = len(content)
        asset.sha256_hash = hashlib.sha256(content).hexdigest()
        asset.status = "cached"
        asset.last_fetched_at = datetime.now(UTC)
        asset.error_message = None
        db.commit()
        logger.info("media_asset_cached key=%s size=%d", asset_key, len(content))
        return MediaFetchOutcome(asset=asset, result="created" if created else "updated")
    except Exception as exc:
        if database_mutated:
            db.rollback()
        asset = db.query(MediaAsset).filter(MediaAsset.asset_key == asset_key).first()
        if isinstance(exc, UnsafeMediaError):
            category, status, retryable, safe_message = "unsupported_resource", None, False, SAFE_MESSAGES["unsupported_resource"]
        else:
            category, status, retryable, safe_message = classify_exception(exc)
        request_url = None
        if isinstance(exc, httpx.HTTPStatusError) and exc.request:
            request_url = str(exc.request.url)
        safe_url = sanitize_url(request_url or source_url)
        # A failed refresh never invalidates or replaces a working local file.
        if not (asset and asset.status == "cached" and asset.file_exists()):
            if asset is None:
                asset = MediaAsset(asset_key=asset_key, source_url=sanitize_url(source_url))
                db.add(asset)
            asset.status = "failed"
            asset.error_message = safe_message
            asset.last_fetched_at = datetime.now(UTC)
            db.commit()
        parsed = urlparse(safe_url or "")
        logger.warning(
            "media_asset_fetch_failed key=%s category=%s http_status=%s provider=%s path=%s",
            asset_key, category, status, parsed.hostname or "unknown", parsed.path or "/",
        )
        return MediaFetchOutcome(
            asset=asset, result="failed", error_category=category, safe_message=safe_message,
            http_status=status, retryable=retryable, safe_url=safe_url,
        )

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
            fetched_at = asset.last_fetched_at
            if fetched_at.tzinfo is None:
                fetched_at = fetched_at.replace(tzinfo=UTC)
            age = (datetime.now(UTC) - fetched_at).total_seconds()
            if age < _RETRY_COOLDOWN_SECONDS:
                return asset  # caller should serve placeholder

    if not autofetch_enabled and not force_refetch:
        return asset  # None or stale asset

    outcome = await cache_media_asset(
        db, asset_key=asset_key, source_url=source_url,
        force_refetch=force_refetch, retry_failed=force_refetch,
    )
    return outcome.asset


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
