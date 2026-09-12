from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.core.security import create_access_token
from app.models.user_activity import UserActivity
from app.models.user_character import UserCharacter
from tests.conftest import make_user


def _headers(user) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.username)}"}


def _character(db, user, name: str = "Planner Knight") -> UserCharacter:
    character = UserCharacter(
        user_id=user.id,
        character_name=name,
        normalized_name=name.lower(),
        ownership_status="verified",
    )
    db.add(character)
    db.flush()
    return character


def test_hunt_search_keeps_only_latest_snapshot_per_character(client, db):
    user = make_user(db, username="planner-history-owner")
    character = _character(db, user)
    db.commit()

    first = client.post(
        "/api/v1/me/activity",
        headers=_headers(user),
        json={
            "activity_type": "hunt_search",
            "character_id": character.id,
            "entity_type": "solo",
            "query": "knight:100",
            "metadata": {"planner_config": {"soloLevel": 100}},
        },
    )
    assert first.status_code == 200

    second = client.post(
        "/api/v1/me/activity",
        headers=_headers(user),
        json={
            "activity_type": "hunt_search",
            "character_id": character.id,
            "entity_type": "solo",
            "query": "knight:180",
            "metadata": {"planner_config": {"soloLevel": 180}},
        },
    )
    assert second.status_code == 200

    rows = (
        db.query(UserActivity)
        .filter_by(
            user_id=user.id,
            character_id=character.id,
            activity_type="hunt_search",
        )
        .all()
    )
    assert len(rows) == 1
    assert rows[0].query == "knight:180"
    assert rows[0].meta_payload["planner_config"]["soloLevel"] == 180


def test_hunt_search_snapshot_expires_after_one_week(client, db):
    user = make_user(db, username="planner-history-expiry")
    character = _character(db, user, "Planner Druid")
    old = UserActivity(
        user_id=user.id,
        character_id=character.id,
        activity_type="hunt_search",
        entity_type="solo",
        query="druid:250",
        meta_payload={"planner_config": {"soloLevel": 250}},
        created_at=datetime.now(timezone.utc) - timedelta(days=8),
    )
    db.add(old)
    db.commit()

    response = client.get(
        "/api/v1/me/activity",
        params={"activity_type": "hunt_search", "character_id": character.id},
        headers=_headers(user),
    )
    assert response.status_code == 200
    assert response.json() == []
    assert db.query(UserActivity).filter(UserActivity.id == old.id).first() is None
