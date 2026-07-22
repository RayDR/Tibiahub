from __future__ import annotations

from app.core.security import create_access_token
from tests.conftest import make_user


def auth(user):
    return {"Authorization": f"Bearer {create_access_token(user.username)}"}


def test_profile_allows_account_without_primary_character(client, db):
    user = make_user(db, username="profile-without-character", guild_name="Profile Guild")
    user.tibia_character_name = None
    db.commit()

    response = client.get("/api/v1/profile/me", headers=auth(user))

    assert response.status_code == 200
    assert response.json()["tibia_character_name"] is None
    assert response.json()["characters"] == []


def test_legacy_profile_endpoint_allows_account_without_primary_character(client, db):
    user = make_user(db, username="legacy-profile-without-character", guild_name="Profile Guild")
    user.tibia_character_name = None
    db.commit()

    response = client.get("/api/v1/profile/profile", headers=auth(user))

    assert response.status_code == 200
    assert response.json()["tibia_character_name"] is None
