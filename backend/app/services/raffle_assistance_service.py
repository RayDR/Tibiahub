"""Audited global-administrator assistance for safe raffle rescheduling."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session, selectinload

from app.models.raffle import Raffle, RaffleEligibilitySnapshot, RafflePrizeDelivery, RaffleRun, RaffleRunResult, RaffleWinner
from app.models.user import User
from app.models.workspace_audit import WorkspaceAudit
from app.services.notification_service import NotificationService


PUBLIC_CODE = re.compile(r"^[A-Za-z0-9]{6}$")


class RaffleAssistanceError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class RaffleAssistanceService:
    @staticmethod
    def extract_identifier(value: str) -> tuple[str, str | int]:
        raw = (value or "").strip()
        if raw.isdigit():
            return "id", int(raw)
        if "://" in raw:
            parts = [part for part in urlparse(raw).path.split("/") if part]
            raw = parts[-1] if parts else ""
        if not PUBLIC_CODE.fullmatch(raw):
            raise RaffleAssistanceError("invalid_public_code", "Enter a six-character public code, raffle ID, or public raffle URL")
        return "code", raw.casefold()

    @classmethod
    def lookup(cls, db: Session, identifier: str) -> Raffle:
        kind, value = cls.extract_identifier(identifier)
        query = db.query(Raffle).options(
            selectinload(Raffle.eligibility_snapshots), selectinload(Raffle.scheduler_attempts),
        )
        row = query.filter(Raffle.id == value).first() if kind == "id" else query.filter(Raffle.public_code.ilike(str(value))).first()
        if row is None:
            raise RaffleAssistanceError("raffle_not_found", "Raffle not found")
        return row

    @staticmethod
    def safety(db: Session, raffle: Raffle) -> tuple[bool, str | None]:
        if raffle.is_deleted or raffle.archived_at is not None or raffle.status in {"archived", "deleted"}:
            return False, "raffle_archived_or_deleted"
        if raffle.execution_state in {"claimed", "running"}:
            return False, "execution_in_progress"
        if db.query(RaffleRun.id).filter(RaffleRun.raffle_id == raffle.id, RaffleRun.state == "succeeded").first():
            return False, "successful_run_exists"
        if db.query(RaffleWinner.id).filter(RaffleWinner.raffle_id == raffle.id).first():
            return False, "winner_history_exists"
        if db.query(RaffleRunResult.id).join(RaffleRun).filter(RaffleRun.raffle_id == raffle.id).first():
            return False, "immutable_result_exists"
        if db.query(RafflePrizeDelivery.id).filter(RafflePrizeDelivery.raffle_id == raffle.id).first():
            return False, "delivery_history_exists"
        return True, None

    @staticmethod
    def _snapshot_state(raffle: Raffle) -> dict:
        active = [row for row in raffle.eligibility_snapshots if row.invalidated_at is None]
        snapshot = max(active, key=lambda row: row.snapshot_number, default=None)
        if snapshot is None:
            return {"exists": False, "valid": True, "warning": None, "id": None}
        valid = (
            _utc(snapshot.cutoff_at) == _utc(raffle.eligibility_cutoff_at)
            and snapshot.timezone_name == raffle.timezone_name
            and snapshot.eligibility_days == raffle.eligibility_days
        )
        return {
            "exists": True, "valid": valid, "id": snapshot.id,
            "warning": "A frozen eligibility snapshot exists and will be preserved." if valid else "The frozen eligibility snapshot no longer matches current eligibility inputs.",
        }

    @classmethod
    def serialize(cls, db: Session, raffle: Raffle) -> dict:
        safe, reason = cls.safety(db, raffle)
        timezone_name = raffle.timezone_name or "America/Chicago"
        try:
            zone = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            zone = ZoneInfo("UTC")
        scheduled = _utc(raffle.scheduled_run_at)
        return {
            "id": raffle.id, "public_code": raffle.public_code, "title": raffle.title,
            "guild_name": raffle.guild_name, "purpose": raffle.purpose, "status": raffle.status,
            "execution_state": raffle.execution_state, "timezone_name": timezone_name,
            "scheduled_run_at_utc": scheduled, "scheduled_run_at_local": scheduled.astimezone(zone) if scheduled else None,
            "participant_count": len([row for row in raffle.participants if not row.is_deleted]),
            "version": raffle.version or 1, "safe_to_reschedule": safe, "unsafe_reason": reason,
            "eligibility_snapshot": cls._snapshot_state(raffle),
            "scheduler": {
                "job_id": raffle.scheduler_job_id, "claimed_at": raffle.claimed_at,
                "lease_expires_at": raffle.lease_expires_at, "next_retry_at": raffle.next_retry_at,
                "retry_count": raffle.retry_count, "attempt_count": len(raffle.scheduler_attempts),
                "last_error_code": raffle.last_error_code,
            },
        }

    @staticmethod
    def _localize(local_value: datetime, timezone_name: str) -> tuple[datetime, datetime]:
        try:
            zone = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError as exc:
            raise RaffleAssistanceError("invalid_timezone", "Unknown IANA timezone") from exc
        naive = local_value.replace(tzinfo=None)
        aware = naive.replace(tzinfo=zone, fold=0)
        roundtrip = aware.astimezone(UTC).astimezone(zone).replace(tzinfo=None)
        if roundtrip != naive:
            raise RaffleAssistanceError("nonexistent_local_time", "The local time does not exist because of a daylight-saving transition")
        alternative = naive.replace(tzinfo=zone, fold=1)
        if aware.utcoffset() != alternative.utcoffset():
            raise RaffleAssistanceError("ambiguous_local_time", "The local time is ambiguous because of a daylight-saving transition")
        return aware, aware.astimezone(UTC)

    @classmethod
    def reschedule(
        cls, db: Session, *, public_code: str, actor: User, local_scheduled_at: datetime,
        timezone_name: str, expected_version: int, reason: str, explicit_confirmation: bool,
        snapshot_decision: str,
    ) -> tuple[Raffle, WorkspaceAudit]:
        if not explicit_confirmation:
            raise RaffleAssistanceError("confirmation_required", "Explicit confirmation is required")
        if len(reason.strip()) < 5:
            raise RaffleAssistanceError("reason_required", "A meaningful audit reason is required")
        if not PUBLIC_CODE.fullmatch(public_code or ""):
            raise RaffleAssistanceError("invalid_public_code", "Invalid public code")
        raffle = db.query(Raffle).options(
            selectinload(Raffle.eligibility_snapshots), selectinload(Raffle.scheduler_attempts),
        ).filter(Raffle.public_code.ilike(public_code)).with_for_update().one_or_none()
        if raffle is None:
            raise RaffleAssistanceError("raffle_not_found", "Raffle not found")
        safe, unsafe_reason = cls.safety(db, raffle)
        if not safe:
            raise RaffleAssistanceError(unsafe_reason or "unsafe_reschedule", "Raffle cannot be safely rescheduled")
        if (raffle.version or 1) != expected_version:
            raise RaffleAssistanceError("optimistic_conflict", "Raffle changed after it was loaded")
        new_local, new_utc = cls._localize(local_scheduled_at, timezone_name)
        if new_utc <= datetime.now(UTC):
            raise RaffleAssistanceError("schedule_in_past", "The new schedule must be in the future")
        old_utc = _utc(raffle.scheduled_run_at)
        try:
            old_zone = ZoneInfo(raffle.timezone_name or timezone_name)
        except ZoneInfoNotFoundError as exc:
            raise RaffleAssistanceError("invalid_existing_timezone", "The raffle has an invalid stored timezone") from exc
        old_local = old_utc.astimezone(old_zone) if old_utc else None
        snapshot_state = cls._snapshot_state(raffle)
        if snapshot_state["exists"] and not snapshot_state["valid"] and snapshot_decision != "invalidate":
            raise RaffleAssistanceError("snapshot_decision_required", "The mismatched frozen snapshot must be explicitly invalidated")
        invalidated_snapshot_id = None
        if snapshot_state["exists"] and snapshot_decision == "invalidate":
            snapshot = db.get(RaffleEligibilitySnapshot, snapshot_state["id"])
            snapshot.invalidated_at = datetime.now(UTC); snapshot.invalidated_by_id = actor.id
            snapshot.invalidation_reason = reason.strip(); invalidated_snapshot_id = snapshot.id
        old_scheduler = raffle.execution_state
        raffle.scheduled_run_at = new_utc
        raffle.timezone_name = timezone_name
        raffle.claim_token = None; raffle.claimed_at = None; raffle.lease_expires_at = None; raffle.next_retry_at = None
        raffle.execution_state = "pending"
        raffle.last_error_code = None; raffle.last_error_summary = None
        raffle.version = (raffle.version or 1) + 1
        audit = WorkspaceAudit(
            actor_id=actor.id, workspace_type="admin_guild_assist", guild_name=raffle.guild_name,
            action="raffle_schedule_rescheduled", target_type="raffle", target_id=str(raffle.id), assisted=True,
            safe_metadata={
                "public_code": raffle.public_code, "old_utc": old_utc.isoformat() if old_utc else None,
                "new_utc": new_utc.isoformat(), "old_local": old_local.isoformat() if old_local else None,
                "new_local": new_local.isoformat(), "timezone": timezone_name, "reason": reason.strip(),
                "scheduler_state_from": old_scheduler, "scheduler_state_to": "pending",
                "snapshot_decision": snapshot_decision, "invalidated_snapshot_id": invalidated_snapshot_id,
            },
        )
        db.add(audit); db.flush()
        NotificationService.emit(db, raffle, "raffle_rescheduled", f"raffle:{raffle.id}:rescheduled:{raffle.version}", payload={"scheduled_at": new_local.isoformat()})
        return raffle, audit
