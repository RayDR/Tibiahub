from app.models import Creature, Element, HuntZone, Loot, SpawnLocation
from app.models.creature import creature_weaknesses


def seed_creature(db):
    creature = Creature(
        name="Reference Orc",
        normalized_name="reference orc",
        slug="reference-orc",
        hitpoints=95,
        experience=58,
        difficulty="Easy",
        classification="Humanoid",
        bestiary_level="Easy",
        bestiary_class="Humanoid",
        creature_class="Orc",
        primary_type="Physical",
        description="A reference creature used by the browser test.",
        behavior="Keeps close and attacks in melee.",
        is_boss=False,
        is_hidden=False,
    )
    db.add(creature)
    db.flush()

    zone = HuntZone(name="Orc Fortress", normalized_name="orc fortress", slug="orc-fortress", city="Rookgaard")
    db.add(zone)
    db.flush()
    db.add(SpawnLocation(creature_id=creature.id, hunt_zone_id=zone.id, quantity="Many"))

    db.add(Loot(creature_id=creature.id, item_name="War Axe", normalized_name="war axe", item_value=1000, percentage=2.1))
    db.add(Loot(creature_id=creature.id, item_name="Orc Leather", normalized_name="orc leather", item_value=80, percentage=12.5))

    fire = Element(name="Fire")
    db.add(fire)
    db.flush()
    db.execute(creature_weaknesses.insert().values(creature_id=creature.id, element_id=fire.id, percentage=110))
    db.flush()
    return creature


def test_browser_items_are_enriched_in_one_batch(client, db):
    creature = seed_creature(db)
    response = client.get(f"/api/v1/creatures/browser-items?ids={creature.id}")
    assert response.status_code == 200
    item = response.json()[0]
    assert item["name"] == "Reference Orc"
    assert item["bestiary_level"] == "Easy"
    assert item["primary_type"] == "Physical"
    assert item["location_preview"]["name"] == "Orc Fortress"
    assert [row["item_name"] for row in item["loot_preview"]] == ["War Axe", "Orc Leather"]


def test_creature_preview_contains_real_relationship_data(client, db):
    creature = seed_creature(db)
    response = client.get(f"/api/v1/creatures/{creature.id}/preview")
    assert response.status_code == 200
    preview = response.json()
    assert preview["description"].startswith("A reference creature")
    assert preview["locations"][0]["name"] == "Orc Fortress"
    assert len(preview["loot"]) == 2
    assert preview["combat_modifiers"] == [{
        "name": "Fire",
        "kind": "weakness",
        "damage_percent": 110,
        "delta_percent": 10,
    }]


def test_browser_page_returns_authoritative_total(client, db):
    seed_creature(db)
    response = client.get("/api/v1/creatures/browser?search=Reference&limit=20")
    assert response.status_code == 200
    page = response.json()
    assert page["total"] == 1
    assert page["items"][0]["name"] == "Reference Orc"
