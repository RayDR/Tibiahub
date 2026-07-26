"""
Tests for the raffle system.

All tests use an in-memory SQLite database (see conftest.py).
No data is written to the production database.
"""
from __future__ import annotations

from datetime import UTC, datetime
import pytest
from sqlalchemy.orm import Session

from app.models.user_character import UserCharacter
from tests.conftest import make_user, make_raffle, make_prize, make_participant


def verified_character(db: Session, user, name: str, *, guild: str | None = None, world: str | None = None):
    character = UserCharacter(
        user_id=user.id, character_name=name, normalized_name=name.casefold(),
        ownership_status="verified", ownership_verified_at=datetime.now(UTC),
        guild_name=guild, guild_rank="Member", world_name=world,
    )
    db.add(character)
    db.flush()
    return character


# ---------------------------------------------------------------------------
# Unit: pick_weighted_participant
# ---------------------------------------------------------------------------

def test_pick_weighted_participant_basic():
    from app.services.raffle_service import pick_weighted_participant
    import random
    participants = [
        {"participant_id": 1, "user_id": 1, "character_name": "Char A", "weight": 1.0},
        {"participant_id": 2, "user_id": 2, "character_name": "Char B", "weight": 1.0},
    ]
    rng = random.Random(42)
    winner = pick_weighted_participant(participants, rng=rng)
    assert winner["participant_id"] in {1, 2}


def test_pick_weighted_participant_single():
    from app.services.raffle_service import pick_weighted_participant
    participants = [{"participant_id": 1, "user_id": 1, "character_name": "Solo", "weight": 3.0}]
    winner = pick_weighted_participant(participants)
    assert winner["participant_id"] == 1


def test_pick_weighted_participant_empty_raises():
    from app.services.raffle_service import pick_weighted_participant
    with pytest.raises(ValueError, match="No participants"):
        pick_weighted_participant([])


def test_pick_weighted_participant_zero_weight_raises():
    from app.services.raffle_service import pick_weighted_participant
    participants = [{"participant_id": 1, "user_id": 1, "character_name": "X", "weight": 0.0}]
    with pytest.raises(ValueError, match="Total weight"):
        pick_weighted_participant(participants)


# ---------------------------------------------------------------------------
# Unit: select_weighted_winners — one winner per account
# ---------------------------------------------------------------------------

def test_select_weighted_winners_one_per_user():
    from app.services.raffle_service import select_weighted_winners
    import random
    participants = [
        {"participant_id": 1, "user_id": 10, "character_name": "A", "weight": 1.0},
        {"participant_id": 2, "user_id": 20, "character_name": "B", "weight": 1.0},
    ]
    prizes = [
        {"prize_id": 1, "name": "Gold", "reward": "10kk"},
        {"prize_id": 2, "name": "Silver", "reward": "5kk"},
    ]
    rng = random.Random(0)
    winners = select_weighted_winners(participants, prizes, rng=rng)
    assert len(winners) == 2
    winner_user_ids = [w["participant"]["user_id"] for w in winners]
    assert len(set(winner_user_ids)) == 2, "Same user won twice"


def test_select_weighted_winners_fewer_than_prizes():
    from app.services.raffle_service import select_weighted_winners
    participants = [{"participant_id": 1, "user_id": 1, "character_name": "A", "weight": 1.0}]
    prizes = [
        {"prize_id": 1, "name": "1st", "reward": "10kk"},
        {"prize_id": 2, "name": "2nd", "reward": "5kk"},
    ]
    winners = select_weighted_winners(participants, prizes)
    assert len(winners) == 1  # Only 1 winner; second prize skipped


# ---------------------------------------------------------------------------
# DB: create raffle
# ---------------------------------------------------------------------------

def test_create_raffle(db: Session):
    from app.models.raffle import Raffle
    user = make_user(db, username="creator")
    raffle = make_raffle(db, creator_id=user.id)
    db.commit()

    fetched = db.query(Raffle).filter(Raffle.id == raffle.id).first()
    assert fetched is not None
    assert fetched.title == "Test Raffle"
    assert fetched.status == "open"
    assert fetched.public_code  # must have a code


def test_custom_guild_leader_rank_can_manage_own_guild_raffles(db: Session):
    from app.core.permissions import can_manage_guild, is_matching_raffle_leader

    leader = make_user(db, username="warbringer", guild_rank="Alpha Warbringer", guild_name="Bald Dwarfs")

    assert can_manage_guild(leader, "bald dwarfs") is True
    assert is_matching_raffle_leader(leader, "BALD DWARFS") is True
    assert is_matching_raffle_leader(leader, "Another Guild") is False


