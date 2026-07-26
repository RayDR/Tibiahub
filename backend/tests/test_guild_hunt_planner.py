from datetime import UTC, datetime, timedelta

import pytest

from app.models.user_character import UserCharacter
from app.services.guild_hunt_service import GuildHuntError, GuildHuntPlannerService
from tests.conftest import make_user


def values(**overrides):
    payload = {
        "scheduled_at": datetime.now(UTC) + timedelta(days=2),
        "timezone_name": "America/Chicago",
        "server_name": "Lobera",
        "location": "Roshamuul",
        "target": "Guild experience hunt",
        "recommended_level": 400,
        "recommended_vocations": ["EK", "ED", "RP", "MS"],
        "maximum_participants": 4,
        "required_ek": 1,
        "required_ed": 1,
        "required_rp": 0,
        "required_ms": 0,
        "description": "Balanced team hunt",
        "discord_channel": "hunts",
        "voice_channel": "Party 1",
    }
    payload.update(overrides)
    return payload


def verified_character(db, user, name, *, guild="Bald Dwarfs", vocation="Elite Knight"):
    row = UserCharacter(
        user_id=user.id,
        character_name=name,
        normalized_name=name.casefold(),
        ownership_status="verified",
        ownership_verified_at=datetime.now(UTC),
        guild_name=guild,
        vocation=vocation,
    )
    db.add(row)
    db.flush()
    return row


def test_leader_creates_and_member_joins_and_leaves(db):
    leader = make_user(db, username="hunt_leader", guild_name="Bald Dwarfs", guild_rank="Alpha Warbringer")
    member = make_user(db, username="hunt_member", guild_name="Bald Dwarfs")
    verified_character(db, member, "Planner Knight")

    hunt = GuildHuntPlannerService.create(db, leader, "Bald Dwarfs", values())
    participant = GuildHuntPlannerService.join(db, member, hunt)
    db.flush()

    assert participant.character_name == "Planner Knight"
    assert participant.attendance_status == "registered"
    GuildHuntPlannerService.leave(db, member, hunt)
    assert participant.attendance_status == "left"


def test_non_leader_cannot_create_or_operate_hunt(db):
    leader = make_user(db, username="authorized_hunt_leader", guild_name="Bald Dwarfs", guild_rank="Leader")
    member = make_user(db, username="unauthorized_hunt_member", guild_name="Bald Dwarfs")
    hunt = GuildHuntPlannerService.create(db, leader, "Bald Dwarfs", values())

    with pytest.raises(PermissionError):
        GuildHuntPlannerService.create(db, member, "Bald Dwarfs", values())
    with pytest.raises(PermissionError):
        GuildHuntPlannerService.transition(db, member, hunt, "start")


def test_capacity_and_verified_guild_character_are_enforced(db):
    leader = make_user(db, username="capacity_leader", guild_name="Bald Dwarfs", guild_rank="Leader")
    first = make_user(db, username="capacity_first", guild_name="Bald Dwarfs")
    second = make_user(db, username="capacity_second", guild_name="Bald Dwarfs")
    verified_character(db, first, "Capacity One")
    verified_character(db, second, "Capacity Two")
    hunt = GuildHuntPlannerService.create(db, leader, "Bald Dwarfs", values(maximum_participants=1, required_ek=1, required_ed=0))

    GuildHuntPlannerService.join(db, first, hunt)
    with pytest.raises(GuildHuntError, match="full"):
        GuildHuntPlannerService.join(db, second, hunt)


def test_lifecycle_and_attendance_are_recorded(db):
    leader = make_user(db, username="attendance_leader", guild_name="Bald Dwarfs", guild_rank="Leader")
    member = make_user(db, username="attendance_member", guild_name="Bald Dwarfs")
    verified_character(db, member, "Attendance Knight")
    hunt = GuildHuntPlannerService.create(db, leader, "Bald Dwarfs", values())
    participant = GuildHuntPlannerService.join(db, member, hunt)

    GuildHuntPlannerService.transition(db, leader, hunt, "start")
    GuildHuntPlannerService.mark_attendance(db, leader, hunt, participant, "attended")
    GuildHuntPlannerService.transition(db, leader, hunt, "finish")

    assert hunt.status == "finished"
    assert participant.attendance_status == "attended"
    assert hunt.started_at and hunt.finished_at


def test_invalid_role_capacity_and_past_schedule_are_rejected(db):
    leader = make_user(db, username="validation_leader", guild_name="Bald Dwarfs", guild_rank="Leader")
    with pytest.raises(GuildHuntError, match="slots"):
        GuildHuntPlannerService.create(db, leader, "Bald Dwarfs", values(maximum_participants=1, required_ek=1, required_ed=1))
    with pytest.raises(GuildHuntError, match="future"):
        GuildHuntPlannerService.create(db, leader, "Bald Dwarfs", values(scheduled_at=datetime.now(UTC) - timedelta(minutes=1)))
