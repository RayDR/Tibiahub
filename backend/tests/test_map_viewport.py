from __future__ import annotations

import base64
from uuid import uuid4

from app.knowledge.models import KnowledgeEntity, KnowledgeEntityType, SpatialMapPoint, SpatialMapRegion
from app.knowledge.services.graph import KnowledgeGraphService, RelationshipInput
from app.models import Creature
from app.models.external_data import TibiaWikiLocation, TibiaWikiNpc, TibiaWikiQuest
from app.models.media_asset import MediaAsset
from app.models.world_map import WorldMapFloor, WorldMapMarker
from app.services import media_asset_service


def _entity(db, kind: str, name: str) -> KnowledgeEntity:
    if db.get(KnowledgeEntityType, kind) is None:
        db.add(KnowledgeEntityType(entity_type=kind, display_name=kind.title()))
        db.flush()
    row = KnowledgeEntity(
        entity_type=kind, canonical_name=name, slug=name.lower().replace(" ", "-"),
        language_neutral_id=f"viewport:{kind}:{name}",
    )
    db.add(row)
    db.flush()
    return row


def _floor(db, number: int = 7) -> WorldMapFloor:
    row = WorldMapFloor(
        provider="tibiamaps/tibia-map-data", upstream_commit=f"{number:x}" * 40,
        upstream_url="https://github.com/tibiamaps/tibia-map-data", license_name="MIT",
        attribution="fixture", floor=number, map_path=f"/tmp/viewport-{number}.png",
        map_sha256=f"{number:x}" * 64, width=2560, height=2048,
        min_x=31744, min_y=30976, max_x=34304, max_y=33024,
        source_metadata={}, is_current=True,
    )
    db.add(row)
    db.flush()
    return row


def _marker(db, floor, entity, x: int, y: int, index: int, *, state: str = "resolved"):
    db.add(WorldMapMarker(
        floor_id=floor.id, source_index=index, description=entity.canonical_name,
        normalized_description=entity.canonical_name.lower(), x=x, y=y, floor=floor.floor,
        raw_data={}, resolved_entity_id=entity.uuid if state == "resolved" else None,
        resolution_state=state, resolution_method="exact_canonical_name_or_alias" if state == "resolved" else None,
    ))


def _location(db, entity, name: str):
    row = TibiaWikiLocation(
        name=name, normalized_name=name.lower(), slug=name.lower().replace(" ", "-"),
        external_id=f"loc:{name}", source_name="fixture", knowledge_entity_id=entity.uuid,
    )
    db.add(row)
    return row


def _params(**overrides):
    values = {
        "min_x": 32000, "min_y": 31800, "max_x": 32300, "max_y": 32100,
        "floor": 7, "layers": "location,npc,creature,boss,quest,hunt_zone", "zoom": 3,
        "limit": 200,
    }
    values.update(overrides)
    return values


def test_viewport_point_bbox_floor_trust_and_hidden_filters(client, db):
    floor7, floor8 = _floor(db, 7), _floor(db, 8)
    inside = _entity(db, "creature", "Inside Beast")
    outside = _entity(db, "creature", "Outside Beast")
    wrong_floor = _entity(db, "creature", "Upstairs Beast")
    hidden = _entity(db, "creature", "Hidden Beast")
    unresolved = _entity(db, "creature", "Unresolved Beast")
    db.add_all([
        Creature(name="Inside Beast", slug="inside-beast", knowledge_entity_id=inside.uuid, is_hidden=False),
        Creature(name="Outside Beast", slug="outside-beast", knowledge_entity_id=outside.uuid, is_hidden=False),
        Creature(name="Upstairs Beast", slug="upstairs-beast", knowledge_entity_id=wrong_floor.uuid, is_hidden=False),
        Creature(name="Hidden Beast", slug="hidden-beast", knowledge_entity_id=hidden.uuid, is_hidden=True),
        Creature(name="Unresolved Beast", slug="unresolved-beast", knowledge_entity_id=unresolved.uuid, is_hidden=False),
    ])
    _marker(db, floor7, inside, 32100, 31900, 1)
    _marker(db, floor7, outside, 33000, 31900, 2)
    _marker(db, floor8, wrong_floor, 32100, 31900, 3)
    _marker(db, floor7, hidden, 32110, 31910, 4)
    _marker(db, floor7, unresolved, 32120, 31920, 5, state="ambiguous")
    db.flush()

    response = client.get("/api/v1/map/viewport", params=_params(layers="creature"))
    assert response.status_code == 200
    assert [row["name"] for row in response.json()["items"]] == ["Inside Beast"]


