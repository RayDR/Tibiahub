from __future__ import annotations

from app.core.security import create_access_token
from app.models.external_data import TibiaWikiQuest
from app.models.quest_progress import QuestCompletion
from app.models.user_character import UserCharacter
from tests.conftest import make_user


def _quest(db, *, name: str = "Progress Quest", slug: str = "progress-quest") -> TibiaWikiQuest:
    quest = TibiaWikiQuest(
        name=name,
        normalized_name=name.lower(),
        slug=slug,
        source_name="tibiawiki",
        external_id="990001",
        is_group=False,
    )
    db.add(quest)
    db.flush()
    return quest


def _verified_character(db, user, *, name: str = "Progress Knight") -> UserCharacter:
    character = UserCharacter(
        user_id=user.id,
        character_name=name,
        normalized_name=name.lower(),
        ownership_status="verified",
    )
    db.add(character)
    db.flush()
    return character


def _headers(user) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.username)}"}


def test_quest_completion_round_trip_is_character_scoped_and_idempotent(client, db):
    user = make_user(db, username="quest-progress-owner")
    character = _verified_character(db, user)
    quest = _quest(db)
    db.commit()

    initial = client.get(
        f"/api/v1/quest-progress/{quest.slug}",
        params={"character_id": character.id},
        headers=_headers(user),
    )
    assert initial.status_code == 200
    assert initial.json() == {
        "quest_id": quest.id,
        "character_id": character.id,
        "completed": False,
        "completed_at": None,
    }

    completed = client.put(
        f"/api/v1/quest-progress/{quest.slug}",
        params={"character_id": character.id},
        headers=_headers(user),
        json={"completed": True},
    )
    assert completed.status_code == 200
    payload = completed.json()
    assert payload["completed"] is True
    assert payload["completed_at"]
    first_completed_at = payload["completed_at"]
    assert db.query(QuestCompletion).filter_by(character_id=character.id, quest_id=quest.id).count() == 1

    repeated = client.put(
        f"/api/v1/quest-progress/{quest.id}",
        params={"character_id": character.id},
        headers=_headers(user),
        json={"completed": True},
    )
    assert repeated.status_code == 200
    assert repeated.json()["completed_at"] == first_completed_at
    assert db.query(QuestCompletion).filter_by(character_id=character.id, quest_id=quest.id).count() == 1

    cleared = client.put(
        f"/api/v1/quest-progress/{quest.slug}",
        params={"character_id": character.id},
        headers=_headers(user),
        json={"completed": False},
    )
    assert cleared.status_code == 200
    assert cleared.json()["completed"] is False
    assert db.query(QuestCompletion).filter_by(character_id=character.id, quest_id=quest.id).count() == 0


def test_quest_progress_rejects_foreign_and_unverified_characters(client, db):
    owner = make_user(db, username="quest-progress-owner-two")
    other = make_user(db, username="quest-progress-other")
    foreign = _verified_character(db, other, name="Foreign Knight")
    unverified = UserCharacter(
        user_id=owner.id,
        character_name="Pending Knight",
        normalized_name="pending knight",
        ownership_status="legacy_unverified",
    )
    db.add(unverified)
    quest = _quest(db, name="Protected Quest", slug="protected-quest")
    db.commit()

    foreign_response = client.put(
        f"/api/v1/quest-progress/{quest.slug}",
        params={"character_id": foreign.id},
        headers=_headers(owner),
        json={"completed": True},
    )
    assert foreign_response.status_code == 404

    unverified_response = client.put(
        f"/api/v1/quest-progress/{quest.slug}",
        params={"character_id": unverified.id},
        headers=_headers(owner),
        json={"completed": True},
    )
    assert unverified_response.status_code == 404
    assert db.query(QuestCompletion).count() == 0


def test_quest_progress_supports_same_identifiers_as_quest_detail(client, db):
    user = make_user(db, username="quest-progress-identifiers")
    character = _verified_character(db, user, name="Identifier Druid")
    quest = _quest(db, name="Identifier Quest", slug="identifier-quest")
    db.commit()

    by_normalized_name = client.get(
        "/api/v1/quest-progress/Identifier%20Quest",
        params={"character_id": character.id},
        headers=_headers(user),
    )
    assert by_normalized_name.status_code == 200
    assert by_normalized_name.json()["quest_id"] == quest.id

    by_external_id = client.get(
        f"/api/v1/quest-progress/{quest.external_id}",
        params={"character_id": character.id},
        headers=_headers(user),
    )
    assert by_external_id.status_code == 200
    assert by_external_id.json()["quest_id"] == quest.id
