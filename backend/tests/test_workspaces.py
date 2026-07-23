from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.core.permissions import (
    can_manage_announcements, can_manage_events, can_manage_guild_members,
    resolve_guild_role,
)
from app.core.scopes import ContentScope, ScopeType, require_scope_creation, scope_from_legacy
from app.core.security import create_access_token
from app.models.guild_member_snapshot import GuildMemberSnapshot
from app.models.workspace_audit import WorkspaceAudit
from app.models.user_character import UserCharacter
from tests.conftest import make_user


def auth(user):
    return {"Authorization": f"Bearer {create_access_token(user.username)}"}


def test_roles_have_explicit_capabilities(db):
    leader = make_user(db, username="leader-workspace", guild_rank="Leader", guild_name="One")
    vice = make_user(db, username="vice-workspace", guild_rank="Vice Leader", guild_name="One")
    member = make_user(db, username="member-workspace", guild_rank="Member", guild_name="One")
    assert resolve_guild_role(leader).value == "guild_leader"
    assert resolve_guild_role(vice).value == "guild_viceleader"
    assert can_manage_guild_members(leader, "One")
    assert not can_manage_guild_members(vice, "One")
    assert can_manage_announcements(vice, "One") and can_manage_events(vice, "One")
    assert not can_manage_announcements(member, "One")


def test_own_workspace_and_member_route_cannot_cross_guild(client, db):
    member = make_user(db, username="own-workspace", guild_name="One")
    db.add(GuildMemberSnapshot(guild_name="Two", character_name="Hidden", snapshot_at=__import__('datetime').datetime.utcnow()))
    db.commit()
    own = client.get("/api/v1/guild/me", headers=auth(member))
    assert own.status_code == 200 and own.json()["guild_name"] == "One"
    assert client.get("/api/v1/guild/Two/members", headers=auth(member)).status_code == 403


def test_admin_directory_and_assistance_are_audited_without_membership_change(client, db):
    make_user(db, username="guild-leader", guild_rank="Leader", guild_name="Blood Moon")
    admin = make_user(db, username="workspace-admin", is_superuser=True, guild_name="Admin Home")
    admin_id = admin.id
    db.commit()
    directory = client.get("/api/v1/admin/guilds", headers=auth(admin))
    assert directory.status_code == 200
    target = next(row for row in directory.json() if row["name"] == "Blood Moon")
    opened = client.get(f"/api/v1/admin/guilds/{target['key']}", headers=auth(admin))
    assert opened.status_code == 200
    assert opened.json()["workspace"]["guild_name"] == "Blood Moon"
    db.expire_all()
    assert db.get(type(admin), admin_id).guild_name == "Admin Home"
    audit = db.query(WorkspaceAudit).filter_by(actor_id=admin_id, action="workspace_opened").one()
    assert audit.guild_name == "Blood Moon" and audit.assisted is True


def test_admin_directory_rejects_non_admin(client, db):
    member = make_user(db, username="directory-member", guild_name="One")
    db.commit()
    assert client.get("/api/v1/admin/guilds", headers=auth(member)).status_code == 403


def test_tibiadata_sync_keeps_matching_accounts_and_unlinks_departed_members(client, db, monkeypatch):
    admin = make_user(db, username="sync-admin", is_superuser=True, guild_name="Admin Home")
    staying = make_user(db, username="staying", guild_name="One", guild_rank="Member")
    departed = make_user(db, username="departed", guild_name="One", guild_rank="Member")
    db.add_all([
        UserCharacter(user_id=staying.id, character_name="Ray On", guild_name="One", guild_rank="Member"),
        UserCharacter(user_id=departed.id, character_name="Gone Away", guild_name="One", guild_rank="Member"),
    ])
    db.commit()

    async def guild_info(_name):
        return {"name": "One", "world": "Antica", "members": [{"name": "Ray On", "rank": "Leader", "level": 500, "vocation": "Knight"}]}

    monkeypatch.setattr("app.api.v1.endpoints.admin.get_guild_info", guild_info)
    response = client.post("/api/v1/guild-management/sync-guild?guild_name=One", headers=auth(admin))
    assert response.status_code == 200
    assert response.json()["unlinked_users"] == 1
    db.refresh(staying); db.refresh(departed)
    assert staying.guild_name == "One" and staying.guild_rank == "Leader"
    assert departed.guild_name is None and departed.guild_rank == "Unranked"
    audit = db.query(WorkspaceAudit).filter_by(action="guild_membership_synchronized").one()
    assert audit.assisted is True and audit.safe_metadata["actor_context"] == "system"


def test_admin_can_assign_composable_capabilities_with_audit(client, db):
    admin = make_user(db, username="roles-admin", is_superuser=True)
    member = make_user(db, username="roles-member", guild_name="One", guild_rank="Vice Leader")
    response = client.put(f"/api/v1/guild-management/users/{member.id}", headers=auth(admin), json={
        "is_superuser": True, "is_moderator": True, "is_writer": True,
    })
    assert response.status_code == 200
    assert response.json()["is_superuser"] is True
    assert response.json()["is_moderator"] is True
    assert response.json()["is_writer"] is True
    assert response.json()["guild_rank"] == "Vice Leader"
    audit = db.query(WorkspaceAudit).filter_by(action="user_capabilities_updated", target_id=str(member.id)).one()
    assert audit.safe_metadata["after"] == {"admin": True, "moderator": True, "writer": True}


def test_scope_policy_and_legacy_compatibility(db):
    leader = make_user(db, username="scope-leader", guild_rank="Leader", guild_name="One")
    admin = make_user(db, username="scope-global", is_superuser=True)
    require_scope_creation(leader, ContentScope(ScopeType.GUILD, guild_name="One", world_name="Antica"))
    with pytest.raises(HTTPException):
        require_scope_creation(leader, ContentScope(ScopeType.SERVER, world_name="Antica"))
    with pytest.raises(HTTPException):
        require_scope_creation(leader, ContentScope(ScopeType.GLOBAL))
    require_scope_creation(admin, ContentScope(ScopeType.SERVER, world_name="Antica"))
    require_scope_creation(admin, ContentScope(ScopeType.GLOBAL))
    with pytest.raises(HTTPException) as coalition:
        require_scope_creation(admin, ContentScope(ScopeType.COALITION))
    assert coalition.value.status_code == 422
    assert scope_from_legacy("guild_only", guild_name="One").scope_type is ScopeType.GUILD
    assert scope_from_legacy("world_only", world_name="Antica").scope_type is ScopeType.SERVER
    assert scope_from_legacy("public").scope_type is ScopeType.GLOBAL
