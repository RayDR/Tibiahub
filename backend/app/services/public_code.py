"""Short public code helpers for raffle/contest sharing URLs."""
from __future__ import annotations

import secrets
import string

from sqlalchemy.orm import Session


ALPHABET = string.ascii_lowercase + string.digits


def _new_code(length: int = 6) -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


def generate_unique_code(db: Session, model_cls, field_name: str = "public_code", length: int = 6) -> str:
    for _ in range(40):
        code = _new_code(length)
        exists = db.query(model_cls).filter(getattr(model_cls, field_name) == code).first()
        if not exists:
            return code
    raise RuntimeError("Could not generate unique public code")
