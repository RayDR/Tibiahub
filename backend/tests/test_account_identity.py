from __future__ import annotations

import io
from datetime import UTC, datetime, timedelta

import pytest
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.models.character_ownership import CharacterOwnershipClaim, CharacterOwnershipHistory
from app.models.email_delivery import EmailOutbox, EmailWorkerHeartbeat
from app.models.guild_management import GuildDirectory, GuildManagementGrant, GuildRosterCharacter
from app.models.user import User
from app.models.user_character import UserCharacter
from app.services.account_identity_service import AccountIdentityError, AccountIdentityService
from app.services.avatar_service import AvatarService
from app.services.email_outbox_service import EmailOutboxService
from app.services.email_service import EmailSendResult, EmailService
from app.services.media_asset_service import UnsafeMediaError
from tests.conftest import make_user


def _image(fmt: str = "PNG", size=(420, 240), *, exif_orientation: int | None = None) -> bytes:
    image = Image.new("RGB", size, (210, 30, 80))
    exif = Image.Exif()
    if exif_orientation:
        exif[274] = exif_orientation
    output = io.BytesIO()
    image.save(output, fmt, exif=exif, comment=b"private metadata")
    return output.getvalue()


def test_avatar_is_validated_cropped_metadata_free_and_path_safe(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "AVATAR_STORAGE_ROOT", str(tmp_path.resolve()))
    key, outputs = AvatarService.process(_image("JPEG", exif_orientation=6), "image/jpeg")
    assert set(outputs) == {64, 256}
    for size, payload in outputs.items():
        with Image.open(io.BytesIO(payload)) as rendered:
            assert rendered.size == (size, size)
            assert rendered.format == "WEBP"
            assert not rendered.getexif() and not rendered.info.get("comment")
    AvatarService.store(key, outputs)
    assert AvatarService.path(key, 64).is_file()
    assert AvatarService.path("../../etc/passwd", 64) is None
    AvatarService.remove(key)
    assert AvatarService.path(key, 64) is None


def test_avatar_rejects_mismatch_polyglot_and_oversize():
    png = _image("PNG")
    with pytest.raises(UnsafeMediaError):
        AvatarService.process(png, "image/jpeg")
    with pytest.raises(UnsafeMediaError):
        AvatarService.process(png + b"<script>alert(1)</script>", "image/png")
    with pytest.raises(UnsafeMediaError):
        AvatarService.process(b"x" * (settings.AVATAR_MAX_BYTES + 1), "image/png")


def test_avatar_api_preserves_legacy_fallback_and_cleans_replaced_managed_files(client, db, tmp_path, monkeypatch):
    from app.core.security import create_access_token
    monkeypatch.setattr(settings, "AVATAR_STORAGE_ROOT", str(tmp_path.resolve()))
    user = make_user(db, username="avatar-owner")
    user.avatar_url = "https://images.example.test/legacy.png"
    db.commit()
    headers = {"Authorization": f"Bearer {create_access_token(user.username)}"}
    assert client.get("/api/v1/auth/me", headers=headers).json()["avatar_url"] == user.avatar_url
    first = client.post("/api/v1/profile/me/avatar", headers=headers, files={"image": ("avatar.png", _image("PNG"), "image/png")})
    assert first.status_code == 200 and first.json()["avatar_url"].startswith("/api/v1/profile/avatars/")
    db.refresh(user); old_key = user.avatar_managed_key
    assert AvatarService.path(old_key, 64).is_file()
    second = client.post("/api/v1/profile/me/avatar", headers=headers, files={"image": ("avatar.jpg", _image("JPEG"), "image/jpeg")})
    assert second.status_code == 200
    assert AvatarService.path(old_key, 64) is None
    removed = client.delete("/api/v1/profile/me/avatar", headers=headers)
    assert removed.status_code == 200 and removed.json()["avatar_url"] is None


