from app.knowledge.models.core import KnowledgeEntity, KnowledgeEntityType
from app.models.creature import Creature
from app.models.external_data import Item, TibiaWikiQuest
from app.models.hunt_zone import HuntZone
from app.models.loot import Loot
from app.models.quest import Quest
from app.models.spawn_location import SpawnLocation


def test_sitemap_contains_only_canonical_public_knowledge(client, db):
    entity_type = KnowledgeEntityType(entity_type="item", display_name="SEO Item")
    entity = KnowledgeEntity(entity_type="item", canonical_name="SEO Sword", slug="seo-sword", language_neutral_id="seo-sword")
    db.add_all([entity_type, entity])
    db.flush()
    db.add_all([
        Creature(name="SEO Dragon", slug="seo-dragon", normalized_name="seo dragon", hitpoints=100, experience=50, is_hidden=False),
        Creature(name="Hidden SEO Dragon", slug="hidden-seo-dragon", normalized_name="hidden seo dragon", hitpoints=100, experience=50, is_hidden=True),
        Item(name="SEO Sword", slug="seo-sword", normalized_name="seo sword", knowledge_entity_id=entity.uuid),
        TibiaWikiQuest(name="SEO Quest", slug="seo-quest", normalized_name="seo quest", is_group=False),
        HuntZone(name="SEO Grounds", slug="seo-grounds", normalized_name="seo grounds", min_level=20),
    ])
    db.flush()

    response = client.get("/api/v1/seo/sitemap.xml")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/xml")
    content = response.text
    assert "https://tibiahub.domoforge.com/creatures/seo-dragon" in content
    assert "https://tibiahub.domoforge.com/items/seo-sword" in content
    assert "https://tibiahub.domoforge.com/quests/seo-quest" in content
    assert "https://tibiahub.domoforge.com/hunt-zones/seo-grounds" in content
    assert "https://tibiahub.domoforge.com/map" in content
    assert "hidden-seo-dragon" not in content
    assert "/admin" not in content
    assert "/profile" not in content


def test_robots_points_to_root_sitemap_and_blocks_private_prefixes(client):
    response = client.get("/api/v1/seo/robots.txt")
    assert response.status_code == 200
    assert "Sitemap: https://tibiahub.domoforge.com/sitemap.xml" in response.text
    assert "Disallow: /admin/" in response.text
    assert "Disallow: /guild/" in response.text


def test_item_and_hunt_zone_numeric_routes_expose_canonical_slugs(client, db):
    entity_type = KnowledgeEntityType(entity_type="item-route", display_name="Route Item")
    entity = KnowledgeEntity(entity_type="item-route", canonical_name="Route Sword", slug="route-sword", language_neutral_id="route-sword")
    db.add_all([entity_type, entity])
    db.flush()
    item = Item(name="Route Sword", slug="route-sword", normalized_name="route sword", knowledge_entity_id=entity.uuid)
    zone = HuntZone(name="Route Grounds", slug="route-grounds", normalized_name="route grounds", min_level=10)
    db.add_all([item, zone])
    db.flush()

    item_response = client.get(f"/api/v1/items/{item.id}")
    zone_response = client.get(f"/api/v1/hunt-zones/{zone.id}")
    slug_response = client.get("/api/v1/hunt-zones/route-grounds")

    assert item_response.status_code == 200
    assert item_response.headers["x-canonical-slug"] == "route-sword"
    assert item_response.json()["slug"] == "route-sword"
    assert zone_response.status_code == 200
    assert zone_response.headers["x-canonical-slug"] == "route-grounds"
    assert slug_response.status_code == 200
    assert slug_response.json()["id"] == zone.id


def test_hunt_zone_detail_exposes_structured_spawns_and_resolved_access_quest(client, db):
    access_quest = Quest(name="Access Quest")
    public_quest = TibiaWikiQuest(name="Access Quest", normalized_name="access quest", slug="access-quest", is_group=False)
    creature = Creature(name="Zone Beast", slug="zone-beast", normalized_name="zone beast", hitpoints=100, experience=50, is_hidden=False)
    db.add_all([access_quest, public_quest, creature])
    db.flush()
    zone = HuntZone(name="Structured Grounds", slug="structured-grounds", normalized_name="structured grounds", min_level=40, requires_quest=True, quest_id=access_quest.id)
    db.add(zone)
    db.flush()
    db.add(SpawnLocation(creature_id=creature.id, hunt_zone_id=zone.id, quantity="Many", notes="Lower floor"))
    db.flush()

    zone_response = client.get("/api/v1/hunt-zones/structured-grounds")
    creature_response = client.get("/api/v1/creatures/zone-beast")

    assert zone_response.status_code == 200
    detail = zone_response.json()
    assert detail["quest_name"] == "Access Quest"
    assert detail["quest_slug"] == "access-quest"
    assert detail["creature_spawns"][0]["creature"]["name"] == "Zone Beast"
    assert detail["creature_spawns"][0]["quantity"] == "Many"
    assert creature_response.status_code == 200
    related_zone = creature_response.json()["spawn_locations"][0]["hunt_zone"]
    assert related_zone["slug"] == "structured-grounds"
    assert related_zone["requires_quest"] is True
    assert related_zone["quest_name"] == "Access Quest"


def test_legacy_loot_item_normalized_route_remains_available(client, db):
    creature = Creature(name="Loot Beast", slug="loot-beast", normalized_name="loot beast", hitpoints=100, experience=50, is_hidden=False)
    db.add(creature)
    db.flush()
    loot = Loot(item_name="Legacy Crystal", normalized_name="legacy crystal", creature_id=creature.id, min_amount=1, max_amount=1)
    db.add(loot)
    db.flush()

    response = client.get("/api/v1/items/legacy-crystal")

    assert response.status_code == 200
    assert response.headers["x-canonical-slug"] == "legacy-crystal"
    assert response.json()["slug"] == "legacy-crystal"
    assert response.json()["drops"][0]["creature_name"] == "Loot Beast"
