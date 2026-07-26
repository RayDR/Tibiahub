from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base
from app.models.character_ownership import CharacterOwnershipClaim, CharacterOwnershipHistory
from app.models.user import User
from app.models.user_character import UserCharacter
from app.services.character_ownership_service import CharacterOwnershipService
from tests.conftest import make_user


@pytest.fixture()
def ownership_factory():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    yield factory
    engine.dispose()


async def _verify(factory, user_id: int, name: str, *, comment_token: str | None = None):
    with factory.begin() as db:
        user = db.get(User, user_id)
        claim, challenge = CharacterOwnershipService.create_claim(db, user, name)
        CharacterOwnershipService.queue(db, claim, user)
        claim_id = claim.id

    async def fetch(_name: str):
        return {
            "name": name, "comment": f"Proof: {comment_token or challenge}",
            "level": 600, "vocation": "Elite Knight", "world": "Antica",
            "guild": {"name": "TEST GUILD", "rank": "Member"},
        }

    assert await CharacterOwnershipService.process_one(session_factory=factory, fetch_character=fetch)
    return claim_id, challenge


@pytest.mark.asyncio
async def test_comment_challenge_is_hash_only_single_use_and_updates_verified_identity(ownership_factory):
    with ownership_factory.begin() as db:
        user = make_user(db, username="ownership-first")
        user_id = user.id
    claim_id, challenge = await _verify(ownership_factory, user_id, "Proof Knight")
    with ownership_factory() as db:
        claim = db.get(CharacterOwnershipClaim, claim_id)
        character = db.query(UserCharacter).filter_by(normalized_name="proof knight").one()
        assert claim.challenge_hash != challenge and challenge not in claim.challenge_hash
        assert claim.status == "verified" and claim.consumed_at is not None
        assert character.user_id == user_id and character.ownership_status == "verified"
        assert character.ownership_claim_id == claim_id
        assert db.query(CharacterOwnershipHistory).filter_by(claim_id=claim_id, action="ownership_verified").count() == 1

    with ownership_factory.begin() as db:
        second = make_user(db, username="ownership-replay")
        second_id = second.id
    replay_id, _new_challenge = await _verify(
        ownership_factory, second_id, "Proof Knight", comment_token=challenge,
    )
    with ownership_factory() as db:
        replay = db.get(CharacterOwnershipClaim, replay_id)
        assert replay.status == "pending"
        assert replay.safe_failure_code == "challenge_not_visible"
        assert db.query(UserCharacter).filter_by(normalized_name="proof knight", ownership_status="verified").one().user_id == user_id


@pytest.mark.asyncio
async def test_transfer_dispute_rejection_and_owner_approval_are_audited(ownership_factory):
    with ownership_factory.begin() as db:
        owner = make_user(db, username="transfer-owner", is_superuser=False)
        claimant = make_user(db, username="transfer-claimant", is_superuser=False)
        admin = make_user(db, username="transfer-admin", is_superuser=True)
        owner_id, claimant_id, admin_id = owner.id, claimant.id, admin.id
    await _verify(ownership_factory, owner_id, "Transfer Knight")
    disputed_claim_id, _ = await _verify(ownership_factory, claimant_id, "Transfer Knight")

    with ownership_factory.begin() as db:
        with pytest.raises(PermissionError):
            CharacterOwnershipService.dispute(
                db, db.get(CharacterOwnershipClaim, disputed_claim_id), db.get(User, claimant_id),
                "A claimant cannot freeze the current owner's identity",
            )
    with ownership_factory.begin() as db:
        claim = db.get(CharacterOwnershipClaim, disputed_claim_id)
        assert claim.status == "transfer_pending"
        CharacterOwnershipService.dispute(db, claim, db.get(User, owner_id), "I still control this character")
        assert claim.status == "disputed"
    with ownership_factory.begin() as db:
        claim = db.get(CharacterOwnershipClaim, disputed_claim_id)
        CharacterOwnershipService.reject(db, claim, db.get(User, admin_id), "Proof reviewed with current owner")
        assert db.query(UserCharacter).filter_by(normalized_name="transfer knight").one().ownership_status == "verified"

    approved_claim_id, _ = await _verify(ownership_factory, claimant_id, "Transfer Knight")
    with ownership_factory.begin() as db:
        claim = db.get(CharacterOwnershipClaim, approved_claim_id)
        CharacterOwnershipService.transfer(db, claim, db.get(User, owner_id))
    with ownership_factory() as db:
        character = db.query(UserCharacter).filter_by(normalized_name="transfer knight", ownership_status="verified").one()
        assert character.user_id == claimant_id
        actions = {row.action for row in db.query(CharacterOwnershipHistory).filter_by(normalized_name="transfer knight")}
        assert {"transfer_requested", "ownership_disputed", "claim_rejected", "transfer_completed"} <= actions


@pytest.mark.asyncio
async def test_legacy_name_link_has_no_ownership_and_first_valid_proof_replaces_it(ownership_factory):
    with ownership_factory.begin() as db:
        legacy = make_user(db, username="legacy-link")
        claimant = make_user(db, username="legacy-proof")
        db.add(UserCharacter(
            user_id=legacy.id, character_name="Legacy Knight", normalized_name="legacy knight",
            ownership_status="legacy_unverified",
        ))
        legacy.tibia_character_name = "Legacy Knight"
        legacy_id, claimant_id = legacy.id, claimant.id
    claim_id, _ = await _verify(ownership_factory, claimant_id, "Legacy Knight")
    with ownership_factory() as db:
        claim = db.get(CharacterOwnershipClaim, claim_id)
        character = db.query(UserCharacter).filter_by(normalized_name="legacy knight").one()
        assert claim.status == "verified" and character.user_id == claimant_id
        assert db.get(User, legacy_id).tibia_character_name is None
        assert db.query(CharacterOwnershipHistory).filter_by(claim_id=claim_id, action="legacy_link_replaced").count() == 1


@pytest.mark.asyncio
async def test_expired_worker_lease_is_recovered(ownership_factory):
    with ownership_factory.begin() as db:
        user = make_user(db, username="lease-owner")
        claim, challenge = CharacterOwnershipService.create_claim(db, user, "Lease Knight")
        CharacterOwnershipService.queue(db, claim, user)
        claim.status = "processing"
        claim.lease_expires_at = datetime(2000, 1, 1, tzinfo=UTC)
        claim_id = claim.id

    async def fetch(_name: str):
        return {"name": "Lease Knight", "comment": challenge, "guild": None}

    assert await CharacterOwnershipService.process_one(session_factory=ownership_factory, fetch_character=fetch)
    with ownership_factory() as db:
        assert db.get(CharacterOwnershipClaim, claim_id).status == "verified"


def test_claim_api_queues_without_request_time_provider_call(client, db, monkeypatch):
    from app.core.security import create_access_token
    user = make_user(db, username="api-ownership")
    db.commit()
    headers = {"Authorization": f"Bearer {create_access_token(user.username)}"}
    monkeypatch.setattr(
        CharacterOwnershipService, "process_one",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("provider work entered request")),
    )
    created = client.post("/api/v1/character-ownership/claims", json={"character_name": "Queued Knight"}, headers=headers)
    assert created.status_code == 201 and "challenge" in created.json()
    queued = client.post(f"/api/v1/character-ownership/claims/{created.json()['id']}/verify", headers=headers)
    assert queued.status_code == 202 and queued.json()["status"] == "queued"
