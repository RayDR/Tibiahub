from __future__ import annotations

from uuid import UUID

import pytest
from sqlalchemy import event

from app.knowledge.metadata import refresh_search_metadata
from app.knowledge.models import KnowledgeEntity, KnowledgeEntityAlias
from app.knowledge.registry import EntityTypeRegistry, ProviderRegistry
from app.knowledge.services.graph import KnowledgeGraphService, RelationshipInput
from app.models.external_data import Item, TibiaWikiLocation, TibiaWikiNpc, TibiaWikiQuest
from app.models.media_asset import MediaAsset
from app.models.world_map import WorldMapFloor, WorldMapMarker


@pytest.fixture(autouse=True)
def npc_registry(db):
    EntityTypeRegistry.register_initial(db)
    ProviderRegistry.register_initial(db)
    db.flush()


def entity(db, entity_type: str, name: str, *, suffix: str = "main") -> KnowledgeEntity:
    row = KnowledgeEntity(
        entity_type=entity_type,
        canonical_name=name,
        slug=f"{name.lower().replace(' ', '-')}-{suffix}" if suffix != "main" else name.lower().replace(" ", "-"),
        language_neutral_id=f"phase3g:{entity_type}:{name}:{suffix}",
    )
    db.add(row)
    db.flush()
    refresh_search_metadata(row)
    db.flush()
    return row


def npc(db, name: str, *, supplied_fields=None, **values) -> TibiaWikiNpc:
    canonical = entity(db, "npc", name)
    row = TibiaWikiNpc(
        name=name,
        normalized_name=name.lower(),
        slug=canonical.slug,
        external_id=f"npc:{name}",
        source_name="tibiawiki",
        source_url=f"https://example.test/wiki/{canonical.slug}",
        knowledge_entity_id=canonical.uuid,
        supplied_fields=supplied_fields or [],
        protected_fields=[],
        provider_metadata={},
        buys=values.pop("buys", []),
        sells=values.pop("sells", []),
        destinations=values.pop("destinations", []),
        related_quests=values.pop("related_quests", []),
        **values,
    )
    db.add(row)
    db.flush()
    return row


def floor(db) -> WorldMapFloor:
    row = WorldMapFloor(
        provider="tibiamaps/tibia-map-data", upstream_commit="a" * 40,
        upstream_url="https://example.test/map", license_name="MIT", attribution="fixture",
        floor=7, map_path="/tmp/phase3g-map.png", map_sha256="b" * 64,
        width=2560, height=2048, min_x=31744, min_y=30976, max_x=34304, max_y=33024,
        source_metadata={}, is_current=True,
    )
    db.add(row)
    db.flush()
    return row


def test_directory_is_paginated_stable_and_preserves_unknown_vs_known_empty(client, db):
    second = npc(db, "Beta Guide", supplied_fields=["buys", "sells", "related_quests", "destinations"])
    first = npc(db, "Alpha Guide", location_name="Thais")
    db.commit()

    page = client.get("/api/v1/npcs/directory", params={"limit": 1}).json()
    assert page["total"] == 2 and page["skip"] == 0 and page["limit"] == 1
    assert page["items"][0]["canonical_id"] == str(first.knowledge_entity_id)
    assert page["items"][0]["buys_count"] is None

    next_page = client.get("/api/v1/npcs/directory", params={"skip": 1, "limit": 1}).json()
    assert next_page["items"][0]["canonical_id"] == str(second.knowledge_entity_id)
    assert next_page["items"][0]["buys_count"] == 0
    assert next_page["items"][0]["quest_count"] == 0


def test_directory_statement_count_does_not_grow_per_card(client, db):
    for index in range(8):
        npc(db, f"Bounded Guide {index}")
    db.commit()
    statements = 0

    def count_statement(*_args, **_kwargs):
        nonlocal statements
        statements += 1

    event.listen(db.bind, "before_cursor_execute", count_statement)
    try:
        assert client.get("/api/v1/npcs/directory", params={"limit": 1}).status_code == 200
        one_card = statements
        statements = 0
        assert client.get("/api/v1/npcs/directory", params={"limit": 8}).status_code == 200
        eight_cards = statements
    finally:
        event.remove(db.bind, "before_cursor_execute", count_statement)
    assert eight_cards == one_card


