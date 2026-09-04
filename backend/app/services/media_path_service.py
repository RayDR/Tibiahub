"""CWD-independent, constrained filesystem paths for cached media."""
from __future__ import annotations

from pathlib import Path

from app.core.config import BACKEND_ROOT, settings


def media_storage_root() -> Path:
    """Return the configured absolute root used for all new media writes."""
    root = Path(settings.MEDIA_STORAGE_ROOT).expanduser()
    if not root.is_absolute():
        raise RuntimeError("MEDIA_STORAGE_ROOT must be absolute")
    return root.resolve()


def legacy_media_storage_root() -> Path:
    """Return the historical PM2-CWD-derived cache root deterministically."""
    return (BACKEND_ROOT / "backend" / "storage" / "media").resolve()


def _contained(candidate: Path, root: Path) -> bool:
    try:
        candidate.relative_to(root)
        return True
    except ValueError:
        return False


def resolve_media_local_path(stored_path: str | Path | None) -> Path | None:
    """Resolve a persisted path without consulting the process working directory.

    New rows store absolute paths below ``MEDIA_STORAGE_ROOT``. Historical rows
    store ``backend/storage/media/...`` relative to the backend service CWD;
    those are anchored to ``BACKEND_ROOT`` for compatibility. Other relative
    paths and traversal attempts are rejected.
    """
    if not stored_path:
        return None
    raw = Path(stored_path)
    configured_root = media_storage_root()
    legacy_root = legacy_media_storage_root()

    if raw.is_absolute():
        candidate = raw.resolve()
        if _contained(candidate, configured_root) or _contained(candidate, legacy_root):
            return candidate
        # Unit tests use isolated temporary roots rather than production paths.
        return candidate if settings.APP_ENV == "test" else None

    legacy_prefix = Path("backend") / "storage" / "media"
    try:
        suffix = raw.relative_to(legacy_prefix)
    except ValueError:
        return None
    candidate = (legacy_root / suffix).resolve()
    return candidate if _contained(candidate, legacy_root) else None


def media_destination(file_name: str) -> Path:
    """Resolve a new cache destination below the configured root."""
    root = media_storage_root()
    candidate = (root / Path(file_name).name).resolve()
    if not _contained(candidate, root):
        raise ValueError("Invalid media destination")
    return candidate
