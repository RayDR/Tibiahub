#!/usr/bin/env python3
"""Read-only consistency verification for the TibiaHub Knowledge Graph."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import settings  # noqa: E402
from app.db.database import SessionLocal, verify_connection_and_schema  # noqa: E402
from app.knowledge.services import KnowledgeGraphService  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Explicitly confirm this read-only verification")
    args = parser.parse_args()
    if settings.database_name != "tibiahub":
        raise SystemExit("Refusing to inspect a database other than the exact TibiaHub database.")
    if not args.dry_run:
        raise SystemExit("Use --dry-run; verification never mutates graph data.")
    verify_connection_and_schema()
    with SessionLocal() as db:
        result = KnowledgeGraphService.verify_consistency(db)
        print(json.dumps(result, indent=2, default=str, sort_keys=True))
    problem_count = sum(value for key, value in result.items() if key not in {"relationships", "registry_errors"} and isinstance(value, int))
    if problem_count or result["registry_errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
