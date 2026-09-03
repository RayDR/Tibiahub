from __future__ import annotations

from app.knowledge.models import (
    KnowledgeEntity,
    KnowledgeEntityAlias,
    KnowledgeExternalMapping,
)
from app.knowledge.registry import EntityTypeRegistry, ProviderRegistry, RelationshipTypeRegistry
from app.knowledge.services import KnowledgeGraphService, RelationshipInput
from app.models import Creature, HuntZone, SpawnLocation
from app.models.external_data import TibiaWikiQuest
from app.models.world_map import WorldMapFloor, WorldMapMarker
from app.services.hunt_zone_projection_service import HuntZoneProjectionService


def _registries(db) -> None:
    EntityTypeRegistry.register_initial(db)
    ProviderRegistry.register_initial(db)
    RelationshipTypeRegistry.register_initial(db)
    db.flush()


def _entity(db, entity_type: str, name: str) -> KnowledgeEntity:
    row = KnowledgeEntity(
        entity_type=entity_type,
        canonical_name=name,
        slug=name.casefold().replace(" ", "-"),
        language_neutral_id=f"projection-test:{entity_type}:{name}",
    )
    db.add(row)
    db.flush()
    return row


def _floor(db, floor: int) -> WorldMapFloor:
    row = WorldMapFloor(
        provider="tibiamaps/tibia-map-data",
        upstream_commit="3" * 40,
        upstream_url="https://github.com/tibiamaps/tibia-map-data",
        license_name="MIT",
        attribution="test fixture",
        floor=floor,
        map_path=f"/tmp/floor-{floor}.png",
        map_sha256="4" * 64,
        width=2560,
        height=2048,
        min_x=31744,
        min_y=30976,
        max_x=34304,
        max_y=33024,
        source_metadata={},
        is_current=True,
    )
    db.add(row)
    db.flush()
    return row


def test_canonical_list_detail_projection_deduplicates_and_preserves_evidence(client, db):
    _registries(db)
    zone_entity = _entity(db, "hunt_zone", "Canonical Grounds")
    creature_entity = _entity(db, "boss", "Projection Tyrant")
    required_quest_entity = _entity(db, "quest", "Required Passage")
    unlock_quest_entity = _entity(db, "quest", "Access Passage")
    access_entity = _entity(db, "access", "Grounds Gate")
    db.add(KnowledgeEntityAlias(
        entity_uuid=zone_entity.uuid,
        entity_type="hunt_zone",
        alias="The Canonical Grounds",
        normalized_alias="the canonical grounds",
    ))
    db.add(KnowledgeExternalMapping(
        provider_id="tibiawiki",
        entity_type_id="hunt_zone",
        external_id="zone-4242",
        entity_uuid=zone_entity.uuid,
        provider_metadata={},
    ))
    zone = HuntZone(
        name="Canonical Grounds",
        normalized_name="canonical grounds",
        slug="canonical-grounds",
        knowledge_entity_id=zone_entity.uuid,
        min_level=250,
        avg_exp_hour=None,
        avg_profit_hour=None,
        supplied_fields=["creatures", "access_quests", "image_reference"],
        source_provider="tibiawiki",
        source_name="tibiawiki",
        map_image_url="https://example.invalid/canonical-grounds.png",
    )
    creature = Creature(
        name="Projection Tyrant",
        normalized_name="projection tyrant",
        slug="projection-tyrant",
        knowledge_entity_id=creature_entity.uuid,
        is_boss=True,
        hitpoints=5000,
        experience=1200,
        source_name="tibiawiki",
    )
    required_quest = TibiaWikiQuest(
        name="Required Passage",
        normalized_name="required passage",
        slug="required-passage",
        knowledge_entity_id=required_quest_entity.uuid,
        source_name="tibiawiki",
        is_group=False,
    )
    unlock_quest = TibiaWikiQuest(
        name="Access Passage",
        normalized_name="access passage",
        slug="access-passage",
        knowledge_entity_id=unlock_quest_entity.uuid,
        source_name="tibiawiki",
        is_group=False,
    )
    db.add_all([zone, creature, required_quest, unlock_quest])
    db.flush()
    db.add(SpawnLocation(
        creature_id=creature.id,
        hunt_zone_id=zone.id,
        quantity="One",
        notes="Legacy evidence",
    ))
    floor = _floor(db, 10)
    db.add(WorldMapMarker(
        floor_id=floor.id,
        source_index=1,
        description="Canonical Grounds",
        normalized_description="canonical grounds",
        icon="star",
        x=34000,
        y=31700,
        floor=10,
        raw_data={},
        resolved_entity_id=zone_entity.uuid,
        resolution_state="resolved",
        resolution_method="exact_canonical_name_or_alias",
    ))
    for relationship in (
        RelationshipInput(
            source_entity_id=zone_entity.uuid,
            relationship_type="has_creature",
            target_entity_id=creature_entity.uuid,
            source_provider_id="tibiawiki",
        ),
        RelationshipInput(
            source_entity_id=creature_entity.uuid,
            relationship_type="appears_in",
            target_entity_id=zone_entity.uuid,
            source_provider_id="tibiamaps",
        ),
        RelationshipInput(
            source_entity_id=zone_entity.uuid,
            relationship_type="has_creature",
            target_entity_type="creature",
            unresolved_name="Unresolved Horror",
            resolution_state="unresolved",
            confidence="medium",
            source_provider_id="tibiawiki",
        ),
        RelationshipInput(
            source_entity_id=zone_entity.uuid,
            relationship_type="requires_hunt_quest",
            target_entity_id=required_quest_entity.uuid,
            source_provider_id="tibiawiki",
        ),
        RelationshipInput(
            source_entity_id=zone_entity.uuid,
            relationship_type="requires_hunt_quest",
            target_entity_type="quest",
            unresolved_name="Unknown Passage",
            resolution_state="unresolved",
            confidence="medium",
            source_provider_id="tibiawiki",
        ),
        RelationshipInput(
            source_entity_id=zone_entity.uuid,
            relationship_type="requires_access",
            target_entity_id=access_entity.uuid,
            source_provider_id="tibiawiki",
        ),
        RelationshipInput(
            source_entity_id=unlock_quest_entity.uuid,
            relationship_type="unlocks_access",
            target_entity_id=access_entity.uuid,
            source_provider_id="tibiawiki",
        ),
        RelationshipInput(
            source_entity_id=zone_entity.uuid,
            relationship_type="located_at",
            target_entity_type="location",
            unresolved_name="Unknown Cavern",
            resolution_state="unresolved",
            confidence="low",
            source_provider_id="tibiawiki",
        ),
    ):
        KnowledgeGraphService.upsert(db, relationship)
    db.commit()

    entity_count = db.query(KnowledgeEntity).count()
    response = client.get("/api/v1/hunt-zones/", params={"search": "The Canonical Grounds"})
    assert response.status_code == 200
    assert db.query(KnowledgeEntity).count() == entity_count
    listed = response.json()[0]
    assert listed["canonical_id"] == str(zone_entity.uuid)
    assert listed["identity_state"] == "canonical"
    assert listed["spatial_state"] == "resolved_point"
    assert listed["spatial"]["geometry_source"] == "tibiamaps_marker"
    assert (listed["spatial"]["x"], listed["spatial"]["y"], listed["spatial"]["z"]) == (34000, 31700, 10)
    assert listed["creature_count"] == 1
    assert listed["boss_count"] == 1
    assert listed["raw_creature_experience"] == 1200
    assert listed["creature_preview"][0]["sources"] == ["canonical_graph", "legacy_spawn"]
    assert "creatures" not in listed and "creature_spawns" not in listed and "access" not in listed
    assert listed["avg_exp_hour"] is None and listed["avg_profit_hour"] is None

    detail_response = client.get("/api/v1/hunt-zones/the-canonical-grounds")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["canonical_identity"] == {
        "canonical_id": str(zone_entity.uuid),
        "domain_id": zone.id,
        "aliases": ["The Canonical Grounds"],
        "provider_mappings": [{"provider": "tibiawiki", "external_id": "zone-4242"}],
    }
    assert len(detail["creatures"]) == 1 and len(detail["creature_spawns"]) == 1
    assert detail["creatures"][0]["relationship_types"] == ["appears_in", "has_creature"]
    assert detail["unresolved_creatures"][0]["name"] == "Unresolved Horror"
    quest_types = {value["name"]: value["requirement_type"] for value in detail["access"]["quests"]}
    assert quest_types == {"Required Passage": "required_for_access", "Access Passage": "unlocks_access"}
    assert detail["access"]["unresolved_quests"][0]["name"] == "Unknown Passage"
    assert detail["unresolved_locations"][0]["name"] == "Unknown Cavern"

    missing = client.get("/api/v1/hunt-zones/canonical-ground")
    assert missing.status_code == 404
    assert db.query(KnowledgeEntity).count() == entity_count


