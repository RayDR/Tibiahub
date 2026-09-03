from __future__ import annotations

from app.knowledge.models import KnowledgeEntity, KnowledgeEntityType, KnowledgeRelationship
from app.knowledge.services.graph import KnowledgeGraphService, RelationshipInput
from app.models import Creature, HuntZone
from app.models.external_data import TibiaWikiLocation, TibiaWikiNpc, TibiaWikiQuest
from app.models.world_map import WorldMapFloor, WorldMapMarker


def _entity(db, entity_type: str, name: str) -> KnowledgeEntity:
    if db.get(KnowledgeEntityType, entity_type) is None:
        db.add(KnowledgeEntityType(entity_type=entity_type, display_name=entity_type.title()))
        db.flush()
    entity = KnowledgeEntity(
        entity_type=entity_type,
        canonical_name=name,
        slug=name.lower().replace(" ", "-"),
        language_neutral_id=f"map-test:{entity_type}:{name}",
    )
    db.add(entity)
    db.flush()
    return entity


def _floor(db, floor: int = 7) -> WorldMapFloor:
    row = WorldMapFloor(
        provider="tibiamaps/tibia-map-data",
        upstream_commit="a" * 40,
        upstream_url="https://github.com/tibiamaps/tibia-map-data",
        license_name="MIT",
        attribution="fixture",
        floor=floor,
        map_path=f"/tmp/map-floor-{floor}.png",
        map_sha256=str(floor) * 64,
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


def _marker(db, floor: WorldMapFloor, entity: KnowledgeEntity, name: str, x: int, y: int, index: int):
    row = WorldMapMarker(
        floor_id=floor.id,
        source_index=index,
        description=name,
        normalized_description=name.lower(),
        x=x,
        y=y,
        floor=floor.floor,
        raw_data={},
        resolved_entity_id=entity.uuid,
        resolution_state="resolved",
        resolution_method="exact_canonical_name_or_alias",
    )
    db.add(row)
    return row


def test_map_result_contract_distinguishes_point_area_knowledge_and_unresolved(client, db):
    floor = _floor(db)
    point_entity = _entity(db, "creature", "Point Beast")
    area_entity = _entity(db, "hunt_zone", "Area Grounds")
    known_entity = _entity(db, "creature", "Known Beast")
    unresolved_entity = _entity(db, "creature", "Unresolved Beast")
    db.add_all([
        Creature(name="Point Beast", normalized_name="point beast", slug="point-beast", is_hidden=False, knowledge_entity_id=point_entity.uuid),
        Creature(name="Known Beast", normalized_name="known beast", slug="known-beast", is_hidden=False, knowledge_entity_id=known_entity.uuid),
        Creature(name="Unresolved Beast", normalized_name="unresolved beast", slug="unresolved-beast", is_hidden=False, knowledge_entity_id=unresolved_entity.uuid),
        HuntZone(name="Area Grounds", normalized_name="area grounds", slug="area-grounds", knowledge_entity_id=area_entity.uuid,
                 map_bounds={"min_x": 32100, "min_y": 32000, "max_x": 32200, "max_y": 32100}),
        HuntZone(name="Legacy Text Grounds", normalized_name="legacy text grounds", slug="legacy-text-grounds"),
    ])
    _marker(db, floor, point_entity, "Point Beast", 32110, 32010, 1)
    _marker(db, floor, area_entity, "Area Grounds", 32150, 32050, 2)
    KnowledgeGraphService.upsert(db, RelationshipInput(
        source_entity_id=unresolved_entity.uuid,
        relationship_type="appears_in",
        target_entity_type="hunt_zone",
        unresolved_name="Unknown Grounds",
        resolution_state="unresolved",
        source_provider_id="tibiawiki",
    ))
    db.flush()
    before = db.query(KnowledgeEntity).count(), db.query(KnowledgeRelationship).count()

    def result(name: str, layer: str):
        response = client.get("/api/v1/map/search", params={"q": name, "layers": layer})
        assert response.status_code == 200
        return response.json()["items"][0]

    point = result("Point Beast", "creature")
    area = result("Area Grounds", "hunt_zone")
    known = result("Known Beast", "creature")
    unresolved = result("Unresolved Beast", "creature")
    assert point["canonical_entity_id"] == str(point_entity.uuid)
    assert point["spatial_state"] == "resolved_point" and point["navigation_url"] == "/creatures/point-beast"
    assert area["spatial_state"] == "resolved_area" and area["bounds"]["min_x"] == 32100
    assert known["spatial_state"] == "knowledge_only" and known["spatial_evidence"] == []
    assert unresolved["spatial_state"] == "unresolved" and unresolved["x"] is None
    assert client.get("/api/v1/map/search", params={"q": "Legacy Text", "layers": "hunt_zone"}).json()["items"] == []
    assert before == (db.query(KnowledgeEntity).count(), db.query(KnowledgeRelationship).count())


def test_independent_layers_preserve_multi_target_roles_and_floor_filter(client, db):
    floor_seven = _floor(db, 7)
    floor_eight = _floor(db, 8)
    first_location = _entity(db, "location", "First Place")
    second_location = _entity(db, "location", "Second Place")
    npc_entity = _entity(db, "npc", "Trusted Guide")
    text_npc_entity = _entity(db, "npc", "Text Only Guide")
    quest_entity = _entity(db, "quest", "Many Places Quest")
    creature_entity = _entity(db, "creature", "Many Places Beast")
    boss_entity = _entity(db, "creature", "Trusted Boss")
    db.add_all([
        TibiaWikiLocation(name="First Place", normalized_name="first place", slug="first-place", external_id="loc:1", source_name="tibiawiki", knowledge_entity_id=first_location.uuid),
        TibiaWikiLocation(name="Second Place", normalized_name="second place", slug="second-place", external_id="loc:2", source_name="tibiawiki", knowledge_entity_id=second_location.uuid),
        TibiaWikiNpc(name="Trusted Guide", normalized_name="trusted guide", slug="trusted-guide", external_id="npc:1", source_name="tibiawiki", location_name="First Place", knowledge_entity_id=npc_entity.uuid),
        TibiaWikiNpc(name="Text Only Guide", normalized_name="text only guide", slug="text-only-guide", external_id="npc:2", source_name="tibiawiki", location_name="Somewhere nearby", knowledge_entity_id=text_npc_entity.uuid),
        TibiaWikiQuest(name="Many Places Quest", normalized_name="many places quest", slug="many-places-quest", external_id="quest:1", source_name="tibiawiki", is_group=False, knowledge_entity_id=quest_entity.uuid),
        Creature(name="Many Places Beast", normalized_name="many places beast", slug="many-places-beast", is_hidden=False, is_boss=False, knowledge_entity_id=creature_entity.uuid),
        Creature(name="Trusted Boss", normalized_name="trusted boss", slug="trusted-boss", is_hidden=False, is_boss=True, knowledge_entity_id=boss_entity.uuid),
    ])
    _marker(db, floor_seven, first_location, "First Place", 32100, 32000, 1)
    _marker(db, floor_eight, second_location, "Second Place", 32200, 32100, 2)
    _marker(db, floor_seven, creature_entity, "Many Places Beast", 32110, 32010, 3)
    _marker(db, floor_eight, creature_entity, "Many Places Beast", 32210, 32110, 4)
    _marker(db, floor_seven, boss_entity, "Trusted Boss", 32120, 32020, 5)
    for relationship in (
        RelationshipInput(source_entity_id=npc_entity.uuid, relationship_type="located_at", target_entity_id=first_location.uuid, source_provider_id="tibiawiki"),
        RelationshipInput(source_entity_id=quest_entity.uuid, relationship_type="occurs_at_location", target_entity_id=first_location.uuid, source_provider_id="tibiawiki"),
        RelationshipInput(source_entity_id=quest_entity.uuid, relationship_type="mission_occurs_at_location", target_entity_id=second_location.uuid, source_provider_id="tibiawiki"),
    ):
        KnowledgeGraphService.upsert(db, relationship)
    db.flush()

    locations = client.get("/api/v1/map/layers/location").json()
    npcs = client.get("/api/v1/map/layers/npc").json()
    quests = client.get("/api/v1/map/layers/quest").json()
    creatures = client.get("/api/v1/map/layers/creature").json()
    bosses = client.get("/api/v1/map/layers/boss").json()
    floor_eight_creatures = client.get("/api/v1/map/layers/creature", params={"floor": 8}).json()
    assert locations["total"] == 2 and {row["name"] for row in locations["items"]} == {"First Place", "Second Place"}
    assert npcs["items"][0]["spatial_evidence"][0]["role"] == "location"
    text_only = client.get("/api/v1/map/search", params={"q": "Text Only Guide", "layers": "npc"}).json()["items"][0]
    assert text_only["spatial_state"] == "knowledge_only" and text_only["subtitle"] == "Somewhere nearby"
    assert {evidence["role"] for evidence in quests["items"][0]["spatial_evidence"]} == {"location", "mission"}
    assert len(creatures["items"][0]["spatial_evidence"]) == 2
    assert bosses["items"][0]["entity_type"] == "boss"
    assert floor_eight_creatures["total"] == 1 and floor_eight_creatures["items"][0]["z"] == 8
    assert client.get("/api/v1/map/layers/item").status_code == 422


def test_bootstrap_uses_small_authoritative_location_set(client, db):
    floor = _floor(db, 9)
    edron = _entity(db, "location", "Edron")
    unmapped = _entity(db, "location", "Text Only Place")
    db.add_all([
        TibiaWikiLocation(name="Edron", normalized_name="edron", slug="edron", external_id="loc:edron", source_name="tibiawiki", knowledge_entity_id=edron.uuid),
        TibiaWikiLocation(name="Text Only Place", normalized_name="text only place", slug="text-only-place", external_id="loc:text", source_name="tibiawiki", knowledge_entity_id=unmapped.uuid),
    ])
    _marker(db, floor, edron, "Edron", 32830, 31797, 1)
    db.flush()

    response = client.get("/api/v1/map/bootstrap", params={"floor": 9})
    assert response.status_code == 200
    defaults = response.json()["default_results"]
    assert [row["name"] for row in defaults] == ["Edron"]
    assert defaults[0]["canonical_entity_id"] == str(edron.uuid)
    assert defaults[0]["spatial_state"] == "resolved_point"
