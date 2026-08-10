#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import settings
from app.db.database import SessionLocal, verify_connection_and_schema
from app.models import Loot


AMOUNT_TOKEN = re.compile(
    r"^\d+(?:\s*-\s*(?:\d+|\?))?\s*[?+]?$"
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--confirm-repair-malformed-loot",
        action="store_true",
    )
    args = parser.parse_args()

    if settings.database_name != "tibiahub":
        raise SystemExit(
            "Refusing to modify a database other than tibiahub."
        )

    if not args.confirm_repair_malformed_loot:
        raise SystemExit(
            "Use --confirm-repair-malformed-loot."
        )

    verify_connection_and_schema()

    provider_host = urlparse(
        settings.TIBIAWIKI_BASE_PAGE_URL
    ).hostname

    with SessionLocal() as db:
        rows = db.query(Loot).all()

        malformed = []

        for row in rows:
            name = (row.item_name or "").strip()

            if not AMOUNT_TOKEN.fullmatch(name):
                continue

            source_host = urlparse(
                row.source_url or ""
            ).hostname

            image_host = urlparse(
                row.item_image_url or ""
            ).hostname

            raw = (
                row.raw_data
                if isinstance(row.raw_data, dict)
                else {}
            )

            if (
                (
                    source_host == provider_host
                    or image_host == provider_host
                )
                and (
                    not raw
                    or str(
                        raw.get("item_name") or ""
                    ).strip() == name
                )
            ):
                malformed.append(row)

        affected_creatures = {
            row.creature_id
            for row in malformed
        }

        for row in malformed:
            db.delete(row)

        db.commit()

        print(
            "malformed_loot_removed="
            f"{len(malformed)} "
            "affected_creatures="
            f"{len(affected_creatures)}"
        )


if __name__ == "__main__":
    main()
