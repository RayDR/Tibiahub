from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy import event

from app.knowledge.models import KnowledgeEntity, KnowledgeEntityType
from app.knowledge.registry import EntityTypeRegistry, ProviderRegistry, RelationshipTypeRegistry
from app.knowledge.services import KnowledgeGraphService, RelationshipInput
from app.core.security import create_access_token
from app.models import Creature
from app.models.external_data import TibiaWikiQuest
from app.models.hunt_zone import HuntZone
from app.models.world_map import WorldMapFloor, WorldMapMarker
from app.models.workspace_audit import WorkspaceAudit
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


def verified_character(db, user, name, *, guild="Bald Dwarfs", vocation="Elite Knight", guild_rank="Member"):
    row = UserCharacter(
        user_id=user.id,
        character_name=name,
        normalized_name=name.casefold(),
        ownership_status="verified",
        ownership_verified_at=datetime.now(UTC),
        guild_name=guild,
        guild_rank=guild_rank,
        vocation=vocation,
    )
    db.add(row)
    db.flush()
    return row


def canonical_zone(db, *, name="Planner Grounds", entity_type="hunt_zone", status="active"):
    if db.get(KnowledgeEntityType, entity_type) is None:
        db.add(KnowledgeEntityType(entity_type=entity_type, display_name=f"Planner {entity_type}"))
        db.flush()
    entity = KnowledgeEntity(
        entity_type=entity_type,
        canonical_name=name,
        slug=name.casefold().replace(" ", "-"),
        language_neutral_id=f"planner:{entity_type}:{name.casefold()}",
        status=status,
        visibility="public",
    )
    db.add(entity)
    db.flush()
    if entity_type == "hunt_zone":
        db.add(HuntZone(
            name=name,
            slug=entity.slug,
            normalized_name=name.casefold(),
            source_provider="tibiawiki",
            external_id=name.replace(" ", "_"),
            knowledge_entity_id=entity.uuid,
            min_level=250,
            supplied_fields=["min_level"],
        ))
        db.flush()
    return entity


def knowledge_registries(db):
    EntityTypeRegistry.register_initial(db)
    ProviderRegistry.register_initial(db)
    RelationshipTypeRegistry.register_initial(db)
    db.flush()


def test_leader_creates_and_member_joins_and_leaves(db):
    leader = make_user(db, username="hunt_leader", guild_name="Bald Dwarfs", guild_rank="Alpha Warbringer")
    verified_character(db, leader, "Planner Leader", guild_rank="Alpha Warbringer")
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
    verified_character(db, leader, "Authorized Leader", guild_rank="Leader")
    member = make_user(db, username="unauthorized_hunt_member", guild_name="Bald Dwarfs")
    hunt = GuildHuntPlannerService.create(db, leader, "Bald Dwarfs", values())

    with pytest.raises(PermissionError):
        GuildHuntPlannerService.create(db, member, "Bald Dwarfs", values())
    with pytest.raises(PermissionError):
        GuildHuntPlannerService.transition(db, member, hunt, "start")


def test_capacity_and_verified_guild_character_are_enforced(db):
    leader = make_user(db, username="capacity_leader", guild_name="Bald Dwarfs", guild_rank="Leader")
    verified_character(db, leader, "Capacity Leader", guild_rank="Leader")
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
    verified_character(db, leader, "Attendance Leader", guild_rank="Leader")
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
    verified_character(db, leader, "Validation Leader", guild_rank="Leader")
    with pytest.raises(GuildHuntError, match="slots"):
        GuildHuntPlannerService.create(db, leader, "Bald Dwarfs", values(maximum_participants=1, required_ek=1, required_ed=1))
    with pytest.raises(GuildHuntError, match="future"):
        GuildHuntPlannerService.create(db, leader, "Bald Dwarfs", values(scheduled_at=datetime.now(UTC) - timedelta(minutes=1)))


def test_custom_and_canonical_hunts_are_both_valid(db):
    leader = make_user(db, username="canonical_hunt_leader", guild_name="Bald Dwarfs", guild_rank="Leader")
    verified_character(db, leader, "Canonical Hunt Leader", guild_rank="Leader")
    zone = canonical_zone(db)

    custom = GuildHuntPlannerService.create(db, leader, "Bald Dwarfs", values())
    canonical = GuildHuntPlannerService.create(
        db, leader, "Bald Dwarfs", values(hunting_zone_id=zone.uuid),
    )

    assert custom.hunting_zone_id is None
    assert canonical.hunting_zone_id == zone.uuid
    assert canonical.location == "Roshamuul"
    assert canonical.target == "Guild experience hunt"
    audit = db.query(WorkspaceAudit).filter_by(target_id=str(canonical.id), action="guild_hunt_created").one()
    assert audit.safe_metadata["hunting_zone"] == {
        "canonical_id": str(zone.uuid), "name": "Planner Grounds",
    }


