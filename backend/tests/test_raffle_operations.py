from datetime import UTC, datetime, timedelta

import pytest

from app.core.security import create_access_token
from app.models.raffle import InternalNotification, RaffleSchedulerAttempt, RaffleSchedulerState
from app.models.user_character import UserCharacter
from app.services.notification_service import NotificationService
from app.services.raffle_scheduler_service import RaffleSchedulerService
from app.services.raffle_eligibility_service import compute_eligibility_cutoff
from tests.conftest import make_user
from tests.test_automatic_raffle_stage1 import make_automatic_raffle


def auth(user):
    return {"Authorization": f"Bearer {create_access_token(user.username)}"}


def due_raffle(db, creator, *, purpose="test"):
    raffle = make_automatic_raffle(db, creator, purpose=purpose)
    raffle.scheduled_run_at = datetime.now(UTC) - timedelta(minutes=5)
    db.commit()
    return raffle


def test_due_discovery_ignores_legacy_and_manual(db):
    admin = make_user(db, username="scheduler_due_admin", is_superuser=True)
    due = due_raffle(db, admin)
    legacy = make_automatic_raffle(db, admin)
    legacy.scheduled_run_at = datetime.now(UTC) - timedelta(minutes=5)
    legacy.purpose = "legacy"
    manual = make_automatic_raffle(db, admin)
    manual.scheduled_run_at = datetime.now(UTC) - timedelta(minutes=5)
    manual.run_mode = "manual"
    db.commit()
    ids = {row.id for row in RaffleSchedulerService("worker-a").due_query(db).all()}
    assert due.id in ids
    assert legacy.id not in ids
    assert manual.id not in ids


def test_chicago_calendar_cutoff_crosses_dst_in_utc():
    draw = datetime(2026, 11, 4, 2, 0, tzinfo=UTC)  # Nov 3, 8 PM CST
    assert compute_eligibility_cutoff(draw, "America/Chicago", 5) == datetime(2026, 10, 30, 1, 0, tzinfo=UTC)


def test_atomic_claim_and_two_workers(db):
    admin = make_user(db, username="scheduler_claim_admin", is_superuser=True)
    raffle = due_raffle(db, admin)
    first = RaffleSchedulerService("worker-a").claim_one(db)
    second = RaffleSchedulerService("worker-b").claim_one(db)
    assert first and first[0] == raffle.id
    assert second is None
    assert db.query(RaffleSchedulerAttempt).filter_by(raffle_id=raffle.id).count() == 1


def test_expired_lease_is_recovered_without_success_duplication(db):
    admin = make_user(db, username="scheduler_recovery_admin", is_superuser=True)
    raffle = due_raffle(db, admin)
    raffle.execution_state = "claimed"
    raffle.claim_token = "abandoned"
    raffle.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()
    claim = RaffleSchedulerService("recovery-worker").claim_one(db)
    assert claim and claim[0] == raffle.id and claim[1] != "abandoned"
    raffle.execution_state = "succeeded"
    raffle.claim_token = None
    db.commit()
    assert RaffleSchedulerService("other-worker").claim_one(db) is None


def test_heartbeat_and_admin_authorization(db, client):
    admin = make_user(db, username="scheduler_health_admin", is_superuser=True)
    member = make_user(db, username="scheduler_health_member")
    RaffleSchedulerService("health-worker").heartbeat(db, success=True)
    assert db.get(RaffleSchedulerState, "health-worker").last_success_at is not None
    assert client.get("/api/v1/notifications/scheduler-health", headers=auth(member)).status_code == 403
    response = client.get("/api/v1/notifications/scheduler-health", headers=auth(admin))
    assert response.status_code == 200
    assert "due_job_count" in response.json()


def test_notification_deduplication_ownership_and_read(db, client):
    admin = make_user(db, username="notify_admin", is_superuser=True)
    other = make_user(db, username="notify_other", guild_name="OTHER")
    raffle = due_raffle(db, admin)
    NotificationService.emit(db, raffle, "raffle_scheduled", f"raffle:{raffle.id}:scheduled")
    NotificationService.emit(db, raffle, "raffle_scheduled", f"raffle:{raffle.id}:scheduled")
    db.commit()
    note = db.query(InternalNotification).filter_by(recipient_user_id=admin.id).one()
    assert client.get("/api/v1/notifications/unread-count", headers=auth(admin)).json() == {"unread_count": 1}
    assert client.post(f"/api/v1/notifications/{note.id}/read", headers=auth(other)).status_code == 404
    assert client.post(f"/api/v1/notifications/{note.id}/read", headers=auth(admin)).status_code == 200
    assert client.get("/api/v1/notifications/unread-count", headers=auth(admin)).json() == {"unread_count": 0}


@pytest.mark.asyncio
async def test_permanent_failure_is_not_retried(db, monkeypatch):
    admin = make_user(db, username="scheduler_failure_admin", is_superuser=True)
    raffle = due_raffle(db, admin)
    service = RaffleSchedulerService("failure-worker")
    claim = service.claim_one(db)
    async def fail(*_args, **_kwargs):
        from app.services.automatic_raffle_service import AutomaticRaffleError
        raise AutomaticRaffleError("invalid_prizes", "Safe invalid configuration")
    monkeypatch.setattr("app.services.raffle_scheduler_service.AutomaticRaffleService.execute", fail)
    assert claim and await service.execute_claim(db, *claim) is False
    db.refresh(raffle)
    assert raffle.next_retry_at is None
    assert db.query(RaffleSchedulerAttempt).filter_by(raffle_id=raffle.id).one().state == "failed_permanent"


@pytest.mark.asyncio
async def test_transient_failure_uses_bounded_retry(db, monkeypatch):
    admin = make_user(db, username="scheduler_retry_admin", is_superuser=True)
    raffle = due_raffle(db, admin)
    service = RaffleSchedulerService("retry-worker")
    claim = service.claim_one(db)
    async def fail(*_args, **_kwargs):
        from app.services.raffle_eligibility_service import RaffleEligibilityError
        raise RaffleEligibilityError("guild_source_unavailable", "Current guild membership is unavailable")
    monkeypatch.setattr("app.services.raffle_scheduler_service.AutomaticRaffleService.execute", fail)
    assert claim and await service.execute_claim(db, *claim) is False
    db.refresh(raffle)
    attempt = db.query(RaffleSchedulerAttempt).filter_by(raffle_id=raffle.id).one()
    assert attempt.state == "retry_scheduled" and attempt.retryable is True
    assert raffle.next_retry_at is not None


def test_test_participants_require_existing_local_guild_account(db, client):
    admin = make_user(db, username="test_fixture_admin", is_superuser=True)
    participant = make_user(db, username="test_fixture_member")
    db.add(UserCharacter(user_id=participant.id, character_name="Fixture Knight", guild_name="TEST GUILD", guild_rank="Member"))
    test_raffle = due_raffle(db, admin, purpose="test")
    real_raffle = due_raffle(db, admin, purpose="real")
    db.commit()
    added = client.post(f"/api/v1/raffles/{test_raffle.id}/participants/manual", json={"character_name": "Fixture Knight"}, headers=auth(admin))
    assert added.status_code == 200
    missing = client.post(f"/api/v1/raffles/{test_raffle.id}/participants/manual", json={"character_name": "Nonexistent Fixture"}, headers=auth(admin))
    assert missing.status_code == 400
    real = client.post(f"/api/v1/raffles/{real_raffle.id}/participants/manual", json={"character_name": "Fixture Knight"}, headers=auth(admin))
    assert real.status_code == 400