def test_detail_statement_count_does_not_grow_per_trade_relationship(client, db):
    one = npc(db, "One Trade")
    many = npc(db, "Many Trades")
    for index in range(8):
        item_entity = entity(db, "item", f"Bounded Item {index}")
        db.add(Item(
            name=f"Bounded Item {index}",
            normalized_name=f"bounded item {index}",
            slug=f"bounded-item-{index}",
            external_id=f"item:bounded:{index}",
            source_name="tibiawiki",
            knowledge_entity_id=item_entity.uuid,
        ))
        KnowledgeGraphService.upsert(db, RelationshipInput(
            source_entity_id=item_entity.uuid,
            source_scope="trade:sold_by_npc",
            relationship_type="sold_by_npc",
            target_entity_id=one.knowledge_entity_id if index == 0 else many.knowledge_entity_id,
            source_provider_id="tibiawiki",
            source_document_ref=f"item:bounded:{index}",
        ))
    db.commit()
    statements = 0

    def count_statement(*_args, **_kwargs):
        nonlocal statements
        statements += 1

    event.listen(db.bind, "before_cursor_execute", count_statement)
    try:
        assert client.get(f"/api/v1/npcs/{one.knowledge_entity_id}").status_code == 200
        one_relationship = statements
        statements = 0
        assert client.get(f"/api/v1/npcs/{many.knowledge_entity_id}").status_code == 200
        many_relationships = statements
    finally:
        event.remove(db.bind, "before_cursor_execute", count_statement)
    assert many_relationships == one_relationship


def test_directory_searches_safe_alias_location_and_occupation(client, db):
    row = npc(db, "Captain Bluebear", location_name="Thais", occupation="Ship Captain")
    db.add(KnowledgeEntityAlias(
        entity_uuid=row.knowledge_entity_id, entity_type="npc", alias="Blue Bear",
        normalized_alias="blue bear",
    ))
    db.commit()
    assert client.get("/api/v1/npcs/directory", params={"search": "Blue Bear"}).json()["total"] == 1
    assert client.get("/api/v1/npcs/directory", params={"search": "Ship Captain"}).json()["total"] == 1
    assert client.get("/api/v1/npcs/directory", params={"search": "Thais"}).json()["total"] == 1
    assert client.get("/api/v1/npcs/directory", params={"location": "Thais"}).json()["items"][0]["name"] == row.name


def test_detail_accepts_canonical_uuid_and_keeps_legacy_slug(client, db):
    row = npc(db, "Angus", supplied_fields=["description"], description="Local knowledge")
    db.commit()
    canonical = client.get(f"/api/v1/npcs/{row.knowledge_entity_id}")
    legacy = client.get("/api/v1/npcs/angus")
    assert canonical.status_code == legacy.status_code == 200
    assert canonical.json()["canonical_id"] == legacy.json()["canonical_id"]
    assert UUID(canonical.json()["canonical_id"]) == row.knowledge_entity_id


def test_npc_media_is_unavailable_and_never_hotlinked(client, db):
    row = npc(db, "Image Keeper", image_url="https://provider.invalid/image.gif")
    db.commit()
    directory = client.get("/api/v1/npcs/directory").json()["items"][0]
    detail = client.get(f"/api/v1/npcs/{row.knowledge_entity_id}").json()
    assert directory["media"]["status"] == detail["media"]["status"] == "unavailable"
    assert directory["media"]["url"] is None and detail["image_url"] is None
    assert detail["media"]["source_url"] is None


