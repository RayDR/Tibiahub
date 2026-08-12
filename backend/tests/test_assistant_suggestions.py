from app.models.creature import Creature
from app.models.entity_metadata import EntityMetadata
from app.models.external_data import Item, TibiaWikiQuest
from app.models.hunt_zone import HuntZone


def _popular(db, entity_type, row, *, display_name, count):
    db.add(EntityMetadata(
        entity_type=entity_type,
        entity_key=f"{entity_type}-{row.id}",
        display_name=display_name,
        entity_id=row.id,
        search_count=count,
    ))


def test_suggestions_mix_real_canonical_entities_without_provider_calls(client, db):
    creature = Creature(name="Popular Werewolf", normalized_name="popular werewolf", slug="popular-werewolf", hitpoints=100, experience=50)
    item = Item(name="Popular Seed", normalized_name="popular seed", slug="popular-seed")
    quest = TibiaWikiQuest(name="Popular Quest", normalized_name="popular quest", slug="popular-quest", is_group=False)
    zone = HuntZone(name="Popular Grounds", normalized_name="popular grounds", slug="popular-grounds", min_level=20)
    db.add_all([creature, item, quest, zone])
    db.flush()
    _popular(db, "creature", creature, display_name="spoofed raw query", count=50)
    _popular(db, "item", item, display_name="another user's prompt", count=40)
    _popular(db, "quest", quest, display_name="not canonical", count=30)
    _popular(db, "hunt_zone", zone, display_name="debug value", count=20)
    db.flush()

    response = client.get("/api/v1/assistant/suggestions?language=en&limit=8")

    assert response.status_code == 200
    payload = response.json()
    assert 4 <= len(payload) <= 8
    assert {row["entity_type"] for row in payload[:4]} == {"creature", "item", "quest", "hunt_zone"}
    assert {row["entity_name"] for row in payload[:4]} == {
        "Popular Werewolf", "Popular Seed", "Popular Quest", "Popular Grounds",
    }
    assert all(row["source"] == "popular" for row in payload[:4])
    assert "spoofed raw query" not in str(payload)
    assert "another user's prompt" not in str(payload)


def test_suggestions_have_spanish_parity_and_bounded_fallback(client):
    response = client.get("/api/v1/assistant/suggestions?language=es&limit=3")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 3
    assert payload[0]["text"].startswith("¿Dónde puedo cazar")
    assert payload[1]["text"].startswith("¿Cómo puedo conseguir")
    assert payload[2]["text"].startswith("¿Qué necesito para comenzar")
    assert all(row["source"] == "fallback" for row in payload)


def test_suggestion_bounds_and_language_are_validated(client):
    assert client.get("/api/v1/assistant/suggestions?limit=30").status_code == 422
    assert client.get("/api/v1/assistant/suggestions?language=pt").status_code == 422
