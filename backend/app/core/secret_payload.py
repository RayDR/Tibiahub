"""Small authenticated-encryption helper for retrievable operational secrets."""

from __future__ import annotations

import base64
import hashlib
import json

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


def _fernet() -> Fernet:
    derived = hashlib.sha256(("tibiahub:payload:v1:" + settings.secret_key).encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(derived))


def encrypt_text(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_text(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return _fernet().decrypt(value.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, UnicodeError):
        return None


def encrypt_json(payload: dict) -> str:
    return encrypt_text(json.dumps(payload, separators=(",", ":"), sort_keys=True))


def decrypt_json(value: str | None) -> dict:
    raw = decrypt_text(value)
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}
