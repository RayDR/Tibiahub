from __future__ import annotations

from app.knowledge.models.core import KnowledgeEntity, KnowledgeEntityType
from app.models.creature import Creature
from app.models.entity_metadata import EntityMetadata
from app.models.external_data import Item
from app.models.hunt_zone import HuntZone
from app.models.loot import Loot


def _boss(name: str, difficulty: str, hitpoints: int, experience: int) -> Creature:
    slug = name.lower().replace(" ", "-")
    return Creature(
        name=name,
        slug=slug,
        normalized_name=name.lower(),
        hitpoints=hitpoints,
        experience=experience,
        difficulty=difficulty,
        is_boss=True,
        is_hidden=False,
    )


def test_every_exposed_boss_sort_stays_on_bosses_and_returns_rows(client, db):
    db.add_all([
        _boss("Alpha Regent", "Easy", 100, 500),
        _boss("Beta Regent", "Medium", 300, 100),
        _boss("Gamma Regent", "Hard", 200, 300),
    ])
    db.flush()

    for sort_by in ("name", "experience", "hitpoints", "difficulty"):
        for sort_order in ("asc", "desc"):
            response = client.get("/api/v1/creatures/bosses", params={
                "sort_by": sort_by,
                "sort_order": sort_order,
                "limit": 20,
            })
            assert response.status_code == 200
            rows = response.json()
            assert rows, (sort_by, sort_order)
            assert all(row["is_boss"] is True for row in rows)


def test_boss_search_and_detail_feed_real_popularity(client, db):
    boss = _boss("Activity Regent", "Hard", 400, 900)
    db.add(boss)
    db.flush()

    assert client.get("/api/v1/creatures/bosses", params={"search": "Activity"}).status_code == 200
    assert client.get("/api/v1/creatures/activity-regent").status_code == 200
    metadata = db.query(EntityMetadata).filter_by(entity_type="creature", entity_id=boss.id).one()
    assert metadata.search_count == 2
    assert metadata.last_viewed_at is not None

    popular = client.get("/api/v1/creatures/bosses/popular")
    assert popular.status_code == 200
    assert [row["id"] for row in popular.json()] == [boss.id]


def test_item_search_routes_resolve_canonical_then_legacy_exactly(client, db):
    entity_type = KnowledgeEntityType(entity_type="manual-item", display_name="Manual item")
    entity = KnowledgeEntity(
        entity_type="manual-item",
        canonical_name="Legion Helmet",
        slug="legion-helmet",
        language_neutral_id="manual:legion-helmet",
    )
    db.add_all([entity_type, entity])
    db.flush()
    canonical = Item(
        name="Legion Helmet",
        normalized_name="legion helmet",
        slug="legion-helmet",
        knowledge_entity_id=entity.uuid,
    )
    creature = Creature(
        name="Legacy Legionnaire",
        slug="legacy-legionnaire",
        normalized_name="legacy legionnaire",
        hitpoints=100,
        experience=100,
        is_hidden=False,
    )
    db.add_all([canonical, creature])
    db.flush()
    db.add_all([
        Loot(item_name="Legion Helmet", normalized_name="legion helmet", creature_id=creature.id),
        Loot(item_name="Legionnaire Flags", normalized_name="legionnaire-flags", creature_id=creature.id),
    ])
    db.flush()

    broad_search = client.get("/api/v1/items/", params={"search": "Legio"})
    assert broad_search.status_code == 200
    assert {row["item_name"] for row in broad_search.json()} >= {"Legion Helmet", "Legionnaire Flags"}

    helmet_search = client.get("/api/v1/items/", params={"search": "Legion Helmet"})
    assert helmet_search.status_code == 200
    helmet_route = helmet_search.json()[0]["slug"]
    helmet_detail = client.get(f"/api/v1/items/{helmet_route}")
    assert helmet_detail.status_code == 200
    assert helmet_detail.json()["knowledge_entity_id"] == str(entity.uuid)

    flags_search = client.get("/api/v1/items/", params={"search": "Legionnaire Flags"})
    assert flags_search.status_code == 200
    flags_route = flags_search.json()[0]["slug"]
    assert flags_route == "legionnaire-flags"
    flags_detail = client.get(f"/api/v1/items/{flags_route}")
    assert flags_detail.status_code == 200
    assert flags_detail.json()["item_name"] == "Legionnaire Flags"
    assert flags_detail.json()["drops"][0]["creature_slug"] == "legacy-legionnaire"


def test_missing_map_can_be_requested_without_product_placeholder(client, db, monkeypatch):
    from app.api.v1.local_media import LocalMediaDescriptor

    zone = HuntZone(name="Mapless Grounds", slug="mapless-grounds", normalized_name="mapless grounds", min_level=20)
    db.add(zone)
    db.flush()
    monkeypatch.setattr(
        "app.api.v1.hunt_zones._resolve_hunt_zone_media_descriptor",
        lambda _zone_id: LocalMediaDescriptor(
            local_path=None,
            content_type=None,
            size_bytes=None,
            asset_hash=None,
            asset_key="zone:mapless-grounds",
            status="missing",
            fallback_label="Mapless Grounds",
        ),
    )

    response = client.get(f"/api/v1/hunt-zones/{zone.id}/map-image", params={"placeholder": "false"})
    assert response.status_code == 404
    assert response.headers["x-image-source"] == "unavailable"
