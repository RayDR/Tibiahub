#!/usr/bin/env python3
"""Recover only expired TibiaHub knowledge leases with explicit confirmation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import settings  # noqa: E402
from app.db.database import SessionLocal, verify_connection_and_schema  # noqa: E402
from app.knowledge.services import KnowledgeJobService  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm-recover-expired-knowledge-jobs", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    if settings.database_name != "tibiahub":
        raise SystemExit("Refusing recovery outside the exact TibiaHub database.")
    if args.limit < 1 or args.limit > 1000:
        raise SystemExit("Recovery limit must be between 1 and 1000.")
    if not args.dry_run and not args.confirm_recover_expired_knowledge_jobs:
        raise SystemExit("Use --confirm-recover-expired-knowledge-jobs or --dry-run.")
    verify_connection_and_schema()
    with SessionLocal.begin() as db:
        recovered = KnowledgeJobService.recover_expired(db, limit=args.limit, dry_run=args.dry_run)
        if args.dry_run:
            db.rollback()
    print(f"Expired knowledge jobs {'found' if args.dry_run else 'recovered'}: count={len(recovered)}")


if __name__ == "__main__":
    main()
