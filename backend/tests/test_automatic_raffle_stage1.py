from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.core.security import create_access_token
from app.models.raffle import (
    RaffleEligibilitySnapshot, RaffleManagerGrant, RafflePrize, RaffleRerunAudit,
    RaffleRun, RaffleRunResult,
)
from app.models.user_character import UserCharacter
from app.services.automatic_raffle_service import (
    AutomaticRaffleError, AutomaticRaffleService, POSITIONS, validate_automatic_prizes,
)
from app.services.raffle_eligibility_service import RaffleEligibilityService, compute_eligibility_cutoff
from tests.conftest import make_raffle, make_user


DRAW_AT = datetime(2026, 7, 25, 1, 0, tzinfo=UTC)
CUTOFF_AT = datetime(2026, 7, 20, 1, 0, tzinfo=UTC)


def auth(user) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.username)}"}


def make_automatic_raffle(db, creator, *, purpose="test", guild_name="TEST GUILD"):
    raffle = make_raffle(db, creator_id=creator.id, guild_name=guild_name, status="closed")
    raffle.purpose = purpose
    raffle.run_mode = "automatic"
    raffle.timezone_name = "America/Chicago"
    raffle.eligibility_days = 5
    raffle.scheduled_run_at = DRAW_AT
    raffle.execution_state = "pending"
    raffle.publication_status = "private"
    raffle.version = 1
    db.add_all([
        RafflePrize(raffle_id=raffle.id, name="Second place", reward="100 TC", order_index=1, position="second", amount=100, currency="TC"),
        RafflePrize(raffle_id=raffle.id, name="First place", reward="250 TC", order_index=2, position="first", amount=250, currency="TC"),
    ])
    db.flush()
    db.refresh(raffle)
    return raffle


def add_candidate(db, username, *, guild_name="TEST GUILD", active=True, guest=False, last_login_at=CUTOFF_AT):
    actual = f"guest_{username}" if guest else username
    user = make_user(db, username=actual, guild_name=guild_name)
    user.is_active = active
    user.last_login_at = last_login_at
    character_name = f"{username} Character"
    character = UserCharacter(
        user_id=user.id, character_name=character_name,
        normalized_name=character_name.casefold(), ownership_status="verified",
        ownership_verified_at=datetime.now(UTC), guild_name=guild_name, guild_rank="Member",
    )
    db.add(character)
    db.flush()
    return user, character


def guild_source(*characters):
    return {"name": "TEST GUILD", "world": "Test", "members": [{"name": name, "rank": "Member"} for name in characters]}


async def execute_fixture(db, monkeypatch, *, purpose="test"):
    admin = make_user(db, username=f"admin_{purpose}", is_superuser=True)
    raffle = make_automatic_raffle(db, admin, purpose=purpose)
    users = [add_candidate(db, f"candidate_{purpose}_{index}") for index in range(4)]
    names = [character.character_name for _, character in users]
    async def fake_guild(_guild):
        return guild_source(*names)
    monkeypatch.setattr("app.services.raffle_eligibility_service.get_guild_info", fake_guild)
    db.commit()
    run = await AutomaticRaffleService.execute(db, raffle, admin)
    return admin, raffle, users, run


def test_exact_two_prizes_and_formal_order(db):
    admin = make_user(db, username="prize_admin", is_superuser=True)
    raffle = make_automatic_raffle(db, admin)
    prizes = validate_automatic_prizes(raffle)
    assert list(POSITIONS) == ["second", "first"]
    prizes["second"].amount = Decimal("75.50")
    prizes["second"].currency = "KK"
    prizes["first"].amount = Decimal("999.00")
    prizes["first"].currency = "TC"
    validated = validate_automatic_prizes(raffle)
    assert validated["second"].amount == Decimal("75.50")
    assert validated["second"].currency == "KK"
    assert validated["first"].amount == Decimal("999.00")
    raffle.prizes.append(RafflePrize(raffle_id=raffle.id, name="extra", reward="1 TC", order_index=3))
    db.flush()
    with pytest.raises(AutomaticRaffleError, match="exactly"):
        validate_automatic_prizes(raffle)