def test_npc_media_uses_safe_local_cache_and_failed_cache_keeps_directory_available(
    client, db, tmp_path,
):
    cached = npc(db, "Cached Keeper", image_url="https://tibia.fandom.com/wiki/Special:FilePath/Cached_Keeper.gif")
    failed = npc(db, "Failed Keeper", image_url="https://tibia.fandom.com/wiki/Special:FilePath/Failed_Keeper.gif")
    cached_path = tmp_path / "cached.gif"
    cached_path.write_bytes(b"GIF89a")
    db.add_all([
        MediaAsset(
            asset_key="npc:tibiawiki:npc_cached_keeper", status="cached",
            local_path=str(cached_path), content_type="image/gif", size_bytes=6,
        ),
        MediaAsset(
            asset_key="npc:tibiawiki:npc_failed_keeper", status="failed",
            error_message="Safe provider failure",
        ),
    ])
    db.commit()
    page = client.get("/api/v1/npcs/directory").json()["items"]
    by_name = {value["name"]: value for value in page}
    assert by_name["Cached Keeper"]["media"]["status"] == "cached"
    assert by_name["Cached Keeper"]["media"]["url"] == f"/api/v1/npcs/{cached.knowledge_entity_id}/image"
    image = client.get(f"/api/v1/npcs/{cached.id}/image")
    assert image.status_code == 200 and image.headers["x-image-source"] == "local-media-asset"
    assert by_name["Failed Keeper"]["media"]["status"] == "unavailable"
    failed_image = client.get(f"/api/v1/npcs/{failed.id}/image")
    assert failed_image.status_code == 404
    assert failed_image.headers["x-image-status"] == "failed"


def test_provider_placeholders_are_not_projected_as_items_or_known_empty(client, db):
    row = npc(db, "Placeholder Trader", supplied_fields=["buys", "sells"], buys=[{"name": "--"}], sells=[{"name": "unknown"}])
    db.commit()
    card = client.get("/api/v1/npcs/directory").json()["items"][0]
    detail = client.get(f"/api/v1/npcs/{row.knowledge_entity_id}").json()
    assert card["buys_count"] is None and card["sells_count"] is None
    assert detail["buys"] == detail["sells"] == []
    assert detail["field_coverage"]["buys"] == detail["field_coverage"]["sells"] == "unknown"


def test_trade_refs_resolve_exact_items_and_keep_semantics(client, db):
    rope = entity(db, "item", "Rope")
    shovel = entity(db, "item", "Shovel")
    db.add_all([
        Item(name="Rope", normalized_name="rope", slug="rope", external_id="item:rope", source_name="tibiawiki", knowledge_entity_id=rope.uuid),
        Item(name="Shovel", normalized_name="shovel", slug="shovel", external_id="item:shovel", source_name="tibiawiki", knowledge_entity_id=shovel.uuid),
    ])
    row = npc(db, "Trader", supplied_fields=["buys", "sells"], buys=[{"name": "Rope", "price": 8}], sells=[{"name": "Shovel", "price": 10}])
    db.commit()
    detail = client.get(f"/api/v1/npcs/{row.knowledge_entity_id}").json()
    assert detail["buys"][0]["semantic"] == "npc_buys_from_player"
    assert detail["sells"][0]["semantic"] == "npc_sells_to_player"
    assert detail["buys"][0]["resolution_state"] == "resolved"
    assert detail["buys"][0]["navigation_url"] == "/items/rope"


def test_canonical_trade_graph_projects_to_npc_and_item_reciprocal_views(client, db):
    item_entity = entity(db, "item", "Passage Ticket")
    trader = npc(db, "Ticket Seller")
    item = Item(
        name="Passage Ticket", normalized_name="passage ticket", slug="passage-ticket",
        external_id="item:ticket", source_name="tibiawiki", knowledge_entity_id=item_entity.uuid,
        buy_from=[{
            "name": "Ticket Seller", "price": 250, "location": None,
            "currency": "gold_coin",
        }],
    )
    db.add(item)
    db.flush()
    KnowledgeGraphService.upsert(db, RelationshipInput(
        source_entity_id=item_entity.uuid, source_scope="trade:sold_by_npc",
        relationship_type="sold_by_npc", target_entity_id=trader.knowledge_entity_id,
        source_provider_id="tibiawiki", source_document_ref="item:ticket",
        source_context={
            "price": 250, "currency": "gold_coin",
            "semantic": "npc_sells_to_player",
        },
    ))
    db.commit()
    card = client.get("/api/v1/npcs/directory").json()["items"][0]
    assert card["sells_count"] == 1
    detail = client.get(f"/api/v1/npcs/{trader.knowledge_entity_id}").json()
    assert detail["sells"][0]["name"] == "Passage Ticket"
    assert detail["sells"][0]["price"] == 250
    assert detail["sells"][0]["currency"] == "gold_coin"
    reciprocal = client.get("/api/v1/items/passage-ticket").json()["related_entities"]
    assert reciprocal[0]["name"] == "Ticket Seller"
    assert reciprocal[0]["semantic"] == "npc_sells_to_player"


