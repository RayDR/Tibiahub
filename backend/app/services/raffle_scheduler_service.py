from __future__ import annotations

import logging
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models.raffle import Raffle, RafflePrizeDelivery, RaffleSchedulerAttempt, RaffleSchedulerState
from app.services.automatic_raffle_service import AutomaticRaffleError, AutomaticRaffleService
from app.services.notification_service import NotificationService
from app.services.raffle_eligibility_service import RaffleEligibilityError

logger = logging.getLogger("app.raffle_scheduler")
RETRYABLE_CODES = {
    "execution_failed", "provider_unavailable", "network_error",
    "temporary_source_failure", "guild_source_unavailable",
}


def utcnow() -> datetime:
    return datetime.now(UTC)


class RaffleSchedulerService:
    def __init__(self, worker_id: str | None = None):
        self.worker_id = worker_id or settings.RAFFLE_SCHEDULER_WORKER_ID

    def heartbeat(self, db: Session, *, failure_code: str | None = None, success: bool = False) -> RaffleSchedulerState:
        now = utcnow()
        state = db.get(RaffleSchedulerState, self.worker_id) or RaffleSchedulerState(worker_id=self.worker_id, heartbeat_at=now)
        state.enabled = settings.RAFFLE_SCHEDULER_ENABLED
        state.heartbeat_at = now
        state.last_poll_at = now
        if success:
            state.last_success_at = now
        if failure_code:
            state.last_failure_at = now
            state.last_failure_code = failure_code
        db.add(state)
        db.commit()
        return state

    def due_query(self, db: Session, now: datetime | None = None):
        now = now or utcnow()
        return db.query(Raffle).filter(
            Raffle.run_mode == "automatic", Raffle.purpose.in_(["test", "real"]),
            Raffle.is_deleted.is_(False), Raffle.archived_at.is_(None),
            Raffle.scheduled_run_at.isnot(None), Raffle.scheduled_run_at <= now,
            Raffle.retry_count <= settings.RAFFLE_SCHEDULER_MAX_RETRIES,
            or_(Raffle.next_retry_at.is_(None), Raffle.next_retry_at <= now),
            or_(
                Raffle.execution_state.in_(["pending", "failed"]),
                (Raffle.execution_state.in_(["claimed", "running"])) & (Raffle.lease_expires_at < now),
            ),
        )

    def counts(self, db: Session) -> tuple[int, int]:
        now = utcnow()
        return self.due_query(db, now).count(), db.query(Raffle).filter(
            Raffle.run_mode == "automatic", Raffle.execution_state.in_(["claimed", "running"]),
            Raffle.lease_expires_at < now,
        ).count()

    def notify_overdue_deliveries(self, db: Session) -> int:
        now = utcnow()
        deliveries = db.query(RafflePrizeDelivery).join(Raffle).filter(
            RafflePrizeDelivery.status == "pending", RafflePrizeDelivery.delivery_deadline_at < now,
            Raffle.run_mode == "automatic", Raffle.purpose.in_(["test", "real"]),
        ).all()
        for delivery in deliveries:
            NotificationService.emit(
                db, delivery.raffle, "raffle_delivery_overdue",
                f"raffle:{delivery.raffle_id}:result:{delivery.result_id}:delivery-overdue",
            )
        db.commit()
        return len(deliveries)

    def claim_one(self, db: Session) -> tuple[int, str, int] | None:
        now = utcnow()
        query = self.due_query(db, now).order_by(Raffle.scheduled_run_at, Raffle.id)
        if db.bind is not None and db.bind.dialect.name == "postgresql":
            raffle = query.with_for_update(skip_locked=True).first()
        else:
            raffle = query.first()
        if not raffle:
            db.commit()
            return None
        old_version = raffle.version or 1
        token = secrets.token_hex(32)
        updated = db.query(Raffle).filter(Raffle.id == raffle.id, Raffle.version == old_version).update({
            Raffle.execution_state: "claimed", Raffle.claim_token: token, Raffle.claimed_at: now,
            Raffle.lease_expires_at: now + timedelta(seconds=settings.RAFFLE_SCHEDULER_LEASE_SECONDS),
            Raffle.scheduler_job_id: f"raffle-{raffle.id}-{old_version + 1}", Raffle.version: old_version + 1,
        }, synchronize_session=False)
        if updated != 1:
            db.rollback()
            return None
        attempt_number = (raffle.retry_count or 0) + 1
        db.add(RaffleSchedulerAttempt(
            raffle_id=raffle.id, job_id=f"raffle-{raffle.id}-{old_version + 1}", worker_id=self.worker_id,
            attempt_number=attempt_number, state="claimed", claimed_at=now,
        ))
        db.commit()
        return raffle.id, token, attempt_number

    async def execute_claim(self, db: Session, raffle_id: int, token: str, attempt_number: int) -> bool:
        raffle = db.query(Raffle).options(selectinload(Raffle.prizes)).filter(Raffle.id == raffle_id).one()
        attempt = db.query(RaffleSchedulerAttempt).filter(RaffleSchedulerAttempt.job_id == raffle.scheduler_job_id).one()
        attempt_id = attempt.id
        job_id = attempt.job_id
        attempt.state = "running"
        attempt.started_at = utcnow()
        db.commit()
        try:
            run = await AutomaticRaffleService.execute(db, raffle, raffle.created_by, trigger="scheduler", claimed_token=token)
            attempt = db.get(RaffleSchedulerAttempt, attempt.id)
            raffle = db.get(Raffle, raffle_id)
            attempt.state = "succeeded"
            attempt.completed_at = utcnow()
            raffle.retry_count = 0
            raffle.next_retry_at = None
            NotificationService.emit(db, raffle, "raffle_completed", f"raffle:{raffle.id}:run:{run.id}:completed")
            for result in run.results:
                NotificationService.emit(db, raffle, "raffle_winner_selected", f"raffle:{raffle.id}:result:{result.id}:winner", payload={"position": result.prize_position})
            db.commit()
            self.heartbeat(db, success=True)
            logger.info("raffle_scheduler_result raffle_id=%s attempt=%s state=succeeded", raffle_id, attempt_number)
            return True
        except (AutomaticRaffleError, RaffleEligibilityError) as exc:
            # The Stage 1 engine persists its safe failed state before raising
            # domain errors. Keep that transaction and append scheduler audit
            # metadata instead of erasing the historical failure.
            raffle = db.get(Raffle, raffle_id)
            attempt = db.get(RaffleSchedulerAttempt, attempt_id)
            if attempt is None:
                # Defensive fallback for databases/test harnesses where a
                # surrounding transaction was rolled back with the engine.
                attempt = RaffleSchedulerAttempt(
                    raffle_id=raffle_id, job_id=job_id, worker_id=self.worker_id,
                    attempt_number=attempt_number, state="failed_permanent", claimed_at=utcnow(),
                )
                db.add(attempt)
            retryable = exc.code in RETRYABLE_CODES and attempt_number <= settings.RAFFLE_SCHEDULER_MAX_RETRIES
            attempt.state = "retry_scheduled" if retryable else "failed_permanent"
            attempt.retryable = retryable
            attempt.failure_code = exc.code
            attempt.failure_summary = exc.summary
            attempt.completed_at = utcnow()
            raffle.retry_count = attempt_number
            raffle.execution_state = "failed"
            raffle.claim_token = None
            raffle.lease_expires_at = None
            raffle.next_retry_at = utcnow() + timedelta(seconds=min(
                settings.RAFFLE_SCHEDULER_INITIAL_RETRY_SECONDS * (2 ** max(attempt_number - 1, 0)), 3600
            )) if retryable else None
            NotificationService.emit(db, raffle, "raffle_execution_failed", f"raffle:{raffle.id}:attempt:{attempt.id}:failed", payload={"code": exc.code})
            db.commit()
            self.heartbeat(db, failure_code=exc.code)
            logger.warning("raffle_scheduler_result raffle_id=%s attempt=%s state=%s code=%s", raffle_id, attempt_number, attempt.state, exc.code)
            return False

    async def poll_once(self, db: Session) -> bool:
        self.heartbeat(db)
        self.notify_overdue_deliveries(db)
        claim = self.claim_one(db)
        return False if claim is None else await self.execute_claim(db, *claim)
