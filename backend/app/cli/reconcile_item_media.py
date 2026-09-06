"""Preview or apply exact canonical Item media bindings."""
from __future__ import annotations

import argparse
import json

from app.db.database import SessionLocal
from app.services.item_media_binding_service import ItemMediaBindingService


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Persist eligible bindings. The default is a read-only preview.",
    )
    args = parser.parse_args()

    with SessionLocal() as db:
        try:
            report = ItemMediaBindingService.reconcile(db, apply=args.apply)
            if args.apply:
                db.commit()
            else:
                db.rollback()
        except Exception:
            db.rollback()
            raise

    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
