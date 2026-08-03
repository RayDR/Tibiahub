from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.models.guild_management import GuildManagementGrant, GuildRosterCharacter
from app.models.raffle import RaffleEligibilitySnapshot
from app.models.user import User
from app.models.user_character import UserCharacter
from app.models.workspace_audit import WorkspaceAudit
from app.core.security import create_access_token
from app.services.guild_authorization_service import (
    GuildAuthorizationError,
    GuildAuthorizationService,
    GuildManagementGrantService,
    SUPPORTED_GUILD_CAPABILITIES,
)
from app.services.guild_roster_service import GuildRosterService, GuildRosterSyncError
from app.services.raffle_participant_service import (
    RaffleCandidateService,
    RaffleParticipantError,
    RaffleParticipantService,
)
from app.services.raffle_service import prepare_participant_pool
from tests.conftest import make_raffle, make_user


def auth(user):
    return {"Authorization": f"Bearer {create_access_token(user.username)}"}


def verified_character(db, user, *, name: str, guild: str, rank: str = "Member") -> UserCharacter:
    row = UserCharacter(
        user_id=user.id, character_name=name, normalized_name=name.casefold(),
        ownership_status="verified", ownership_verified_at=datetime.now(UTC),
        guild_name=guild, guild_rank=rank, world_name="Antica",
    )
    db.add(row)
    db.flush()
    return row


def roster_character(
    db, *, name: str, guild: str = "Architecture Guild", days_ago: int = 1,
    user_character: UserCharacter | None = None,
) -> GuildRosterCharacter:
    row = GuildRosterCharacter(
        guild_name=guild, normalized_guild_name=guild.casefold(),
        world_name="Antica", normalized_world_name="antica",
        character_name=name, normalized_character_name=name.casefold(),
        guild_rank="Member", level=500, vocation="Knight",
        last_activity_at=datetime.now(UTC) - timedelta(days=days_ago),
        first_synchronized_at=datetime.now(UTC), last_synchronized_at=datetime.now(UTC),
        is_current=True, source="tibiadata", source_metadata={},
        linked_user_character_id=user_character.id if user_character else None,
        linked_user_id=user_character.user_id if user_character else None,
    )
    db.add(row)
    db.flush()
    return row


@pytest.mark.asyncio
async def test_roster_sync_persists_external_links_and_departures_without_creating_users(db):
    guild = "Architecture Guild"
    linked_user = make_user(db, username="roster-linked", guild_name=guild)
    linked = verified_character(db, linked_user, name="Linked Knight", guild=guild)
    before_users = db.query(User).count()

    async def first_guild(_name):
        return {
            "name": guild, "world": "Antica", "members": [
                {"name": "Linked Knight", "rank": "Leader", "level": 600, "vocation": "Elite Knight", "last_login": datetime.now(UTC).isoformat()},
                {"name": "External Druid", "rank": "Member", "level": 450, "vocation": "Elder Druid", "last_login": datetime.now(UTC).isoformat()},
            ],
        }

    async def no_enrichment(_name):
        raise AssertionError("direct guild activity should avoid character enrichment")

    first = await GuildRosterService.synchronize(db, guild, guild_fetcher=first_guild, character_fetcher=no_enrichment)
    assert first.inserted == 2 and first.linked == 1 and first.unlinked == 1
    assert db.query(User).count() == before_users
    external = db.query(GuildRosterCharacter).filter_by(normalized_character_name="external druid").one()
    assert external.linked_user_id is None and external.is_current is True
    linked_row = db.query(GuildRosterCharacter).filter_by(normalized_character_name="linked knight").one()
    assert linked_row.linked_user_character_id == linked.id

    async def second_guild(_name):
        return {"name": guild, "world": "Antica", "members": [{
            "name": "Linked Knight", "rank": "Leader", "last_login": datetime.now(UTC).isoformat(),
        }]}

    second = await GuildRosterService.synchronize(db, guild, guild_fetcher=second_guild, character_fetcher=no_enrichment)
    assert second.departed == 1
    assert external.is_current is False

    async def unavailable(_name):
        raise RuntimeError("provider unavailable")

    with pytest.raises(GuildRosterSyncError):
        await GuildRosterService.synchronize(db, guild, guild_fetcher=unavailable)
    assert linked_row.is_current is True and external.is_current is False


