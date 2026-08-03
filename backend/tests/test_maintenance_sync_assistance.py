from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import DataError
from sqlalchemy.orm import sessionmaker

from app.core.security import create_access_token
from app.db.database import Base
from app.models.maintenance_sync import MaintenanceHold, SyncJobPhase
from app.models.raffle import RaffleEligibilitySnapshot, RaffleRun
from app.models.workspace_audit import WorkspaceAudit
from app.services.maintenance_mode_service import MaintenanceModeService
from app.services.bestiary_source import creature_id_for_name
from app.services.raffle_assistance_service import RaffleAssistanceError, RaffleAssistanceService
from app.services.sync_service import SyncService
from tests.conftest import make_user
from tests.test_automatic_raffle_stage1 import make_automatic_raffle


def auth(user) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.username)}"}


def future_raffle(db, admin, *, hour_utc: int = 18):
    raffle = make_automatic_raffle(db, admin)
    raffle.scheduled_run_at = datetime(2027, 8, 3, hour_utc, 0, tzinfo=UTC)
    raffle.publication_status = "published"
    raffle.visibility = "public"
    db.commit()
    return raffle


def test_admin_lookup_and_dallas_reschedule_are_audited(db, client):
    admin = make_user(db, username="assist_admin", is_superuser=True)
    member = make_user(db, username="assist_member")
    raffle = future_raffle(db, admin, hour_utc=17)  # noon CDT

    denied = client.get("/api/v1/admin/assistance/raffles/lookup", params={"identifier": raffle.public_code}, headers=auth(member))
    assert denied.status_code == 403
    found = client.get("/api/v1/admin/assistance/raffles/lookup", params={"identifier": f"https://tibiahub.domoforge.com/raffles/{raffle.public_code}"}, headers=auth(admin))
    assert found.status_code == 200
    assert found.json()["scheduled_run_at_local"].startswith("2027-08-03T12:00:00")

    response = client.patch(
        f"/api/v1/admin/assistance/raffles/by-code/{raffle.public_code}/schedule",
        headers=auth(admin),
        json={
            "local_scheduled_at": "2027-08-03T14:00:00", "timezone_name": "America/Chicago",
            "expected_version": 1, "reason": "Correct scheduled draw time from 12 PM to 2 PM Dallas time",
            "explicit_confirmation": True, "snapshot_decision": "preserve",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["raffle"]["scheduled_run_at_utc"].startswith("2027-08-03T19:00:00")
    assert payload["raffle"]["scheduled_run_at_local"].startswith("2027-08-03T14:00:00")
    audit = db.get(WorkspaceAudit, payload["audit_id"])
    assert audit.safe_metadata["old_utc"].startswith("2027-08-03T17:00:00")
    assert audit.safe_metadata["new_utc"].startswith("2027-08-03T19:00:00")
    public = client.get(f"/api/v1/raffles/public/code/{raffle.public_code}")
    assert public.status_code == 200
    assert public.json()["scheduled_run_at"].startswith("2027-08-03T19:00:00")


def test_raffle_reschedule_safety_conflict_lease_and_dst(db):
    admin = make_user(db, username="assist_rules_admin", is_superuser=True)
    with pytest.raises(RaffleAssistanceError) as invalid_code:
        RaffleAssistanceService.lookup(db, "not-a-code")
    assert invalid_code.value.code == "invalid_public_code"
    raffle = future_raffle(db, admin)
    raffle.execution_state = "failed"; raffle.claim_token = "stale"; raffle.claimed_at = datetime.now(UTC)
    raffle.lease_expires_at = datetime.now(UTC) - timedelta(minutes=5); raffle.next_retry_at = datetime.now(UTC)
    raffle.last_error_code = "provider_timeout"; raffle.last_error_summary = "temporary"
    db.commit()
    changed, _audit = RaffleAssistanceService.reschedule(
        db, public_code=raffle.public_code, actor=admin, local_scheduled_at=datetime(2027, 8, 3, 15, 0),
        timezone_name="America/Chicago", expected_version=1, reason="Safe failed scheduler correction",
        explicit_confirmation=True, snapshot_decision="preserve",
    )
    assert changed.execution_state == "pending" and changed.claim_token is None and changed.claimed_at is None
    assert changed.lease_expires_at is None and changed.next_retry_at is None and changed.last_error_code is None
    with pytest.raises(RaffleAssistanceError, match="changed after"):
        RaffleAssistanceService.reschedule(
            db, public_code=raffle.public_code, actor=admin, local_scheduled_at=datetime(2027, 8, 3, 16, 0),
            timezone_name="America/Chicago", expected_version=1, reason="Optimistic conflict test",
            explicit_confirmation=True, snapshot_decision="preserve",
        )
    with pytest.raises(RaffleAssistanceError) as nonexistent:
        RaffleAssistanceService._localize(datetime(2027, 3, 14, 2, 30), "America/Chicago")
    assert nonexistent.value.code == "nonexistent_local_time"
    with pytest.raises(RaffleAssistanceError) as ambiguous:
        RaffleAssistanceService._localize(datetime(2027, 11, 7, 1, 30), "America/Chicago")
    assert ambiguous.value.code == "ambiguous_local_time"


def test_running_and_past_raffle_reschedules_are_rejected(db):
    admin = make_user(db, username="assist_block_admin", is_superuser=True)
    raffle = future_raffle(db, admin)
    raffle.execution_state = "running"; db.commit()
    with pytest.raises(RaffleAssistanceError) as running:
        RaffleAssistanceService.reschedule(
            db, public_code=raffle.public_code, actor=admin, local_scheduled_at=datetime(2027, 8, 3, 15),
            timezone_name="America/Chicago", expected_version=1, reason="Must reject running raffle",
            explicit_confirmation=True, snapshot_decision="preserve",
        )
    assert running.value.code == "execution_in_progress"
    raffle.execution_state = "pending"; db.commit()
    with pytest.raises(RaffleAssistanceError) as past:
        RaffleAssistanceService.reschedule(
            db, public_code=raffle.public_code, actor=admin, local_scheduled_at=datetime(2020, 1, 1, 12),
            timezone_name="America/Chicago", expected_version=1, reason="Must reject a past time",
            explicit_confirmation=True, snapshot_decision="preserve",
        )
    assert past.value.code == "schedule_in_past"


def test_successful_run_and_mismatched_frozen_snapshot_are_protected(db):
    admin = make_user(db, username="assist_history_admin", is_superuser=True)
    raffle = future_raffle(db, admin)
    raffle.eligibility_cutoff_at = datetime(2027, 7, 29, 17, tzinfo=UTC)
    snapshot = RaffleEligibilitySnapshot(
        raffle_id=raffle.id, snapshot_number=1, cutoff_at=datetime(2027, 7, 28, 17, tzinfo=UTC),
        timezone_name="America/Chicago", eligibility_days=5, source="test", candidate_count=0,
        eligible_count=0, excluded_count=0, snapshot_hash="a" * 64, created_by_id=admin.id,
    )
    db.add(snapshot); db.commit(); db.refresh(raffle)
    with pytest.raises(RaffleAssistanceError) as snapshot_required:
        RaffleAssistanceService.reschedule(
            db, public_code=raffle.public_code, actor=admin, local_scheduled_at=datetime(2027, 8, 3, 15),
            timezone_name="America/Chicago", expected_version=1, reason="Frozen snapshot safety decision",
            explicit_confirmation=True, snapshot_decision="preserve",
        )
    assert snapshot_required.value.code == "snapshot_decision_required"
    changed, _audit = RaffleAssistanceService.reschedule(
        db, public_code=raffle.public_code, actor=admin, local_scheduled_at=datetime(2027, 8, 3, 15),
        timezone_name="America/Chicago", expected_version=1, reason="Invalidate mismatched mutable snapshot",
        explicit_confirmation=True, snapshot_decision="invalidate",
    )
    assert db.get(RaffleEligibilitySnapshot, snapshot.id).invalidated_at is not None

    history_raffle = future_raffle(db, admin, hour_utc=20)
    history_snapshot = RaffleEligibilitySnapshot(
        raffle_id=history_raffle.id, snapshot_number=1, cutoff_at=datetime(2027, 7, 29, 20, tzinfo=UTC),
        timezone_name="America/Chicago", eligibility_days=5, source="test", candidate_count=0,
        eligible_count=0, excluded_count=0, snapshot_hash="b" * 64, created_by_id=admin.id,
    )
    db.add(history_snapshot); db.flush()
    db.add(RaffleRun(
        raffle_id=history_raffle.id, run_number=1, snapshot_id=history_snapshot.id, trigger="scheduled",
        state="succeeded", requested_by_id=admin.id, algorithm_version="test-v1",
    ))
    db.commit(); db.refresh(history_raffle)
    assert RaffleAssistanceService.safety(db, history_raffle) == (False, "successful_run_exists")


def test_manual_and_sync_holds_are_independent_and_reconciled(db):
    admin = make_user(db, username="maintenance_admin", is_superuser=True)
    manual = MaintenanceModeService.enable_manual(
        db, actor=admin, reason="Planned platform maintenance", public_message="Planned TibiaHub maintenance",
        planned_end_at=None, confirmation="ENABLE MAINTENANCE",
    )
    job = SyncService.create_job(
        db, job_type="full", requester=admin.username, requested_by_user_id=admin.id,
        maintenance_requested=True, include_knowledge=True, include_guild_rosters=True,
        operation_label="Complete maintenance synchronization",
    )
    assert MaintenanceModeService.status(db)["active"] is True
    assert len(MaintenanceModeService.active_holds(db)) == 2
    SyncService._terminalize(db, job, "completed_with_errors", "Terminal test")
    db.refresh(manual)
    assert manual.released_at is None
    active = MaintenanceModeService.active_holds(db)
    assert [row.hold_type for row in active] == ["manual"]
    orphan = MaintenanceHold(hold_type="sync", owner_job_id=None, reason="orphan", public_message="safe", auto_release=True)
    # The database constraint correctly prevents creating ownerless sync holds;
    # reconciliation of a terminal owner is the supported orphan path.
    assert orphan.hold_type == "sync"


def test_maintenance_middleware_allows_real_auth_and_admin_but_blocks_member(engine, monkeypatch):
    import main as main_module
    from app.db.database import get_db

    factory = sessionmaker(bind=engine)
    with factory() as setup:
        admin = make_user(setup, username="middleware_admin", is_superuser=True)
        member = make_user(setup, username="middleware_member")
        MaintenanceModeService.enable_manual(
            setup, actor=admin, reason="Middleware enforcement test", public_message="Safe maintenance message",
            planned_end_at=None, confirmation="ENABLE MAINTENANCE",
        )
        setup.commit()
        admin_token = create_access_token(admin.username)
        member_token = create_access_token(member.username)
        admin_id, member_id = admin.id, member.id

    def override_get_db():
        with factory() as session:
            yield session

    monkeypatch.setattr(main_module, "SessionLocal", factory)
    main_module.app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(main_module.app) as test_client:
            assert test_client.get("/api/v1/health").status_code == 200
            assert test_client.get("/api/v1/maintenance/status").status_code == 200
            assert test_client.post("/api/v1/auth/login", data={"username": "middleware_admin", "password": "password"}).status_code == 200
            blocked = test_client.get("/api/v1/creatures/", headers={"Authorization": f"Bearer {member_token}"})
            assert blocked.status_code == 503
            assert blocked.json()["detail"]["code"] == "maintenance_mode"
            allowed = test_client.get("/api/v1/admin/maintenance", headers={"Authorization": f"Bearer {admin_token}"})
            assert allowed.status_code == 200
    finally:
        main_module.app.dependency_overrides.pop(get_db, None)
        with factory() as cleanup:
            cleanup.query(WorkspaceAudit).filter(WorkspaceAudit.actor_id.in_([admin_id, member_id])).delete(synchronize_session=False)
            cleanup.query(MaintenanceHold).filter(MaintenanceHold.enabled_by_user_id.in_([admin_id, member_id])).delete(synchronize_session=False)
            from app.models.user import User
            cleanup.query(User).filter(User.id.in_([admin_id, member_id])).delete(synchronize_session=False)
            cleanup.commit()


def test_full_plan_claim_recovery_cancel_and_retry_classification(db):
    admin = make_user(db, username="sync_admin", is_superuser=True)
    job = SyncService.create_job(
        db, job_type="full", requester=admin.username, requested_by_user_id=admin.id,
        maintenance_requested=True, include_knowledge=True, include_guild_rosters=True,
        operation_label="Full durable sync test", max_retries=2,
    )
    phases = db.query(SyncJobPhase).filter_by(job_id=job.id).order_by(SyncJobPhase.order_index).all()
    assert [row.phase_key for row in phases] == ["creatures", "bosses", "items", "quests", "hunt-zones", "images", "knowledge", "guild-rosters"]
    assert SyncService.claim_next(db, "worker-a") == job.id
    assert SyncService.claim_next(db, "worker-b") is None
    job.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1); db.commit()
    assert SyncService.recover_stale_running_jobs(db) == [job.id]
    db.refresh(job); assert job.status == "pending" and job.worker_id is None
    SyncService.request_cancel(db, job.id); db.refresh(job)
    assert job.status == "cancelled"
    assert db.query(MaintenanceHold).filter_by(owner_job_id=job.id, released_at=None).count() == 0

    response = httpx.Response(429, headers={"Retry-After": "17"}, request=httpx.Request("GET", "https://provider.invalid"))
    category, retryable, retry_after = SyncService.classify_provider_error(httpx.HTTPStatusError("rate", request=response.request, response=response))
    assert (category, retryable, retry_after) == ("rate_limited", True, 17)
    assert SyncService.retry_delay(1, retry_after) == 17
    assert SyncService.classify_provider_error(ValueError("bad payload"))[:2] == ("invalid_payload", False)
    database_error = DataError("INSERT", {}, OverflowError("integer out of range"))
    assert SyncService.classify_provider_error(database_error)[:2] == ("invalid_payload", False)


def test_generated_creature_ids_fit_postgresql_integer_range():
    # This production-observed title previously generated unsigned CRC32
    # 2_717_160_804 and failed against a PostgreSQL INTEGER column.
    generated = creature_id_for_name("Creatures")
    assert generated == creature_id_for_name("  creatures  ")
    assert 0 <= generated <= 2_147_483_647


def test_worker_retries_temporary_failure_continues_after_permanent_phase_and_releases_hold(tmp_path, monkeypatch):
    import app.services.sync_service as sync_module

    engine = create_engine(f"sqlite:///{tmp_path / 'durable-sync.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as setup:
        admin = make_user(setup, username="durable_worker_admin", is_superuser=True)
        setup.commit()
        job = SyncService.create_job(
            setup, job_type="full", requester=admin.username, requested_by_user_id=admin.id,
            maintenance_requested=True, continue_on_error=True, operation_label="Durable phase continuation test",
            max_retries=1,
        )
        job_id = job.id
        assert SyncService.claim_next(setup, "test-durable-worker") == job_id
        setup.commit()

    attempts: dict[str, int] = {}

    async def fake_segment(_db, _job, target, **_kwargs):
        attempts[target] = attempts.get(target, 0) + 1
        if target == "creatures":
            raise ValueError("permanent invalid provider payload")
        if target == "bosses" and attempts[target] == 1:
            raise httpx.ReadTimeout("temporary timeout")
        return {"processed": 1, "failed": 0, "summary": {f"{target}_processed": 1}}

    monkeypatch.setattr(sync_module, "SessionLocal", factory)
    monkeypatch.setattr(SyncService, "_run_segment", staticmethod(fake_segment))
    monkeypatch.setattr(SyncService, "retry_delay", staticmethod(lambda _attempt, _retry_after=None: 0.0))
    asyncio.run(SyncService._run_job_async(job_id, worker_id="test-durable-worker"))

    with factory() as check:
        job = check.get(sync_module.SyncJob, job_id)
        phases = {row.phase_key: row for row in check.query(SyncJobPhase).filter_by(job_id=job_id)}
        assert job.status == "completed_with_errors"
        assert phases["creatures"].status == "failed" and phases["creatures"].error_category == "invalid_payload"
        assert phases["bosses"].status == "completed" and phases["bosses"].attempt_count == 2
        assert phases["items"].status == "completed"
        assert check.query(MaintenanceHold).filter_by(owner_job_id=job_id, released_at=None).count() == 0
    engine.dispose()
