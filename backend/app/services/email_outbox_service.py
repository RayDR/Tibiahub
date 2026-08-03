"""Transactional email enqueueing, leasing, retry, and sanitized diagnostics."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.secret_payload import decrypt_json, encrypt_json
from app.db.database import SessionLocal
from app.models.email_delivery import EmailOutbox, EmailWorkerHeartbeat
from app.models.user import User
from app.services.email_service import EmailSendResult, EmailService


WORKER_VERSION = "email-outbox-v1"
TRANSIENT_FAILURES = {"connection_failed", "smtp_rejected"}


def _safe_idempotency(prefix: str, value: str) -> str:
    return f"{prefix}:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"


class EmailOutboxService:
    @staticmethod
    def enqueue(
        db: Session, *, message_type: str, recipient_email: str,
        recipient_user_id: int | None, locale: str, template_payload: dict,
        secret_payload: dict | None, idempotency_key: str,
    ) -> EmailOutbox:
        existing = db.query(EmailOutbox).filter_by(idempotency_key=idempotency_key).first()
        if existing:
            return existing
        row = EmailOutbox(
            message_type=message_type, recipient_email=recipient_email.strip().casefold(),
            recipient_user_id=recipient_user_id, locale="es" if locale.casefold().startswith("es") else "en",
            template_payload=template_payload,
            secret_payload_ciphertext=encrypt_json(secret_payload or {}) if secret_payload else None,
            idempotency_key=idempotency_key, status="pending", next_attempt_at=datetime.now(UTC),
        )
        try:
            with db.begin_nested():
                db.add(row)
                db.flush()
            return row
        except IntegrityError:
            # A concurrent request won the unique idempotency key. The
            # savepoint keeps the caller's surrounding transaction usable.
            return db.query(EmailOutbox).filter_by(idempotency_key=idempotency_key).one()

    @staticmethod
    def enqueue_verification(db: Session, *, user: User, raw_token: str, locale: str) -> EmailOutbox:
        return EmailOutboxService.enqueue(
            db, message_type="email_verification", recipient_email=user.email,
            recipient_user_id=user.id, locale=locale,
            template_payload={"username": user.display_name or user.username},
            secret_payload={"link": f"{settings.VERIFY_EMAIL_URL}?token={raw_token}"},
            idempotency_key=_safe_idempotency("verify", raw_token),
        )

    @staticmethod
    def enqueue_password_reset(db: Session, *, user: User, raw_token: str, locale: str) -> EmailOutbox:
        return EmailOutboxService.enqueue(
            db, message_type="password_reset", recipient_email=user.email,
            recipient_user_id=user.id, locale=locale,
            template_payload={"username": user.display_name or user.username},
            secret_payload={"link": f"{settings.RESET_PASSWORD_URL}?token={raw_token}"},
            idempotency_key=_safe_idempotency("reset", raw_token),
        )

    @staticmethod
    def enqueue_test(db: Session, *, recipient_email: str, locale: str) -> EmailOutbox:
        return EmailOutboxService.enqueue(
            db, message_type="smtp_test", recipient_email=recipient_email,
            recipient_user_id=None, locale=locale, template_payload={}, secret_payload=None,
            idempotency_key=f"smtp-test:{uuid.uuid4().hex}",
        )

    @staticmethod
    def enqueue_notification(
        db: Session, *, user: User, subject: str, message: str, event_key: str, locale: str = "en",
    ) -> EmailOutbox | None:
        if not user.email or not user.email_notifications_enabled:
            return None
        return EmailOutboxService.enqueue(
            db, message_type="notification", recipient_email=user.email,
            recipient_user_id=user.id, locale=locale,
            template_payload={"subject": subject[:200], "message": message[:2000]}, secret_payload=None,
            idempotency_key=_safe_idempotency("notification", f"{event_key}:{user.id}"),
        )

    @staticmethod
    def heartbeat(db: Session, worker_id: str, *, state: str, current_job_id: int | None = None, result: EmailSendResult | None = None) -> None:
        now = datetime.now(UTC)
        row = db.get(EmailWorkerHeartbeat, worker_id)
        if row is None:
            row = EmailWorkerHeartbeat(worker_id=worker_id, state=state, last_seen_at=now, version=WORKER_VERSION)
            db.add(row)
        row.state = state
        row.last_seen_at = now
        row.current_job_id = current_job_id
        row.version = WORKER_VERSION
        row.enabled = settings.EMAIL_WORKER_ENABLED
        if result and result.ok:
            row.last_success_at = now
            row.last_failure_category = None
        elif result:
            row.last_failure_category = result.failure_category or "delivery_failed"

    @staticmethod
    def claim_one(db: Session, worker_id: str) -> int | None:
        now = datetime.now(UTC)
        db.execute(update(EmailOutbox).where(
            EmailOutbox.status == "processing", EmailOutbox.lease_expires_at <= now,
            EmailOutbox.attempt_count < settings.EMAIL_WORKER_MAX_ATTEMPTS,
        ).values(status="retry", lease_expires_at=None, next_attempt_at=now, safe_failure_category="worker_interrupted"))
        db.execute(update(EmailOutbox).where(
            EmailOutbox.status == "processing", EmailOutbox.lease_expires_at <= now,
            EmailOutbox.attempt_count >= settings.EMAIL_WORKER_MAX_ATTEMPTS,
        ).values(status="failed", lease_expires_at=None, completed_at=now, safe_failure_category="worker_interrupted"))
        row = db.query(EmailOutbox).filter(
            EmailOutbox.status.in_(["pending", "retry"]),
            (EmailOutbox.next_attempt_at.is_(None)) | (EmailOutbox.next_attempt_at <= now),
        ).order_by(EmailOutbox.id).with_for_update(skip_locked=True).first()
        if row is None:
            EmailOutboxService.heartbeat(db, worker_id, state="idle")
            return None
        row.status = "processing"
        row.attempt_count += 1
        row.started_at = now
        row.lease_expires_at = now + timedelta(seconds=settings.EMAIL_WORKER_LEASE_SECONDS)
        EmailOutboxService.heartbeat(db, worker_id, state="running", current_job_id=row.id)
        return row.id

    @staticmethod
    def _deliver(row: EmailOutbox) -> EmailSendResult:
        payload = row.template_payload or {}
        secret = decrypt_json(row.secret_payload_ciphertext)
        if row.message_type == "email_verification":
            return EmailService.send_verification_email(
                to_email=row.recipient_email, username=payload.get("username") or "TibiaHub member",
                verification_link=secret.get("link") or "", locale=row.locale,
            )
        if row.message_type == "password_reset":
            return EmailService.send_password_reset_email(
                to_email=row.recipient_email, username=payload.get("username") or "TibiaHub member",
                reset_link=secret.get("link") or "", locale=row.locale,
            )
        if row.message_type == "smtp_test":
            return EmailService.send_test_email(to_email=row.recipient_email, locale=row.locale)
        if row.message_type == "notification":
            return EmailService.send_notification_email(
                to_email=row.recipient_email,
                subject=str(payload.get("subject") or "TibiaHub notification"),
                message=str(payload.get("message") or "You have a new TibiaHub notification."),
            )
        return EmailSendResult(ok=False, detail="Unsupported email type", failure_category="unsupported_message_type")

    @staticmethod
    def process_one(*, session_factory: sessionmaker = SessionLocal, worker_id: str | None = None) -> bool:
        selected_worker = worker_id or settings.EMAIL_WORKER_ID
        with session_factory.begin() as db:
            job_id = EmailOutboxService.claim_one(db, selected_worker)
        if job_id is None:
            return False
        with session_factory() as db:
            row = db.get(EmailOutbox, job_id)
            result = EmailOutboxService._deliver(row)
        with session_factory.begin() as db:
            row = db.query(EmailOutbox).filter_by(id=job_id, status="processing").with_for_update().first()
            if row is None:
                return True
            now = datetime.now(UTC)
            row.lease_expires_at = None
            if result.ok:
                row.status = "sent"
                row.completed_at = now
                row.safe_failure_category = None
                row.secret_payload_ciphertext = None
            else:
                category = result.failure_category or "delivery_failed"
                row.safe_failure_category = category
                if category in TRANSIENT_FAILURES and row.attempt_count < settings.EMAIL_WORKER_MAX_ATTEMPTS:
                    row.status = "retry"
                    row.next_attempt_at = now + timedelta(seconds=min(3600, 30 * (2 ** (row.attempt_count - 1))))
                else:
                    row.status = "failed"
                    row.completed_at = now
                    row.secret_payload_ciphertext = None
            EmailOutboxService.heartbeat(db, selected_worker, state="idle", result=result)
        return True

    @staticmethod
    def diagnostics(db: Session) -> dict:
        heartbeat = db.get(EmailWorkerHeartbeat, settings.EMAIL_WORKER_ID)
        pending = db.query(func.count(EmailOutbox.id)).filter(EmailOutbox.status.in_(["pending", "retry", "processing"])).scalar() or 0
        latest_success = db.query(func.max(EmailOutbox.completed_at)).filter(EmailOutbox.status == "sent").scalar()
        latest_failure = db.query(EmailOutbox.safe_failure_category).filter(
            EmailOutbox.safe_failure_category.isnot(None),
        ).order_by(EmailOutbox.id.desc()).scalar()
        return {
            "configured": settings.smtp_configured,
            "host": settings.SMTP_HOST or None,
            "port": settings.SMTP_PORT,
            "mode": "ssl" if settings.SMTP_USE_SSL else "starttls" if settings.SMTP_USE_TLS else "none",
            "from_address": settings.smtp_from_address if settings.SMTP_FROM else None,
            "last_successful_delivery_at": latest_success,
            "last_failure_category": latest_failure,
            "queue_depth": pending,
            "worker": None if heartbeat is None else {
                "worker_id": heartbeat.worker_id, "state": heartbeat.state,
                "last_seen_at": heartbeat.last_seen_at, "version": heartbeat.version,
                "enabled": heartbeat.enabled,
            },
        }