def test_chicago_five_calendar_day_cutoff():
    assert compute_eligibility_cutoff(DRAW_AT, "America/Chicago", 5) == CUTOFF_AT


@pytest.mark.asyncio
async def test_manual_trigger_automatic_raffle_uses_trigger_time_cutoff(db, monkeypatch):
    admin = make_user(db, username="manual_trigger_admin", is_superuser=True)
    raffle = make_automatic_raffle(db, admin, purpose="real")
    raffle.scheduled_run_at = None
    member, character = add_candidate(db, "manual_trigger_member", last_login_at=datetime.now(UTC))

    async def fake_guild(_guild):
        return guild_source(character.character_name)

    monkeypatch.setattr("app.services.raffle_eligibility_service.get_guild_info", fake_guild)
    before = datetime.now(UTC) - timedelta(days=raffle.eligibility_days, seconds=2)
    preview = await RaffleEligibilityService.preview(db, raffle)
    after = datetime.now(UTC) - timedelta(days=raffle.eligibility_days) + timedelta(seconds=2)
    assert before <= preview["cutoff_at"] <= after
    member_entry = next(entry for entry in preview["entries"] if entry["user_id"] == member.id)
    assert member_entry["is_eligible"] is True


@pytest.mark.asyncio
async def test_eligibility_boundary_equal_weight_and_exclusions(db, monkeypatch):
    admin = make_user(db, username="eligibility_admin", is_superuser=True)
    raffle = make_automatic_raffle(db, admin)
    boundary, boundary_char = add_candidate(db, "boundary", last_login_at=CUTOFF_AT)
    stale, stale_char = add_candidate(db, "stale", last_login_at=CUTOFF_AT - timedelta(seconds=1))
    inactive, inactive_char = add_candidate(db, "inactive", active=False)
    guest, guest_char = add_candidate(db, "visitor", guest=True)
    missing, missing_char = add_candidate(db, "missing", last_login_at=None)
    outsider, outsider_char = add_candidate(db, "outsider", guild_name="OTHER")
    no_character = make_user(db, username="no_character")
    no_character.last_login_at = CUTOFF_AT
    member_names = [boundary_char.character_name, stale_char.character_name, inactive_char.character_name, guest_char.character_name, missing_char.character_name]
    async def fake_guild(_guild):
        return guild_source(*member_names)
    monkeypatch.setattr("app.services.raffle_eligibility_service.get_guild_info", fake_guild)

    preview = await RaffleEligibilityService.preview(db, raffle)
    by_user = {entry["user_id"]: entry for entry in preview["entries"]}
    assert by_user[boundary.id]["is_eligible"] is True
    assert by_user[stale.id]["exclusion_code"] == "stale_activity"
    assert by_user[inactive.id]["exclusion_code"] == "inactive_account"
    assert by_user[guest.id]["exclusion_code"] == "guest_account"
    assert by_user[missing.id]["exclusion_code"] == "missing_activity"
    assert by_user[outsider.id]["exclusion_code"] == "not_guild_member"
    assert by_user[no_character.id]["exclusion_code"] == "no_linked_character"
    assert all("weight" not in entry for entry in preview["entries"])


@pytest.mark.asyncio
async def test_snapshot_is_immutable(db, monkeypatch):
    admin = make_user(db, username="snapshot_admin", is_superuser=True)
    raffle = make_automatic_raffle(db, admin)
    one, one_char = add_candidate(db, "snapshot_one")
    two, two_char = add_candidate(db, "snapshot_two")
    async def fake_guild(_guild):
        return guild_source(one_char.character_name, two_char.character_name)
    monkeypatch.setattr("app.services.raffle_eligibility_service.get_guild_info", fake_guild)
    snapshot = await RaffleEligibilityService.freeze(db, raffle, admin)
    original_hash = snapshot.snapshot_hash
    original_names = [entry.character_name for entry in snapshot.entries]
    one.last_login_at = CUTOFF_AT - timedelta(days=100)
    await RaffleEligibilityService.preview(db, raffle)
    db.expire(snapshot, ["entries"])
    assert snapshot.snapshot_hash == original_hash
    assert [entry.character_name for entry in snapshot.entries] == original_names