def test_canonical_zone_validation_rejects_wrong_missing_and_noncurrent_entities(db):
    leader = make_user(db, username="canonical_validation_leader", guild_name="Bald Dwarfs", guild_rank="Leader")
    verified_character(db, leader, "Canonical Validation Leader", guild_rank="Leader")
    creature = canonical_zone(db, name="Not a Zone", entity_type="creature")
    retired = canonical_zone(db, name="Retired Grounds", status="retired")

    with pytest.raises(GuildHuntError, match="not a Hunting Zone"):
        GuildHuntPlannerService.create(db, leader, "Bald Dwarfs", values(hunting_zone_id=creature.uuid))
    with pytest.raises(GuildHuntError, match="not current"):
        GuildHuntPlannerService.create(db, leader, "Bald Dwarfs", values(hunting_zone_id=retired.uuid))
    with pytest.raises(GuildHuntError, match="does not exist"):
        GuildHuntPlannerService.create(
            db,
            leader,
            "Bald Dwarfs",
            values(hunting_zone_id=UUID("00000000-0000-0000-0000-000000000001")),
        )


def test_canonical_zone_edit_transitions_preserve_hunt_state_and_people(db):
    leader = make_user(db, username="zone_edit_leader", guild_name="Bald Dwarfs", guild_rank="Leader")
    verified_character(db, leader, "Zone Edit Leader", guild_rank="Leader")
    member = make_user(db, username="zone_edit_member", guild_name="Bald Dwarfs")
    verified_character(db, member, "Zone Edit Knight")
    first = canonical_zone(db, name="First Grounds")
    second = canonical_zone(db, name="Second Grounds")
    hunt = GuildHuntPlannerService.create(db, leader, "Bald Dwarfs", values())
    participant = GuildHuntPlannerService.join(db, member, hunt)

    GuildHuntPlannerService.update(db, leader, hunt, {"hunting_zone_id": first.uuid})
    assert hunt.hunting_zone_id == first.uuid
    GuildHuntPlannerService.update(db, leader, hunt, {"hunting_zone_id": second.uuid})
    assert hunt.hunting_zone_id == second.uuid
    GuildHuntPlannerService.update(db, leader, hunt, {"hunting_zone_id": None})

    assert hunt.hunting_zone_id is None
    assert hunt.status == "scheduled"
    assert hunt.participants == [participant]
    assert participant.attendance_status == "registered"
    audits = db.query(WorkspaceAudit).filter_by(target_id=str(hunt.id), action="guild_hunt_updated").all()
    assert audits[-1].safe_metadata["hunting_zone_change"]["from"]["name"] == "Second Grounds"
    assert audits[-1].safe_metadata["hunting_zone_change"]["to"] is None


def test_zone_summary_is_lightweight_batched_and_retired_links_remain_readable(db):
    leader = make_user(db, username="zone_summary_leader", guild_name="Bald Dwarfs", guild_rank="Leader")
    verified_character(db, leader, "Zone Summary Leader", guild_rank="Leader")
    zone = canonical_zone(db, name="Summary Grounds")
    other_zone = canonical_zone(db, name="Other Summary Grounds")
    hunts = [
        GuildHuntPlannerService.create(db, leader, "Bald Dwarfs", values(hunting_zone_id=zone.uuid)),
        GuildHuntPlannerService.create(db, leader, "Bald Dwarfs", values(hunting_zone_id=other_zone.uuid)),
    ]
    db.flush()
    statements = []

    def count_statement(*args):
        statements.append(args[2])

    event.listen(db.bind, "before_cursor_execute", count_statement)
    try:
        GuildHuntPlannerService.zone_summaries(db, hunts[:1])
        one_zone_count = len(statements)
        statements.clear()
        summaries = GuildHuntPlannerService.zone_summaries(db, hunts)
    finally:
        event.remove(db.bind, "before_cursor_execute", count_statement)

    assert len(summaries) == 2
    summary = summaries[zone.uuid]
    assert summary["name"] == "Summary Grounds"
    assert summary["min_level"] == 250
    assert summary["media_url"] is None
    assert len(statements) == one_zone_count
    assert len(statements) < 20

    zone.status = "retired"
    retired = GuildHuntPlannerService.zone_summaries(db, [hunts[0]])[zone.uuid]
    assert retired["is_current"] is False


def test_legacy_hunt_zone_is_never_promoted_by_planner(db):
    leader = make_user(db, username="legacy_zone_leader", guild_name="Bald Dwarfs", guild_rank="Leader")
    verified_character(db, leader, "Legacy Zone Leader", guild_rank="Leader")
    legacy = HuntZone(name="Legacy Free Text", normalized_name="legacy free text")
    db.add(legacy)
    db.flush()

    hunt = GuildHuntPlannerService.create(
        db,
        leader,
        "Bald Dwarfs",
        values(location=legacy.name, target=legacy.name),
    )

    assert hunt.hunting_zone_id is None
    assert legacy.knowledge_entity_id is None


