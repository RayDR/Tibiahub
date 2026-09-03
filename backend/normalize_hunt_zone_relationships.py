"""Replay stored Creature location evidence through canonical normalization."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from app.db.database import SessionLocal
from app.knowledge.services.hunt_zone_relationships import (
    HuntZoneRelationshipNormalizationResult,
    HuntZoneRelationshipRepairService,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--after-creature-id", type=int, default=0)
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.after_creature_id < 0 or (args.limit is not None and args.limit < 1):
        parser.error("IDs must be nonnegative and limit must be positive")

    db = SessionLocal()
    cursor = args.after_creature_id
    processed_total = skipped_total = batches = 0
    metrics = HuntZoneRelationshipNormalizationResult()
    try:
        while True:
            remaining = None if args.limit is None else args.limit - processed_total - skipped_total
            if remaining is not None and remaining <= 0:
                break
            batch = HuntZoneRelationshipRepairService.run_batch(
                db,
                after_creature_id=cursor,
                limit=min(args.batch_size, remaining) if remaining is not None else args.batch_size,
            )
            batches += 1
            processed_total += batch.processed_creatures
            skipped_total += batch.skipped_creatures
            metrics = HuntZoneRelationshipNormalizationResult(**{
                field_name: getattr(metrics, field_name) + getattr(batch.metrics, field_name)
                for field_name in HuntZoneRelationshipNormalizationResult.__dataclass_fields__
            })
            if args.dry_run:
                db.flush()
            else:
                db.commit()
            if batch.next_creature_id is None or not batch.has_more:
                cursor = batch.next_creature_id or cursor
                break
            cursor = batch.next_creature_id
        if args.dry_run:
            db.rollback()
        print(json.dumps({
            "dry_run": args.dry_run,
            "batches": batches,
            "processed_creatures": processed_total,
            "skipped_creatures": skipped_total,
            "next_creature_id": cursor,
            "metrics": asdict(metrics),
        }, sort_keys=True))
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
