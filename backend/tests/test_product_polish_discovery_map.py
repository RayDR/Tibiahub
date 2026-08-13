from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.knowledge.models.core import KnowledgeEntity, KnowledgeEntityType
from app.models.creature import Creature
from app.models.entity_metadata import EntityMetadata
from app.models.external_data import Item, TibiaWikiQuest
from app.models.hunt_zone import HuntZone
from app.models.media_asset import MediaAsset
from app.models.spawn_location import SpawnLocation
from app.models.world_map import WorldMapFloor, WorldMapMarker


def _entity(db, kind: str, name: str) -> KnowledgeEntity:
    entity_type = db.get(KnowledgeEntityType, kind)
    if entity_type is None:
        entity_type = KnowledgeEntityType(entity_type=kind, display_name=kind.title())
        db.add(entity_type)
        db.flush()
    entity = KnowledgeEntity(
        entity_type=kind,
        canonical_name=name,
        slug=name.lower().replace(" ", "-"),
        language_neutral_id=f"test:{kind}:{name}",
    )
    db.add(entity)
    db.flush()
    return entity


def test_popular_loot_uses_real_local_activity_order(client, db):
    first_entity = _entity(db, "test-item", "First Relic")
    second_entity = _entity(db, "test-item", "Second Relic")
    first = Item(name="First Relic", normalized_name="first relic", slug="first-relic", knowledge_entity_id=first_entity.uuid)
    second = Item(name="Second Relic", normalized_name="second relic", slug="second-relic", knowledge_entity_id=second_entity.uuid)
    db.add_all([first, second])
    db.flush()
    db.add_all([
        EntityMetadata(entity_type="item", entity_key="first relic", display_name=first.name, entity_id=first.id, search_count=2, last_viewed_at=datetime.now(UTC)),
        EntityMetadata(entity_type="item", entity_key="second relic", display_name=second.name, entity_id=second.id, search_count=9, last_viewed_at=datetime.now(UTC) - timedelta(days=1)),
    ])
    db.flush()

    response = client.get("/api/v1/items/popular", params={"limit": 2})
    assert response.status_code == 200
    assert [row["slug"] for row in response.json()] == ["second-relic", "first-relic"]

    trending = client.get("/api/v1/items/trending", params={"limit": 2})
    assert trending.status_code == 200
    assert [row["slug"] for row in trending.json()] == ["first-relic", "second-relic"]


def test_quest_shelves_are_local_and_activity_ranked(client, db):
    first = TibiaWikiQuest(name="Ancient Path", normalized_name="ancient path", slug="ancient-path", is_group=False)
    second = TibiaWikiQuest(name="Fresh Path", normalized_name="fresh path", slug="fresh-path", is_group=False)
    db.add_all([first, second])
    db.flush()
    db.add_all([
        EntityMetadata(entity_type="quest", entity_key="ancient path", display_name=first.name, entity_id=first.id, search_count=12),
        EntityMetadata(entity_type="quest", entity_key="fresh path", display_name=second.name, entity_id=second.id, search_count=3),
    ])
    db.flush()

    popular = client.get("/api/v1/quests/popular", params={"limit": 2})
    assert popular.status_code == 200
    assert [row["slug"] for row in popular.json()] == ["ancient-path", "fresh-path"]


def test_public_map_returns_real_zone_geometry_and_honest_related_context(client, db):
    asset = MediaAsset(asset_key="zone:mapped-grounds", status="cached", local_path="/tmp/not-read-by-bootstrap.png")
    zone_entity = _entity(db, "hunt_zone", "Mapped Grounds")
    zone = HuntZone(
        name="Mapped Grounds", slug="mapped-grounds", normalized_name="mapped grounds", min_level=80,
        location_x=120, location_y=220, location_z=7,
        map_bounds={"min_x": 100, "min_y": 200, "max_x": 300, "max_y": 400},
        map_asset_id=None,
        knowledge_entity_id=zone_entity.uuid,
    )
    creature = Creature(name="Ground Walker", slug="ground-walker", normalized_name="ground walker", hitpoints=100, experience=100, is_hidden=False)
    floor = WorldMapFloor(
        provider="tibiamaps/tibia-map-data", upstream_commit="a" * 40,
        upstream_url="https://github.com/tibiamaps/tibia-map-data", license_name="MIT", attribution="fixture",
        floor=7, map_path="/tmp/floor-07-map.png", pathfinding_path="/tmp/floor-07-path.png",
        map_sha256="b" * 64, pathfinding_sha256="c" * 64, width=2560, height=2048,
        min_x=31744, min_y=30976, max_x=34304, max_y=33024, source_metadata={}, is_current=True,
    )
    db.add_all([asset, zone, creature, floor])
    db.flush()
    db.add(WorldMapMarker(
        floor_id=floor.id, source_index=1, description="Mapped Grounds",
        normalized_description="mapped grounds", icon="star", x=32120, y=32220,
        floor=7, raw_data={}, resolved_entity_id=zone_entity.uuid,
        resolution_state="resolved", resolution_method="exact_canonical_name_or_alias",
    ))
    zone.map_asset_id = asset.id
    db.add(SpawnLocation(creature_id=creature.id, hunt_zone_id=zone.id))
    db.flush()

    bootstrap = client.get("/api/v1/map/bootstrap")
    assert bootstrap.status_code == 200
    assert bootstrap.json()["world_map"]["image_url"] == "/api/v1/map/floors/7/image"
    assert bootstrap.json()["world_map"]["upstream_commit"] == "a" * 40
    search = client.get("/api/v1/map/search", params={"q": "Ground Walker", "layers": "creature"})
    assert search.status_code == 200
    result = search.json()["items"][0]
    assert result["name"] == "Ground Walker"
    assert result["geometry_status"] == "knowledge_only"
    context = client.get("/api/v1/map/hunt-zones/mapped-grounds/context").json()
    assert context["hunt_zone"]["geometry_source"] == "tibiamaps_marker"
    assert (context["hunt_zone"]["x"], context["hunt_zone"]["y"]) == (32120, 32220)
    assert context["creatures"][0]["geometry_status"] == "knowledge_only"


