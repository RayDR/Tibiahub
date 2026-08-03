#!/usr/bin/env python3
"""Ensure the primary admin account exists and can access the admin panel."""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_ROOT = PROJECT_ROOT / "backend"
os.chdir(BACKEND_ROOT)
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.security import get_password_hash
from app.core.password_policy import PasswordPolicyError, validate_password
from app.db.database import SessionLocal, init_db
from app.models.user import User


def _read_admin_env() -> tuple[str, str | None, str | None]:
    username = (os.environ.get("ADMIN_USERNAME") or "admin").strip() or "admin"
    password_value = os.environ.get("ADMIN_PASSWORD")
    password = password_value if password_value not in {None, ""} else None
    email = (os.environ.get("ADMIN_EMAIL") or "").strip() or None
    return username, password, email


def main() -> int:
    username, password, email = _read_admin_env()
    if password:
        try:
            validate_password(password)
        except PasswordPolicyError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
    init_db()

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        created = False

        if user is None:
            if not password:
                print("error: ADMIN_PASSWORD is required when creating a missing admin user", file=sys.stderr)
                return 1

            user = User(
                username=username,
                email=email,
                hashed_password=get_password_hash(password),
                join_date=datetime.now(UTC),
                is_active=True,
                is_superuser=True,
                guild_rank="Global Admin",
                tibia_status="admin_restored",
                tibia_last_error=None,
            )
            db.add(user)
            created = True
        else:
            if password:
                user.hashed_password = get_password_hash(password)
            if email:
                user.email = email
            user.is_active = True
            user.is_superuser = True
            user.guild_rank = "Global Admin"
            user.tibia_last_error = None
            if not user.tibia_status or user.tibia_status == "disabled_test_data":
                user.tibia_status = "admin_restored"

        db.commit()
        db.refresh(user)

        action = "created" if created else "updated"
        print(
            f"ok action={action} username={user.username} id={user.id} "
            f"is_active={user.is_active} is_superuser={user.is_superuser} guild_rank={user.guild_rank}"
        )
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
