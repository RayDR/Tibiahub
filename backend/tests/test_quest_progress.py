from __future__ import annotations

from app.core.security import create_access_token
from app.models.external_data import QuestMission, TibiaWikiQuest
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


def _add_missions(db, quest: TibiaWikiQuest, count: int = 3) -> list[QuestMission]:
    missions = []
    for sequence in range(1, count + 1):
        mission = QuestMission(
            quest_id=quest.id,
            provider_id="tibiawiki",
            identity_key=f"mission-{sequence}",
            title=f"Mission {sequence}",
            normalized_title=f"mission {sequence}",
            sequence=sequence,
        )
        db.add(mission)
        missions.append(mission)
    db.flush()
    return missions


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
    initial_payload = initial.json()
    assert initial_payload["quest_id"] == quest.id
    assert initial_payload["character_id"] == character.id
    assert initial_payload["status"] == "not_started"
    assert initial_payload["completed"] is False
    assert initial_payload["completed_mission_ids"] == []
    assert initial_payload["completed_at"] is None

    completed = client.put(
        f"/api/v1/quest-progress/{quest.slug}",
        params={"character_id": character.id},
        headers=_headers(user),
        json={"completed": True},
    )
    assert completed.status_code == 200
    payload = completed.json()
    assert payload["status"] == "completed"
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
    assert cleared.json()["status"] == "not_started"
    assert cleared.json()["completed"] is False
    assert db.query(QuestCompletion).filter_by(character_id=character.id, quest_id=quest.id).count() == 0


def test_partial_progress_tracks_ordered_missions_and_auto_completes(client, db):
    user = make_user(db, username="quest-progress-partial")
    character = _verified_character(db, user, name="Partial Paladin")
    quest = _quest(db, name="Mission Quest", slug="mission-quest")
    missions = _add_missions(db, quest, count=3)
    db.commit()

    partial = client.put(
        f"/api/v1/quest-progress/{quest.slug}",
        params={"character_id": character.id},
        headers=_headers(user),
        json={"completed_mission_ids": [str(missions[0].id), str(missions[1].id)]},
    )
    assert partial.status_code == 200
    payload = partial.json()
    assert payload["status"] == "in_progress"
    assert payload["completed"] is False
    assert payload["completed_steps"] == 2
    assert payload["total_steps"] == 3
    assert payload["completed_mission_ids"] == [str(missions[0].id), str(missions[1].id)]
    assert payload["current_mission_id"] == str(missions[2].id)
    assert payload["completed_at"] is None

    listed = client.get(
        "/api/v1/quest-progress",
        params={"character_id": character.id},
        headers=_headers(user),
    )
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["quest_id"] == quest.id
    assert listed.json()[0]["status"] == "in_progress"

    completed = client.put(
        f"/api/v1/quest-progress/{quest.slug}",
        params={"character_id": character.id},
        headers=_headers(user),
        json={"completed_mission_ids": [str(mission.id) for mission in missions]},
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    assert completed.json()["completed_steps"] == 3
    assert completed.json()["completed_at"]


def test_quest_progress_rejects_foreign_missions(client, db):
    user = make_user(db, username="quest-progress-mission-owner")
    character = _verified_character(db, user, name="Mission Knight")
    quest = _quest(db, name="Owned Mission Quest", slug="owned-mission-quest")
    _add_missions(db, quest, count=1)
    other_quest = _quest(db, name="Other Mission Quest", slug="other-mission-quest")
    foreign_mission = _add_missions(db, other_quest, count=1)[0]
    db.commit()

    response = client.put(
        f"/api/v1/quest-progress/{quest.slug}",
        params={"character_id": character.id},
        headers=_headers(user),
        json={"completed_mission_ids": [str(foreign_mission.id)]},
    )
    assert response.status_code == 400
    assert db.query(QuestCompletion).count() == 0


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