def test_viewport_intersecting_regions_only_and_no_legacy_geometry(client, db):
    _floor(db)
    intersecting = _entity(db, "location", "Intersecting Region")
    outside = _entity(db, "location", "Outside Region")
    ambiguous = _entity(db, "location", "Ambiguous Region")
    legacy = _entity(db, "location", "Legacy Text Place")
    for entity in (intersecting, outside, ambiguous, legacy):
        _location(db, entity, entity.canonical_name)
    db.add_all([
        SpatialMapRegion(
            knowledge_entity_id=intersecting.uuid, external_id="region:inside", name="Intersecting Region",
            min_x=31950, min_y=31850, max_x=32050, max_y=31950, min_z=7, max_z=7,
            confidence="high", verification_state="verified", is_current=True,
        ),
        SpatialMapRegion(
            knowledge_entity_id=outside.uuid, external_id="region:outside", name="Outside Region",
            min_x=33000, min_y=31850, max_x=33100, max_y=31950, min_z=7, max_z=7,
            confidence="high", verification_state="verified", is_current=True,
        ),
        SpatialMapRegion(
            knowledge_entity_id=ambiguous.uuid, external_id="region:ambiguous", name="Ambiguous Region",
            min_x=32050, min_y=31850, max_x=32150, max_y=31950, min_z=7, max_z=7,
            confidence="high", verification_state="ambiguous", is_current=True,
        ),
    ])
    db.flush()

    response = client.get("/api/v1/map/viewport", params=_params(layers="location"))
    assert response.status_code == 200
    assert [row["name"] for row in response.json()["items"]] == ["Intersecting Region"]
    assert response.json()["items"][0]["spatial_evidence"][0]["spatial_state"] == "resolved_area"


def test_viewport_layers_multi_location_pagination_and_hard_limit(client, db):
    floor = _floor(db)
    npc_entity = _entity(db, "npc", "Moving Guide")
    creature_entity = _entity(db, "creature", "Layer Beast")
    boss_entity = _entity(db, "creature", "Layer Boss")
    db.add_all([
        TibiaWikiNpc(name="Moving Guide", normalized_name="moving guide", slug="moving-guide", external_id="npc:moving", source_name="fixture", knowledge_entity_id=npc_entity.uuid),
        Creature(name="Layer Beast", slug="layer-beast", knowledge_entity_id=creature_entity.uuid, is_hidden=False, is_boss=False),
        Creature(name="Layer Boss", slug="layer-boss", knowledge_entity_id=boss_entity.uuid, is_hidden=False, is_boss=True),
    ])
    _marker(db, floor, npc_entity, 32050, 31850, 1)
    _marker(db, floor, npc_entity, 32150, 31950, 2)
    _marker(db, floor, creature_entity, 32100, 31900, 3)
    _marker(db, floor, boss_entity, 32200, 32000, 4)
    _marker(db, floor, npc_entity, 32050, 31850, 5)
    db.flush()

    all_rows = client.get("/api/v1/map/viewport", params=_params(layers="npc,creature,boss")).json()["items"]
    assert {row["entity_type"] for row in all_rows} == {"npc", "creature", "boss"}
    assert len(next(row for row in all_rows if row["name"] == "Moving Guide")["spatial_evidence"]) == 2
    first = client.get("/api/v1/map/viewport", params=_params(layers="npc,creature,boss", limit=2)).json()
    second = client.get("/api/v1/map/viewport", params=_params(layers="npc,creature,boss", limit=2, cursor=first["page"]["next_cursor"])).json()
    assert first["page"]["has_more"] is True
    assert {row["id"] for row in first["items"]}.isdisjoint({row["id"] for row in second["items"]})
    repeated = client.get("/api/v1/map/viewport", params=_params(layers="npc,creature,boss", limit=2)).json()
    assert [row["id"] for row in repeated["items"]] == [row["id"] for row in first["items"]]
    assert client.get("/api/v1/map/viewport", params=_params(limit=201)).status_code == 422