def test_recent_activity_windows_and_linked_account_qualification(db):
    owner = make_user(db, username="activity-owner")
    active_character = verified_character(db, owner, name="Active Alt", guild="Architecture Guild")
    inactive_character = verified_character(db, owner, name="Inactive Main", guild="Architecture Guild")
    recent = roster_character(db, name="Active Alt", days_ago=5, user_character=active_character)
    inactive = roster_character(db, name="Inactive Main", days_ago=40, user_character=inactive_character)
    fifteen = roster_character(db, name="Fifteen External", days_ago=10)
    thirty = roster_character(db, name="Thirty External", days_ago=20)
    raffle = make_raffle(db, creator_id=owner.id, guild_name="Architecture Guild")

    seven_ids = {item["roster_character_id"] for item in RaffleCandidateService.list_candidates(db, raffle, days=7)}
    fifteen_ids = {item["roster_character_id"] for item in RaffleCandidateService.list_candidates(db, raffle, days=15)}
    thirty_ids = {item["roster_character_id"] for item in RaffleCandidateService.list_candidates(db, raffle, days=30)}
    assert seven_ids == {recent.id, inactive.id}
    assert fifteen_ids == {recent.id, inactive.id, fifteen.id}
    assert thirty_ids == {recent.id, inactive.id, fifteen.id, thirty.id}
    with pytest.raises(RaffleParticipantError, match="7, 15, or 30"):
        RaffleCandidateService.list_candidates(db, raffle, days=14)


def test_verified_multi_guild_grants_are_module_scoped_audited_and_revocable(db):
    leader = make_user(db, username="permissions-leader")
    target = make_user(db, username="permissions-target")
    outsider = make_user(db, username="permissions-outsider")
    verified_character(db, leader, name="Leader One", guild="Guild One", rank="Leader")
    verified_character(db, target, name="Manager One", guild="Guild One")
    verified_character(db, target, name="Manager Two", guild="Guild Two")
    verified_character(db, outsider, name="Outsider Two", guild="Guild Two")

    with pytest.raises(GuildAuthorizationError):
        GuildManagementGrantService.grant(
            db, actor=leader, target=outsider, guild_name="Guild Two", capabilities=["raffles.manage"],
        )
    GuildManagementGrantService.grant(
        db, actor=leader, target=target, guild_name="Guild One", capabilities=["raffles.manage"],
    )
    admin = make_user(db, username="permissions-admin", is_superuser=True)
    GuildManagementGrantService.grant_all(db, actor=admin, target=target, guild_name="Guild Two")
    assert GuildAuthorizationService.can_manage(db, target, "Guild One", "raffles.manage")
    assert not GuildAuthorizationService.can_manage(db, target, "Guild One", "events.manage")
    assert set(GuildAuthorizationService.manageable_guilds(db, target, "raffles.manage")) == {"Guild One", "Guild Two"}
    assert db.query(GuildManagementGrant).filter_by(user_id=target.id, normalized_guild_name="guild two").count() == len(SUPPORTED_GUILD_CAPABILITIES)
    assert db.query(WorkspaceAudit).filter_by(action="guild_management_permissions_granted", target_id=str(target.id)).count() == 2

    revoked = GuildManagementGrantService.revoke(
        db, actor=leader, target=target, guild_name="Guild One", capabilities=["raffles.manage"],
    )
    assert revoked == 1
    assert not GuildAuthorizationService.can_manage(db, target, "Guild One", "raffles.manage")
    assert db.query(WorkspaceAudit).filter_by(action="guild_management_permissions_revoked", target_id=str(target.id)).count() == 1