def test_planner_api_validates_and_projects_canonical_zone(client, db):
    leader = make_user(db, username="planner_api_leader", guild_name="Bald Dwarfs", guild_rank="Leader")
    verified_character(db, leader, "Planner API Leader", guild_rank="Leader")
    zone = canonical_zone(db, name="API Grounds")
    headers = {"Authorization": f"Bearer {create_access_token(leader.username)}"}
    payload = values(hunting_zone_id=str(zone.uuid))
    payload["scheduled_at"] = payload["scheduled_at"].isoformat()
    payload["guild_name"] = "Bald Dwarfs"

    created = client.post("/api/v1/hunts/planner", json=payload, headers=headers)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["hunting_zone_id"] == str(zone.uuid)
    assert body["hunting_zone_summary"]["canonical_id"] == str(zone.uuid)
    assert body["hunting_zone_summary"]["name"] == "API Grounds"

    listed = client.get("/api/v1/hunts/planner?guild_name=Bald%20Dwarfs", headers=headers)
    assert listed.status_code == 200
    assert listed.json()[0]["hunting_zone_summary"]["name"] == "API Grounds"

def test_canonical_picker_query_excludes_legacy_and_retired_zones(client, db):
    current = canonical_zone(db, name="Picker Current")
    canonical_zone(db, name="Picker Retired", status="retired")
    db.add(HuntZone(name="Picker Legacy", normalized_name="picker legacy"))
    db.flush()

    response = client.get("/api/v1/hunt-zones/?canonical_only=true&search=Picker&limit=20")

    assert response.status_code == 200, response.text
    rows = response.json()
    assert [row["canonical_id"] for row in rows] == [str(current.uuid)]
    assert [row["name"] for row in rows] == ["Picker Current"]


def test_planner_summary_projects_canonical_creature_access_and_map_context(db):
    knowledge_registries(db)
    leader = make_user(db, username="rich_summary_leader", guild_name="Bald Dwarfs", guild_rank="Leader")
    verified_character(db, leader, "Rich Summary Leader", guild_rank="Leader")
    zone_entity = canonical_zone(db, name="Rich Planner Grounds")
    zone = db.query(HuntZone).filter_by(knowledge_entity_id=zone_entity.uuid).one()
    zone.region = "North of Thais"
    creature_entity = canonical_zone(db, name="Planner Tyrant", entity_type="boss")
    quest_entity = canonical_zone(db, name="Planner Passage", entity_type="quest")
    creature = Creature(
        name="Planner Tyrant",
        normalized_name="planner tyrant",
        slug="planner-tyrant",
        knowledge_entity_id=creature_entity.uuid,
        is_boss=True,
    )
    quest = TibiaWikiQuest(
        name="Planner Passage",
        normalized_name="planner passage",
        slug="planner-passage",
        knowledge_entity_id=quest_entity.uuid,
        source_name="tibiawiki",
        is_group=False,
    )
    floor = WorldMapFloor(
        provider="tibiamaps/tibia-map-data",
        upstream_commit="f" * 40,
        upstream_url="https://github.com/tibiamaps/tibia-map-data",
        license_name="MIT",
        attribution="test fixture",
        floor=7,
        map_path="/tmp/planner-floor-7.png",
        map_sha256="e" * 64,
        width=2560,
        height=2048,
        min_x=31744,
        min_y=30976,
        max_x=34304,
        max_y=33024,
        source_metadata={},
        is_current=True,
    )
    db.add_all([creature, quest, floor])
    db.flush()
    db.add(WorldMapMarker(
        floor_id=floor.id,
        source_index=17,
        description=zone.name,
        normalized_description=zone.normalized_name,
        icon="star",
        x=32300,
        y=31800,
        floor=7,
        raw_data={},
        resolved_entity_id=zone_entity.uuid,
        resolution_state="resolved",
        resolution_method="exact_canonical_name_or_alias",
    ))
    KnowledgeGraphService.upsert(db, RelationshipInput(
        source_entity_id=zone_entity.uuid,
        relationship_type="has_creature",
        target_entity_id=creature_entity.uuid,
        source_provider_id="tibiawiki",
    ))
    KnowledgeGraphService.upsert(db, RelationshipInput(
        source_entity_id=zone_entity.uuid,
        relationship_type="requires_hunt_quest",
        target_entity_id=quest_entity.uuid,
        source_provider_id="tibiawiki",
    ))
    hunt = GuildHuntPlannerService.create(
        db, leader, "Bald Dwarfs", values(hunting_zone_id=zone_entity.uuid),
    )

    summary = GuildHuntPlannerService.zone_summaries(db, [hunt])[zone_entity.uuid]

    assert summary["region"] == "North of Thais"
    assert summary["creature_count"] == 1
    assert summary["boss_count"] == 1
    assert summary["creature_preview"][0]["name"] == "Planner Tyrant"
    assert summary["access_required"] is True
    assert summary["access_quests"][0]["name"] == "Planner Passage"
    assert summary["map_available"] is True
    assert summary["map_floor"] == 7