def test_bounds_knowledge_only_and_legacy_unknowns_are_honest(db):
    floor = _floor(db, 8)
    bounded = HuntZone(
        name="Bounded Grounds",
        normalized_name="bounded grounds",
        slug="bounded-grounds",
        map_z=8,
        map_bounds={"min_x": 32000, "min_y": 31500, "max_x": 32200, "max_y": 31700},
    )
    knowledge_only = HuntZone(
        name="Knowledge Grounds",
        normalized_name="knowledge grounds",
        slug="knowledge-grounds",
    )
    placeholder = HuntZone(
        name="Recovered Placeholder",
        normalized_name="recovered placeholder",
        slug="recovered-placeholder",
        source_provider="tibiamaps",
        source_name="tibiawiki",
        min_level=0,
        avg_exp_hour=0,
        avg_profit_hour=0,
        knights_recommended=False,
        paladins_recommended=False,
        sorcerers_recommended=False,
        druids_recommended=False,
        monks_recommended=False,
        requires_quest=False,
        requires_premium=False,
        map_z=8,
        map_bounds={"min_x": 31744, "min_y": 30976, "max_x": 34304, "max_y": 33024},
        map_image_url="https://example.invalid/floor-08-map.png",
        raw_data={"source_provider": "tibiamaps", "tibiamaps_marker_count": 5000},
    )
    db.add_all([bounded, knowledge_only, placeholder])
    db.flush()

    values = {
        item["name"]: item
        for item in HuntZoneProjectionService.project(
            db,
            [bounded, knowledge_only, placeholder],
            detail=True,
        )
    }
    assert floor.is_current is True
    assert values["Bounded Grounds"]["spatial_state"] == "resolved_bounds"
    assert values["Bounded Grounds"]["spatial"]["z"] == 8
    assert values["Knowledge Grounds"]["spatial_state"] == "knowledge_only"
    assert values["Knowledge Grounds"]["spatial"]["x"] is None
    recovered = values["Recovered Placeholder"]
    assert recovered["spatial_state"] == "knowledge_only"
    assert recovered["spatial"]["bounds"] is None
    assert recovered["min_level"] is None
    assert recovered["avg_exp_hour"] is None and recovered["avg_profit_hour"] is None
    assert recovered["knights_recommended"] is None
    assert recovered["requires_quest"] is None and recovered["requires_premium"] is None
    assert recovered["representative_media"]["status"] == "missing"