def test_guild_grant_endpoints_list_grant_all_and_revoke(client, db):
    admin = make_user(db, username="grant-api-admin", is_superuser=True)
    target = make_user(db, username="grant-api-target")
    verified_character(db, target, name="Grant Target", guild="Grant Guild")
    roster_character(db, name="Grant Target", guild="Grant Guild")
    db.commit()

    created = client.post(
        "/api/v1/guild-management/guilds/Grant%20Guild/grants",
        json={"user_id": target.id, "grant_all": True},
        headers=auth(admin),
    )
    assert created.status_code == 200, created.text
    assert {row["capability"] for row in created.json()} == set(SUPPORTED_GUILD_CAPABILITIES)

    listed = client.get(
        "/api/v1/guild-management/guilds/Grant%20Guild/grants",
        headers=auth(admin),
    )
    assert listed.status_code == 200
    assert {row["user_id"] for row in listed.json()} == {target.id}

    revoked = client.post(
        f"/api/v1/guild-management/guilds/Grant%20Guild/grants/{target.id}/revoke",
        json={"capabilities": None},
        headers=auth(admin),
    )
    assert revoked.status_code == 200 and revoked.json()["revoked"] == len(SUPPORTED_GUILD_CAPABILITIES)
    assert client.get(
        "/api/v1/guild-management/guilds/Grant%20Guild/grants",
        headers=auth(admin),
    ).json() == []

    missing = client.post(
        "/api/v1/guild-management/guilds/Grant%20Guild/grants",
        json={"user_id": 999999, "grant_all": True},
        headers=auth(admin),
    )
    assert missing.status_code == 404


def test_external_participant_bulk_replace_remove_uniqueness_and_freeze_guards(db):
    actor = make_user(db, username="participant-manager", is_superuser=True)
    owner = make_user(db, username="known-owner")
    first_character = verified_character(db, owner, name="Known Main", guild="Architecture Guild")
    second_character = verified_character(db, owner, name="Known Alt", guild="Architecture Guild")
    known_main = roster_character(db, name="Known Main", user_character=first_character)
    known_alt = roster_character(db, name="Known Alt", user_character=second_character)
    external_one = roster_character(db, name="External One")
    external_two = roster_character(db, name="External Two")
    raffle = make_raffle(db, creator_id=actor.id, guild_name="Architecture Guild")
    raffle.purpose = "real"

    result = RaffleParticipantService.add_roster_characters(
        db, raffle, actor, roster_character_ids=[known_main.id, external_one.id, external_two.id],
    )
    assert result.added == 3
    assert sum(participant.user_id is None for participant in raffle.participants) == 2
    with pytest.raises(RaffleParticipantError) as duplicate:
        RaffleParticipantService.add_roster_characters(db, raffle, actor, roster_character_ids=[external_one.id])
    assert duplicate.value.code == "duplicate_character"
    with pytest.raises(RaffleParticipantError) as known_conflict:
        RaffleParticipantService.add_roster_characters(db, raffle, actor, roster_character_ids=[known_alt.id])
    assert known_conflict.value.code == "duplicate_known_account"

    RaffleParticipantService.update_settings(db, raffle, actor, unique_account_participation=False)
    assert RaffleParticipantService.add_roster_characters(
        db, raffle, actor, roster_character_ids=[known_alt.id],
    ).added == 1
    with pytest.raises(RaffleParticipantError, match="duplicate known-account"):
        RaffleParticipantService.update_settings(db, raffle, actor, unique_account_participation=True)

    replaced = RaffleParticipantService.add_roster_characters(
        db, raffle, actor, roster_character_ids=[external_two.id], replace_existing=True,
    )
    assert replaced.removed == 3 and replaced.unchanged == 1
    current = [participant for participant in raffle.participants if not participant.is_deleted]
    assert [participant.character_name for participant in current] == ["External Two"]
    removed = RaffleParticipantService.remove(db, raffle, actor, participant_ids=[current[0].id])
    assert removed.removed == 1 and not [participant for participant in raffle.participants if not participant.is_deleted]

    RaffleParticipantService.add_roster_characters(db, raffle, actor, roster_character_ids=[external_one.id])
    db.add(RaffleEligibilitySnapshot(
        raffle=raffle, snapshot_number=1, cutoff_at=datetime.now(UTC), timezone_name="UTC",
        eligibility_days=7, source="test", candidate_count=1, eligible_count=1,
        excluded_count=0, snapshot_hash="f" * 64, created_by_id=actor.id,
    ))
    db.flush()
    with pytest.raises(RaffleParticipantError) as frozen:
        RaffleParticipantService.remove(
            db, raffle, actor,
            participant_ids=[next(participant.id for participant in raffle.participants if not participant.is_deleted)],
        )
    assert frozen.value.code == "eligibility_frozen"


