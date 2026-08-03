"""Durable application maintenance holds and terminal reconciliation."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.external_data import SyncJob
from app.models.maintenance_sync import MaintenanceHold
from app.models.user import User
from app.models.workspace_audit import WorkspaceAudit


TERMINAL_SYNC_STATES = {"completed", "completed_with_errors", "failed", "cancelled"}
DEFAULT_PUBLIC_MESSAGE = "TibiaHub is temporarily synchronizing game data. Please try again soon."


class MaintenanceModeError(ValueError):
    pass


class MaintenanceModeService:
    @staticmethod
    def active_holds(db: Session) -> list[MaintenanceHold]:
        return db.query(MaintenanceHold).filter(MaintenanceHold.released_at.is_(None)).order_by(MaintenanceHold.enabled_at, MaintenanceHold.id).all()

    @classmethod
    def status(cls, db: Session, *, include_private: bool = False) -> dict:
        holds = cls.active_holds(db)
        planned = [row.planned_end_at for row in holds if row.planned_end_at]
        public = {
            "active": bool(holds),
            "message": holds[0].public_message if holds else None,
            "started_at": min((row.enabled_at for row in holds), default=None),
            "planned_end_at": max(planned) if planned else None,
            "service_status": "maintenance" if holds else "online",
        }
        if include_private:
            public["holds"] = [cls.serialize(row) for row in holds]
        return public

    @staticmethod
    def serialize(row: MaintenanceHold) -> dict:
        return {
            "id": row.id, "hold_type": row.hold_type, "owner_job_id": row.owner_job_id,
            "reason": row.reason, "public_message": row.public_message,
            "enabled_at": row.enabled_at, "planned_end_at": row.planned_end_at,
            "auto_release": row.auto_release, "released_at": row.released_at,
            "release_reason": row.release_reason, "last_heartbeat_at": row.last_heartbeat_at,
            "safe_metadata": row.safe_metadata or {},
        }

    @staticmethod
    def _audit(db: Session, actor_id: int | None, action: str, hold: MaintenanceHold, metadata: dict | None = None) -> None:
        if actor_id is None:
            return
        db.add(WorkspaceAudit(
            actor_id=actor_id, workspace_type="admin", action=action,
            target_type="maintenance_hold", target_id=str(hold.id), assisted=False,
            safe_metadata={"hold_type": hold.hold_type, "owner_job_id": hold.owner_job_id, **(metadata or {})},
        ))

    @classmethod
    def enable_manual(
        cls, db: Session, *, actor: User, reason: str, public_message: str,
        planned_end_at: datetime | None, confirmation: str,
    ) -> MaintenanceHold:
        if confirmation != "ENABLE MAINTENANCE":
            raise MaintenanceModeError("Explicit maintenance confirmation is required")
        if len(reason.strip()) < 5 or len(public_message.strip()) < 5:
            raise MaintenanceModeError("A reason and safe public message are required")
        row = MaintenanceHold(
            hold_type="manual", reason=reason.strip(), public_message=public_message.strip() or DEFAULT_PUBLIC_MESSAGE,
            enabled_by_user_id=actor.id, planned_end_at=planned_end_at, auto_release=False,
            safe_metadata={"source": "admin_manual"},
        )
        db.add(row); db.flush()
        cls._audit(db, actor.id, "maintenance_manual_enabled", row, {"reason": reason.strip()})
        return row

    @classmethod
    def disable_manual(cls, db: Session, *, actor: User, reason: str, confirmation: str) -> list[MaintenanceHold]:
        if confirmation != "DISABLE MAINTENANCE":
            raise MaintenanceModeError("Explicit maintenance confirmation is required")
        if len(reason.strip()) < 5:
            raise MaintenanceModeError("A release reason is required")
        rows = db.query(MaintenanceHold).filter(
            MaintenanceHold.hold_type == "manual", MaintenanceHold.released_at.is_(None),
        ).with_for_update().all()
        if not rows:
            raise MaintenanceModeError("No active manual maintenance hold exists")
        now = datetime.now(UTC)
        for row in rows:
            row.released_at = now; row.released_by_user_id = actor.id; row.release_reason = reason.strip()
            cls._audit(db, actor.id, "maintenance_manual_disabled", row, {"reason": reason.strip()})
        return rows

    @classmethod
    def acquire_sync(cls, db: Session, *, job: SyncJob, actor_id: int | None, reason: str) -> MaintenanceHold:
        existing = db.query(MaintenanceHold).filter(MaintenanceHold.owner_job_id == job.id).one_or_none()
        if existing:
            if existing.released_at is not None:
                existing.released_at = None; existing.release_reason = None; existing.released_by_user_id = None
                cls._audit(db, actor_id, "maintenance_sync_acquired", existing, {"reacquired": True})
            existing.last_heartbeat_at = datetime.now(UTC)
            return existing
        row = MaintenanceHold(
            hold_type="sync", owner_job_id=job.id, reason=reason.strip(),
            public_message=DEFAULT_PUBLIC_MESSAGE, enabled_by_user_id=actor_id,
            auto_release=True, last_heartbeat_at=datetime.now(UTC), safe_metadata={"operation": job.operation_label or job.job_type},
        )
        db.add(row); db.flush()
        cls._audit(db, actor_id, "maintenance_sync_acquired", row)
        return row

    @classmethod
    def heartbeat_sync(cls, db: Session, job_id: str) -> None:
        row = db.query(MaintenanceHold).filter(
            MaintenanceHold.owner_job_id == job_id, MaintenanceHold.released_at.is_(None),
        ).one_or_none()
        if row:
            row.last_heartbeat_at = datetime.now(UTC)

    @classmethod
    def release_sync(cls, db: Session, *, job: SyncJob, reason: str) -> MaintenanceHold | None:
        row = db.query(MaintenanceHold).filter(
            MaintenanceHold.owner_job_id == job.id, MaintenanceHold.released_at.is_(None),
        ).with_for_update().one_or_none()
        if not row:
            return None
        row.released_at = datetime.now(UTC); row.release_reason = reason; row.last_heartbeat_at = row.released_at
        cls._audit(db, job.requested_by_user_id, "maintenance_sync_released", row, {"terminal_state": job.status})
        return row

    @classmethod
    def release_hold(cls, db: Session, *, hold_id: int, actor: User, reason: str) -> MaintenanceHold:
        row = db.query(MaintenanceHold).filter(MaintenanceHold.id == hold_id).with_for_update().one_or_none()
        if not row:
            raise MaintenanceModeError("Maintenance hold not found")
        if row.released_at is None:
            row.released_at = datetime.now(UTC); row.released_by_user_id = actor.id; row.release_reason = reason.strip()
            cls._audit(db, actor.id, "maintenance_hold_released", row, {"reason": reason.strip()})
        return row

    @classmethod
    def reconcile(cls, db: Session) -> list[int]:
        released: list[int] = []
        rows = db.query(MaintenanceHold).filter(
            MaintenanceHold.hold_type == "sync", MaintenanceHold.auto_release.is_(True),
            MaintenanceHold.released_at.is_(None),
        ).all()
        for row in rows:
            job = db.get(SyncJob, row.owner_job_id) if row.owner_job_id else None
            if job is None or job.status in TERMINAL_SYNC_STATES:
                row.released_at = datetime.now(UTC)
                row.release_reason = "orphaned_sync_hold" if job is None else f"sync_terminal:{job.status}"
                cls._audit(db, job.requested_by_user_id if job else None, "maintenance_sync_reconciled", row, {"terminal_state": job.status if job else None})
                released.append(row.id)
        return released
