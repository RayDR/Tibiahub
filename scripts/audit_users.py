#!/usr/bin/env python3
"""Audit current user activation state without modifying user records."""

from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_ROOT = PROJECT_ROOT / "backend"
os.chdir(BACKEND_ROOT)
sys.path.insert(0, str(BACKEND_ROOT))

from app.db.database import SessionLocal, init_db
from app.models.user import User


def main() -> int:
    init_db()
    db = SessionLocal()
    try:
        users = db.query(User).order_by(User.id).all()
        total_users = len(users)
        active_users = [user for user in users if user.is_active]
        inactive_users = [user for user in users if not user.is_active]
        global_admins = [user for user in users if user.is_superuser]
        cleanup_marked = [
            user for user in inactive_users
            if (user.tibia_status or "") == "disabled_test_data" or (user.tibia_last_error or "")
        ]
        admin = next((user for user in users if user.username == "admin"), None)

        print(f"total_users={total_users}")
        print(f"active_users={len(active_users)}")
        print(f"inactive_users={len(inactive_users)}")
        print("global_admins=")
        for user in global_admins:
            print(
                f"  - id={user.id} username={user.username} active={user.is_active} "
                f"email_present={bool(user.email)} guild_rank={user.guild_rank or '-'}"
            )

        if admin:
            print(
                f"admin_status=id={admin.id} active={admin.is_active} superuser={admin.is_superuser} "
                f"email_present={bool(admin.email)} guild_rank={admin.guild_rank or '-'}"
            )
        else:
            print("admin_status=missing")

        print("likely_recently_deactivated=")
        if cleanup_marked:
            for user in cleanup_marked:
                print(
                    f"  - id={user.id} username={user.username} email_present={bool(user.email)} "
                    f"tibia_status={user.tibia_status or '-'} reason={user.tibia_last_error or '-'}"
                )
        else:
            print("  - none")

        print("inactive_users_all=")
        if inactive_users:
            for user in inactive_users:
                print(
                    f"  - id={user.id} username={user.username} email_present={bool(user.email)} "
                    f"superuser={user.is_superuser} tibia_status={user.tibia_status or '-'}"
                )
        else:
            print("  - none")

        if cleanup_marked:
            print("note=users table has no deactivated_at column; likely_recently_deactivated is inferred from cleanup markers")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
