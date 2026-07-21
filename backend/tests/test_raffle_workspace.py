from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.core.security import create_access_token
from app.models.raffle import RaffleManagerGrant
from app.models.workspace_audit import WorkspaceAudit
from app.schemas.raffle import EligibilityEntryResponse
from tests.conftest import make_raffle, make_user


def auth(user):
    return {"Authorization": f"Bearer {create_access_token(user.username)}"}


def automatic_payload(guild_name: str) -> dict:
    return {
        "title": "Workspace raffle", "guild_name": guild_name, "scope_type": "guild",
        "purpose": "test", "run_mode": "automatic", "scheduled_run_at": (datetime.now(UTC) + timedelta(hours=2)).isoformat(),
        "timezone_name": "UTC", "eligibility_days": 5, "show_participants": False,
        "prizes": [
            {"name": "Second Place", "reward": "100 TC", "order_index": 1, "position": "second", "amount": 100, "currency": "TC"},
            {"name": "First Place", "reward": "250 TC", "order_index": 2, "position": "first", "amount": 250, "currency": "TC"},
        ],
    }


def test_member_workspace_is_guild_scoped_and_safe(client, db):
    member = make_user(db, username="raffle-member", guild_name="One")
    creator = make_user(db, username="raffle-creator", guild_name="One", guild_rank="Leader")
    other = make_user(db, username="other-creator", guild_name="Two", guild_rank="Leader")
    own = make_raffle(db, title="Own", guild_name="One", creator_id=creator.id)
    hidden = make_raffle(db, title="Hidden", guild_name="Two", creator_id=other.id)
    own.scope_type = hidden.scope_type = "guild"
    db.commit()
    response = client.get("/api/v1/raffles/workspace", headers=auth(member))
    assert response.status_code == 200
    assert [row["title"] for row in response.json()] == ["Own"]
    assert "participants" not in response.json()[0]
    assert "current_winners" not in response.json()[0]


def test_scope_creation_policy_denies_leader_and_allows_admin(client, db):
    leader = make_user(db, username="scope-raffle-leader", guild_name="One", guild_rank="Leader", is_superuser=False)
    admin = make_user(db, username="scope-raffle-admin", guild_name="Admin Home", is_superuser=True)
    db.commit()
    payload = {"title": "Server contest", "guild_name": "TibiaHub", "scope_type": "server", "world_name": "Antica", "purpose": "legacy", "run_mode": "manual", "prizes": []}
    assert client.post("/api/v1/raffles/", json=payload, headers=auth(leader)).status_code == 403
    created = client.post("/api/v1/raffles/", json=payload, headers=auth(admin))
    assert created.status_code == 201
    assert created.json()["scope_type"] == "server" and created.json()["world_name"] == "Antica"


def test_admin_assisted_raffle_creation_is_audited(client, db):
    make_user(db, username="assisted-leader", guild_name="Assisted", guild_rank="Leader")
    admin = make_user(db, username="assisting-admin", guild_name="Admin Home", is_superuser=True)
    db.commit()
    created = client.post("/api/v1/raffles/", json=automatic_payload("Assisted"), headers=auth(admin))
    assert created.status_code == 201
    audit = db.query(WorkspaceAudit).filter_by(actor_id=admin.id, action="raffle_created").one()
    assert audit.guild_name == "Assisted" and audit.assisted is True


def test_viceleader_requires_explicit_raffle_grant(client, db):
    leader = make_user(db, username="grant-leader", guild_name="One", guild_rank="Leader")
    vice = make_user(db, username="grant-vice", guild_name="One", guild_rank="Vice Leader")
    raffle = make_raffle(db, guild_name="One", creator_id=leader.id); raffle.scope_type = "guild"
    db.commit()
    before = client.get("/api/v1/raffles/workspace", headers=auth(vice)).json()[0]
    assert before["capabilities"]["manage"] is False
    db.add(RaffleManagerGrant(raffle_id=raffle.id, user_id=vice.id, granted_by_id=leader.id)); db.commit()
    after = client.get("/api/v1/raffles/workspace", headers=auth(vice)).json()[0]
    assert after["capabilities"]["manage"] is True and after["capabilities"]["publish"] is False


def test_eligibility_contract_does_not_expose_internal_user_ids():
    assert "user_id" not in EligibilityEntryResponse.model_fields