def test_equal_mode_ignores_weights_and_weighted_mode_preserves_them(db):
    actor = make_user(db, username="weight-manager", is_superuser=True)
    raffle = make_raffle(db, creator_id=actor.id, guild_name="Architecture Guild")
    first = roster_character(db, name="Weight One")
    second = roster_character(db, name="Weight Two")
    RaffleParticipantService.add_roster_characters(db, raffle, actor, roster_character_ids=[first.id, second.id])
    participants = [participant for participant in raffle.participants if not participant.is_deleted]
    RaffleParticipantService.update_weight(db, raffle, actor, participant_id=participants[0].id, weight=Decimal("7.25"))
    equal, _, _ = prepare_participant_pool(participants, unique_account_participation=True, weighting_mode="equal")
    weighted, _, _ = prepare_participant_pool(participants, unique_account_participation=True, weighting_mode="weighted")
    assert [row["weight"] for row in equal] == [Decimal("1"), Decimal("1")]
    assert [row["weight"] for row in weighted] == [Decimal("7.2500"), Decimal("1")]
    with pytest.raises(RaffleParticipantError) as invalid:
        RaffleParticipantService.update_weight(db, raffle, actor, participant_id=participants[0].id, weight=0)
    assert invalid.value.code == "invalid_weight"


def test_raffle_creation_is_admin_test_only_and_uses_authorized_guilds(client, db):
    leader = make_user(db, username="creation-leader")
    manager = make_user(db, username="creation-manager")
    admin = make_user(db, username="creation-admin", is_superuser=True)
    verified_character(db, leader, name="Creation Leader", guild="Guild One", rank="Leader")
    verified_character(db, manager, name="Creation Manager One", guild="Guild One")
    verified_character(db, manager, name="Creation Manager Two", guild="Guild Two")
    GuildManagementGrantService.grant(
        db, actor=leader, target=manager, guild_name="Guild One", capabilities=["raffles.manage"],
    )
    GuildManagementGrantService.grant(
        db, actor=admin, target=manager, guild_name="Guild Two", capabilities=["raffles.manage"],
    )
    db.commit()
    test_payload = {
        "title": "Admin test raffle", "guild_name": "Guild One", "scope_type": "guild",
        "purpose": "test", "run_mode": "automatic", "timezone_name": "UTC",
        "scheduled_run_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        "prizes": [
            {"name": "Second", "reward": "100 TC", "position": "second", "amount": 100, "currency": "TC"},
            {"name": "First", "reward": "200 TC", "position": "first", "amount": 200, "currency": "TC"},
        ],
    }
    assert client.post("/api/v1/raffles/", json=test_payload, headers=auth(leader)).status_code == 403
    assert client.post("/api/v1/raffles/", json=test_payload, headers=auth(admin)).status_code == 201

    real_payload = {
        "title": "Guild manager raffle", "guild_name": "Guild Two", "scope_type": "guild",
        "purpose": "real", "run_mode": "manual", "world_name": "Antica",
        "prizes": [{"name": "Prize", "reward": "100 TC"}],
    }
    created = client.post("/api/v1/raffles/", json=real_payload, headers=auth(manager))
    assert created.status_code == 201, created.text
    assert created.json()["purpose"] == "real" and created.json()["scope_type"] == "guild"
    visible = client.get(
        "/api/v1/guild-management/manageable-guilds",
        params={"capability": "raffles.manage"}, headers=auth(manager),
    )
    assert visible.status_code == 200
    assert set(visible.json()["guilds"]) == {"Guild One", "Guild Two"}
    context = client.get("/api/v1/guild-management/context", headers=auth(manager))
    assert context.status_code == 200
    by_guild = {row["guild_name"]: row for row in context.json()["guilds"]}
    assert set(by_guild) == {"Guild One", "Guild Two"}
    assert by_guild["Guild One"]["role"] == "delegated_manager"
    assert by_guild["Guild One"]["capabilities"]["raffles.manage"] is True
    assert by_guild["Guild One"]["capabilities"]["events.manage"] is False
    assert by_guild["Guild Two"]["representative_character_name"] == "Creation Manager Two"
    crafted = {**real_payload, "title": "Unauthorized guild", "guild_name": "Guild Three"}
    assert client.post("/api/v1/raffles/", json=crafted, headers=auth(manager)).status_code == 403