@pytest.mark.asyncio
async def test_secure_execution_one_win_per_user_and_private(db, monkeypatch):
    _, raffle, _, run = await execute_fixture(db, monkeypatch)
    assert run.state == "succeeded"
    assert [result.prize_position for result in sorted(run.results, key=lambda item: POSITIONS.index(item.prize_position))] == ["second", "first"]
    assert len({result.participant_user_id for result in run.results}) == 2
    assert raffle.publication_status == "private"
    assert all(result.derived_entropy_hash and len(result.derived_entropy_hash) == 64 for result in run.results)
    assert all(result.delivery.status == "pending" for result in run.results)
    assert all(result.delivery.delivery_deadline_at == run.completed_at + timedelta(hours=24) for result in run.results)


@pytest.mark.asyncio
async def test_duplicate_and_concurrent_claim_rejected(db, monkeypatch):
    admin, raffle, _, _ = await execute_fixture(db, monkeypatch)
    with pytest.raises(AutomaticRaffleError, match="already been executed"):
        await AutomaticRaffleService.execute(db, raffle, admin)
    raffle.execution_state = "pending"
    raffle.version += 1
    db.commit()
    AutomaticRaffleService.claim(db, raffle)
    with pytest.raises(AutomaticRaffleError, match="already in progress"):
        AutomaticRaffleService.claim(db, raffle)
    db.rollback()


@pytest.mark.asyncio
@pytest.mark.parametrize("positions", [["second"], ["first"], ["second", "first"]])
async def test_partial_and_full_rerun_preserve_history(db, monkeypatch, positions):
    admin, raffle, _, first_run = await execute_fixture(db, monkeypatch, purpose="test")
    active_before = {result.prize_position: result for result in first_run.results}
    new_run = AutomaticRaffleService.rerun(
        db, raffle, admin, positions=positions, reason="Audited correction",
        override_delivered=False, override_reason=None, is_global_admin=True,
    )
    assert new_run.snapshot_id == first_run.snapshot_id
    assert {result.prize_position for result in new_run.results} == set(positions)
    active_after = db.query(RaffleRunResult).join(RaffleRun).filter(RaffleRun.raffle_id == raffle.id, RaffleRunResult.is_active.is_(True)).all()
    assert {result.prize_position for result in active_after} == {"second", "first"}
    assert len({result.participant_user_id for result in active_after}) == 2
    for position, result in active_before.items():
        assert result.is_active is (position not in positions)
    assert db.query(RaffleRerunAudit).filter_by(new_run_id=new_run.id).count() == 1
    assert raffle.publication_status == "private"


@pytest.mark.asyncio
async def test_delivered_rerun_requires_global_override(db, monkeypatch):
    admin, raffle, _, run = await execute_fixture(db, monkeypatch)
    delivered = next(result for result in run.results if result.prize_position == "second")
    delivered.delivery.status = "delivered"
    delivered.delivery.delivered_at = datetime.now(UTC)
    delivered.delivery.delivered_by_id = admin.id
    db.commit()
    with pytest.raises(AutomaticRaffleError, match="Delivered prizes"):
        AutomaticRaffleService.rerun(db, raffle, admin, positions=["second"], reason="retry", override_delivered=False, override_reason=None, is_global_admin=True)
    replacement = AutomaticRaffleService.rerun(db, raffle, admin, positions=["second"], reason="retry", override_delivered=True, override_reason="Approved compensation", is_global_admin=True)
    assert replacement.results[0].prize_position == "second"


