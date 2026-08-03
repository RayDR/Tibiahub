from datetime import UTC, datetime, timedelta

import pytest

from app.core.security import get_password_hash, verify_password
from app.models.auth_security import AuthOneTimeToken
from app.models.user import User
from app.models.workspace_audit import WorkspaceAudit
from app.services.admin_user_service import (
    AdminRecoveryError,
    recover_administrator,
)


def test_recovers_existing_admin_and_invalidates_open_tokens(db):
    user = User(
        username="admin",
        email="admin@example.com",
        hashed_password=get_password_hash("old-password-123"),
        is_active=False,
        is_superuser=False,
    )
    db.add(user)
    db.flush()
    db.add(
        AuthOneTimeToken(
            user_id=user.id,
            purpose="password_reset",
            token_hash="a" * 64,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
    )
    db.flush()

    result = recover_administrator(
        db,
        identifier="ADMIN@example.com",
        password="new-password-123",
        mark_email_verified=True,
    )

    assert result.created is False
    assert result.revoked_one_time_tokens == 1
    assert user.is_active is True
    assert user.is_superuser is True
    assert user.email_verified_at is not None
    assert verify_password("new-password-123", user.hashed_password)

    token = db.query(AuthOneTimeToken).filter_by(user_id=user.id).one()
    assert token.invalidated_at is not None
    audit = db.query(WorkspaceAudit).filter_by(
        action="administrator_recovered",
        target_id=str(user.id),
    ).one()
    assert audit.safe_metadata["created"] is False
    assert audit.safe_metadata["revoked_one_time_tokens"] == 1


def test_requires_explicit_create_for_missing_user(db):
    with pytest.raises(AdminRecoveryError, match="explicit create"):
        recover_administrator(
            db,
            identifier="missing@example.com",
            password="new-password-123",
        )


def test_creates_admin_only_when_explicitly_requested(db):
    result = recover_administrator(
        db,
        identifier="admin@example.com",
        password="new-password-123",
        create_if_missing=True,
        username="admin",
        email="admin@example.com",
        mark_email_verified=True,
    )

    assert result.created is True
    assert result.user.username == "admin"
    assert result.user.email == "admin@example.com"
    assert result.user.is_active is True
    assert result.user.is_superuser is True
    assert result.user.email_verified_at is not None


def test_rejects_invalid_admin_password(db):
    with pytest.raises(AdminRecoveryError, match="8–128"):
        recover_administrator(
            db,
            identifier="admin@example.com",
            password="too-short",
            create_if_missing=True,
            username="admin",
            email="admin@example.com",
        )


def test_rejects_ambiguous_cross_field_identifier(db):
    db.add_all(
        [
            User(
                username="shared",
                email="first@example.com",
                hashed_password=get_password_hash("old-password-123"),
                is_active=True,
            ),
            User(
                username="second",
                email="shared",
                hashed_password=get_password_hash("old-password-123"),
                is_active=True,
            ),
        ]
    )
    db.flush()

    with pytest.raises(AdminRecoveryError, match="multiple accounts"):
        recover_administrator(
            db,
            identifier="shared",
            password="new-password-123",
        )


def test_rejects_duplicate_identity_when_creating(db):
    db.add(
        User(
            username="existing",
            email="existing@example.com",
            hashed_password=get_password_hash("old-password-123"),
            is_active=True,
        )
    )
    db.flush()

    with pytest.raises(AdminRecoveryError, match="already in use"):
        recover_administrator(
            db,
            identifier="missing@example.com",
            password="new-password-123",
            create_if_missing=True,
            username="existing",
            email="different@example.com",
        )
