"""Domain services for secure administrator recovery and user lifecycle work."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.auth_security import AuthOneTimeToken
from app.models.user import User
from app.models.workspace_audit import WorkspaceAudit


class AdminRecoveryError(ValueError):
    """Raised when an operator recovery request is invalid or unsafe."""


@dataclass(frozen=True)
class AdminRecoveryResult:
    user: User
    created: bool
    revoked_one_time_tokens: int


def _normalized(value: str) -> str:
    return (value or "").strip().casefold()


def find_user_by_identifier(db: Session, identifier: str) -> User | None:
    normalized = _normalized(identifier)
    if not normalized:
        raise AdminRecoveryError("A username or email identifier is required")

    matches = (
        db.query(User)
        .filter(
            or_(
                func.lower(User.username) == normalized,
                func.lower(User.email) == normalized,
            )
        )
        .order_by(User.id)
        .limit(2)
        .all()
    )
    if len(matches) > 1:
        raise AdminRecoveryError(
            "Identifier matches multiple accounts; resolve duplicate identities first"
        )
    return matches[0] if matches else None


def _ensure_unique_identity(
    db: Session,
    *,
    username: str,
    email: str,
) -> None:
    normalized_username = _normalized(username)
    normalized_email = _normalized(email)
    if not normalized_username:
        raise AdminRecoveryError("Username is required when creating an administrator")
    if not normalized_email:
        raise AdminRecoveryError("Email is required when creating an administrator")

    existing = (
        db.query(User.id)
        .filter(
            or_(
                func.lower(User.username) == normalized_username,
                func.lower(User.email) == normalized_email,
            )
        )
        .first()
    )
    if existing:
        raise AdminRecoveryError("The requested username or email is already in use")


def recover_administrator(
    db: Session,
    *,
    identifier: str,
    password: str,
    create_if_missing: bool = False,
    username: str | None = None,
    email: str | None = None,
    mark_email_verified: bool = False,
    revoke_one_time_tokens: bool = True,
) -> AdminRecoveryResult:
    """Recover one administrator without committing or exposing credentials."""

    if len(password) < 12:
        raise AdminRecoveryError("Administrator passwords must contain at least 12 characters")

    user = find_user_by_identifier(db, identifier)
    created = False

    if user is None:
        if not create_if_missing:
            raise AdminRecoveryError("No matching user exists; use the explicit create option")
        _ensure_unique_identity(db, username=username or "", email=email or "")
        user = User(
            username=(username or "").strip(),
            display_name=(username or "").strip(),
            email=(email or "").strip(),
            hashed_password=get_password_hash(password),
            is_active=True,
            is_superuser=True,
        )
        db.add(user)
        db.flush()
        created = True
    else:
        user.hashed_password = get_password_hash(password)
        user.is_active = True
        user.is_superuser = True

    now = datetime.now(UTC)
    if mark_email_verified and user.email:
        user.email_verified_at = now

    revoked = 0
    if revoke_one_time_tokens:
        revoked = (
            db.query(AuthOneTimeToken)
            .filter(
                AuthOneTimeToken.user_id == user.id,
                AuthOneTimeToken.consumed_at.is_(None),
                AuthOneTimeToken.invalidated_at.is_(None),
            )
            .update(
                {AuthOneTimeToken.invalidated_at: now},
                synchronize_session=False,
            )
        )

    db.add(
        WorkspaceAudit(
            actor_id=user.id,
            workspace_type="admin",
            action="administrator_recovered",
            target_type="user",
            target_id=str(user.id),
            assisted=False,
            safe_metadata={
                "actor_context": "operator",
                "created": created,
                "email_marked_verified": bool(mark_email_verified and user.email),
                "revoked_one_time_tokens": revoked,
            },
        )
    )
    db.flush()

    return AdminRecoveryResult(
        user=user,
        created=created,
        revoked_one_time_tokens=revoked,
    )
