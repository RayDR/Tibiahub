"""Hashed, single-use auth tokens with database-backed cooldowns and limits."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.auth_security import AuthOneTimeToken, AuthRequestEvent
from app.models.user import User


PASSWORD_RESET = "password_reset"
EMAIL_VERIFICATION = "email_verification"


def token_hash(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def private_identifier_hash(value: str) -> str:
    return hmac.new(
        settings.secret_key.encode("utf-8"),
        value.strip().casefold().encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


class AuthTokenService:
    @staticmethod
    def allow_request(db: Session, *, purpose: str, subject: str, requester: str) -> bool:
        now = datetime.now(UTC)
        subject_hash = private_identifier_hash(subject)
        requester_hash = private_identifier_hash(requester or "unknown")
        if db.bind is not None and db.bind.dialect.name == "postgresql":
            # Serialize both dimensions. Sorting prevents deadlocks when the
            # same subject/requester pair arrives in a different order.
            lock_keys = sorted({
                int.from_bytes(bytes.fromhex(value[:16]), "big", signed=True)
                for value in (subject_hash, requester_hash)
            })
            for lock_key in lock_keys:
                db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_key})
        cooldown_cutoff = now - timedelta(seconds=settings.AUTH_TOKEN_COOLDOWN_SECONDS)
        hourly_cutoff = now - timedelta(hours=1)
        recent_subject = db.query(AuthRequestEvent.id).filter(
            AuthRequestEvent.purpose == purpose,
            AuthRequestEvent.subject_hash == subject_hash,
            AuthRequestEvent.created_at >= cooldown_cutoff,
        ).first()
        subject_hourly = db.query(AuthRequestEvent.id).filter(
            AuthRequestEvent.purpose == purpose,
            AuthRequestEvent.subject_hash == subject_hash,
            AuthRequestEvent.created_at >= hourly_cutoff,
        ).count()
        requester_hourly = db.query(AuthRequestEvent.id).filter(
            AuthRequestEvent.purpose == purpose,
            AuthRequestEvent.requester_hash == requester_hash,
            AuthRequestEvent.created_at >= hourly_cutoff,
        ).count()
        allowed = not recent_subject and subject_hourly < settings.AUTH_TOKEN_MAX_PER_SUBJECT_HOUR and requester_hourly < settings.AUTH_TOKEN_MAX_PER_REQUESTER_HOUR
        if allowed:
            db.add(AuthRequestEvent(purpose=purpose, subject_hash=subject_hash, requester_hash=requester_hash))
            db.flush()
        return allowed

    @staticmethod
    def issue(db: Session, *, user: User, purpose: str, ttl: timedelta) -> str:
        now = datetime.now(UTC)
        db.query(AuthOneTimeToken).filter(
            AuthOneTimeToken.user_id == user.id,
            AuthOneTimeToken.purpose == purpose,
            AuthOneTimeToken.consumed_at.is_(None),
            AuthOneTimeToken.invalidated_at.is_(None),
        ).update({AuthOneTimeToken.invalidated_at: now}, synchronize_session=False)
        raw_token = secrets.token_urlsafe(48)
        db.add(AuthOneTimeToken(
            user_id=user.id,
            purpose=purpose,
            token_hash=token_hash(raw_token),
            expires_at=now + ttl,
        ))
        db.flush()
        return raw_token

    @staticmethod
    def consume(db: Session, *, purpose: str, raw_token: str) -> User | None:
        now = datetime.now(UTC)
        row = db.query(AuthOneTimeToken).filter(
            AuthOneTimeToken.purpose == purpose,
            AuthOneTimeToken.token_hash == token_hash(raw_token),
            AuthOneTimeToken.consumed_at.is_(None),
            AuthOneTimeToken.invalidated_at.is_(None),
            AuthOneTimeToken.expires_at > now,
        ).with_for_update().first()
        if row is None:
            return None
        updated = db.query(AuthOneTimeToken).filter(
            AuthOneTimeToken.id == row.id,
            AuthOneTimeToken.consumed_at.is_(None),
            AuthOneTimeToken.invalidated_at.is_(None),
            AuthOneTimeToken.expires_at > now,
        ).update({AuthOneTimeToken.consumed_at: now}, synchronize_session=False)
        if updated != 1:
            return None
        db.query(AuthOneTimeToken).filter(
            AuthOneTimeToken.user_id == row.user_id,
            AuthOneTimeToken.purpose == purpose,
            AuthOneTimeToken.id != row.id,
            AuthOneTimeToken.consumed_at.is_(None),
            AuthOneTimeToken.invalidated_at.is_(None),
        ).update({AuthOneTimeToken.invalidated_at: now}, synchronize_session=False)
        return db.get(User, row.user_id)
