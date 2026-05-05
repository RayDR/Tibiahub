#!/usr/bin/env python3
"""Clean raffle-related test data while preserving the real Bloodborne raffle."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_ROOT = PROJECT_ROOT / "backend"
os.chdir(BACKEND_ROOT)
sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy.orm import Session

from app.db.database import SessionLocal, init_db
from app.models.events import Event
from app.models.guild import Announcement, GuildEvent
from app.models.raffle import Raffle, RaffleParticipant, RafflePrize, RaffleWinner
from app.models.user_character import UserCharacter
from app.services.tibia_api import get_guild_info


KEEP_GUILD_NAME = "Bloodborne Warhowl"
KEEP_RAFFLE_TITLE = "Double XP - Mayo 26"
KEEP_ANNOUNCEMENT_TITLE = f"Raffle: {KEEP_RAFFLE_TITLE}"
FAKE_GUILD_NAMES = {"testguild", "bald dwarfs"}
TEST_MARKERS = (
    "test",
    "tmp",
    "mock",
    "demo",
    "runtime",
    "seed",
    "check",
    "leader_",
    "user_",
    "admin-",
    "leader-",
)


@dataclass
class CleanupPlan:
    protected: list[str] = field(default_factory=list)
    normalize_protected_raffles: list[tuple[Raffle, str]] = field(default_factory=list)
    delete_user_characters: list[tuple[UserCharacter, str]] = field(default_factory=list)
    soft_delete_raffles: list[tuple[Raffle, str]] = field(default_factory=list)
    soft_delete_participants: list[tuple[RaffleParticipant, str]] = field(default_factory=list)
    hard_delete_prizes: list[tuple[RafflePrize, str]] = field(default_factory=list)
    hard_delete_winners: list[tuple[RaffleWinner, str]] = field(default_factory=list)
    soft_delete_events: list[tuple[Event, str]] = field(default_factory=list)
    soft_delete_guild_events: list[tuple[GuildEvent, str]] = field(default_factory=list)
    soft_delete_announcements: list[tuple[Announcement, str]] = field(default_factory=list)


def looks_like_test(value: str | None) -> bool:
    if not value:
        return False
    lowered = value.strip().lower()
    return any(marker in lowered for marker in TEST_MARKERS)


async def build_plan(db: Session) -> CleanupPlan:
    guild_info = await get_guild_info(KEEP_GUILD_NAME)
    if not guild_info:
        raise RuntimeError(f"Unable to fetch guild data for '{KEEP_GUILD_NAME}'")

    real_members = {
        (member.get("name") or "").strip().lower()
        for member in (guild_info.get("members") or [])
        if (member.get("name") or "").strip()
    }
    plan = CleanupPlan()

    protected_raffles = db.query(Raffle).filter(
        Raffle.title == KEEP_RAFFLE_TITLE,
        Raffle.guild_name == KEEP_GUILD_NAME,
        Raffle.is_deleted == False,
    ).all()
    protected_raffle_ids = {raffle.id for raffle in protected_raffles}
    if not protected_raffle_ids:
        raise RuntimeError(f"Protected raffle '{KEEP_RAFFLE_TITLE}' was not found")

    for raffle in protected_raffles:
        plan.protected.append(f"Raffle #{raffle.id} '{raffle.title}'")
        if raffle.status != "open" or getattr(raffle, "access_mode", None) != "guild_only" or getattr(raffle, "show_participants", True) is not True:
            plan.normalize_protected_raffles.append((raffle, "normalize protected raffle to open/guild_only/show_participants"))

    for character in db.query(UserCharacter).order_by(UserCharacter.id).all():
        guild_name = (character.guild_name or "").strip().lower()
        if guild_name and guild_name != KEEP_GUILD_NAME.lower() and (guild_name in FAKE_GUILD_NAMES or looks_like_test(character.character_name)):
            plan.delete_user_characters.append((character, f"character guild '{character.guild_name}' is not real"))

    for raffle in db.query(Raffle).filter(Raffle.is_deleted == False).order_by(Raffle.id).all():
        if raffle.id in protected_raffle_ids:
            continue
        plan.soft_delete_raffles.append((raffle, "non-protected raffle"))

    protected_participants = db.query(RaffleParticipant).filter(RaffleParticipant.raffle_id.in_(protected_raffle_ids)).all()
    for participant in protected_participants:
        if participant.is_deleted:
            continue
        if (participant.character_name or "").strip().lower() not in real_members:
            plan.soft_delete_participants.append((participant, "character is not a current Bloodborne Warhowl member"))
        else:
            plan.protected.append(f"Participant #{participant.id} '{participant.character_name}'")

    for participant in (
        db.query(RaffleParticipant)
        .filter(RaffleParticipant.raffle_id.notin_(protected_raffle_ids), RaffleParticipant.is_deleted == False)
        .all()
    ):
        plan.soft_delete_participants.append((participant, "participant belongs to non-protected raffle"))

    for prize in db.query(RafflePrize).order_by(RafflePrize.id).all():
        if prize.raffle_id in protected_raffle_ids:
            plan.protected.append(f"Prize #{prize.id} '{prize.name}'")
            continue
        plan.hard_delete_prizes.append((prize, "prize belongs to non-protected raffle"))

    for winner in db.query(RaffleWinner).order_by(RaffleWinner.id).all():
        if winner.raffle_id in protected_raffle_ids:
            plan.protected.append(f"Winner #{winner.id} run={winner.run_number}")
            continue
        plan.hard_delete_winners.append((winner, "winner history belongs to non-protected raffle"))

    for event in db.query(Event).filter(Event.is_deleted == False).order_by(Event.id).all():
        keep_event = event.type == "raffle" and event.title == KEEP_RAFFLE_TITLE and (event.guild_name or "") == KEEP_GUILD_NAME
        if keep_event:
            plan.protected.append(f"Event #{event.id} '{event.title}'")
            continue
        plan.soft_delete_events.append((event, "non-protected contest/event/raffle"))

    for guild_event in db.query(GuildEvent).filter(GuildEvent.is_deleted == False).order_by(GuildEvent.id).all():
        plan.soft_delete_guild_events.append((guild_event, "guild event is not part of protected raffle scope"))

    for announcement in db.query(Announcement).filter(Announcement.is_deleted == False).order_by(Announcement.id).all():
        if announcement.title == KEEP_ANNOUNCEMENT_TITLE:
            plan.protected.append(f"Announcement #{announcement.id} '{announcement.title}'")
            continue
        plan.soft_delete_announcements.append((announcement, "announcement is outside protected raffle scope"))

    return plan


def print_plan(plan: CleanupPlan) -> None:
    print("\nDRY RUN" if os.environ.get("TIBIAHUB_CLEANUP_MODE") != "live" else "\nLIVE RUN")
    print("=" * 72)
    print("Protected rows:")
    for item in plan.protected:
        print(f"  KEEP  {item}")

    sections = [
        ("Protected raffles to normalize", plan.normalize_protected_raffles, lambda row, reason: f"Raffle #{row.id} {row.title} -> {reason}"),
        ("User characters to delete", plan.delete_user_characters, lambda row, reason: f"UserCharacter #{row.id} {row.character_name} -> {reason}"),
        ("Raffles to soft-delete", plan.soft_delete_raffles, lambda row, reason: f"Raffle #{row.id} {row.title} -> {reason}"),
        ("Participants to soft-delete", plan.soft_delete_participants, lambda row, reason: f"Participant #{row.id} {row.character_name} -> {reason}"),
        ("Prizes to hard-delete", plan.hard_delete_prizes, lambda row, reason: f"Prize #{row.id} {row.name} -> {reason}"),
        ("Winners to hard-delete", plan.hard_delete_winners, lambda row, reason: f"Winner #{row.id} raffle={row.raffle_id} -> {reason}"),
        ("Events to soft-delete", plan.soft_delete_events, lambda row, reason: f"Event #{row.id} {row.title} -> {reason}"),
        ("Guild events to soft-delete", plan.soft_delete_guild_events, lambda row, reason: f"GuildEvent #{row.id} {row.title} -> {reason}"),
        ("Announcements to soft-delete", plan.soft_delete_announcements, lambda row, reason: f"Announcement #{row.id} {row.title} -> {reason}"),
    ]

    total = 0
    for title, items, formatter in sections:
        print(f"\n{title}: {len(items)}")
        for row, reason in items:
            total += 1
            print(f"  DELETE {formatter(row, reason)}")

    print("\n" + "=" * 72)
    print(f"Total planned operations: {total}")


def apply_plan(db: Session, plan: CleanupPlan) -> None:
    now = datetime.now(UTC)

    for raffle, _ in plan.normalize_protected_raffles:
        raffle.status = "open"
        raffle.access_mode = "guild_only"
        raffle.show_participants = True
        raffle.visibility = "private"
        raffle.registration_enabled = True
        raffle.is_active = True

    for character, _ in plan.delete_user_characters:
        db.delete(character)

    for raffle, reason in plan.soft_delete_raffles:
        raffle.is_deleted = True
        raffle.deleted_at = now
        raffle.delete_reason = f"cleanup_raffle_test_data: {reason}"
        raffle.status = "deleted"
        raffle.is_active = False

    for participant, reason in plan.soft_delete_participants:
        participant.is_deleted = True
        participant.deleted_at = now
        participant.delete_reason = f"cleanup_raffle_test_data: {reason}"
        participant.is_eligible = False

    for prize, _ in plan.hard_delete_prizes:
        db.delete(prize)

    for winner, _ in plan.hard_delete_winners:
        db.delete(winner)

    for event, reason in plan.soft_delete_events:
        event.is_deleted = True
        event.deleted_at = now
        event.delete_reason = f"cleanup_raffle_test_data: {reason}"
        event.is_active = False
        event.registration_enabled = False
        if event.status != "completed":
            event.status = "cancelled"

    for guild_event, reason in plan.soft_delete_guild_events:
        guild_event.is_deleted = True
        guild_event.deleted_at = now
        guild_event.delete_reason = f"cleanup_raffle_test_data: {reason}"

    for announcement, reason in plan.soft_delete_announcements:
        announcement.is_deleted = True
        announcement.deleted_at = now
        announcement.delete_reason = f"cleanup_raffle_test_data: {reason}"

    db.commit()


def main() -> int:
    parser = argparse.ArgumentParser(description="Clean raffle-related test data from the real database.")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes only")
    parser.add_argument("--yes", action="store_true", help="Apply the cleanup")
    args = parser.parse_args()

    if not args.dry_run and not args.yes:
        parser.error("Use --dry-run to preview or --yes to apply changes")

    init_db()
    db = SessionLocal()
    try:
        if args.yes:
            os.environ["TIBIAHUB_CLEANUP_MODE"] = "live"
        plan = asyncio.run(build_plan(db))
        print_plan(plan)
        if args.dry_run:
            print("\nDry run complete. No rows were changed.")
            return 0
        apply_plan(db, plan)
        print("\nCleanup complete.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())