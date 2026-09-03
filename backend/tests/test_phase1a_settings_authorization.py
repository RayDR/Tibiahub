from __future__ import annotations

import pytest

from app.core.security import create_access_token
from app.models.guild_management import GuildManagementGrant
from app.models.user_character import UserCharacter
from tests.conftest import make_user


def auth(user):
    return {"Authorization": f"Bearer {create_access_token(user.username)}"}


def link_verified(db, user, guild_name: str, rank: str = "Member") -> None:
    character_name = f"{user.username} Settings"
    db.add(UserCharacter(
        user_id=user.id,
        character_name=character_name,
        normalized_name=character_name.casefold(),
        ownership_status="verified",
        ownership_verified_at=user.created_at,
        guild_name=guild_name,
        guild_rank=rank,
        world_name="Antica",
    ))


@pytest.mark.parametrize("method", ["get", "put"])
def test_global_settings_reject_anonymous(method, client):
    response = getattr(client, method)(
        "/api/v1/guild-management/settings",
        **({"json": {}} if method == "put" else {}),
    )
    assert response.status_code == 401


@pytest.mark.parametrize("method", ["get", "put"])
def test_global_settings_reject_every_non_global_admin_role(method, client, db):
    admin = make_user(db, username=f"settings-grantor-{method}", is_superuser=True)
    normal = make_user(db, username=f"settings-normal-{method}", guild_name="Settings Guild")
    delegated = make_user(db, username=f"settings-delegated-{method}", guild_name="Settings Guild")
    leader = make_user(db, username=f"settings-leader-{method}", guild_name="Settings Guild", guild_rank="Leader")
    link_verified(db, normal, "Settings Guild")
    link_verified(db, delegated, "Settings Guild")
    link_verified(db, leader, "Settings Guild", "Leader")
    db.add(GuildManagementGrant(
        user_id=delegated.id,
        guild_name="Settings Guild",
        normalized_guild_name="settings guild",
        capability="events.manage",
        granted_by_id=admin.id,
    ))
    db.commit()

    for user in (normal, delegated, leader):
        response = getattr(client, method)(
            "/api/v1/guild-management/settings",
            headers=auth(user),
            **({"json": {}} if method == "put" else {}),
        )
        assert response.status_code == 403, (method, user.username, response.text)


@pytest.mark.parametrize("method", ["get", "put"])
def test_global_settings_preserve_global_admin_access(method, client, db):
    admin = make_user(db, username=f"settings-admin-{method}", is_superuser=True)
    db.commit()
    response = getattr(client, method)(
        "/api/v1/guild-management/settings",
        headers=auth(admin),
        **({"json": {}} if method == "put" else {}),
    )
    assert response.status_code == 200

