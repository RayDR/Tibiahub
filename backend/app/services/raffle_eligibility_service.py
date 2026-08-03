from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.models.guild_management import GuildRosterCharacter
from app.models.raffle import Raffle, RaffleEligibilityEntry, RaffleEligibilitySnapshot, RaffleParticipant
from app.models.user import User
from app.services.guild_roster_service import normalize_guild_identity
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
    "test_override_excluded": "Excluded by an audited test override",
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
        "participant_id": item.get("participant_id"),
        "guild_roster_character_id": item.get("guild_roster_character_id"),
        "character_name": item.get("character_name"),
        "normalized_character_name": item.get("normalized_character_name"),
        "known_account_identity_key": item.get("known_account_identity_key"),
        "guild_name": item.get("guild_name"),
        "guild_rank": item.get("guild_rank"),
        "last_activity_at": as_utc(item.get("last_activity_at")).isoformat() if item.get("last_activity_at") else None,
        "is_eligible": item["is_eligible"],
        "exclusion_code": item.get("exclusion_code"),
        "weight_snapshot": str(item.get("weight_snapshot", 1)),
    } for item in sorted(entries, key=lambda row: (row.get("normalized_character_name") or "", row.get("user_id") or 0))]
    payload = {"raffle_id": raffle_id, "cutoff_at": as_utc(cutoff_at).isoformat(), "entries": canonical_entries}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class RaffleEligibilityService:
    @staticmethod
    def _preview_selected_participants(db: Session, raffle: Raffle, cutoff_at: datetime) -> list[dict]:
        active = sorted(
            db.query(RaffleParticipant).options(
                selectinload(RaffleParticipant.user),
                selectinload(RaffleParticipant.guild_roster_character),
            ).filter(
                RaffleParticipant.raffle_id == raffle.id,
                RaffleParticipant.is_deleted.is_(False),
            ).all(),
            key=lambda row: row.normalized_character_name,
        )
        linked_user_ids = {participant.user_id for participant in active if participant.user_id is not None}
        account_activity: dict[int, datetime] = {}
        if linked_user_ids:
            rows = db.query(GuildRosterCharacter).filter(
                GuildRosterCharacter.normalized_guild_name == normalize_guild_identity(raffle.guild_name),
                GuildRosterCharacter.is_current.is_(True),
                GuildRosterCharacter.linked_user_id.in_(linked_user_ids),
                GuildRosterCharacter.last_activity_at.isnot(None),
            ).all()
            for row in rows:
                activity = as_utc(row.last_activity_at)
                if activity and (row.linked_user_id not in account_activity or activity > account_activity[row.linked_user_id]):
                    account_activity[row.linked_user_id] = activity
        entries = []
        seen_accounts: set[str] = set()
        for participant in active:
            activity = account_activity.get(participant.user_id) if participant.user_id is not None else None
            activity = activity or (
                participant.guild_roster_character.last_activity_at
                if participant.guild_roster_character else participant.user.last_login_at if participant.user else None
            )
            exclusion_code = None
            if not participant.is_eligible:
                exclusion_code = "test_override_excluded"
            elif participant.user is not None and not participant.user.is_active:
                exclusion_code = "inactive_account"
            elif participant.user is not None and participant.user.username.casefold().startswith("guest_"):
                exclusion_code = "guest_account"
            elif activity is None:
                exclusion_code = "missing_activity"
            elif as_utc(activity) < cutoff_at:
                exclusion_code = "stale_activity"
            elif (
                raffle.unique_account_participation
                and participant.known_account_identity_key
                and participant.known_account_identity_key in seen_accounts
            ):
                exclusion_code = "duplicate_account"
            if participant.eligibility_override is True and exclusion_code in {"missing_activity", "stale_activity"}:
                exclusion_code = None
            elif participant.eligibility_override is False and exclusion_code is None:
                exclusion_code = "test_override_excluded"
            if participant.known_account_identity_key:
                seen_accounts.add(participant.known_account_identity_key)
            entries.append({
                "participant_id": participant.id,
                "user_id": participant.user_id,
                "guild_roster_character_id": participant.guild_roster_character_id,
                "character_name": participant.character_name,
                "normalized_character_name": participant.normalized_character_name,
                "known_account_identity_key": participant.known_account_identity_key,
                "guild_name": participant.guild_name_snapshot or raffle.guild_name,
                "world_name": participant.world_name_snapshot,
                "guild_rank": participant.guild_rank,
                "weight_snapshot": 1 if raffle.weighting_mode == "equal" else participant.weight,
                "last_activity_at": as_utc(activity),
                "is_eligible": exclusion_code is None,
                "exclusion_code": exclusion_code,
                "exclusion_summary": participant.eligibility_override_reason if exclusion_code == "test_override_excluded" else EXCLUSION_SUMMARIES.get(exclusion_code),
                "source_data": {"participant_source": participant.source, "account_identity_known": participant.known_account_identity_key is not None},
            })
        return entries

    @staticmethod
    async def preview(db: Session, raffle: Raffle) -> dict:
        if raffle.purpose not in {"test", "real"}:
            raise RaffleEligibilityError("unsupported_raffle", "Eligibility snapshots require a test or real automatic raffle")
        if raffle.run_mode != "automatic" or raffle.access_mode != "guild_only":
            raise RaffleEligibilityError("invalid_raffle_mode", "Automatic eligibility requires a guild-only automatic raffle")

        # Manual-trigger automatic draws use the trigger-time preview as their
        # effective draw time; scheduled draws retain their configured instant.
        effective_draw_at = raffle.scheduled_run_at or utc_now()
        cutoff_at = raffle.eligibility_cutoff_at or compute_eligibility_cutoff(
            effective_draw_at, raffle.timezone_name, raffle.eligibility_days,
        )
        selected_entries = RaffleEligibilityService._preview_selected_participants(db, raffle, cutoff_at)
        if selected_entries:
            eligible_count = sum(1 for entry in selected_entries if entry["is_eligible"])
            return {
                "raffle_id": raffle.id, "cutoff_at": cutoff_at,
                "timezone_name": raffle.timezone_name, "eligibility_days": raffle.eligibility_days,
                "candidate_count": len(selected_entries), "eligible_count": eligible_count,
                "excluded_count": len(selected_entries) - eligible_count,
                "snapshot_hash": _snapshot_hash(selected_entries, raffle_id=raffle.id, cutoff_at=cutoff_at),
                "entries": selected_entries, "persisted": False, "snapshot_id": None,
            }
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
        participant_overrides = {
            participant.user_id: participant
            for participant in raffle.participants
            if raffle.purpose == "test" and not participant.is_deleted and participant.eligibility_override is not None
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
            selected_character = None
            if user.id in seen:
                exclusion_code = "duplicate_account"
            elif not user.is_active:
                exclusion_code = "inactive_account"
            elif user.username.casefold().startswith("guest_"):
                exclusion_code = "guest_account"
            else:
                characters = [
                    character for character in user.characters
                    if character.character_name and character.ownership_status == "verified"
                ]
                for candidate in characters:
                    current = member_lookup.get(candidate.character_name.strip().casefold())
                    if current:
                        selected_character = candidate
                        character_name = current.get("name") or candidate.character_name
                        member_data = current
                        break
                if not characters:
                    exclusion_code = "no_linked_character"
                elif not character_name:
                    exclusion_code = "not_guild_member"
                elif user.last_login_at is None:
                    exclusion_code = "missing_activity"
                elif as_utc(user.last_login_at) < cutoff_at:
                    exclusion_code = "stale_activity"

            override = participant_overrides.get(user.id)
            if override and override.eligibility_override is True and exclusion_code in {"missing_activity", "stale_activity"}:
                exclusion_code = None
            elif override and override.eligibility_override is False and exclusion_code is None:
                exclusion_code = "test_override_excluded"

            seen.add(user.id)
            entries.append({
                "participant_id": None,
                "user_id": user.id,
                "guild_roster_character_id": None,
                "character_name": character_name,
                "normalized_character_name": (character_name or f"user-{user.id}").strip().casefold(),
                "known_account_identity_key": f"user:{user.id}",
                "guild_name": raffle.guild_name if character_name else None,
                "world_name": selected_character.world_name if selected_character else None,
                "guild_rank": (member_data or {}).get("rank") or (member_data or {}).get("title") or (member_data or {}).get("position"),
                "weight_snapshot": 1,
                "last_activity_at": as_utc(user.last_login_at),
                "is_eligible": exclusion_code is None,
                "exclusion_code": exclusion_code,
                "exclusion_summary": (
                    override.eligibility_override_reason
                    if override and exclusion_code == "test_override_excluded"
                    else EXCLUSION_SUMMARIES.get(exclusion_code) if exclusion_code else None
                ),
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
            raise RaffleEligibilityError("insufficient_eligible_participants", "At least two eligible participants are required")
        next_number = (db.query(func.max(RaffleEligibilitySnapshot.snapshot_number))
                       .filter(RaffleEligibilitySnapshot.raffle_id == raffle.id).scalar() or 0) + 1
        snapshot = RaffleEligibilitySnapshot(
            raffle_id=raffle.id,
            snapshot_number=next_number,
            cutoff_at=preview["cutoff_at"],
            timezone_name=preview["timezone_name"],
            eligibility_days=preview["eligibility_days"],
            source="persisted_raffle_participants",
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
