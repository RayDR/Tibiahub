"""Secure, file-based runtime secret discovery for TibiaHub."""
from __future__ import annotations

import os
import stat
from pathlib import Path


DEFAULT_RUNTIME_SECRETS_FILE = Path("/forge/tibiahub-secrets/runtime.env")


def runtime_secrets_file() -> Path:
    """Return the configured absolute runtime secret path without reading it."""
    configured = os.environ.get("TIBIAHUB_SECRETS_FILE", str(DEFAULT_RUNTIME_SECRETS_FILE))
    path = Path(configured).expanduser()
    if not path.is_absolute():
        raise RuntimeError("TIBIAHUB_SECRETS_FILE must be an absolute path")
    return path


def validate_secret_file(path: Path, *, required: bool = False) -> Path | None:
    """Reject missing, linked, shared, or foreign-owned secret files."""
    if not path.exists():
        if required:
            raise RuntimeError(f"Required TibiaHub secret file is missing: {path}")
        return None
    if path.is_symlink() or not path.is_file():
        raise RuntimeError(f"TibiaHub secret path must be a regular file, not a link: {path}")

    file_status = path.stat()
    if file_status.st_uid != os.geteuid():
        raise RuntimeError(f"TibiaHub secret file must be owned by the service user: {path}")
    if stat.S_IMODE(file_status.st_mode) & 0o077:
        raise RuntimeError(f"TibiaHub secret file must not grant group or other access: {path}")

    parent_status = path.parent.stat()
    if parent_status.st_uid != os.geteuid():
        raise RuntimeError(f"TibiaHub secret directory must be owned by the service user: {path.parent}")
    if stat.S_IMODE(parent_status.st_mode) & 0o077:
        raise RuntimeError(f"TibiaHub secret directory must not grant group or other access: {path.parent}")
    return path


RUNTIME_SECRETS_FILE = runtime_secrets_file()
VALIDATED_RUNTIME_SECRETS_FILE = validate_secret_file(RUNTIME_SECRETS_FILE)
