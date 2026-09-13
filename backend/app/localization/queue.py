"""Durable translation queue, leasing, retries, and worker diagnostics."""

from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.database import SessionLocal
from app.knowledge.models import KnowledgeLocalization, LocalizationJob, LocalizationWorkerHeartbeat
from app.localization.factory import build_translation_provider
from app.localization.provider import TranslationProviderError
from app.localization.service import ContentTranslationService, normalize_language_tag, source_text_hash


WORKER_VERSION = "localization-worker-v1"
TRANSIENT_FAILURES = {"provider_timeout", "provider_unavailable", "provider_error", "worker_interrupted"}


def _idempotency_key(*parts: str) -> str:
    payload = "\x1f".join(parts)
    return f"loc:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"


class LocalizationQueueService:
    @staticmethod
    def enqueue_field(
        db: Session,
        *,
        resource_type: str,
        resource_key: str,
        field_path: str,
        source_text: str | None,
        source_language: str,
        target_language: str,
        entity_uuid: UUID | None = None,
        protected_terms: tuple[str, ...] = (),
        context: str | None = None,
    ) -> LocalizationJob | None:
        if not settings.LOCALIZATION_ENABLED or not settings.LOCALIZATION_AUTO_ENQUEUE:
            return None
        text = (source_text or "").strip()
        if not text:
            return None
        if len(text) > settings.LOCALIZATION_MAX_SOURCE_CHARS:
            return None
        source_language = normalize_language_tag(source_language) or source_language
        target_language = normalize_language_tag(target_language) or target_language
        if source_language == target_language:
            return None
        digest = source_text_hash(text)
        existing_localization = (
            db.query(KnowledgeLocalization)
            .filter_by(
                resource_type=resource_type,
                resource_key=resource_key,
                field_path=field_path,
                language=target_language,
            )
            .first()
        )
        if (
            existing_localization is not None
            and existing_localization.source_text_hash == digest
            and existing_localization.status not in {"failed", "stale"}
        ):
            return None

        idempotency_key = _idempotency_key(
            resource_type,
            resource_key,
            field_path,
            source_language,
            target_language,
            digest,
        )
        existing_job = db.query(LocalizationJob).filter_by(idempotency_key=idempotency_key).first()
        if existing_job is not None:
            return existing_job

        row = LocalizationJob(
            entity_uuid=entity_uuid,
            resource_type=resource_type,
            resource_key=resource_key,
            field_path=field_path,
            source_text=text,
            source_text_hash=digest,
            source_language=source_language,
            target_language=target_language,
            protected_terms=list(dict.fromkeys(term for term in protected_terms if term)),
            context=(context or "")[:512] or None,
            idempotency_key=idempotency_key,
            status="pending",
            next_attempt_at=datetime.now(UTC),
        )
        try:
            with db.begin_nested():
                db.add(row)
                db.flush()
            return row
        except IntegrityError:
            return db.query(LocalizationJob).filter_by(idempotency_key=idempotency_key).one()

    @staticmethod
    def enqueue_targets(
        db: Session,
        *,
        resource_type: str,
        resource_key: str,
        fields: dict[str, str | None],
        source_language: str,
        entity_uuid: UUID | None = None,
        protected_terms: tuple[str, ...] = (),
        context: str | None = None,
        target_languages: tuple[str, ...] | None = None,
    ) -> int:
        targets = target_languages or tuple(settings.localization_target_languages)
        queued = 0
        for field_path, source_text in fields.items():
            for target_language in targets:
                row = LocalizationQueueService.enqueue_field(
                    db,
                    resource_type=resource_type,
                    resource_key=resource_key,
                    field_path=field_path,
                    source_text=source_text,
                    source_language=source_language,
                    target_language=target_language,
                    entity_uuid=entity_uuid,
                    protected_terms=protected_terms,
                    context=context,
                )
                queued += int(row is not None and row.status in {"pending", "retry"})
        return queued

    @staticmethod
    def heartbeat(
        db: Session,
        worker_id: str,
        *,
        state: str,
        current_job_id: int | None = None,
        failure_category: str | None = None,
        success: bool = False,
    ) -> None:
        now = datetime.now(UTC)
        row = db.get(LocalizationWorkerHeartbeat, worker_id)
        if row is None:
            row = LocalizationWorkerHeartbeat(
                worker_id=worker_id,
                state=state,
                last_seen_at=now,
                version=WORKER_VERSION,
                enabled=settings.LOCALIZATION_WORKER_ENABLED,
            )
            db.add(row)
        row.state = state
        row.last_seen_at = now
        row.current_job_id = current_job_id
        row.version = WORKER_VERSION
        row.enabled = settings.LOCALIZATION_WORKER_ENABLED
        if success:
            row.last_success_at = now
            row.last_failure_category = None
        elif failure_category:
            row.last_failure_category = failure_category

    @staticmethod
    def claim_one(db: Session, worker_id: str) -> int | None:
        now = datetime.now(UTC)
        db.execute(
            update(LocalizationJob)
            .where(
                LocalizationJob.status == "processing",
                LocalizationJob.lease_expires_at <= now,
                LocalizationJob.attempt_count < settings.LOCALIZATION_WORKER_MAX_ATTEMPTS,
            )
            .values(
                status="retry",
                lease_expires_at=None,
                worker_id=None,
                next_attempt_at=now,
                safe_failure_category="worker_interrupted",
            )
        )
        db.execute(
            update(LocalizationJob)
            .where(
                LocalizationJob.status == "processing",
                LocalizationJob.lease_expires_at <= now,
                LocalizationJob.attempt_count >= settings.LOCALIZATION_WORKER_MAX_ATTEMPTS,
            )
            .values(
                status="failed",
                lease_expires_at=None,
                worker_id=None,
                completed_at=now,
                safe_failure_category="worker_interrupted",
            )
        )
        row = (
            db.query(LocalizationJob)
            .filter(
                LocalizationJob.status.in_(["pending", "retry"]),
                (LocalizationJob.next_attempt_at.is_(None)) | (LocalizationJob.next_attempt_at <= now),
            )
            .order_by(LocalizationJob.id)
            .with_for_update(skip_locked=True)
            .first()
        )
        if row is None:
            LocalizationQueueService.heartbeat(db, worker_id, state="idle")
            return None
        row.status = "processing"
        row.attempt_count += 1
        row.started_at = now
        row.worker_id = worker_id
        row.lease_expires_at = now + timedelta(seconds=settings.LOCALIZATION_WORKER_LEASE_SECONDS)
        LocalizationQueueService.heartbeat(db, worker_id, state="running", current_job_id=row.id)
        return row.id

    @staticmethod
    def _failure_category(exc: Exception) -> str:
        message = str(exc).lower()
        if "timed out" in message or "timeout" in message:
            return "provider_timeout"
        if "http 429" in message or "http 5" in message:
            return "provider_unavailable"
        if isinstance(exc, TranslationProviderError):
            return "provider_error"
        return "translation_failed"

    @staticmethod
    def process_one(
        *,
        session_factory: sessionmaker = SessionLocal,
        worker_id: str | None = None,
    ) -> bool:
        selected_worker = worker_id or settings.LOCALIZATION_WORKER_ID
        with session_factory.begin() as db:
            job_id = LocalizationQueueService.claim_one(db, selected_worker)
        if job_id is None:
            return False

        try:
            with session_factory() as db:
                job = db.get(LocalizationJob, job_id)
                if job is None or job.status != "processing":
                    return True
                provider = build_translation_provider()
                service = ContentTranslationService(provider)
                asyncio.run(
                    service.translate_and_store(
                        db,
                        resource_type=job.resource_type,
                        resource_key=job.resource_key,
                        field_path=job.field_path,
                        source_text=job.source_text,
                        source_language=job.source_language,
                        target_language=job.target_language,
                        entity_uuid=job.entity_uuid,
                        protected_terms=tuple(job.protected_terms or ()),
                        context=job.context,
                    )
                )
                db.commit()
            failure_category = None
        except Exception as exc:
            failure_category = LocalizationQueueService._failure_category(exc)

        with session_factory.begin() as db:
            row = (
                db.query(LocalizationJob)
                .filter_by(id=job_id, status="processing")
                .with_for_update()
                .first()
            )
            if row is None:
                return True
            now = datetime.now(UTC)
            row.lease_expires_at = None
            row.worker_id = None
            if failure_category is None:
                row.status = "succeeded"
                row.completed_at = now
                row.safe_failure_category = None
                LocalizationQueueService.heartbeat(db, selected_worker, state="idle", success=True)
            else:
                row.safe_failure_category = failure_category
                retryable = failure_category in TRANSIENT_FAILURES
                if retryable and row.attempt_count < settings.LOCALIZATION_WORKER_MAX_ATTEMPTS:
                    row.status = "retry"
                    row.next_attempt_at = now + timedelta(seconds=min(3600, 30 * (2 ** (row.attempt_count - 1))))
                else:
                    row.status = "failed"
                    row.completed_at = now
                LocalizationQueueService.heartbeat(
                    db,
                    selected_worker,
                    state="idle",
                    failure_category=failure_category,
                )
        return True

    @staticmethod
    def diagnostics(db: Session) -> dict:
        heartbeat = db.get(LocalizationWorkerHeartbeat, settings.LOCALIZATION_WORKER_ID)
        queue_depth = (
            db.query(func.count(LocalizationJob.id))
            .filter(LocalizationJob.status.in_(["pending", "retry", "processing"]))
            .scalar()
            or 0
        )
        failed = db.query(func.count(LocalizationJob.id)).filter(LocalizationJob.status == "failed").scalar() or 0
        generated = (
            db.query(func.count(KnowledgeLocalization.id))
            .filter(KnowledgeLocalization.status == "generated")
            .scalar()
            or 0
        )
        stale = db.query(func.count(KnowledgeLocalization.id)).filter(KnowledgeLocalization.status == "stale").scalar() or 0
        approved = db.query(func.count(KnowledgeLocalization.id)).filter(KnowledgeLocalization.status == "approved").scalar() or 0
        return {
            "enabled": settings.LOCALIZATION_ENABLED,
            "auto_enqueue": settings.LOCALIZATION_AUTO_ENQUEUE,
            "provider": settings.LOCALIZATION_PROVIDER,
            "model": settings.LOCALIZATION_MODEL,
            "default_language": settings.LOCALIZATION_DEFAULT_LANGUAGE,
            "target_languages": settings.localization_target_languages,
            "queue_depth": queue_depth,
            "failed_jobs": failed,
            "generated_pending_review": generated,
            "stale": stale,
            "approved": approved,
            "worker": None if heartbeat is None else {
                "worker_id": heartbeat.worker_id,
                "state": heartbeat.state,
                "last_seen_at": heartbeat.last_seen_at,
                "last_success_at": heartbeat.last_success_at,
                "last_failure_category": heartbeat.last_failure_category,
                "enabled": heartbeat.enabled,
            },
        }
