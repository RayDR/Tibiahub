"""Transactional enqueue, claim, lease, retry, heartbeat, and cursor services."""

from __future__ import annotations

import os
import socket
import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.knowledge.models import (
    ACTIVE_KNOWLEDGE_JOB_STATES,
    KnowledgeEntityType,
    KnowledgeJob,
    KnowledgeJobAttempt,
    KnowledgeProvider,
    KnowledgeProviderCursor,
    KnowledgeWorkerHeartbeat,
)
from app.knowledge.services.failures import ClassifiedFailure, retry_delay_seconds
from app.knowledge.services.idempotency import knowledge_job_idempotency_key, normalize_json, scope_hash


class KnowledgeJobConflictError(RuntimeError):
    pass


class KnowledgeJobNotFoundError(LookupError):
    pass


class KnowledgeJobOwnershipError(KnowledgeJobConflictError):
    pass


class CompletedJobRecreationError(KnowledgeJobConflictError):
    pass


class ProviderUnavailableForJobError(KnowledgeJobConflictError):
    pass


@dataclass(frozen=True, slots=True)
class EnqueueKnowledgeJob:
    provider_id: str
    job_type: str
    entity_type: str | None = None
    scope: dict[str, Any] | None = None
    payload: dict[str, Any] | None = None
    priority: int = 100
    scheduled_at: datetime | None = None
    max_attempts: int = 5
    parent_job_id: UUID | None = None
    correlation_id: UUID | None = None
    created_by_id: int | None = None
    trigger: str = "system"
    time_bucket: str | None = None
    allow_completed_recreate: bool = False


@dataclass(frozen=True, slots=True)
class EnqueueResult:
    job: KnowledgeJob
    created: bool


def _utc(value: datetime | None = None) -> datetime:
    current = value or datetime.now(UTC)
    return current if current.tzinfo else current.replace(tzinfo=UTC)


