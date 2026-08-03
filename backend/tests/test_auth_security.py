from __future__ import annotations

from datetime import timedelta
from urllib.parse import parse_qs, urlparse

from app.core.security import verify_password
from app.models.auth_security import AuthOneTimeToken, AuthRequestEvent
from app.models.user import User
from app.models.user_character import UserCharacter
from app.services.auth_token_service import AuthTokenService, EMAIL_VERIFICATION, PASSWORD_RESET
from tests.conftest import make_user


def _token_from_link(link: str) -> str:
    return parse_qs(urlparse(link).query)["token"][0]


def test_auth_me_serializes_legacy_internal_email_without_weakening_registration(client, db):
    from app.core.security import create_access_token

    user = make_user(db, username="legacy-email-admin", is_superuser=True)
    user.email = "admin@tibiahub.local"
    db.commit()
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {create_access_token(user.username)}"},
    )
    assert response.status_code == 200
    assert response.json()["email"] == "admin@tibiahub.local"
    assert client.post("/api/v1/auth/register", json={
        "username": "invalid-new-email",
        "email": "new@tibiahub.local",
        "password": "valid password 2026",
    }).status_code == 422


def test_registration_does_not_claim_character_and_verification_is_single_use(client, db, monkeypatch):
    sent: list[dict] = []
    monkeypatch.setattr(
        "app.services.email_service.EmailService.send_verification_email",
        lambda **kwargs: sent.append(kwargs) or type("Result", (), {"ok": True})(),
    )
    response = client.post("/api/v1/auth/register", json={
        "username": "secure-register",
        "email": "secure-register@example.com",
        "password": "correct horse battery staple 7",
        "tibia_character_name": "Name Is Not Proof",
        "locale": "es",
    })
    assert response.status_code == 200
    user = db.query(User).filter_by(username="secure-register").one()
    assert user.tibia_character_name is None
    assert user.characters == []
    assert user.tibia_status == "ownership_unverified"
    assert len(sent) == 1 and sent[0]["locale"] == "es"

    raw = _token_from_link(sent[0]["verification_link"])
    stored = db.query(AuthOneTimeToken).filter_by(user_id=user.id, purpose=EMAIL_VERIFICATION).one()
    assert stored.token_hash != raw and raw not in stored.token_hash
    assert client.post("/api/v1/email-verification/confirm", json={"token": raw}).status_code == 200
    db.refresh(user)
    assert user.email_verified_at is not None
    assert client.post("/api/v1/email-verification/confirm", json={"token": raw}).status_code == 400


def test_password_recovery_is_neutral_rate_limited_hashed_and_replay_safe(client, db, monkeypatch):
    user = make_user(db, username="recovery-user")
    user.email = "recovery-user@example.com"
    db.commit()
    sent: list[dict] = []
    monkeypatch.setattr(
        "app.services.email_service.EmailService.send_password_reset_email",
        lambda **kwargs: sent.append(kwargs) or type("Result", (), {"ok": True})(),
    )

    known = client.post("/api/v1/password/request-reset", json={"email": user.email, "locale": "en"})
    unknown = client.post("/api/v1/password/request-reset", json={"email": "missing-account@example.com", "locale": "en"})
    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()
    assert len(sent) == 1
    raw = _token_from_link(sent[0]["reset_link"])
    row = db.query(AuthOneTimeToken).filter_by(user_id=user.id, purpose=PASSWORD_RESET).one()
    assert len(row.token_hash) == 64 and raw not in row.token_hash

    repeated = client.post("/api/v1/password/request-reset", json={"email": user.email, "locale": "en"})
    assert repeated.status_code == 200 and repeated.json() == known.json()
    assert len(sent) == 1
    assert db.query(AuthRequestEvent).filter_by(purpose=PASSWORD_RESET).count() == 2

    reset = client.post("/api/v1/password/reset-password", json={
        "token": raw, "new_password": "new secure password 2026",
    })
    assert reset.status_code == 200
    db.refresh(user)
    assert verify_password("new secure password 2026", user.hashed_password)
    assert client.post("/api/v1/password/reset-password", json={
        "token": raw, "new_password": "another secure password 2",
    }).status_code == 400