# ---------------------------------------------------------------------------
# DB: add participant by character name + duplicate account blocked
# ---------------------------------------------------------------------------

def test_add_participant(db: Session):
    from app.models.raffle import RaffleParticipant
    user = make_user(db, username="alice")
    raffle = make_raffle(db, creator_id=user.id)
    p = make_participant(db, raffle_id=raffle.id, user_id=user.id, character_name="Alice")
    db.commit()

    fetched = db.query(RaffleParticipant).filter(RaffleParticipant.raffle_id == raffle.id).all()
    assert len(fetched) == 1
    assert fetched[0].character_name == "Alice"


def test_duplicate_account_blocked_by_db_constraint(db: Session):
    from sqlalchemy.exc import IntegrityError
    user = make_user(db, username="bob")
    raffle = make_raffle(db, creator_id=user.id)
    make_participant(db, raffle_id=raffle.id, user_id=user.id, character_name="Bob")
    db.flush()
    # Second participant with same user_id in same raffle must fail
    from app.models.raffle import RaffleParticipant
    db.add(RaffleParticipant(
        raffle_id=raffle.id,
        user_id=user.id,
        character_name="BobAlt",
        weight=1.0,
        weight_multiplier=1.0,
        is_eligible=True,
        source="manual_override",
    ))
    with pytest.raises(IntegrityError):
        db.flush()


# ---------------------------------------------------------------------------
# DB: vice leader weight
# ---------------------------------------------------------------------------

def test_vice_leader_weight():
    from app.services.raffle_service import participant_weight_from_rank
    assert participant_weight_from_rank("Vice Leader") == pytest.approx(1.1)
    assert participant_weight_from_rank("vice leader") == pytest.approx(1.1)
    assert participant_weight_from_rank("Member") == pytest.approx(1.0)
    assert participant_weight_from_rank(None) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# DB: execute draw — real winners created
# ---------------------------------------------------------------------------

def test_execute_draw(db: Session):
    from app.models.raffle import RaffleWinner
    from app.services.raffle_service import RaffleService

    admin = make_user(db, username="admin_draw", is_superuser=True)
    user_a = make_user(db, username="player_a")
    user_b = make_user(db, username="player_b")
    raffle = make_raffle(db, creator_id=admin.id)
    prize = make_prize(db, raffle_id=raffle.id)
    make_participant(db, raffle_id=raffle.id, user_id=user_a.id, character_name="PlayerA")
    make_participant(db, raffle_id=raffle.id, user_id=user_b.id, character_name="PlayerB")
    db.commit()

    # Need relationships loaded — re-fetch
    from sqlalchemy.orm import selectinload
    from app.models.raffle import Raffle, RaffleParticipant
    raffle = db.query(Raffle).options(
        selectinload(Raffle.participants).selectinload(RaffleParticipant.user),
        selectinload(Raffle.prizes),
        selectinload(Raffle.winners),
    ).filter(Raffle.id == raffle.id).first()

    winners = RaffleService.execute_raffle(db, raffle, admin)
    assert len(winners) == 1
    db_winners = db.query(RaffleWinner).filter(RaffleWinner.raffle_id == raffle.id).all()
    assert len(db_winners) == 1


# ---------------------------------------------------------------------------
# DB: dry-run (simulate) does NOT persist winners
# ---------------------------------------------------------------------------

def test_dry_run_does_not_persist(db: Session):
    from app.models.raffle import RaffleWinner
    from app.services.raffle_service import RaffleService
    from sqlalchemy.orm import selectinload
    from app.models.raffle import Raffle, RaffleParticipant

    admin = make_user(db, username="admin_sim", is_superuser=True)
    user_a = make_user(db, username="sim_a")
    raffle = make_raffle(db, creator_id=admin.id)
    make_prize(db, raffle_id=raffle.id)
    make_participant(db, raffle_id=raffle.id, user_id=user_a.id, character_name="SimA")
    db.commit()

    raffle = db.query(Raffle).options(
        selectinload(Raffle.participants).selectinload(RaffleParticipant.user),
        selectinload(Raffle.prizes),
        selectinload(Raffle.winners),
    ).filter(Raffle.id == raffle.id).first()

    simulated = RaffleService.execute_raffle(db, raffle, admin, dry_run=True)
    assert len(simulated) == 1

    # Flush without commit — in-memory transaction ensures no persistence
    db.flush()
    db_winners = db.query(RaffleWinner).filter(RaffleWinner.raffle_id == raffle.id).all()
    assert len(db_winners) == 0, "Dry-run should not persist winners"