class KnowledgeJobService:
    @staticmethod
    def enqueue(db: Session, command: EnqueueKnowledgeJob) -> EnqueueResult:
        provider = db.get(KnowledgeProvider, command.provider_id)
        if provider is None:
            raise ValueError("Provider is not registered")
        if not provider.enabled or provider.health == "disabled":
            raise ProviderUnavailableForJobError("Provider is disabled")
        if command.entity_type is not None:
            entity_type = db.get(KnowledgeEntityType, command.entity_type)
            if entity_type is None or not entity_type.enabled:
                raise ValueError("Entity type is not registered or enabled")
        if command.priority < 0 or command.max_attempts <= 0:
            raise ValueError("Priority and maximum attempts are invalid")
        scope = normalize_json(command.scope or {})
        payload = normalize_json(command.payload or {})
        key = knowledge_job_idempotency_key(
            provider_id=command.provider_id,
            job_type=command.job_type,
            entity_type=command.entity_type,
            scope=scope,
            payload=payload,
            time_bucket=command.time_bucket,
        )
        active = (
            db.query(KnowledgeJob)
            .filter(
                KnowledgeJob.idempotency_key == key,
                KnowledgeJob.state.in_(ACTIVE_KNOWLEDGE_JOB_STATES),
            )
            .first()
        )
        if active is not None:
            return EnqueueResult(active, False)
        if not command.allow_completed_recreate:
            historical = (
                db.query(KnowledgeJob.id)
                .filter(
                    KnowledgeJob.idempotency_key == key,
                    KnowledgeJob.state.in_(("succeeded", "partially_succeeded")),
                )
                .first()
            )
            if historical is not None:
                raise CompletedJobRecreationError("Completed jobs require explicit recreation")

        job = KnowledgeJob(
            provider_id=command.provider_id,
            job_type=command.job_type,
            entity_type_id=command.entity_type,
            scope=scope,
            payload=payload,
            priority=command.priority,
            scheduled_at=_utc(command.scheduled_at),
            max_attempts=command.max_attempts,
            idempotency_key=key,
            parent_job_id=command.parent_job_id,
            correlation_id=command.correlation_id or uuid4(),
            created_by_id=command.created_by_id,
            trigger=command.trigger,
        )
        try:
            with db.begin_nested():
                db.add(job)
                db.flush()
        except IntegrityError:
            active = (
                db.query(KnowledgeJob)
                .filter(
                    KnowledgeJob.idempotency_key == key,
                    KnowledgeJob.state.in_(ACTIVE_KNOWLEDGE_JOB_STATES),
                )
                .first()
            )
            if active is None:
                raise
            return EnqueueResult(active, False)
        return EnqueueResult(job, True)

    @staticmethod
    def claim_one(
        db: Session,
        worker_id: str,
        *,
        lease_seconds: int,
        now: datetime | None = None,
    ) -> KnowledgeJob | None:
        claimed_at = _utc(now)
        statement = (
            select(KnowledgeJob)
            .join(KnowledgeProvider, KnowledgeProvider.provider_id == KnowledgeJob.provider_id)
            .where(
                KnowledgeJob.state.in_(("pending", "retrying")),
                KnowledgeJob.scheduled_at <= claimed_at,
                KnowledgeProvider.enabled.is_(True),
                KnowledgeProvider.health != "disabled",
                or_(KnowledgeProvider.cooldown_until.is_(None), KnowledgeProvider.cooldown_until <= claimed_at),
            )
            .order_by(KnowledgeJob.priority.desc(), KnowledgeJob.scheduled_at.asc(), KnowledgeJob.created_at.asc())
            .with_for_update(skip_locked=True, of=KnowledgeJob)
            .limit(1)
        )
        job = db.execute(statement).scalars().first()
        if job is None:
            return None
        job.state = "claimed"
        job.worker_id = worker_id
        job.claimed_at = claimed_at
        job.lease_expires_at = claimed_at + timedelta(seconds=lease_seconds)
        job.last_error_code = None
        job.safe_last_error = None
        return job

    @staticmethod
    def start_attempt(
        db: Session,
        job_id: UUID,
        worker_id: str,
        *,
        now: datetime | None = None,
    ) -> KnowledgeJobAttempt:
        started_at = _utc(now)
        job = db.execute(select(KnowledgeJob).where(KnowledgeJob.id == job_id).with_for_update()).scalar_one_or_none()
        if job is None:
            raise KnowledgeJobNotFoundError("Knowledge job not found")
        if job.state != "claimed" or job.worker_id != worker_id:
            raise KnowledgeJobOwnershipError("Worker does not own the claimed job")
        if job.lease_expires_at is None or _utc(job.lease_expires_at) <= started_at:
            raise KnowledgeJobOwnershipError("Worker lease expired before start")
        if job.attempt_count >= job.max_attempts:
            raise KnowledgeJobConflictError("Maximum attempts reached")
        job.attempt_count += 1
        job.state = "running"
        job.started_at = job.started_at or started_at
        attempt = KnowledgeJobAttempt(
            job_id=job.id,
            attempt_number=job.attempt_count,
            worker_id=worker_id,
            started_at=started_at,
            outcome="running",
        )
        db.add(attempt)
        db.flush()
        return attempt

    @staticmethod
    def assert_owner(job: KnowledgeJob, worker_id: str, now: datetime) -> None:
        if job.state != "running" or job.worker_id != worker_id:
            raise KnowledgeJobOwnershipError("Worker no longer owns this job")
        if job.lease_expires_at is None or _utc(job.lease_expires_at) <= now:
            raise KnowledgeJobOwnershipError("Worker lease is no longer valid")

    @classmethod
    def complete(
        cls,
        db: Session,
        job_id: UUID,
        attempt_id: UUID,
        worker_id: str,
        *,
        partial: bool,
        metrics: dict[str, Any],
        now: datetime | None = None,
    ) -> KnowledgeJob:
        completed_at = _utc(now)
        job = db.execute(select(KnowledgeJob).where(KnowledgeJob.id == job_id).with_for_update()).scalar_one_or_none()
        if job is None:
            raise KnowledgeJobNotFoundError("Knowledge job not found")
        cls.assert_owner(job, worker_id, completed_at)
        attempt = db.get(KnowledgeJobAttempt, attempt_id)
        if attempt is None or attempt.job_id != job.id or attempt.worker_id != worker_id or attempt.outcome != "running":
            raise KnowledgeJobOwnershipError("Worker does not own this attempt")
        outcome = "partially_succeeded" if partial else "succeeded"
        job.state = outcome
        job.completed_at = completed_at
        job.worker_id = None
        job.lease_expires_at = None
        attempt.outcome = outcome
        attempt.completed_at = completed_at
        attempt.metrics = normalize_json(metrics)
        return job

    @classmethod
    def fail(
        cls,
        db: Session,
        job_id: UUID,
        attempt_id: UUID,
        worker_id: str,
        failure: ClassifiedFailure,
        *,
        jitter_fraction: float = 0.0,
        now: datetime | None = None,
    ) -> KnowledgeJob:
        failed_at = _utc(now)
        job = db.execute(select(KnowledgeJob).where(KnowledgeJob.id == job_id).with_for_update()).scalar_one_or_none()
        if job is None:
            raise KnowledgeJobNotFoundError("Knowledge job not found")
        cls.assert_owner(job, worker_id, failed_at)
        attempt = db.get(KnowledgeJobAttempt, attempt_id)
        if attempt is None or attempt.job_id != job.id or attempt.worker_id != worker_id or attempt.outcome != "running":
            raise KnowledgeJobOwnershipError("Worker does not own this attempt")
        will_retry = failure.retryable and job.attempt_count < job.max_attempts
        attempt.completed_at = failed_at
        attempt.retryable = will_retry
        attempt.error_code = failure.code
        attempt.safe_error = failure.safe_message[:512]
        attempt.outcome = "retrying" if will_retry else "failed"
        job.state = attempt.outcome
        job.last_error_code = failure.code
        job.safe_last_error = failure.safe_message[:512]
        job.worker_id = None
        job.lease_expires_at = None
        if will_retry:
            delay = retry_delay_seconds(
                job.attempt_count,
                retry_after_seconds=failure.retry_after_seconds,
                jitter_fraction=jitter_fraction,
            )
            job.scheduled_at = failed_at + timedelta(seconds=delay)
        else:
            job.completed_at = failed_at
        return job

    @staticmethod
    def cancel(db: Session, job_id: UUID, *, now: datetime | None = None) -> KnowledgeJob:
        job = db.execute(select(KnowledgeJob).where(KnowledgeJob.id == job_id).with_for_update()).scalar_one_or_none()
        if job is None:
            raise KnowledgeJobNotFoundError("Knowledge job not found")
        if job.state not in ACTIVE_KNOWLEDGE_JOB_STATES:
            raise KnowledgeJobConflictError("Only active jobs can be cancelled")
        completed_at = _utc(now)
        job.state = "cancelled"
        job.completed_at = completed_at
        job.worker_id = None
        job.lease_expires_at = None
        running = next((attempt for attempt in reversed(job.attempts) if attempt.outcome == "running"), None)
        if running:
            running.outcome = "cancelled"
            running.completed_at = completed_at
            running.retryable = False
            running.error_code = "job_cancelled"
            running.safe_error = "The knowledge job was cancelled."
        return job

    @staticmethod
    def manual_retry(db: Session, job_id: UUID, *, now: datetime | None = None) -> KnowledgeJob:
        job = db.execute(select(KnowledgeJob).where(KnowledgeJob.id == job_id).with_for_update()).scalar_one_or_none()
        if job is None:
            raise KnowledgeJobNotFoundError("Knowledge job not found")
        if job.state != "failed":
            raise KnowledgeJobConflictError("Only failed jobs can be retried")
        if job.attempt_count >= job.max_attempts:
            raise KnowledgeJobConflictError("Maximum attempts reached; explicitly enqueue a new job")
        job.state = "retrying"
        job.trigger = "retry"
        job.scheduled_at = _utc(now)
        job.completed_at = None
        job.last_error_code = None
        job.safe_last_error = None
        return job

    @staticmethod
    def recover_expired(
        db: Session,
        *,
        limit: int = 100,
        now: datetime | None = None,
        dry_run: bool = False,
    ) -> list[UUID]:
        recovered_at = _utc(now)
        jobs = db.execute(
            select(KnowledgeJob)
            .where(
                KnowledgeJob.state.in_(("claimed", "running")),
                KnowledgeJob.lease_expires_at < recovered_at,
            )
            .order_by(KnowledgeJob.lease_expires_at.asc())
            .with_for_update(skip_locked=True)
            .limit(limit)
        ).scalars().all()
        ids = [job.id for job in jobs]
        if dry_run:
            return ids
        for job in jobs:
            can_retry = job.attempt_count < job.max_attempts
            running = next((attempt for attempt in reversed(job.attempts) if attempt.outcome == "running"), None)
            if running:
                running.completed_at = recovered_at
                running.outcome = "lease_expired"
                running.retryable = can_retry
                running.error_code = "expired_lease"
                running.safe_error = "The prior worker lease expired."
            job.state = "retrying" if can_retry else "failed"
            job.scheduled_at = recovered_at
            job.completed_at = None if can_retry else recovered_at
            job.worker_id = None
            job.lease_expires_at = None
            job.last_error_code = "expired_lease"
            job.safe_last_error = "The prior worker lease expired."
        return ids

    @staticmethod
    def heartbeat(
        db: Session,
        worker_id: str,
        *,
        state: str,
        current_job_id: UUID | None = None,
        version: str = "stage-2a-2",
        now: datetime | None = None,
    ) -> KnowledgeWorkerHeartbeat:
        observed_at = _utc(now)
        heartbeat = db.get(KnowledgeWorkerHeartbeat, worker_id)
        if heartbeat is None:
            node = hashlib.sha256(socket.gethostname().encode("utf-8")).hexdigest()[:16]
            heartbeat = KnowledgeWorkerHeartbeat(
                worker_id=worker_id,
                worker_type="knowledge",
                node_id=node,
                process_id=os.getpid(),
                started_at=observed_at,
                version=version,
                safe_metadata={},
            )
            db.add(heartbeat)
        heartbeat.last_seen_at = observed_at
        heartbeat.current_job_id = current_job_id
        heartbeat.state = state
        heartbeat.version = version
        return heartbeat

    @staticmethod
    def update_cursor(
        db: Session,
        job: KnowledgeJob,
        cursor_value: dict[str, Any],
        *,
        version: str | None = None,
        now: datetime | None = None,
    ) -> KnowledgeProviderCursor | None:
        if job.entity_type_id is None:
            return None
        digest = scope_hash(job.scope)
        cursor = (
            db.query(KnowledgeProviderCursor)
            .filter_by(provider_id=job.provider_id, entity_type_id=job.entity_type_id, scope_hash=digest)
            .first()
        )
        if cursor is None:
            cursor = KnowledgeProviderCursor(
                provider_id=job.provider_id,
                entity_type_id=job.entity_type_id,
                scope_hash=digest,
            )
            db.add(cursor)
        cursor.cursor = normalize_json(cursor_value)
        cursor.last_success_at = _utc(now)
        cursor.last_job_id = job.id
        cursor.version = version
        return cursor
