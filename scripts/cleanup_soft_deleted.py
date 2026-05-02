#!/usr/bin/env python3
"""Safely clean up soft-deleted data with dry-run support.

Examples:
python scripts/cleanup_soft_deleted.py --dry-run --older-than-days 30
python scripts/cleanup_soft_deleted.py --yes --older-than-days 30
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.db.database import SessionLocal, init_db  # noqa: E402
from app.models.creature import Creature  # noqa: E402
from app.models.events import Event, EventParticipant, PublicEventParticipant  # noqa: E402
from app.models.external_data import CachedResource  # noqa: E402
from app.models.guild import Announcement, GuildEvent  # noqa: E402
from app.models.raffle import Raffle, RaffleParticipant, RafflePrize, RaffleWinner  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cleanup soft-deleted entities")
    parser.add_argument("--dry-run", action="store_true", help="Only print what would be removed")
    parser.add_argument("--yes", action="store_true", help="Execute deletion without interactive confirmation")
    parser.add_argument("--older-than-days", type=int, default=30, help="Only purge records deleted before this age")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dry_run = args.dry_run or not args.yes
    cutoff = datetime.utcnow() - timedelta(days=max(0, args.older_than_days))

    init_db()
    db = SessionLocal()
    try:
        tasks = []

        # Soft-deleted core entities.
        tasks.append((
            "announcements_soft_deleted",
            db.query(Announcement).filter(Announcement.is_deleted == True, Announcement.deleted_at.isnot(None), Announcement.deleted_at < cutoff),
        ))
        tasks.append((
            "guild_events_soft_deleted",
            db.query(GuildEvent).filter(GuildEvent.is_deleted == True, GuildEvent.deleted_at.isnot(None), GuildEvent.deleted_at < cutoff),
        ))
        tasks.append((
            "events_soft_deleted",
            db.query(Event).filter(Event.is_deleted == True, Event.deleted_at.isnot(None), Event.deleted_at < cutoff),
        ))
        tasks.append((
            "raffles_soft_deleted",
            db.query(Raffle).filter(Raffle.is_deleted == True, Raffle.deleted_at.isnot(None), Raffle.deleted_at < cutoff),
        ))
        tasks.append((
            "raffle_participants_soft_deleted",
            db.query(RaffleParticipant).filter(RaffleParticipant.is_deleted == True, RaffleParticipant.deleted_at.isnot(None), RaffleParticipant.deleted_at < cutoff),
        ))
        tasks.append((
            "public_event_participants_soft_deleted",
            db.query(PublicEventParticipant).filter(PublicEventParticipant.is_deleted == True, PublicEventParticipant.deleted_at.isnot(None), PublicEventParticipant.deleted_at < cutoff),
        ))

        # Orphans.
        tasks.append((
            "event_participants_orphans",
            db.query(EventParticipant).outerjoin(Event, Event.id == EventParticipant.event_id).filter(Event.id.is_(None)),
        ))
        tasks.append((
            "raffle_participants_orphans",
            db.query(RaffleParticipant).outerjoin(Raffle, Raffle.id == RaffleParticipant.raffle_id).filter(Raffle.id.is_(None)),
        ))
        tasks.append((
            "raffle_winners_orphans",
            db.query(RaffleWinner).outerjoin(Raffle, Raffle.id == RaffleWinner.raffle_id).filter(Raffle.id.is_(None)),
        ))
        tasks.append((
            "raffle_prizes_orphans",
            db.query(RafflePrize).outerjoin(Raffle, Raffle.id == RafflePrize.raffle_id).filter(Raffle.id.is_(None)),
        ))

        # Unreferenced cached resources.
        stale_resources = []
        for resource in db.query(CachedResource).all():
            if resource.entity_type == "creature" and resource.entity_id:
                if not db.query(Creature).filter(Creature.id == resource.entity_id).first() and resource.status != "ready":
                    stale_resources.append(resource.id)
            elif resource.entity_id is None:
                stale_resources.append(resource.id)

        total_candidates = 0
        print(f"[INFO] cutoff_utc={cutoff.isoformat()} dry_run={dry_run}")
        for name, query in tasks:
            count = query.count()
            total_candidates += count
            print(f"[PLAN] {name}: {count}")

        print(f"[PLAN] cached_resources_unreferenced: {len(stale_resources)}")
        total_candidates += len(stale_resources)

        if dry_run:
            print(f"[DRY-RUN] total_candidates={total_candidates}")
            return 0

        if not args.yes:
            print("[ABORT] Refusing to delete without --yes")
            return 1

        deleted_total = 0
        for name, query in tasks:
            records = query.all()
            for record in records:
                db.delete(record)
            deleted_total += len(records)
            print(f"[DELETE] {name}: {len(records)}")

        if stale_resources:
            rows = db.query(CachedResource).filter(CachedResource.id.in_(stale_resources)).all()
            for row in rows:
                if row.local_path and os.path.exists(row.local_path):
                    try:
                        os.remove(row.local_path)
                    except OSError:
                        pass
                db.delete(row)
            deleted_total += len(rows)
            print(f"[DELETE] cached_resources_unreferenced: {len(rows)}")

        db.commit()
        print(f"[DONE] deleted_total={deleted_total}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
