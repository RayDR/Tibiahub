"""Shared helpers for serving local cached media safely."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.media_asset import MediaAsset


@dataclass(frozen=True)
class LocalMediaDescriptor:
    """Primitive media attributes copied during the short DB phase."""

    local_path: str | None
    content_type: str | None
    size_bytes: int | None
    asset_hash: str | None
    asset_key: str
    status: str
    fallback_label: str


def _legacy_item_asset_key(label: str) -> str | None:
    """Build the historical item media key from a canonical display name."""
    normalized = (label or "").strip().lower()
    for extension in (".gif", ".png", ".jpg", ".jpeg", ".webp"):
        if normalized.endswith(extension):
            normalized = normalized[: -len(extension)]
            break
    normalized = re.sub(r"[^a-z0-9]+", "_", normalized).strip("_")
    return f"item:{normalized}" if normalized else None


def _bridge_legacy_item_descriptor(
    db: Session,
    descriptor: LocalMediaDescriptor,
) -> LocalMediaDescriptor:
    """Reuse an already-cached legacy item asset for a canonical item key."""
    if descriptor.status == "cached" or not descriptor.asset_key.startswith("item:knowledge:"):
        return descriptor

    legacy_key = _legacy_item_asset_key(descriptor.fallback_label)
    if not legacy_key:
        return descriptor

    asset = db.query(MediaAsset).filter(MediaAsset.asset_key == legacy_key).first()
    if not asset or asset.status != "cached" or not asset.file_exists():
        return descriptor

    return LocalMediaDescriptor(
        local_path=str(asset.local_path) if asset.local_path else None,
        content_type=asset.content_type,
        size_bytes=asset.size_bytes,
        asset_hash=asset.sha256_hash,
        asset_key=legacy_key,
        status="cached",
        fallback_label=descriptor.fallback_label,
    )


def resolve_local_media_descriptor(
    resolver: Callable[[Session], LocalMediaDescriptor],
    *,
    session_factory: Callable[[], Session] = SessionLocal,
) -> LocalMediaDescriptor:
    """Run DB lookups in a short-lived session and always release the pool slot."""
    db = session_factory()
    try:
        descriptor = resolver(db)
        return _bridge_legacy_item_descriptor(db, descriptor)
    finally:
        try:
            # Public media lookups are read-only; ensure no idle transaction lingers.
            db.rollback()
        except Exception:
            pass
        db.close()


def _compute_etag(path: Path, asset_hash: str | None) -> str | None:
    if asset_hash:
        return asset_hash[:20]

    digest = hashlib.sha1()
    try:
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(128 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
    except OSError:
        return None

    return digest.hexdigest()


def build_local_media_file_response(
    request: Request,
    descriptor: LocalMediaDescriptor,
    *,
    default_media_type: str,
    cache_max_age_seconds: int,
    extra_headers: dict[str, str] | None = None,
) -> Response | None:
    """Create a cache-aware FileResponse using descriptor primitives only."""
    if not descriptor.local_path:
        return None

    path = Path(descriptor.local_path)
    if not path.exists() or not path.is_file():
        return None

    etag = _compute_etag(path, descriptor.asset_hash)
    headers = {
        "Cache-Control": f"public, max-age={cache_max_age_seconds}",
        **(extra_headers or {}),
    }

    if etag:
        headers["ETag"] = etag

    if etag and request.headers.get("if-none-match") == etag:
        # A 304 response has no body. Do not propagate the cached file size as
        # Content-Length or Uvicorn will reject the empty response body.
        return Response(status_code=304, headers=headers)

    if descriptor.size_bytes is not None:
        headers["Content-Length"] = str(descriptor.size_bytes)

    return FileResponse(
        path=str(path),
        media_type=descriptor.content_type or default_media_type,
        headers=headers,
    )