def test_multiple_characters_primary_and_unlink_preserve_history_and_revoke_grant(db):
    user = make_user(db, username="multi-owner", guild_name=None)
    actor = user
    first = UserCharacter(user_id=user.id, character_name="First Knight", normalized_name="first knight", ownership_status="verified", world_name="Antica", guild_name="Guild One", guild_rank="Leader")
    second = UserCharacter(user_id=user.id, character_name="Second Druid", normalized_name="second druid", ownership_status="verified", world_name="Secura", guild_name="Guild Two", guild_rank="Member")
    db.add_all([first, second]); db.flush()
    AccountIdentityService.set_primary(db, user, first, actor)
    db.add(GuildManagementGrant(user_id=user.id, guild_name="Guild One", normalized_guild_name="guild one", capability="events.manage", granted_by_id=user.id))
    db.commit(); first_id, second_id = first.id, second.id
    assert user.primary_character_id == first_id and user.guild_name == "Guild One"
    AccountIdentityService.set_primary(db, user, second, actor); db.commit()
    assert user.primary_character_id == second_id and user.guild_name == "Guild Two"
    with pytest.raises(AccountIdentityError):
        AccountIdentityService.set_primary(db, user, UserCharacter(user_id=user.id + 1, character_name="Foreign", normalized_name="foreign", ownership_status="verified"), actor)
    AccountIdentityService.unlink(db, user, first, actor, "No longer used"); db.commit()
    assert first.ownership_status == "unlinked"
    assert db.query(CharacterOwnershipHistory).filter_by(action="ownership_unlinked", normalized_name="first knight").one()
    assert db.query(GuildManagementGrant).filter_by(user_id=user.id).one().revoked_at is not None
    AccountIdentityService.unlink(db, user, second, actor, "Remove primary"); db.commit()
    assert user.primary_character_id is None and user.tibia_character_name is None


def test_admin_link_requires_explicit_transfer_and_preserves_previous_primary(db):
    admin = make_user(db, username="identity-admin", is_superuser=True)
    owner = make_user(db, username="identity-owner", guild_name=None)
    target = make_user(db, username="identity-target", guild_name=None)
    character = UserCharacter(user_id=owner.id, character_name="Owned Knight", normalized_name="owned knight", ownership_status="verified", world_name="Antica")
    db.add(character); db.flush(); AccountIdentityService.set_primary(db, owner, character, owner); db.commit()
    snapshot = {"name": "Owned Knight", "world": "Antica", "guild": {"name": "One", "rank": "Member"}}
    with pytest.raises(AccountIdentityError):
        AccountIdentityService.admin_link(db, admin=admin, target=target, character_name="Owned Knight", snapshot=snapshot, reason="Legacy ownership restoration", set_primary=True, allow_transfer=False)
    linked = AccountIdentityService.admin_link(db, admin=admin, target=target, character_name="Owned Knight", snapshot=snapshot, reason="Legacy ownership restoration", set_primary=True, allow_transfer=True)
    db.commit()
    assert linked.user_id == target.id and linked.verification_method == "admin_override"
    assert linked.verified_by_user_id == admin.id and target.primary_character_id == linked.id
    assert owner.primary_character_id is None


def test_active_challenge_is_private_retrievable_and_cleared_on_cancel(client, db):
    from app.core.security import create_access_token
    owner = make_user(db, username="challenge-owner")
    other = make_user(db, username="challenge-other")
    db.commit()
    owner_headers = {"Authorization": f"Bearer {create_access_token(owner.username)}"}
    other_headers = {"Authorization": f"Bearer {create_access_token(other.username)}"}
    created = client.post("/api/v1/character-ownership/claims", json={"character_name": "Private Knight"}, headers=owner_headers)
    challenge = created.json()["challenge"]
    claim_id = created.json()["id"]
    assert client.get(f"/api/v1/character-ownership/claims/{claim_id}", headers=owner_headers).json()["challenge"] == challenge
    assert client.get(f"/api/v1/character-ownership/claims/{claim_id}", headers=other_headers).status_code == 404
    assert client.post(f"/api/v1/character-ownership/claims/{claim_id}/cancel", headers=owner_headers).status_code == 200
    db.expire_all()
    assert db.get(CharacterOwnershipClaim, claim_id).challenge_ciphertext is None


def test_admin_identity_endpoints_deny_non_admin(client, db):
    from app.core.security import create_access_token
    member = make_user(db, username="not-identity-admin")
    db.commit()
    headers = {"Authorization": f"Bearer {create_access_token(member.username)}"}
    assert client.get("/api/v1/admin/character-ownership/search", params={"query": "Knight"}, headers=headers).status_code == 403
    assert client.post("/api/v1/admin/character-ownership/link", headers=headers, json={
        "user_id": member.id, "character_name": "Knight", "set_primary": False,
        "allow_transfer": False, "reason": "This should never be accepted",
        "confirmation": f"LINK Knight TO {member.username}",
    }).status_code == 403


