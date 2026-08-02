#!/usr/bin/env python3
"""Explicit operator-only recovery for a TibiaHub global administrator."""

from __future__ import annotations

import argparse
import os
import stat
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import settings  # noqa: E402
from app.db.database import SessionLocal, verify_connection_and_schema  # noqa: E402
from app.services.admin_user_service import (  # noqa: E402
    AdminRecoveryError,
    recover_administrator,
)


CONFIRMATION = "RECOVER TIBIAHUB ADMIN"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recover or explicitly create one TibiaHub global administrator.",
    )
    parser.add_argument("--identifier", required=True, help="Existing username or email.")
    parser.add_argument("--password-file", required=True, help="Absolute path to a mode-0600 password file.")
    parser.add_argument("--create-if-missing", action="store_true")
    parser.add_argument("--username", help="Required with --create-if-missing.")
    parser.add_argument("--email", help="Required with --create-if-missing.")
    parser.add_argument("--mark-email-verified", action="store_true")
    parser.add_argument(
        "--keep-one-time-tokens",
        action="store_true",
        help="Do not invalidate outstanding verification/reset tokens.",
    )
    parser.add_argument("--confirm", required=True, help=f"Must equal: {CONFIRMATION}")
    return parser.parse_args()


def read_password_file(raw_path: str) -> str:
    path = Path(raw_path)
    if not path.is_absolute():
        raise AdminRecoveryError("Password file path must be absolute")
    if not path.is_file():
        raise AdminRecoveryError("Password file does not exist")

    file_mode = stat.S_IMODE(path.stat().st_mode)
    if file_mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise AdminRecoveryError("Password file must not be accessible by group or others")

    value = path.read_text(encoding="utf-8")
    if "\x00" in value:
        raise AdminRecoveryError("Password file contains invalid data")

    password = value.rstrip("\r\n")
    if "\n" in password or "\r" in password:
        raise AdminRecoveryError("Password file must contain exactly one line")
    if len(password) < 12:
        raise AdminRecoveryError("Administrator passwords must contain at least 12 characters")
    if len(password) > 256:
        raise AdminRecoveryError("Password is unexpectedly long")
    return password


def main() -> None:
    args = parse_args()
    if args.confirm != CONFIRMATION:
        raise SystemExit(f"Confirmation must exactly match: {CONFIRMATION}")

    if settings.database_name != "tibiahub":
        raise SystemExit("Refusing recovery because the configured database is not tibiahub")

    try:
        password = read_password_file(args.password_file)
        verify_connection_and_schema()
        with SessionLocal.begin() as db:
            result = recover_administrator(
                db,
                identifier=args.identifier,
                password=password,
                create_if_missing=args.create_if_missing,
                username=args.username,
                email=args.email,
                mark_email_verified=args.mark_email_verified,
                revoke_one_time_tokens=not args.keep_one_time_tokens,
            )
    except AdminRecoveryError as exc:
        raise SystemExit(str(exc)) from exc
    finally:
        password = ""

    print(
        "Administrator recovery completed "
        f"user_id={result.user.id} "
        f"username={result.user.username} "
        f"created={str(result.created).lower()} "
        f"revoked_one_time_tokens={result.revoked_one_time_tokens}"
    )


if __name__ == "__main__":
    main()
