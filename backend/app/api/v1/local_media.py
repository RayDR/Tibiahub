"""Shared helpers for serving local cached media safely."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.database import SessionLocal


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


def resolve_local_media_descriptor(
    resolver: Callable[[Session], LocalMediaDescriptor],
    *,
    session_factory: Callable[[], Session] = SessionLocal,
) -> LocalMediaDescriptor:
    """Run DB lookups in a short-lived session and always release the pool slot."""
    db = session_factory()
    try:
        return resolver(db)
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

    if descriptor.size_bytes is not None:
        headers["Content-Length"] = str(descriptor.size_bytes)

    if etag and request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)

    return FileResponse(
        path=str(path),
        media_type=descriptor.content_type or default_media_type,
        headers=headers,
    )