@pytest.mark.asyncio
async def test_public_results_gated_and_have_no_user_ids(db, client, monkeypatch):
    admin, raffle, _, _ = await execute_fixture(db, monkeypatch)
    leader = make_user(db, username="publication_leader", guild_rank="Leader", guild_name=raffle.guild_name)
    db.commit()
    hidden = client.get(f"/api/v1/raffles/public/code/{raffle.public_code}")
    assert hidden.status_code == 200
    assert hidden.json()["winners"] == []
    assert "user_id" not in str(hidden.json())
    published = client.post(f"/api/v1/raffles/{raffle.id}/publish", headers=auth(leader))
    assert published.status_code == 200
    visible = client.get(f"/api/v1/raffles/public/code/{raffle.public_code}").json()
    assert [winner["prize_position"] for winner in visible["winners"]] == ["second", "first"]
    assert "user_id" not in str(visible)
    client.post(f"/api/v1/raffles/{raffle.id}/unpublish", headers=auth(admin))
    assert client.get(f"/api/v1/raffles/public/code/{raffle.public_code}").json()["winners"] == []


def test_manager_grant_revoke_cross_guild_and_publish_boundaries(db, client):
    admin = make_user(db, username="grant_admin", is_superuser=True)
    leader = make_user(db, username="grant_leader", guild_rank="Leader")
    manager = make_user(db, username="grant_manager")
    outsider = make_user(db, username="grant_outsider", guild_name="OTHER")
    raffle = make_automatic_raffle(db, admin)
    db.commit()
    assert client.post(f"/api/v1/raffles/{raffle.id}/managers", json={"user_id": outsider.id}, headers=auth(admin)).status_code == 400
    assert client.get(f"/api/v1/raffles/{raffle.id}/runs", headers=auth(outsider)).status_code == 403
    granted = client.post(f"/api/v1/raffles/{raffle.id}/managers", json={"user_id": manager.id}, headers=auth(leader))
    assert granted.status_code == 200
    assert client.get(f"/api/v1/raffles/{raffle.id}/runs", headers=auth(manager)).status_code == 200
    assert client.post(f"/api/v1/raffles/{raffle.id}/publish", headers=auth(manager)).status_code == 403
    revoked = client.delete(f"/api/v1/raffles/{raffle.id}/managers/{manager.id}", headers=auth(leader))
    assert revoked.status_code == 200
    assert client.get(f"/api/v1/raffles/{raffle.id}/runs", headers=auth(manager)).status_code == 403


@pytest.mark.asyncio
async def test_test_and_real_raffles_are_isolated(db, monkeypatch):
    _, test_raffle, _, test_run = await execute_fixture(db, monkeypatch, purpose="test")
    _, real_raffle, _, real_run = await execute_fixture(db, monkeypatch, purpose="real")
    assert test_raffle.id != real_raffle.id
    assert test_run.snapshot_id != real_run.snapshot_id
    assert {run.raffle_id for run in db.query(RaffleRun).all()} >= {test_raffle.id, real_raffle.id}


@pytest.mark.asyncio
async def test_delivery_endpoint_rules(db, client, monkeypatch):
    admin, raffle, _, run = await execute_fixture(db, monkeypatch)
    result = next(item for item in run.results if item.prize_position == "second")
    url = f"/api/v1/raffles/{raffle.id}/results/{result.id}/delivery"
    assert client.patch(url, json={"status": "disputed"}, headers=auth(admin)).status_code == 400
    delivered = client.patch(url, json={"status": "delivered"}, headers=auth(admin))
    assert delivered.status_code == 200
    assert delivered.json()["delivered_by_id"] == admin.id
    assert delivered.json()["delivered_at"]
    assert client.patch(url, json={"status": "pending"}, headers=auth(admin)).status_code == 409
    overridden = client.patch(url, json={"status": "cancelled", "note": "Administrative correction", "admin_override": True}, headers=auth(admin))
    assert overridden.status_code == 200


def test_successful_login_tracks_application_login_separately(db, client):
    user = make_user(db, username="app_login_user")
    user.last_login_at = CUTOFF_AT
    db.commit()
    response = client.post("/api/v1/auth/login", data={"username": user.username, "password": "password"})
    assert response.status_code == 200
    db.refresh(user)
    assert user.last_app_login_at is not None
    assert user.last_login_at.replace(tzinfo=UTC) == CUTOFF_AT
