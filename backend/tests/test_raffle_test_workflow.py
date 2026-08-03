from datetime import UTC, datetime, timedelta

from app.models.raffle import (
    Raffle, RaffleEligibilitySnapshot, RaffleParticipant, RaffleRun,
    RaffleSchedulerAttempt, RaffleTestAudit,
)
from app.models.user import User
from app.models.user_character import UserCharacter
from tests.conftest import make_user
from tests.test_automatic_raffle_stage1 import auth, make_automatic_raffle


def automatic_payload(*, purpose="test", scheduled_run_at=None):
    return {
        "title": "Isolated automatic test",
        "guild_name": "TEST GUILD",
        "access_mode": "guild_only",
        "show_participants": True,
        "run_mode": "automatic",
        "purpose": purpose,
        "timezone_name": "America/Chicago",
        "eligibility_days": 5,
        "scheduled_run_at": (scheduled_run_at or datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
        "prizes": [
            {"name": "Second place", "reward": "100 TC", "order_index": 1, "position": "second", "amount": 100, "currency": "TC"},
            {"name": "First place", "reward": "250 TC", "order_index": 2, "position": "first", "amount": 250, "currency": "TC"},
        ],
    }


def test_test_raffle_rejects_past_schedule(db, client):
    admin = make_user(db, username="test_workflow_past_admin", is_superuser=True)
    past = automatic_payload(scheduled_run_at=datetime.now(UTC) - timedelta(minutes=1))
    assert client.post("/api/v1/raffles/", json=past, headers=auth(admin)).status_code == 400


def test_test_raffle_rejects_schedule_beyond_seven_days(db, client):
    admin = make_user(db, username="test_workflow_future_admin", is_superuser=True)
    too_far = automatic_payload(scheduled_run_at=datetime.now(UTC) + timedelta(days=8))
    assert client.post("/api/v1/raffles/", json=too_far, headers=auth(admin)).status_code == 400


def test_test_raffle_near_future_creation_is_audited(db, client):
    admin = make_user(db, username="test_workflow_create_admin", is_superuser=True)
    created = client.post("/api/v1/raffles/", json=automatic_payload(), headers=auth(admin))
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["purpose"] == "test"
    assert [(prize["position"], float(prize["amount"])) for prize in body["prizes"]] == [("second", 100.0), ("first", 250.0)]
    assert db.query(RaffleTestAudit).filter_by(raffle_id=body["id"], action="test_raffle_created").count() == 1


def test_test_participant_duplicate_override_and_removal_are_isolated(db, client):
    admin = make_user(db, username="test_workflow_participant_admin", is_superuser=True)
    member = make_user(db, username="test_workflow_member")
    db.add(UserCharacter(user_id=member.id, character_name="Workflow Knight", normalized_name="workflow knight", ownership_status="verified", ownership_verified_at=datetime.now(UTC), guild_name="TEST GUILD", guild_rank="Member"))
    raffle = make_automatic_raffle(db, admin)
    db.commit()

    added = client.post(f"/api/v1/raffles/{raffle.id}/participants/manual", json={"character_name": "Workflow Knight"}, headers=auth(admin))
    assert added.status_code == 200, added.text
    participant_id = next(row["id"] for row in added.json()["participants"] if row["user_id"] == member.id)
    assert client.post(f"/api/v1/raffles/{raffle.id}/participants/manual", json={"character_name": "Workflow Knight"}, headers=auth(admin)).status_code == 400

    overridden = client.patch(
        f"/api/v1/raffles/{raffle.id}/participants/{participant_id}/test-eligibility-override",
        json={"eligible": False, "reason": "Exercise exclusion path"}, headers=auth(admin),
    )
    assert overridden.status_code == 200, overridden.text
    assert db.query(RaffleTestAudit).filter_by(raffle_id=raffle.id, action="test_eligibility_override").count() == 1

    removed = client.delete(f"/api/v1/raffles/{raffle.id}/participants/{participant_id}", headers=auth(admin))
    assert removed.status_code == 200, removed.text
    assert db.get(User, member.id) is not None
    assert db.get(RaffleParticipant, participant_id).is_deleted is True


def test_eligibility_override_is_global_admin_test_only_and_pre_freeze(db, client):
    admin = make_user(db, username="test_workflow_boundary_admin", is_superuser=True)
    manager = make_user(db, username="test_workflow_boundary_manager", guild_rank="Leader")
    member = make_user(db, username="test_workflow_boundary_member")
    db.add(UserCharacter(user_id=member.id, character_name="Boundary Knight", normalized_name="boundary knight", ownership_status="verified", ownership_verified_at=datetime.now(UTC), guild_name="TEST GUILD", guild_rank="Member"))
    test_raffle = make_automatic_raffle(db, admin)
    real_raffle = make_automatic_raffle(db, admin, purpose="real")
    db.commit()
    for raffle in (test_raffle, real_raffle):
        response = client.post(f"/api/v1/raffles/{raffle.id}/participants/manual", json={"character_name": "Boundary Knight"}, headers=auth(admin))
        if raffle.purpose == "test":
            assert response.status_code == 200
            participant_id = response.json()["participants"][0]["id"]
        else:
            assert response.status_code == 400

    url = f"/api/v1/raffles/{test_raffle.id}/participants/{participant_id}/test-eligibility-override"
    payload = {"eligible": True, "reason": "Exercise stale activity override"}
    assert client.patch(url, json=payload, headers=auth(manager)).status_code == 403
    assert client.patch(url, json=payload, headers=auth(admin)).status_code == 200


def test_cleanup_archives_only_test_associations_and_preserves_audit(db, client):
    admin = make_user(db, username="test_workflow_cleanup_admin", is_superuser=True)
    member = make_user(db, username="test_workflow_cleanup_member")
    db.add(UserCharacter(user_id=member.id, character_name="Cleanup Knight", normalized_name="cleanup knight", ownership_status="verified", ownership_verified_at=datetime.now(UTC), guild_name="TEST GUILD", guild_rank="Member"))
    test_raffle = make_automatic_raffle(db, admin)
    real_raffle = make_automatic_raffle(db, admin, purpose="real")
    db.commit()
    added = client.post(f"/api/v1/raffles/{test_raffle.id}/participants/manual", json={"character_name": "Cleanup Knight"}, headers=auth(admin))
    assert added.status_code == 200

    assert client.post(f"/api/v1/raffles/{real_raffle.id}/test-cleanup", json={"confirmation": "ARCHIVE TEST RAFFLE", "reason": "Reject real cleanup"}, headers=auth(admin)).status_code == 400
    cleaned = client.post(
        f"/api/v1/raffles/{test_raffle.id}/test-cleanup",
        json={"confirmation": "ARCHIVE TEST RAFFLE", "reason": "End isolated workflow"}, headers=auth(admin),
    )
    assert cleaned.status_code == 200, cleaned.text
    assert cleaned.json()["participant_associations_removed"] == 1
    assert cleaned.json()["users_modified"] == cleaned.json()["guilds_modified"] == cleaned.json()["real_raffles_modified"] == 0
    assert db.get(User, member.id) is not None
    db.refresh(real_raffle)
    assert real_raffle.status != "cancelled"
    assert db.query(RaffleTestAudit).filter_by(raffle_id=test_raffle.id, action="test_cleanup").count() == 1


def test_safe_retry_is_global_admin_and_test_only(db, client):
    admin = make_user(db, username="test_workflow_retry_admin", is_superuser=True)
    member = make_user(db, username="test_workflow_retry_member")
    test_raffle = make_automatic_raffle(db, admin)
    real_raffle = make_automatic_raffle(db, admin, purpose="real")
    for raffle in (test_raffle, real_raffle):
        raffle.execution_state = "failed"
        raffle.last_error_code = "guild_source_unavailable"
    db.commit()
    payload = {"reason": "Retry transient guild source failure"}

    assert client.post(f"/api/v1/raffles/{test_raffle.id}/test-retry", json=payload, headers=auth(member)).status_code == 403
    assert client.post(f"/api/v1/raffles/{real_raffle.id}/test-retry", json=payload, headers=auth(admin)).status_code == 400
    retried = client.post(f"/api/v1/raffles/{test_raffle.id}/test-retry", json=payload, headers=auth(admin))
    assert retried.status_code == 200, retried.text
    assert retried.json()["execution_state"] == "pending"
    assert db.query(RaffleTestAudit).filter_by(raffle_id=test_raffle.id, action="test_scheduler_retry").count() == 1


def test_failed_test_raffle_with_manager_review_and_audits_can_be_permanently_deleted(db, client):
    admin = make_user(db, username="test_delete_admin", is_superuser=True)
    unrelated_user = make_user(db, username="test_delete_unrelated")
    test_raffle = make_automatic_raffle(db, admin)
    real_raffle = make_automatic_raffle(db, admin, purpose="real")
    test_raffle.execution_state = "failed"
    test_raffle.last_error_code = "manager_review_required"
    test_raffle.last_error_summary = "Manager review error"
    snapshot = RaffleEligibilitySnapshot(
        raffle=test_raffle, snapshot_number=1, cutoff_at=datetime.now(UTC), timezone_name="UTC",
        eligibility_days=7, source="persisted_raffle_participants", candidate_count=0,
        eligible_count=0, excluded_count=0, snapshot_hash="a" * 64, created_by_id=admin.id,
    )
    db.add(snapshot)
    db.flush()
    db.add_all([
        RaffleRun(
            raffle_id=test_raffle.id, run_number=1, snapshot_id=snapshot.id,
            trigger="scheduler", state="failed", requested_by_id=admin.id,
            failure_code="manager_review_required", failure_summary="Manager review error",
            algorithm_version="hmac-sha256-rejection-v2",
        ),
        RaffleSchedulerAttempt(
            raffle_id=test_raffle.id, job_id="failed-test-delete-job", worker_id="test-worker",
            trigger="scheduler", attempt_number=1, state="failed", retryable=False,
            failure_code="manager_review_required", failure_summary="Manager review error",
            claimed_at=datetime.now(UTC), completed_at=datetime.now(UTC),
        ),
        RaffleTestAudit(
            raffle_id=test_raffle.id, raffle_id_snapshot=test_raffle.id,
            raffle_title_snapshot=test_raffle.title, guild_name_snapshot=test_raffle.guild_name,
            actor_id=admin.id, action="manager_review_error",
            details={"failure_code": "manager_review_required"},
        ),
    ])
    db.commit()
    deleted_id = test_raffle.id
    real_id = real_raffle.id
    unrelated_id = unrelated_user.id

    protected_real = client.delete(
        f"/api/v1/raffles/{real_id}/permanent",
        params={"reason": "Must remain protected", "confirmation": f"DELETE RAFFLE {real_id}"},
        headers=auth(admin),
    )
    assert protected_real.status_code == 409

    response = client.delete(
        f"/api/v1/raffles/{deleted_id}/permanent",
        params={"reason": "Remove failed isolated test", "confirmation": f"DELETE RAFFLE {deleted_id}"},
        headers=auth(admin),
    )
    assert response.status_code == 200, response.text
    assert response.json()["deleted"] is True and response.json()["audit_preserved"] is True
    assert db.get(Raffle, deleted_id) is None
    preserved = db.query(RaffleTestAudit).filter_by(raffle_id_snapshot=deleted_id).all()
    assert {row.action for row in preserved} >= {"manager_review_error", "test_raffle_permanently_deleted"}
    assert all(row.raffle_id is None for row in preserved)
    assert db.get(Raffle, real_id) is not None
    assert db.get(User, unrelated_id) is not None