def test_character_recovery_requires_verified_ownership(client, db, monkeypatch):
    user = make_user(db, username="character-recovery")
    db.add_all([
        UserCharacter(user_id=user.id, character_name="Legacy Name", normalized_name="legacy name"),
        UserCharacter(
            user_id=user.id, character_name="Verified Name", normalized_name="verified name",
            ownership_status="verified", ownership_verified_at=user.created_at,
        ),
    ])
    db.commit()
    sent: list[dict] = []
    monkeypatch.setattr(
        "app.services.email_service.EmailService.send_password_reset_email",
        lambda **kwargs: sent.append(kwargs) or type("Result", (), {"ok": True})(),
    )
    legacy = client.post("/api/v1/password/request-reset", json={"character_name": "Legacy Name"})
    verified = client.post("/api/v1/password/request-reset", json={"character_name": "Verified Name"})
    assert legacy.status_code == verified.status_code == 200
    assert legacy.json() == verified.json()
    assert len(sent) == 1


def test_issuing_a_new_token_invalidates_old_and_expired_tokens_fail(db):
    user = make_user(db, username="token-lifecycle")
    first = AuthTokenService.issue(db, user=user, purpose=PASSWORD_RESET, ttl=timedelta(minutes=10))
    second = AuthTokenService.issue(db, user=user, purpose=PASSWORD_RESET, ttl=timedelta(minutes=10))
    expired = AuthTokenService.issue(db, user=user, purpose=EMAIL_VERIFICATION, ttl=timedelta(seconds=-1))
    db.commit()
    assert AuthTokenService.consume(db, purpose=PASSWORD_RESET, raw_token=first) is None
    assert AuthTokenService.consume(db, purpose=PASSWORD_RESET, raw_token=second) == user
    assert AuthTokenService.consume(db, purpose=EMAIL_VERIFICATION, raw_token=expired) is None


def test_email_or_password_profile_change_revokes_pending_tokens_and_rejects_legacy_password_field(client, db):
    from app.core.security import create_access_token

    user = make_user(db, username="profile-token-revoke")
    email_token = AuthTokenService.issue(db, user=user, purpose=EMAIL_VERIFICATION, ttl=timedelta(minutes=10))
    reset_token = AuthTokenService.issue(db, user=user, purpose=PASSWORD_RESET, ttl=timedelta(minutes=10))
    db.commit()
    headers = {"Authorization": f"Bearer {create_access_token(user.username)}"}
    bypass = client.put("/api/v1/profile/me", json={"password": "bypass password value"}, headers=headers)
    assert bypass.status_code == 422
    changed = client.put("/api/v1/profile/me", json={"email": "new-profile-email@example.com"}, headers=headers)
    assert changed.status_code == 200 and changed.json()["email_verified_at"] is None
    assert AuthTokenService.consume(db, purpose=EMAIL_VERIFICATION, raw_token=email_token) is None
    assert AuthTokenService.consume(db, purpose=PASSWORD_RESET, raw_token=reset_token) is None


def test_registration_rejects_casefolded_account_duplicates(client, db):
    user = make_user(db, username="CaseFoldedUser")
    user.email = "casefolded@example.com"
    db.commit()
    username = client.post("/api/v1/auth/register", json={
        "username": "casefoldeduser", "email": "another@example.com",
        "password": "a sufficiently long password 4",
    })
    email = client.post("/api/v1/auth/register", json={
        "username": "another-user", "email": "CASEFOLDED@example.com",
        "password": "a sufficiently long password 4",
    })
    assert username.status_code == email.status_code == 400


def test_test_environment_never_opens_smtp(monkeypatch):
    from email.message import EmailMessage
    from app.services.email_service import EmailService

    monkeypatch.setattr("smtplib.SMTP", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("network SMTP used")))
    message = EmailMessage()
    message["To"] = "nobody@example.test"
    assert EmailService.send_message(message).ok is True
