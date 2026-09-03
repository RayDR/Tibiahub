"""Replay immutable Item documents through canonical NPC trade normalization."""

from __future__ import annotations

import argparse
import json

from app.db.database import SessionLocal
from app.knowledge.services.npc_trade_repair import NpcTradeRelationshipRepairService


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--after-item-id", type=int, default=0)
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.after_item_id < 0 or not 1 <= args.batch_size <= 500:
        parser.error("cursor must be nonnegative and batch size must be between 1 and 500")
    if args.limit is not None and args.limit < 1:
        parser.error("limit must be positive")

    db = SessionLocal()
    cursor = args.after_item_id
    processed = skipped = batches = 0
    try:
        while True:
            remaining = None if args.limit is None else args.limit - processed - skipped
            if remaining is not None and remaining <= 0:
                break
            batch = NpcTradeRelationshipRepairService.run_batch(
                db,
                after_item_id=cursor,
                limit=min(args.batch_size, remaining) if remaining is not None else args.batch_size,
            )
            if batch.next_item_id is None:
                break
            batches += 1
            processed += batch.processed_items
            skipped += batch.skipped_items
            cursor = batch.next_item_id
            if not args.dry_run:
                db.commit()
            if not batch.has_more:
                break
        if args.dry_run:
            db.rollback()
        print(json.dumps({
            "dry_run": args.dry_run,
            "batches": batches,
            "processed_items": processed,
            "skipped_items": skipped,
            "next_item_id": cursor,
        }, sort_keys=True))
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