def test_planner_returns_stored_rates_access_spawns_and_stable_map_links(client, db):
    zone = HuntZone(
        name="Planner Grounds", slug="planner-grounds", normalized_name="planner grounds", min_level=100,
        max_level=180, knights_recommended=True, avg_exp_hour=325000, avg_profit_hour=170000,
        requires_premium=True, requires_quest=False, city="Thais", map_asset_id=77,
        location_x=0, location_y=245, location_z=7,
    )
    creature = Creature(name="Planner Beast", slug="planner-beast", normalized_name="planner beast", hitpoints=500, experience=400, is_hidden=False)
    db.add_all([zone, creature])
    db.flush()
    db.add(SpawnLocation(creature_id=creature.id, hunt_zone_id=zone.id, quantity="Many"))
    db.flush()

    response = client.get("/api/v1/recommendations/solo", params={"vocation": "knight", "level": 120, "goal": "balanced", "limit": 5})
    assert response.status_code == 200
    row = next(value for value in response.json()["recommendations"] if value["zone_id"] == zone.id)
    assert row["avg_exp_hour"] == 325000
    assert row["avg_profit_hour"] == 170000
    assert row["rate_basis"] == "stored_local_average"
    assert row["location_x"] == 0
    assert row["map_image_url"] is None
    assert row["requires_premium"] is True
    assert row["creatures"][0]["slug"] == "planner-beast"
    assert row["creatures"][0]["image_url"].startswith("/api/v1/creatures/")
    assert any("knight" in reason for reason in row["reasons"])

    invalid_party = client.post("/api/v1/recommendations/party", json=[])
    assert invalid_party.status_code == 422


def test_planner_recommendations_are_incrementally_paginated(client, db):
    for index in range(8):
        db.add(HuntZone(name=f"Paged Hunt {index}", slug=f"paged-hunt-{index}", normalized_name=f"paged hunt {index}", min_level=80, max_level=180, knights_recommended=True))
    db.flush()
    first = client.get("/api/v1/recommendations/solo", params={"vocation": "knight", "level": 120, "limit": 3, "skip": 0}).json()
    second = client.get("/api/v1/recommendations/solo", params={"vocation": "knight", "level": 120, "limit": 3, "skip": 3}).json()
    assert len(first["recommendations"]) == 3 and first["has_more"] is True
    assert {row["zone_id"] for row in first["recommendations"]}.isdisjoint({row["zone_id"] for row in second["recommendations"]})


def test_planner_falls_back_to_spawn_profile_when_zone_metadata_is_empty(client, db):
    zone = HuntZone(name="Fallback Grounds", slug="fallback-grounds", normalized_name="fallback grounds", min_level=0)
    creature = Creature(name="Fallback Beast", slug="fallback-beast", normalized_name="fallback beast", hitpoints=1500, experience=1500, is_hidden=False)
    db.add_all([zone, creature])
    db.flush()
    db.add(SpawnLocation(creature_id=creature.id, hunt_zone_id=zone.id))
    db.flush()

    response = client.get("/api/v1/recommendations/solo", params={"vocation": "knight", "level": 100, "goal": "exp", "limit": 50})
    assert response.status_code == 200
    row = next(value for value in response.json()["recommendations"] if value["zone_id"] == zone.id)
    assert row["profile_basis"] == "spawn_profile"
    assert row["suggested_level"] == 100
    assert row["raw_creature_exp"] == 1500
    assert row["level_fit"] == "strong"
    assert row["danger"] == "high"
    assert any("known creature spawns" in reason for reason in row["reasons"])


def test_category_registry_prefers_cached_gif_over_earlier_static_creature(client, db):
    static_asset = MediaAsset(asset_key="creature:static", status="cached", content_type="image/png", local_path="/tmp/static.png")
    gif_asset = MediaAsset(asset_key="creature:animated", status="cached", content_type="image/gif", local_path="/tmp/animated.gif")
    db.add_all([static_asset, gif_asset])
    db.flush()
    static = Creature(name="Static First", slug="static-first", normalized_name="static first", hitpoints=10, experience=10, is_hidden=False, is_boss=False, image_asset_id=static_asset.id)
    animated = Creature(name="Animated Second", slug="animated-second", normalized_name="animated second", hitpoints=10, experience=10, is_hidden=False, is_boss=False, image_asset_id=gif_asset.id)
    db.add_all([static, animated])
    db.flush()

    response = client.get("/api/v1/catalog/category-visuals")
    assert response.status_code == 200
    assert response.json()["creatures"].startswith(f"/api/v1/creatures/{animated.id}/image")