# ---------------------------------------------------------------------------
# DB: no participants raises ValueError
# ---------------------------------------------------------------------------

def test_draw_no_participants_raises(db: Session):
    from app.services.raffle_service import RaffleService
    from sqlalchemy.orm import selectinload
    from app.models.raffle import Raffle, RaffleParticipant

    admin = make_user(db, username="admin_empty", is_superuser=True)
    raffle = make_raffle(db, creator_id=admin.id)
    make_prize(db, raffle_id=raffle.id)
    db.commit()

    raffle = db.query(Raffle).options(
        selectinload(Raffle.participants).selectinload(RaffleParticipant.user),
        selectinload(Raffle.prizes),
        selectinload(Raffle.winners),
    ).filter(Raffle.id == raffle.id).first()

    with pytest.raises(ValueError, match="No eligible participants"):
        RaffleService.execute_raffle(db, raffle, admin)


# ---------------------------------------------------------------------------
# DB: no prizes raises ValueError
# ---------------------------------------------------------------------------

def test_draw_no_prizes_raises(db: Session):
    from app.services.raffle_service import RaffleService
    from sqlalchemy.orm import selectinload
    from app.models.raffle import Raffle, RaffleParticipant

    admin = make_user(db, username="admin_noprize", is_superuser=True)
    user_a = make_user(db, username="pl_noprize")
    raffle = make_raffle(db, creator_id=admin.id)
    make_participant(db, raffle_id=raffle.id, user_id=user_a.id, character_name="NoprizeChar")
    db.commit()

    raffle = db.query(Raffle).options(
        selectinload(Raffle.participants).selectinload(RaffleParticipant.user),
        selectinload(Raffle.prizes),
        selectinload(Raffle.winners),
    ).filter(Raffle.id == raffle.id).first()

    with pytest.raises(ValueError, match="No prizes"):
        RaffleService.execute_raffle(db, raffle, admin)


# ---------------------------------------------------------------------------
# DB: soft-delete sets correct fields
# ---------------------------------------------------------------------------

def test_soft_delete(db: Session):
    from app.models.raffle import Raffle

    admin = make_user(db, username="admin_del", is_superuser=True)
    raffle = make_raffle(db, creator_id=admin.id)
    db.commit()

    raffle.is_deleted = True
    raffle.status = "deleted"
    raffle.is_active = False
    db.commit()

    fetched = db.query(Raffle).filter(Raffle.id == raffle.id).first()
    assert fetched.is_deleted is True
    assert fetched.status == "deleted"
    assert fetched.is_active is False

    # Should not appear in normal listing
    active = db.query(Raffle).filter(Raffle.is_deleted == False).all()
    assert all(r.id != raffle.id for r in active)


def test_simulation_payload_serializes(db: Session):
    from app.models.raffle import Raffle, RaffleParticipant
    from app.services.raffle_service import RaffleService
    from sqlalchemy.orm import selectinload

    admin = make_user(db, username="admin_sim_payload", is_superuser=True)
    user_a = make_user(db, username="sim_payload_user")
    raffle = make_raffle(db, creator_id=admin.id)
    make_prize(db, raffle_id=raffle.id)
    make_participant(db, raffle_id=raffle.id, user_id=user_a.id, character_name="SimPayload")
    db.commit()

    raffle = db.query(Raffle).options(
        selectinload(Raffle.participants).selectinload(RaffleParticipant.user),
        selectinload(Raffle.prizes),
        selectinload(Raffle.winners),
    ).filter(Raffle.id == raffle.id).first()

    winners = RaffleService.execute_raffle(db, raffle, admin, dry_run=True)
    payload = RaffleService.build_simulation_payload(raffle, winners)

    assert payload["simulation"] is True
    assert payload["winners"][0]["id"] is not None
    assert payload["winners"][0]["created_at"] is not None
    assert payload["eligible_count"] == 1
    assert payload["prizes"][0]["name"] == "1st Prize"


@pytest.mark.asyncio
async def test_register_closed_raffle_fails(db: Session):
    from app.api.v1.endpoints.raffles import _register_participant_for_raffle

    admin = make_user(db, username="admin_closed", is_superuser=True, guild_name="Bloodborne Warhowl")
    raffle = make_raffle(db, creator_id=admin.id, guild_name="Bloodborne Warhowl", status="closed")
    db.commit()

    with pytest.raises(Exception) as exc_info:
        await _register_participant_for_raffle(db, raffle, "Mecho", actor=admin)
    assert "not accepting participants" in str(exc_info.value)


