from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.core.security import create_access_token
from app.models.events import Event
from app.models.guild_management import GuildManagementGrant
from app.models.user_character import UserCharacter
from tests.conftest import make_user


def auth(user):
    return {"Authorization": f"Bearer {create_access_token(user.username)}"}


def link_verified(db, user, guild_name: str, rank: str = "Member") -> None:
    character_name = f"{user.username} Event"
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


def grant_events(db, user, guild_name: str, grantor_id: int) -> None:
    db.add(GuildManagementGrant(
        user_id=user.id,
        guild_name=guild_name,
        normalized_guild_name=guild_name.casefold(),
        capability="events.manage",
        granted_by_id=grantor_id,
    ))


def event_payload(guild_name: str, **overrides):
    payload = {
        "type": "contest",
        "title": "Scoped event",
        "description": "Guild-only event",
        "start_date": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
        "guild_name": guild_name,
        "is_public": False,
    }
    payload.update(overrides)
    return payload


def seed_event(db, creator, guild_name: str, *, public: bool = False) -> Event:
    event = Event(
        type="contest",
        title="Public event" if public else "Private event",
        description="Scoped participants",
        start_date=datetime.now(UTC) + timedelta(days=1),
        guild_name=guild_name,
        creator_id=creator.id,
        is_public=public,
        public_code=f"P{creator.id:05d}"[-6:],
    )
    db.add(event)
    db.flush()
    return event


def test_event_creation_requires_target_guild_management(client, db):
    admin = make_user(db, username="event-grantor", is_superuser=True)
    manager = make_user(db, username="event-manager-a", guild_name="Guild A")
    member = make_user(db, username="event-member-a", guild_name="Guild A")
    link_verified(db, member, "Guild A")
    grant_events(db, manager, "Guild A", admin.id)
    db.commit()

    created = client.post("/api/v1/events/", json=event_payload("Guild A"), headers=auth(manager))
    assert created.status_code == 201
    assert created.json()["guild_name"] == "Guild A"

    denied_member = client.post("/api/v1/events/", json=event_payload("Guild A"), headers=auth(member))
    assert denied_member.status_code == 403

    denied_other_guild = client.post("/api/v1/events/", json=event_payload("Guild B"), headers=auth(manager))
    assert denied_other_guild.status_code == 403


def test_manager_cannot_manage_another_guild_event(client, db):
    admin = make_user(db, username="event-manage-grantor", is_superuser=True)
    manager_a = make_user(db, username="event-manager-only-a", guild_name="Guild A")
    creator_b = make_user(db, username="event-creator-b", guild_name="Guild B")
    grant_events(db, manager_a, "Guild A", admin.id)
    event_b = seed_event(db, creator_b, "Guild B")
    db.commit()

    response = client.put(
        f"/api/v1/events/{event_b.id}",
        json={"title": "Cross-guild update"},
        headers=auth(manager_a),
    )
    assert response.status_code == 403

    event_a = seed_event(db, manager_a, "Guild A")
    db.commit()
    reassignment = client.put(
        f"/api/v1/events/{event_a.id}",
        json={"guild_name": "Guild B"},
        headers=auth(manager_a),
    )
    assert reassignment.status_code == 403


def test_private_event_detail_is_visible_only_inside_authorized_guild(client, db):
    creator = make_user(db, username="private-event-creator", guild_name="Private Guild")
    member = make_user(db, username="private-event-member", guild_name="Private Guild")
    outsider = make_user(db, username="private-event-outsider", guild_name="Other Guild")
    link_verified(db, member, "Private Guild")
    link_verified(db, outsider, "Other Guild")
    event = seed_event(db, creator, "Private Guild")
    db.commit()

    assert client.get(f"/api/v1/events/{event.id}", headers=auth(outsider)).status_code == 403
    authorized = client.get(f"/api/v1/events/{event.id}", headers=auth(member))
    assert authorized.status_code == 200
    assert authorized.json()["guild_name"] == "Private Guild"


def test_public_event_detail_remains_public(client, db):
    creator = make_user(db, username="public-event-creator", guild_name="Public Guild")
    outsider = make_user(db, username="public-event-outsider", guild_name="Other Guild")
    event = seed_event(db, creator, "Public Guild", public=True)
    db.commit()

    assert client.get(f"/api/v1/events/{event.id}", headers=auth(outsider)).status_code == 200
    assert client.get(f"/api/v1/events/public/{event.uuid}").status_code == 200
