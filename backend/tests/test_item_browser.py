from app.knowledge.models import KnowledgeEntity, KnowledgeEntityType
from app.models.external_data import Item as ExternalItemModel


def _seed_item(db, *, name: str, category: str, external_id: str):
    slug = name.lower().replace(" ", "-")
    entity = KnowledgeEntity(
        entity_type="item",
        canonical_name=name,
        slug=slug,
        language_neutral_id=f"item:{external_id}",
    )
    db.add(entity)
    db.flush()
    item = ExternalItemModel(
        name=name,
        normalized_name=name.lower(),
        slug=slug,
        external_id=external_id,
        source_name="tibiawiki",
        knowledge_entity_id=entity.uuid,
        category=category,
        type="loot",
        raw_data={"supplied_fields": ["category", "item_type"]},
    )
    db.add(item)
    db.flush()
    return item


def _seed_catalog(db):
    db.add(KnowledgeEntityType(entity_type="item", display_name="Item"))
    db.flush()
    _seed_item(db, name="Axe", category="Weapons", external_id="1")
    _seed_item(db, name="Backpack", category="Containers", external_id="2")
    _seed_item(db, name="Crystal Coin", category="Valuables", external_id="3")
    _seed_item(db, name="Demon Shield", category="Armors", external_id="4")
    db.flush()


def test_item_facets_are_canonical_local_counts(client, db):
    _seed_catalog(db)

    response = client.get("/api/v1/items/facets")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 4
    assert payload["categories"] == [
        {"value": "Armors", "count": 1},
        {"value": "Containers", "count": 1},
        {"value": "Valuables", "count": 1},
        {"value": "Weapons", "count": 1},
    ]


def test_item_browser_filters_sorts_and_paginates(client, db):
    _seed_catalog(db)

    filtered = client.get(
        "/api/v1/items/browse",
        params={"category": "Weapons", "limit": 20},
    )
    assert filtered.status_code == 200
    assert [row["item_name"] for row in filtered.json()] == ["Axe"]

    paged = client.get(
        "/api/v1/items/browse",
        params={"sort_by": "name", "sort_order": "desc", "skip": 1, "limit": 2},
    )
    assert paged.status_code == 200
    assert [row["item_name"] for row in paged.json()] == ["Crystal Coin", "Backpack"]

    searched = client.get(
        "/api/v1/items/browse",
        params={"search": "demon", "limit": 20},
    )
    assert searched.status_code == 200
    assert [row["item_name"] for row in searched.json()] == ["Demon Shield"]