@pytest.mark.asyncio
async def test_register_guild_only_blocks_outsider_without_network(db: Session, monkeypatch):
    from fastapi import HTTPException
    from app.api.v1.endpoints.raffles import _register_participant_for_raffle

    admin = make_user(db, username="admin_guild_only", is_superuser=True, guild_name="Bloodborne Warhowl")
    verified_character(db, admin, "Outsider", guild="Other Guild", world="Yovera")
    raffle = make_raffle(db, creator_id=admin.id, guild_name="Bloodborne Warhowl", access_mode="guild_only", status="open")
    db.commit()

    with pytest.raises(HTTPException) as exc_info:
        await _register_participant_for_raffle(db, raffle, "Outsider", actor=admin)
    assert exc_info.value.status_code == 400
    assert "Only members of this guild can join" in exc_info.value.detail


@pytest.mark.asyncio
async def test_register_world_only_accepts_same_verified_world_without_network(db: Session, monkeypatch):
    from app.api.v1.endpoints.raffles import _register_participant_for_raffle

    admin = make_user(db, username="admin_world_only", is_superuser=True, guild_name="Bloodborne Warhowl")
    raffle = make_raffle(db, creator_id=admin.id, guild_name="Bloodborne Warhowl", access_mode="world_only", status="open")
    raffle.world_name = "Yovera"
    verified_character(db, admin, "WorldFriend", world="Yovera")
    db.commit()

    updated = await _register_participant_for_raffle(db, raffle, "WorldFriend", actor=admin)
    assert updated["participant_count"] == 1


@pytest.mark.asyncio
async def test_register_public_accepts_verified_character_from_any_world(db: Session, monkeypatch):
    from app.api.v1.endpoints.raffles import _register_participant_for_raffle

    admin = make_user(db, username="admin_public", is_superuser=True, guild_name="Bloodborne Warhowl")
    raffle = make_raffle(db, creator_id=admin.id, guild_name="Bloodborne Warhowl", access_mode="public", status="open")
    verified_character(db, admin, "AnyWorld", world="Antica")
    db.commit()

    updated = await _register_participant_for_raffle(db, raffle, "AnyWorld", actor=admin)
    assert updated["participant_count"] == 1


def test_public_registration_route_requires_the_verified_owner_and_returns_public_contract(db: Session, client):
    from app.core.security import create_access_token

    manager = make_user(db, username="public-route-manager", is_superuser=True)
    owner = make_user(db, username="public-route-owner")
    other = make_user(db, username="public-route-other")
    verified_character(db, owner, "Public Route Knight", world="Antica")
    raffle = make_raffle(db, creator_id=manager.id, access_mode="public", status="open")
    db.commit()
    endpoint = f"/api/v1/raffles/public/code/{raffle.public_code}/register"
    assert client.post(endpoint, json={"character_name": "Public Route Knight"}).status_code == 401
    other_headers = {"Authorization": f"Bearer {create_access_token(other.username)}"}
    assert client.post(endpoint, json={"character_name": "Public Route Knight"}, headers=other_headers).status_code == 400
    owner_headers = {"Authorization": f"Bearer {create_access_token(owner.username)}"}
    response = client.post(endpoint, json={"character_name": "Public Route Knight"}, headers=owner_headers)
    assert response.status_code == 200
    assert response.json()["public_code"] == raffle.public_code
    assert response.json()["participants"] == [{"character_name": "Public Route Knight", "guild_rank": "Member"}]
    assert "user_id" not in response.json()


def test_public_hidden_participants(db: Session):
    from app.models.raffle import Raffle, RaffleParticipant
    from app.services.raffle_service import RaffleService
    from sqlalchemy.orm import selectinload

    admin = make_user(db, username="admin_hidden", is_superuser=True)
    user_a = make_user(db, username="hidden_user")
    raffle = make_raffle(db, creator_id=admin.id, show_participants=False)
    make_prize(db, raffle_id=raffle.id)
    make_participant(db, raffle_id=raffle.id, user_id=user_a.id, character_name="HiddenUser")
    db.commit()

    raffle = db.query(Raffle).options(
        selectinload(Raffle.participants).selectinload(RaffleParticipant.user),
        selectinload(Raffle.prizes),
        selectinload(Raffle.winners),
    ).filter(Raffle.id == raffle.id).first()

    payload = RaffleService.serialize_raffle(raffle, include_participants=False)
    assert payload["participant_count"] == 1
    assert payload["participants"] == []