def test_references_remain_unresolved_or_ambiguous_without_guessing(client, db):
    entity(db, "item", "Shared Token", suffix="one")
    entity(db, "item", "Shared Token", suffix="two")
    row = npc(db, "Careful Trader", supplied_fields=["buys"], buys=[{"name": "Shared Token"}, {"name": "Almost Rope"}])
    db.commit()
    values = client.get(f"/api/v1/npcs/{row.knowledge_entity_id}").json()["buys"]
    assert values[0]["resolution_state"] == "ambiguous" and values[0]["canonical_id"] is None
    assert values[1]["resolution_state"] == "unresolved" and values[1]["navigation_url"] is None


def test_quest_and_destination_refs_use_exact_canonical_links(client, db):
    quest = entity(db, "quest", "Explorer Society Quest")
    place = entity(db, "town", "Port Hope")
    db.add_all([
        TibiaWikiQuest(name="Explorer Society Quest", normalized_name="explorer society quest", slug="explorer-society-quest", external_id="quest:1", source_name="tibiawiki", is_group=False, knowledge_entity_id=quest.uuid),
        TibiaWikiLocation(name="Port Hope", normalized_name="port hope", slug="port-hope", external_id="location:1", source_name="tibiawiki", knowledge_entity_id=place.uuid),
    ])
    row = npc(db, "Explorer", supplied_fields=["destinations", "related_quests"], destinations=[{"name": "Port Hope"}], related_quests=[{"name": "Explorer Society Quest"}])
    db.commit()
    detail = client.get(f"/api/v1/npcs/{row.knowledge_entity_id}").json()
    assert detail["destinations"][0]["navigation_url"] == "/locations/port-hope"
    assert detail["related_quests"][0]["navigation_url"] == "/quests/explorer-society-quest"
    assert detail["related_quests"][0]["semantic"] == "related"


def test_location_prose_does_not_create_fake_location(client, db):
    row = npc(db, "Wanderer", location_name="north of Edron, past the bridge")
    before = db.query(KnowledgeEntity).count()
    db.commit()
    detail = client.get(f"/api/v1/npcs/{row.knowledge_entity_id}").json()
    assert detail["location_name"] == "north of Edron, past the bridge"
    assert not [value for value in detail["relationships"] if value["relationship_type"] == "located_at"]
    assert db.query(KnowledgeEntity).count() == before


def test_exact_map_identity_is_used_and_name_similarity_is_ignored(client, db):
    mapped = npc(db, "Trusted Guide")
    text_only = npc(db, "Trusted Guide Assistant")
    current_floor = floor(db)
    db.add(WorldMapMarker(
        floor_id=current_floor.id, source_index=1, description="Trusted Guide",
        normalized_description="trusted guide", x=32100, y=32000, floor=7, raw_data={},
        resolved_entity_id=mapped.knowledge_entity_id, resolution_state="resolved",
        resolution_method="exact_canonical_name_or_alias",
    ))
    db.commit()
    page = client.get("/api/v1/npcs/directory").json()["items"]
    by_name = {value["name"]: value for value in page}
    assert by_name["Trusted Guide"]["map_available"] is True
    assert by_name["Trusted Guide Assistant"]["map_available"] is False
    map_result = client.get("/api/v1/map/search", params={"q": "Trusted Guide", "layers": "npc"}).json()["items"][0]
    assert map_result["navigation_url"] == f"/npcs/{mapped.knowledge_entity_id}"
    assert map_result["image_url"] is None


def test_graph_quest_semantics_and_provenance_are_preserved(client, db):
    row = npc(db, "Quest Giver")
    quest = entity(db, "quest", "Canonical Quest")
    KnowledgeGraphService.upsert(db, RelationshipInput(
        source_entity_id=quest.uuid, relationship_type="starts_at_npc",
        target_entity_id=row.knowledge_entity_id, source_provider_id="tibiawiki",
        source_document_ref="quest:canonical",
    ))
    db.commit()
    relationship = client.get(f"/api/v1/npcs/{row.knowledge_entity_id}").json()["relationships"][0]
    assert relationship["relationship_type"] == "starts_quest"
    assert relationship["target_canonical_id"] == str(quest.uuid)
    assert relationship["source_providers"] == ["tibiawiki"]
