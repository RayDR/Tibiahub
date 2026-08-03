#!/usr/bin/env python3
"""Explicitly create the first global administrator after a clean bootstrap."""
from __future__ import annotations

import os

from app.core.security import get_password_hash
from app.core.password_policy import PasswordPolicyError, validate_password
from app.db.database import SessionLocal, verify_connection_and_schema
from app.models.user import User


def required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"{name} is required")
    return value


def required_password(name: str) -> str:
    value = os.environ.get(name)
    if value is None or value == "":
        raise SystemExit(f"{name} is required")
    return value


def main() -> None:
    username = required("BOOTSTRAP_ADMIN_USERNAME")
    password = required_password("BOOTSTRAP_ADMIN_PASSWORD")
    try:
        validate_password(password)
    except PasswordPolicyError as exc:
        raise SystemExit(str(exc)) from exc
    email = required("BOOTSTRAP_ADMIN_EMAIL")
    verify_connection_and_schema()
    with SessionLocal.begin() as db:
        if db.query(User).filter((User.username == username) | (User.email == email)).first():
            raise SystemExit("Bootstrap administrator already exists")
        db.add(
            User(
                username=username,
                email=email,
                hashed_password=get_password_hash(password),
                is_active=True,
                is_superuser=True,
                is_moderator=True,
            )
        )
    print("Initial global administrator created.")


if __name__ == "__main__":
    main()