def test_viewport_validation_is_strict(client):
    assert client.get("/api/v1/map/viewport", params=_params(min_x=32300, max_x=32000)).status_code == 422
    assert client.get("/api/v1/map/viewport", params=_params(layers="location,item")).status_code == 422
    assert client.get("/api/v1/map/viewport", params=_params(cursor="not-base64!!")).status_code == 422
    assert client.get("/api/v1/map/viewport", params=_params(floor=16)).status_code == 422


def test_viewport_uses_local_media_only_and_is_read_only(client, db, monkeypatch):
    floor = _floor(db)
    entity = _entity(db, "creature", "Local Image Beast")
    asset = MediaAsset(
        asset_key="creature:local_image_beast", source_url="https://provider.invalid/unsafe.gif",
        local_path="media/creature.gif", status="cached",
    )
    creature = Creature(
        name="Local Image Beast", slug="local-image-beast", knowledge_entity_id=entity.uuid,
        is_hidden=False, image_url="https://provider.invalid/unsafe.gif",
    )
    db.add_all([asset, creature])
    db.flush()
    creature.image_asset_id = asset.id
    _marker(db, floor, entity, 32100, 31900, 1)
    db.flush()
    before = {
        "entities": db.query(KnowledgeEntity).count(),
        "markers": db.query(WorldMapMarker).count(),
        "assets": db.query(MediaAsset).count(),
    }
    monkeypatch.setattr(MediaAsset, "file_exists", lambda _self: True)
    monkeypatch.setattr(media_asset_service, "cache_media_asset", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("network/cache mutation")))

    response = client.get("/api/v1/map/viewport", params=_params(layers="creature"))
    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["image_url"].endswith("/image?placeholder=false")
    assert "provider.invalid" not in str(payload)
    assert before == {
        "entities": db.query(KnowledgeEntity).count(),
        "markers": db.query(WorldMapMarker).count(),
        "assets": db.query(MediaAsset).count(),
    }
    assert not db.new and not db.dirty and not db.deleted


def test_viewport_verified_spatial_point_included_once(client, db):
    _floor(db)
    entity = _entity(db, "location", "Verified Point")
    _location(db, entity, "Verified Point")
    db.add(SpatialMapPoint(
        knowledge_entity_id=entity.uuid, external_id="point:verified", name="Verified Point",
        tibia_x=32100, tibia_y=31900, tibia_z=7, geom="POINT Z (32100 31900 7)",
        min_x=32100, max_x=32100, min_y=31900, max_y=31900, min_z=7, max_z=7,
        confidence="high", verification_state="verified", is_current=True,
    ))
    db.flush()
    response = client.get("/api/v1/map/viewport", params=_params(layers="location"))
    assert response.status_code == 200
    assert len(response.json()["items"]) == 1
    assert len(response.json()["items"][0]["spatial_evidence"]) == 1


def test_viewport_projects_only_trusted_resolved_relationships(client, db):
    floor = _floor(db)
    location = _entity(db, "location", "Relationship Place")
    trusted_quest = _entity(db, "quest", "Trusted Quest")
    ambiguous_quest = _entity(db, "quest", "Ambiguous Quest")
    _location(db, location, "Relationship Place")
    db.add_all([
        TibiaWikiQuest(name="Trusted Quest", slug="trusted-quest", is_group=False, knowledge_entity_id=trusted_quest.uuid),
        TibiaWikiQuest(name="Ambiguous Quest", slug="ambiguous-quest", is_group=False, knowledge_entity_id=ambiguous_quest.uuid),
    ])
    _marker(db, floor, location, 32100, 31900, 1)
    KnowledgeGraphService.upsert(db, RelationshipInput(
        source_entity_id=trusted_quest.uuid, relationship_type="occurs_at_location",
        target_entity_id=location.uuid, confidence="high",
    ))
    KnowledgeGraphService.upsert(db, RelationshipInput(
        source_entity_id=ambiguous_quest.uuid, relationship_type="occurs_at_location",
        target_entity_type="location", unresolved_name="Relationship Place",
        resolution_state="ambiguous", confidence="unknown",
    ))
    db.flush()

    response = client.get("/api/v1/map/viewport", params=_params(layers="quest"))
    assert response.status_code == 200
    assert [row["name"] for row in response.json()["items"]] == ["Trusted Quest"]
    assert response.json()["items"][0]["spatial_evidence"][0]["relationship"] == "occurs_at_location"