def test_public_profile_never_exposes_email_or_claim(client, db):
    user = make_user(db, username="public-identity", guild_name=None)
    character = UserCharacter(user_id=user.id, character_name="Public Knight", normalized_name="public knight", ownership_status="verified", world_name="Antica")
    db.add(character); db.flush(); AccountIdentityService.set_primary(db, user, character, user)
    claim = CharacterOwnershipClaim(user_id=user.id, character_name="Secret Knight", normalized_name="secret knight", challenge_hash="a" * 64, challenge_ciphertext="encrypted", status="pending", expires_at=datetime.now(UTC) + timedelta(minutes=20))
    db.add(claim); db.commit()
    payload = client.get(f"/api/v1/profile/public/{user.username}").json()
    serialized = str(payload).casefold()
    assert "email" not in payload and "challenge" not in serialized and user.email.casefold() not in serialized
    assert payload["characters"][0]["character_name"] == "Public Knight"


@pytest.fixture()
def outbox_factory():
    from app.db.database import Base
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    yield factory
    engine.dispose()


def test_email_outbox_idempotency_retry_delivery_and_heartbeat(outbox_factory, monkeypatch):
    with outbox_factory.begin() as db:
        user = make_user(db, username="outbox-user")
        first = EmailOutboxService.enqueue_notification(db, user=user, subject="Notice", message="Safe body", event_key="event-1")
        second = EmailOutboxService.enqueue_notification(db, user=user, subject="Notice", message="Safe body", event_key="event-1")
        assert first is second
    results = iter([
        EmailSendResult(False, "failed", "connection_failed"),
        EmailSendResult(True, "sent"),
    ])
    monkeypatch.setattr(EmailService, "send_notification_email", lambda **_kwargs: next(results))
    assert EmailOutboxService.process_one(session_factory=outbox_factory, worker_id="test-email-worker")
    with outbox_factory.begin() as db:
        job = db.query(EmailOutbox).one()
        assert job.status == "retry" and job.attempt_count == 1 and job.safe_failure_category == "connection_failed"
        job.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)
    assert EmailOutboxService.process_one(session_factory=outbox_factory, worker_id="test-email-worker")
    with outbox_factory() as db:
        job = db.query(EmailOutbox).one(); heartbeat = db.get(EmailWorkerHeartbeat, "test-email-worker")
        assert job.status == "sent" and job.attempt_count == 2
        assert heartbeat.state == "idle" and heartbeat.last_success_at is not None


def test_notification_opt_out_does_not_block_security_email(db):
    user = make_user(db, username="security-email")
    user.email_notifications_enabled = False
    assert EmailOutboxService.enqueue_notification(db, user=user, subject="Optional", message="No", event_key="optional") is None
    row = EmailOutboxService.enqueue_verification(db, user=user, raw_token="secret-token", locale="en")
    db.flush()
    assert row.message_type == "email_verification"


def test_email_diagnostics_are_sanitized_and_test_delivery_is_queued(client, db, monkeypatch):
    from app.core.security import create_access_token
    admin = make_user(db, username="email-diagnostics-admin", is_superuser=True)
    db.commit()
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.test")
    monkeypatch.setattr(settings, "SMTP_USER", "smtp-user")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "never-return-this")
    monkeypatch.setattr(settings, "SMTP_FROM", "sender@example.test")
    headers = {"Authorization": f"Bearer {create_access_token(admin.username)}"}
    payload = client.get("/api/v1/password/email-diagnostics", headers=headers).json()
    assert payload["configured"] is True and payload["host"] == "smtp.example.test"
    assert "password" not in str(payload).casefold() and "never-return-this" not in str(payload)
    queued = client.post("/api/v1/password/test-email", headers=headers, json={"email": "recipient@example.com", "locale": "en"})
    assert queued.status_code == 200
    assert db.query(EmailOutbox).filter_by(message_type="smtp_test", recipient_email="recipient@example.com").one()
