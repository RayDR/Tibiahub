#!/usr/bin/env python3
"""Create/update deterministic local users for validation tests."""

from __future__ import annotations

import os
from datetime import datetime

from app.core.security import get_password_hash
from app.db.database import SessionLocal
from app.models.user import User


def _ensure_test_data_allowed() -> None:
    if os.environ.get("TIBIAHUB_ALLOW_TEST_DATA") == "1":
        return
    raise RuntimeError("Refusing to create test users without TIBIAHUB_ALLOW_TEST_DATA=1")


def upsert_user(
    *,
    username: str,
    email: str,
    password: str,
    is_superuser: bool,
    guild_rank: str,
    guild_name: str | None,
) -> User:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            user = User(
                username=username,
                email=email,
                hashed_password=get_password_hash(password),
                join_date=datetime.utcnow(),
                is_active=True,
                is_superuser=is_superuser,
                guild_rank=guild_rank,
                guild_name=guild_name,
            )
            db.add(user)
        else:
            user.email = email
            user.hashed_password = get_password_hash(password)
            user.is_active = True
            user.is_superuser = is_superuser
            user.guild_rank = guild_rank
            user.guild_name = guild_name

        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


def main() -> None:
    _ensure_test_data_allowed()
    users = [
        {
            "username": "admin",
            "email": "admin@tibiahub.local",
            "password": "admin123",
            "is_superuser": True,
            "guild_rank": "Leader",
            "guild_name": "TestGuild",
        },
        {
            "username": "leader_test",
            "email": "leader_test@tibiahub.local",
            "password": "leader123",
            "is_superuser": False,
            "guild_rank": "Leader",
            "guild_name": "TestGuild",
        },
        {
            "username": "user_test",
            "email": "user_test@tibiahub.local",
            "password": "user123",
            "is_superuser": False,
            "guild_rank": "Member",
            "guild_name": "OtherGuild",
        },
    ]

    for payload in users:
        user = upsert_user(**payload)
        print(
            f"ok username={user.username} id={user.id} superuser={user.is_superuser} "
            f"rank={user.guild_rank} guild={user.guild_name}"
        )


if __name__ == "__main__":
    main()