def test_low_zoom_balances_layers_and_resumes_exact_cursor(client, db):
    floor = _floor(db)
    candidates = {"creature": [], "location": [], "npc": [], "quest": []}
    for layer, count in (("creature", 45), ("location", 1), ("npc", 3), ("quest", 2)):
        for index in range(count):
            name = f"Density {layer} {index}"
            entity = _entity(db, layer, name)
            candidates[layer].append(f"{layer}:{entity.uuid}")
            if layer == "creature":
                db.add(Creature(name=name, slug=entity.slug, knowledge_entity_id=entity.uuid,
                                is_hidden=False, is_boss=False))
            elif layer == "location":
                _location(db, entity, name)
            elif layer == "npc":
                db.add(TibiaWikiNpc(name=name, normalized_name=name.lower(), slug=entity.slug,
                                   external_id=f"npc:density:{index}", source_name="fixture",
                                   knowledge_entity_id=entity.uuid))
            else:
                db.add(TibiaWikiQuest(name=name, slug=entity.slug, is_group=False,
                                     knowledge_entity_id=entity.uuid))
            _marker(db, floor, entity, 32100, 31900,
                    sum(len(ids) for ids in candidates.values()))
    db.flush()
    # Expected rounds are independent of SQL insertion order and skip empty layers.
    for ids in candidates.values():
        ids.sort()
    expected = []
    for index in range(45):
        for layer in ("creature", "location", "npc", "quest"):
            if index < len(candidates[layer]):
                expected.append(candidates[layer][index])

    def request(**kwargs):
        response = client.get("/api/v1/map/viewport", params=_params(zoom=-3, **kwargs))
        assert response.status_code == 200, response.text
        return response.json()

    first = request()
    first_ids = [row["id"] for row in first["items"]]
    assert len(first_ids) <= 40
    assert first["page"]["limit"] == 40
    assert {row["entity_type"] for row in first["items"]} == set(candidates)
    assert first_ids == expected[:40]
    assert request() == first
    second = request(cursor=first["page"]["next_cursor"])
    second_ids = [row["id"] for row in second["items"]]
    assert set(first_ids).isdisjoint(second_ids)
    assert first_ids + second_ids == expected
    assert second["page"] == {"limit": 40, "has_more": False, "next_cursor": None}

    # End a page at a later layer, then resume at an earlier layer in the next round.
    boundary = request(limit=4)
    assert [row["id"] for row in boundary["items"]] == expected[:4]
    token = boundary["page"]["next_cursor"]
    decoded = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4)).decode()
    assert decoded == expected[3]
    assert expected[4] < decoded  # A lexicographic cursor would wrongly skip this row.
    resumed = request(limit=4, cursor=token)
    assert [row["id"] for row in resumed["items"]] == expected[4:8]
    assert request(limit=4, cursor=token) == resumed

    # The exact cursor entity is stale if it leaves the bbox or active layers.
    for overrides in ({"min_x": 32101}, {"layers": "creature,npc,location"}):
        response = client.get("/api/v1/map/viewport", params=_params(zoom=-3, cursor=token, **overrides))
        assert response.status_code == 422
        assert response.json()["detail"] == {"code": "invalid_map_cursor"}


def test_viewport_missing_cursor_entity_does_not_restart(client):
    token = base64.urlsafe_b64encode(f"npc:{uuid4()}".encode()).decode().rstrip("=")
    response = client.get("/api/v1/map/viewport", params=_params(cursor=token))
    assert response.status_code == 422
    assert response.json()["detail"] == {"code": "invalid_map_cursor"}
