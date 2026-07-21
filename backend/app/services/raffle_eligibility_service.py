from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.models.raffle import Raffle, RaffleEligibilityEntry, RaffleEligibilitySnapshot
from app.models.user import User
from app.services.tibia_api import get_guild_info


EXCLUSION_SUMMARIES = {
    "inactive_account": "Account is inactive",
    "guest_account": "Guest accounts are not eligible",
    "no_linked_character": "No linked character belongs to the raffle guild",
    "not_guild_member": "No linked character is a current guild member",
    "stale_activity": "Activity is older than the eligibility cutoff",
    "duplicate_account": "Account already appears in the candidate set",
    "missing_activity": "No qualifying activity timestamp is available",
    "guild_source_unavailable": "Current guild membership could not be verified",
}


class RaffleEligibilityError(ValueError):
    def __init__(self, code: str, summary: str):
        super().__init__(summary)
        self.code = code
        self.summary = summary


def utc_now() -> datetime:
    return datetime.now(UTC)


def as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def compute_eligibility_cutoff(scheduled_run_at: datetime, timezone_name: str, eligibility_days: int) -> datetime:
    if not scheduled_run_at:
        raise RaffleEligibilityError("missing_schedule", "A scheduled draw time is required")
    try:
        timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise RaffleEligibilityError("invalid_timezone", "The configured timezone is invalid") from exc
    scheduled_utc = as_utc(scheduled_run_at)
    local_draw = scheduled_utc.astimezone(timezone)
    local_cutoff = local_draw - timedelta(days=eligibility_days)
    return local_cutoff.astimezone(UTC)


def _snapshot_hash(entries: list[dict], *, raffle_id: int, cutoff_at: datetime) -> str:
    canonical_entries = [{
        "user_id": item["user_id"],
        "character_name": item.get("character_name"),
        "guild_name": item.get("guild_name"),
        "guild_rank": item.get("guild_rank"),
        "last_activity_at": as_utc(item.get("last_activity_at")).isoformat() if item.get("last_activity_at") else None,
        "is_eligible": item["is_eligible"],
        "exclusion_code": item.get("exclusion_code"),
    } for item in sorted(entries, key=lambda row: row["user_id"])]
    payload = {"raffle_id": raffle_id, "cutoff_at": as_utc(cutoff_at).isoformat(), "entries": canonical_entries}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class RaffleEligibilityService:
    @staticmethod
    async def preview(db: Session, raffle: Raffle) -> dict:
        if raffle.purpose not in {"test", "real"}:
            raise RaffleEligibilityError("unsupported_raffle", "Eligibility snapshots require a test or real automatic raffle")
        if raffle.run_mode != "automatic" or raffle.access_mode != "guild_only":
            raise RaffleEligibilityError("invalid_raffle_mode", "Automatic eligibility requires a guild-only automatic raffle")

        cutoff_at = raffle.eligibility_cutoff_at or compute_eligibility_cutoff(
            raffle.scheduled_run_at, raffle.timezone_name, raffle.eligibility_days,
        )
        try:
            guild_info = await get_guild_info(raffle.guild_name)
        except Exception as exc:
            raise RaffleEligibilityError("guild_source_unavailable", "Current guild membership is unavailable") from exc
        if not guild_info:
            raise RaffleEligibilityError("guild_source_unavailable", "Current guild membership is unavailable")

        member_lookup = {
            (member.get("name") or "").strip().casefold(): member
            for member in guild_info.get("members", [])
            if (member.get("name") or "").strip()
        }
        user_query = db.query(User).options(selectinload(User.characters))
        explicit_test_user_ids = {
            participant.user_id for participant in raffle.participants
            if raffle.purpose == "test" and not participant.is_deleted
        }
        if explicit_test_user_ids:
            user_query = user_query.filter(User.id.in_(explicit_test_user_ids))
        users = user_query.order_by(User.id).all()
        entries: list[dict] = []
        seen: set[int] = set()
        for user in users:
            exclusion_code = None
            character_name = None
            member_data = None
            if user.id in seen:
                exclusion_code = "duplicate_account"
            elif not user.is_active:
                exclusion_code = "inactive_account"
            elif user.username.casefold().startswith("guest_"):
                exclusion_code = "guest_account"
            else:
                names: list[str] = []
                if user.tibia_character_name:
                    names.append(user.tibia_character_name)
                names.extend(character.character_name for character in user.characters if character.character_name)
                for name in names:
                    current = member_lookup.get(name.strip().casefold())
                    if current:
                        character_name = current.get("name") or name
                        member_data = current
                        break
                if not names:
                    exclusion_code = "no_linked_character"
                elif not character_name:
                    exclusion_code = "not_guild_member"
                elif user.last_login_at is None:
                    exclusion_code = "missing_activity"
                elif as_utc(user.last_login_at) < cutoff_at:
                    exclusion_code = "stale_activity"

            seen.add(user.id)
            entries.append({
                "user_id": user.id,
                "character_name": character_name,
                "guild_name": raffle.guild_name if character_name else None,
                "guild_rank": (member_data or {}).get("rank") or (member_data or {}).get("title") or (member_data or {}).get("position"),
                "last_activity_at": as_utc(user.last_login_at),
                "is_eligible": exclusion_code is None,
                "exclusion_code": exclusion_code,
                "exclusion_summary": EXCLUSION_SUMMARIES.get(exclusion_code) if exclusion_code else None,
                "source_data": member_data,
            })

        eligible_count = sum(1 for entry in entries if entry["is_eligible"])
        return {
            "raffle_id": raffle.id,
            "cutoff_at": cutoff_at,
            "timezone_name": raffle.timezone_name,
            "eligibility_days": raffle.eligibility_days,
            "candidate_count": len(entries),
            "eligible_count": eligible_count,
            "excluded_count": len(entries) - eligible_count,
            "snapshot_hash": _snapshot_hash(entries, raffle_id=raffle.id, cutoff_at=cutoff_at),
            "entries": entries,
            "persisted": False,
            "snapshot_id": None,
        }

    @staticmethod
    async def freeze(db: Session, raffle: Raffle, actor: User) -> RaffleEligibilitySnapshot:
        preview = await RaffleEligibilityService.preview(db, raffle)
        if preview["eligible_count"] < 2:
            raise RaffleEligibilityError("insufficient_eligible_accounts", "At least two eligible accounts are required")
        next_number = (db.query(func.max(RaffleEligibilitySnapshot.snapshot_number))
                       .filter(RaffleEligibilitySnapshot.raffle_id == raffle.id).scalar() or 0) + 1
        snapshot = RaffleEligibilitySnapshot(
            raffle_id=raffle.id,
            snapshot_number=next_number,
            cutoff_at=preview["cutoff_at"],
            timezone_name=preview["timezone_name"],
            eligibility_days=preview["eligibility_days"],
            source="tibiadata_guild_and_user_last_login_at",
            candidate_count=preview["candidate_count"],
            eligible_count=preview["eligible_count"],
            excluded_count=preview["excluded_count"],
            snapshot_hash=preview["snapshot_hash"],
            created_by_id=actor.id,
        )
        db.add(snapshot)
        db.flush()
        for item in preview["entries"]:
            db.add(RaffleEligibilityEntry(snapshot_id=snapshot.id, **item))
        raffle.eligibility_cutoff_at = preview["cutoff_at"]
        db.flush()
        return snapshot
