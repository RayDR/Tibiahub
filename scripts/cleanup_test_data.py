#!/usr/bin/env python3
"""
Cleanup test/mock data from the TibiaHub production database.

Usage:
  python scripts/cleanup_test_data.py --dry-run   # Preview only (default)
  python scripts/cleanup_test_data.py --yes        # Actually delete

Rules:
  - NEVER deletes the raffle titled "Double XP - Mayo 26" for guild "BLOODBORNE WARHOWL"
  - NEVER deletes real users
  - NEVER deletes "BLOODBORNE WARHOWL" guild data
  - Soft-deletes (is_deleted=True) where models support it, hard-deletes orphan rows
  - All deletes require explicit --yes flag
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from typing import List, Tuple

# Make sure backend package is importable when run from project root
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from sqlalchemy.orm import Session

from app.db.database import SessionLocal, engine
from app.models.raffle import Raffle, RaffleParticipant, RafflePrize, RaffleWinner
from app.models.guild import Announcement, GuildEvent, EventAttendance

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

KEEP_RAFFLE_TITLE = "Double XP - Mayo 26"
KEEP_GUILD_NAME = "BLOODBORNE WARHOWL"

# Heuristics: consider a row "test/mock" when it matches any of these patterns
TEST_PATTERNS = [
    "test", "mock", "demo", "seed", "fake", "placeholder",
    "lorem", "ipsum", "dummy", "example", "prueba", "ejemplo",
    "tmp_", "temp_", "debug_",
]


def looks_like_test(text: str) -> bool:
    if not text:
        return False
    lower = text.strip().lower()
    return any(p in lower for p in TEST_PATTERNS)


# ---------------------------------------------------------------------------
# Analysis helpers
# ---------------------------------------------------------------------------

Report = List[Tuple[str, str, str]]  # (model, identifier, reason)


def _is_protected_raffle(raffle: Raffle) -> bool:
    title_match = raffle.title.strip().lower() == KEEP_RAFFLE_TITLE.lower()
    guild_match = raffle.guild_name.strip().upper() == KEEP_GUILD_NAME.upper()
    return title_match and guild_match


def analyze_raffles(db: Session) -> Tuple[List[Raffle], Report]:
    """Return list of raffles to delete and human-readable report."""
    all_raffles = db.query(Raffle).filter(Raffle.is_deleted == False).all()
    to_delete: List[Raffle] = []
    report: Report = []

    for r in all_raffles:
        if _is_protected_raffle(r):
            report.append(("Raffle", f"#{r.id} '{r.title}'", "PROTECTED — kept"))
            continue

        reason = None
        if looks_like_test(r.title):
            reason = f"title looks like test data: '{r.title}'"
        elif looks_like_test(r.description or ""):
            reason = f"description looks like test data"
        elif r.guild_name.strip() and looks_like_test(r.guild_name):
            reason = f"guild_name looks like test data: '{r.guild_name}'"

        if reason:
            to_delete.append(r)
            report.append(("Raffle", f"#{r.id} '{r.title}' guild={r.guild_name}", f"DELETE — {reason}"))
        else:
            report.append(("Raffle", f"#{r.id} '{r.title}' guild={r.guild_name}", "KEEP — no test pattern found"))

    return to_delete, report


def analyze_events(db: Session) -> Tuple[List[GuildEvent], Report]:
    all_events = db.query(GuildEvent).filter(GuildEvent.is_deleted == False).all()
    to_delete: List[GuildEvent] = []
    report: Report = []

    for e in all_events:
        reason = None
        if looks_like_test(e.title):
            reason = f"title looks like test data: '{e.title}'"
        elif looks_like_test(e.description or ""):
            reason = "description looks like test data"

        if reason:
            to_delete.append(e)
            report.append(("GuildEvent", f"#{e.id} '{e.title}'", f"DELETE — {reason}"))
        else:
            report.append(("GuildEvent", f"#{e.id} '{e.title}'", "KEEP"))

    return to_delete, report


def analyze_announcements(db: Session) -> Tuple[List[Announcement], Report]:
    all_ann = db.query(Announcement).filter(Announcement.is_deleted == False).all()
    to_delete: List[Announcement] = []
    report: Report = []

    for a in all_ann:
        reason = None
        if looks_like_test(a.title or ""):
            reason = f"title looks like test data: '{a.title}'"
        elif looks_like_test(a.content or ""):
            reason = "content looks like test data"

        if reason:
            to_delete.append(a)
            report.append(("Announcement", f"#{a.id} '{a.title}'", f"DELETE — {reason}"))
        else:
            report.append(("Announcement", f"#{a.id} '{a.title}'", "KEEP"))

    return to_delete, report


def find_orphan_participants(db: Session) -> Tuple[List[RaffleParticipant], Report]:
    """Participants whose raffle was soft-deleted."""
    orphans = (
        db.query(RaffleParticipant)
        .join(Raffle, RaffleParticipant.raffle_id == Raffle.id)
        .filter(Raffle.is_deleted == True, RaffleParticipant.is_deleted == False)
        .all()
    )
    report: Report = [
        ("RaffleParticipant", f"#{p.id} raffle_id={p.raffle_id}", "DELETE — orphan (parent raffle deleted)")
        for p in orphans
    ]
    return orphans, report


# ---------------------------------------------------------------------------
# Execute
# ---------------------------------------------------------------------------

def run(dry_run: bool) -> None:
    db: Session = SessionLocal()
    try:
        print(f"\n{'DRY RUN — no changes will be made' if dry_run else 'LIVE RUN — deleting data'}\n")
        print("=" * 70)

        raffles_to_delete, raffle_report = analyze_raffles(db)
        events_to_delete, event_report = analyze_events(db)
        announcements_to_delete, ann_report = analyze_announcements(db)
        orphan_participants, op_report = find_orphan_participants(db)

        # Print full report
        for model_name, identifier, status in raffle_report + event_report + ann_report + op_report:
            marker = "⚠ " if status.startswith("DELETE") else ("✓ " if "PROTECTED" in status else "  ")
            print(f"  {marker}{model_name}: {identifier}")
            print(f"      → {status}")

        print("=" * 70)
        total_deletes = len(raffles_to_delete) + len(events_to_delete) + len(announcements_to_delete) + len(orphan_participants)
        print(f"\nSummary:")
        print(f"  Raffles to soft-delete:       {len(raffles_to_delete)}")
        print(f"  GuildEvents to delete:        {len(events_to_delete)}")
        print(f"  Announcements to deactivate:  {len(announcements_to_delete)}")
        print(f"  Orphan participants to clean:  {len(orphan_participants)}")
        print(f"  Total operations:              {total_deletes}")

        if total_deletes == 0:
            print("\n✅ Database is already clean. Nothing to do.")
            return

        if dry_run:
            print(f"\n🔒 DRY RUN complete. Run with --yes to apply {total_deletes} deletions.")
            return

        # === LIVE EXECUTION ===
        now = datetime.utcnow()

        for raffle in raffles_to_delete:
            raffle.is_deleted = True
            raffle.deleted_at = now
            raffle.delete_reason = "cleanup_test_data: identified as test/mock entry"
            raffle.status = "deleted"
            raffle.is_active = False

        for event in events_to_delete:
            event.is_deleted = True
            event.deleted_at = now
            event.delete_reason = "cleanup_test_data: identified as test/mock entry"

        for announcement in announcements_to_delete:
            announcement.is_deleted = True
            announcement.deleted_at = now
            announcement.delete_reason = "cleanup_test_data: identified as test/mock entry"

        for participant in orphan_participants:
            participant.is_deleted = True
            participant.deleted_at = now
            participant.delete_reason = "cleanup_test_data: orphan"

        db.commit()
        print(f"\n✅ Cleanup complete. {total_deletes} operations applied.")

    finally:
        db.close()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Cleanup test/mock data from TibiaHub database",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true", default=True, help="Preview only (default)")
    group.add_argument("--yes", action="store_true", default=False, help="Actually apply deletions")
    args = parser.parse_args()

    dry_run = not args.yes
    run(dry_run=dry_run)


if __name__ == "__main__":
    main()
