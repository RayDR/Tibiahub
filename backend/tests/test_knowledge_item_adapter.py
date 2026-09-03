from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token
from app.db.database import Base
from app.knowledge.adapters import (
    KnowledgeAdapterRegistry,
    KnowledgeDocumentDTO,
    KnowledgeFetchRequest,
    KnowledgeFetchResult,
    KnowledgeNormalizationContext,
    TibiaWikiItemAdapter,
)
from app.knowledge.dto import ItemKnowledgeDTO
from app.knowledge.indexing import normalize_name
from app.knowledge.models import (
    KnowledgeCreatureItemDrop,
    KnowledgeDocument,
    KnowledgeEntity,
    KnowledgeExternalMapping,
    KnowledgeJob,
    KnowledgeProvider,
    KnowledgeProviderCursor,
    KnowledgeRelationship,
)
from app.knowledge.registry import EntityTypeRegistry, ProviderRegistry
from app.knowledge.schemas import KnowledgeEntityCreate
from app.knowledge.services import (
    DuplicateKnowledgeEntityError,
    EnqueueKnowledgeJob,
    ItemIdentityConflictError,
    KnowledgeEntityService,
    KnowledgeJobService,
)
from app.knowledge.services.normalization import KnowledgeNormalizationService
from app.knowledge.services.npc_trade_repair import NpcTradeRelationshipRepairService
from app.knowledge.schemas import KnowledgeDocumentCreate
from app.knowledge.storage import KnowledgeDocumentStore
from app.knowledge.workers.knowledge_worker import KnowledgeWorker
from app.models import Creature, Item, TibiaWikiNpc
from app.models.workspace_audit import WorkspaceAudit
from tests.conftest import make_user


FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class FixtureItemClient:
    def __init__(self):
        self.catalog_calls = 0
        self.detail_calls = 0

    def fetch_catalog(self, *, continuation: str | None, limit: int) -> dict:
        self.catalog_calls += 1
        value = fixture("tibiawiki_item_catalog.json")
        if continuation:
            value.pop("continue", None)
            value["query"]["categorymembers"] = [
                {"pageid": 333, "ns": 0, "title": "Golden Helmet"}
            ]
        return value

    def fetch_detail(self, *, external_id: str | None, page_title: str | None) -> dict:
        self.detail_calls += 1
        value = fixture("tibiawiki_item_detail.json")
        if external_id == "222" or page_title == "Demon Shield":
            value["parse"]["pageid"] = 222
            value["parse"]["title"] = "Demon Shield"
            value["parse"]["wikitext"]["*"] = (
                value["parse"]["wikitext"]["*"]
                .replace("Magic Sword", "Demon Shield")
                .replace("3288", "3420")
                .replace("Sword", "Shield")
            )
        return value


def request(job_type: str, *, scope: dict | None = None, payload: dict | None = None) -> KnowledgeFetchRequest:
    return KnowledgeFetchRequest(
        job_id=uuid4(),
        attempt_id=uuid4(),
        correlation_id=uuid4(),
        provider_code="tibiawiki",
        job_type=job_type,
        entity_type="item",
        scope=scope or {},
        payload=payload or {},
    )


def normalization_context() -> KnowledgeNormalizationContext:
    return KnowledgeNormalizationContext(
        job_id=uuid4(),
        attempt_id=uuid4(),
        correlation_id=uuid4(),
        provider_code="tibiawiki",
        entity_type="item",
    )


@pytest.fixture
def item_registry(db):
    EntityTypeRegistry.register_initial(db)
    ProviderRegistry.register_initial(db)
    provider = db.get(KnowledgeProvider, "tibiawiki")
    provider.enabled = True
    provider.health = "unknown"
    provider.rate_limit = {}
    db.flush()


def _document(raw: dict) -> KnowledgeDocumentDTO:
    return KnowledgeDocumentDTO(
        "tibiawiki",
        f"item:{raw['parse']['pageid']}",
        raw,
        metadata={"document_kind": "item_detail"},
    )


def _apply_detail(db, raw: dict):
    adapter = TibiaWikiItemAdapter(FixtureItemClient())
    return KnowledgeNormalizationService.apply(db, adapter.normalize(_document(raw), normalization_context()))


def _variant_raw(*, external_id: int, title: str, game_item_id: int, canonical_name: str = "Magic Sword") -> dict:
    raw = fixture("tibiawiki_item_detail.json")
    raw["parse"]["pageid"] = external_id
    raw["parse"]["title"] = title
    raw["parse"]["wikitext"]["*"] = raw["parse"]["wikitext"]["*"].replace("3288", str(game_item_id))
    if canonical_name != "Magic Sword":
        raw["parse"]["wikitext"]["*"] = raw["parse"]["wikitext"]["*"].replace("Magic Sword", canonical_name)
    return raw


def test_item_catalog_preserves_unknown_fields_and_creates_bounded_children():
    adapter = TibiaWikiItemAdapter(FixtureItemClient())
    result = adapter.fetch(request("item_catalog", scope={"batch_limit": 2}))
    assert adapter.validate(result).classification == "valid"
    assert result.documents[0].raw_json["future_catalog_field"] == {"preserved": True}
    assert [(child.job_type, child.payload.get("external_id")) for child in result.child_jobs] == [
        ("item_detail", "111"),
        ("item_detail", "222"),
        ("item_catalog", None),
    ]
    assert result.cursor["continuation"] == "page|4d414749432053574f5244|111"
    assert all(child.allow_completed_recreate for child in result.child_jobs)


def test_item_detail_maps_real_fields_categories_and_unknown_envelope():
    adapter = TibiaWikiItemAdapter(FixtureItemClient())
    result = adapter.fetch(request("item_detail", payload={"external_id": "111", "page_title": "Magic Sword"}))
    assert adapter.validate(result).classification == "valid"
    document = result.documents[0]
    assert document.raw_json["future_envelope_field"] == "retained"
    normalized = adapter.normalize(document, normalization_context())
    dto = ItemKnowledgeDTO.from_canonical_data(normalized.canonical_data)
    assert dto.external_id == "111" and dto.game_item_id == 3288
    assert dto.canonical_name == "Magic Sword" and dto.category == "Weapon" and dto.item_type == "Sword"
    assert dto.weight == 42.0 and dto.attack == 48 and dto.defense == 35
    assert dto.vocation_requirements == ("Knight", "Elite Knight")
    assert [reference.name for reference in dto.dropped_by] == ["Demon", "Ferumbras"]
    assert dto.provider_metadata["provider_category"] == "Weapon"


def test_item_trade_parser_preserves_explicit_price_currency_and_unknown_price():
    raw = fixture("tibiawiki_item_detail.json")
    raw["parse"]["wikitext"]["*"] = raw["parse"]["wikitext"]["*"].replace(
        "| buyfrom = [[A Sweaty Cyclops]]",
        "| buyfrom = Captain Bluebear: 1,000, Unknown Merchant",
    ).replace(
        "| sellto = [[Rashid]]",
        "| sellto = Rashid:6400;sayname, Fiona",
    )
    dto = ItemKnowledgeDTO.from_canonical_data(
        TibiaWikiItemAdapter(FixtureItemClient()).normalize(
            _document(raw), normalization_context(),
        ).canonical_data,
    )
    assert [(value.name, value.price, value.currency) for value in dto.buy_from] == [
        ("Captain Bluebear", 1000, "gold_coin"),
        ("Unknown Merchant", None, None),
    ]
    assert [(value.name, value.price, value.currency) for value in dto.sell_to] == [
        ("Rashid", 6400, "gold_coin"),
        ("Fiona", None, None),
    ]


def test_item_trade_parser_removes_provider_display_modifier_from_identity():
    raw = fixture("tibiawiki_item_detail.json")
    raw["parse"]["wikitext"]["*"] = raw["parse"]["wikitext"]["*"].replace(
        "| sellto = [[Rashid]]",
        "| sellto = Telas;sayname, Sandra: 20;oil",
    )
    dto = ItemKnowledgeDTO.from_canonical_data(
        TibiaWikiItemAdapter(FixtureItemClient()).normalize(
            _document(raw), normalization_context(),
        ).canonical_data,
    )
    assert [(value.name, value.price, value.currency, value.qualifier) for value in dto.sell_to] == [
        ("Telas", None, None, None),
        ("Sandra", 20, "gold_coin", "oil"),
    ]


def test_item_trade_parser_preserves_special_currency_and_decimal_unknown_currency():
    raw = fixture("tibiawiki_item_detail.json")
    raw["parse"]["wikitext"]["*"] = raw["parse"]["wikitext"]["*"].replace(
        "| buyfrom = [[A Sweaty Cyclops]]",
        "| buyfrom = Yana: 50 Gold Tokens, Lily: 0.2",
    )
    dto = ItemKnowledgeDTO.from_canonical_data(
        TibiaWikiItemAdapter(FixtureItemClient()).normalize(
            _document(raw), normalization_context(),
        ).canonical_data,
    )
    assert [(value.name, value.price, value.currency) for value in dto.buy_from] == [
        ("Yana", 50, "gold_tokens"),
        ("Lily", 0.2, None),
    ]



def test_item_detail_treats_double_dash_list_placeholder_as_empty():
    raw = fixture("tibiawiki_item_detail.json")
    raw["parse"]["wikitext"]["*"] = raw["parse"]["wikitext"]["*"].replace(
        "| buyfrom = [[A Sweaty Cyclops]]",
        "| buyfrom = --",
    )

    adapter = TibiaWikiItemAdapter(FixtureItemClient())
    document = _document(raw)

    normalized = adapter.normalize(document, normalization_context())
    dto = ItemKnowledgeDTO.from_canonical_data(normalized.canonical_data)

    assert dto.buy_from == ()
    assert [reference.name for reference in dto.sell_to] == ["Rashid"]
    assert "buy_from" in dto.supplied_fields


def test_item_enqueue_requires_bounded_catalog_and_safe_identifiers():
    adapter = TibiaWikiItemAdapter(FixtureItemClient())
    with pytest.raises(ValueError, match="batch_limit"):
        adapter.validate_enqueue("item_catalog", {}, {})
    with pytest.raises(ValueError, match="numeric page IDs"):
        adapter.validate_enqueue("item_detail", {}, {"external_id": "weak-name-id"})
    with pytest.raises(ValueError, match="safe"):
        adapter.validate_enqueue("item_detail", {}, {"page_title": "Sword\nInjected"})
    adapter.validate_enqueue("item_detail", {}, {"external_id": "111", "page_title": "Magic Sword"})


@pytest.mark.parametrize(
    ("result", "classification"),
    [
        (KnowledgeFetchResult(documents=()), "empty"),
        (
            KnowledgeFetchResult(
                documents=(KnowledgeDocumentDTO("tibiawiki", "bad", {"error": {"code": "bad"}}),)
            ),
            "provider_error",
        ),
        (
            KnowledgeFetchResult(
                documents=(KnowledgeDocumentDTO("tibiawiki", "bad", {"unexpected": True}),)
            ),
            "invalid",
        ),
    ],
)
def test_item_adapter_classifies_empty_provider_error_and_malformed(result, classification):
    validation = TibiaWikiItemAdapter(FixtureItemClient()).validate(result)
    assert validation.valid is False and validation.classification == classification


def test_item_adapter_preserves_partial_without_normalizing_and_rejects_unsafe_text():
    adapter = TibiaWikiItemAdapter(FixtureItemClient())
    partial_document = KnowledgeDocumentDTO(
        "tibiawiki",
        "item:111",
        fixture("tibiawiki_item_partial.json"),
        metadata={"document_kind": "item_detail"},
    )
    partial = KnowledgeFetchResult(documents=(partial_document,), partial=True)
    assert adapter.validate(partial).classification == "partial"
    assert adapter.normalize(partial_document, normalization_context()).action == "noop"
    unsafe = deepcopy(partial_document.raw_json)
    unsafe["parse"]["wikitext"]["*"] += "<script>alert(1)</script>"
    validation = adapter.validate(
        KnowledgeFetchResult(
            documents=(KnowledgeDocumentDTO("tibiawiki", "item:111", unsafe, metadata={"document_kind": "item_detail"}),)
        )
    )
    assert validation.valid is False and validation.safe_errors == ("unsafe_text",)


def test_item_adapter_rejects_oversized_and_out_of_range_numeric_values():
    adapter = TibiaWikiItemAdapter(FixtureItemClient())
    huge = {"parse": {"blob": "x" * (2 * 1024 * 1024 + 1)}}
    assert adapter.validate(
        KnowledgeFetchResult(documents=(KnowledgeDocumentDTO("tibiawiki", "huge", huge),))
    ).classification == "oversized"
    raw = fixture("tibiawiki_item_detail.json")
    raw["parse"]["wikitext"]["*"] = raw["parse"]["wikitext"]["*"].replace("| attack = 48", "| attack = -1")
    validation = adapter.validate(KnowledgeFetchResult(documents=(_document(raw),)))
    assert validation.valid is False and validation.safe_errors == ("numeric_range",)


def test_item_mapping_reuses_uuid_updates_and_versions_only_canonical_changes(db, item_registry):
    first = _apply_detail(db, fixture("tibiawiki_item_detail.json"))
    db.flush()
    item = db.query(Item).one()
    entity = db.get(KnowledgeEntity, first.entity_uuid)
    assert item.knowledge_entity_id == entity.uuid and item.data_version == 1
    assert item.raw_data is None and item.category == "Weapon"
    assert db.query(KnowledgeExternalMapping).filter_by(entity_type_id="item", external_id="111").one().entity_uuid == entity.uuid
    assert entity.search_metadata.normalized_name == "magic sword"
    assert {alias.normalized_alias for alias in entity.aliases} == {"magic sword"}

    unchanged = _apply_detail(db, fixture("tibiawiki_item_detail.json"))
    assert unchanged.status == "unchanged" and item.data_version == 1
    changed = fixture("tibiawiki_item_detail.json")
    changed["parse"]["wikitext"]["*"] = changed["parse"]["wikitext"]["*"].replace("| attack = 48", "| attack = 49")
    assert _apply_detail(db, changed).status == "updated"
    assert item.attack == 49 and item.data_version == 2



def test_item_explicit_empty_list_clears_stale_bridge_value(db, item_registry):
    _apply_detail(db, fixture("tibiawiki_item_detail.json"))
    item = db.query(Item).one()

    assert item.buy_from == [
        {"name": "A Sweaty Cyclops", "price": None, "location": None}
    ]
    assert item.data_version == 1

    raw = fixture("tibiawiki_item_detail.json")
    raw["parse"]["wikitext"]["*"] = raw["parse"]["wikitext"]["*"].replace(
        "| buyfrom = [[A Sweaty Cyclops]]",
        "| buyfrom = --",
    )

    applied = _apply_detail(db, raw)

    assert applied.status == "updated"
    assert item.buy_from == []
    assert item.sell_to == [
        {"name": "Rashid", "price": None, "location": None}
    ]
    assert item.data_version == 2


def test_item_partial_missing_and_protected_fields_do_not_erase_good_values(db, item_registry):
    _apply_detail(db, fixture("tibiawiki_item_detail.json"))
    item = db.query(Item).one()
    item.protected_fields = ["attack"]
    raw = fixture("tibiawiki_item_detail.json")
    raw["parse"]["wikitext"]["*"] = raw["parse"]["wikitext"]["*"].replace("| attack = 48", "| attack = 60")
    _apply_detail(db, raw)
    assert item.attack == 48
    prior_description = item.description
    _apply_detail(db, fixture("tibiawiki_item_partial.json"))
    assert item.description == prior_description and item.attack == 48


def test_item_exact_match_reuses_entity_but_fuzzy_name_and_other_types_do_not(db, item_registry):
    exact = KnowledgeEntityService.create(
        db,
        KnowledgeEntityCreate(entity_type="item", canonical_name="Magic Sword", language_neutral_id="item:legacy:magic-sword"),
    )
    fuzzy = KnowledgeEntityService.create(
        db,
        KnowledgeEntityCreate(entity_type="item", canonical_name="Magic Sword Replica", language_neutral_id="item:legacy:replica"),
    )
    creature = KnowledgeEntityService.create(
        db,
        KnowledgeEntityCreate(entity_type="creature", canonical_name="Demon Shield", language_neutral_id="creature:legacy:demon-shield"),
    )
    db.flush()
    first = _apply_detail(db, fixture("tibiawiki_item_detail.json"))
    second = _apply_detail(db, _variant_raw(external_id=222, title="Demon Shield", game_item_id=3420, canonical_name="Demon Shield"))
    assert first.entity_uuid == exact.uuid and first.entity_uuid != fuzzy.uuid
    assert second.entity_uuid != creature.uuid


def test_same_name_distinct_provider_pages_remain_distinct_variants(db, item_registry):
    first = _apply_detail(db, fixture("tibiawiki_item_detail.json"))
    variant = _apply_detail(db, _variant_raw(external_id=333, title="Magic Sword (Charged)", game_item_id=3289))
    third = _apply_detail(db, _variant_raw(external_id=444, title="Magic Sword (Tier 2)", game_item_id=3290))
    db.flush()
    assert len({first.entity_uuid, variant.entity_uuid, third.entity_uuid}) == 3
    assert db.query(KnowledgeEntity).filter_by(entity_type="item", canonical_name="Magic Sword").count() == 3
    assert db.query(Item).filter_by(name="Magic Sword").count() == 3
    assert db.get(KnowledgeEntity, variant.entity_uuid).slug.endswith("-333")


def test_unique_approved_alias_is_an_exact_identity_match(db, item_registry):
    entity = KnowledgeEntityService.create(
        db,
        KnowledgeEntityCreate(
            entity_type="item",
            canonical_name="Bright Sword",
            language_neutral_id="item:legacy:bright-sword",
            aliases=["Magic Sword"],
        ),
    )
    applied = _apply_detail(db, fixture("tibiawiki_item_detail.json"))
    assert applied.entity_uuid == entity.uuid


def test_item_alias_collision_is_reported_instead_of_guessed(db, item_registry):
    KnowledgeEntityService.create(
        db,
        KnowledgeEntityCreate(
            entity_type="item",
            canonical_name="Replica",
            language_neutral_id="item:legacy:replica",
            aliases=["Magic Sword (Replica)"],
        ),
    )
    raw = fixture("tibiawiki_item_detail.json")
    raw["parse"]["pageid"] = 555
    raw["parse"]["title"] = "Magic Sword (Replica)"
    with pytest.raises(DuplicateKnowledgeEntityError):
        _apply_detail(db, raw)


def test_drop_relationship_resolves_deduplicates_and_retains_unresolved(db, item_registry):
    demon_entity = KnowledgeEntityService.create(
        db,
        KnowledgeEntityCreate(entity_type="creature", canonical_name="Demon", language_neutral_id="creature:legacy:demon"),
    )
    db.add(
        Creature(
            name="Demon",
            normalized_name="demon",
            slug="demon",
            hitpoints=8200,
            experience=6000,
            knowledge_entity_id=demon_entity.uuid,
        )
    )
    db.flush()
    applied = _apply_detail(db, fixture("tibiawiki_item_detail.json"))
    _apply_detail(db, fixture("tibiawiki_item_detail.json"))
    relationships = db.query(KnowledgeRelationship).filter(
        KnowledgeRelationship.is_current.is_(True),
        KnowledgeRelationship.relationship_type_code.in_(("drops", "dropped_by")),
        (KnowledgeRelationship.source_entity_id == applied.entity_uuid)
        | (KnowledgeRelationship.target_entity_id == applied.entity_uuid),
    ).all()
    assert len(relationships) == 2
    demon = next(row for row in relationships if row.target_entity_id == applied.entity_uuid)
    ferumbras = next(row for row in relationships if row.unresolved_name == "Ferumbras")
    assert demon.resolution_state == "resolved" and demon.source_entity_id == demon_entity.uuid
    assert ferumbras.resolution_state == "unresolved" and ferumbras.target_entity_id is None
    assert demon.source_context["direction"] == "item_dropped_by"
    assert db.query(KnowledgeCreatureItemDrop).count() == 0


def _npc_entity(db, name: str, *, suffix: str = "one") -> KnowledgeEntity:
    entity = KnowledgeEntityService.create(
        db,
        KnowledgeEntityCreate(
            entity_type="npc", canonical_name=name,
            language_neutral_id=f"npc:test:{normalize_name(name)}:{suffix}",
            allow_name_collision=suffix != "one", slug_suffix=suffix if suffix != "one" else None,
        ),
    )
    db.add(TibiaWikiNpc(
        name=name, normalized_name=normalize_name(name), slug=entity.slug,
        external_id=f"npc-{normalize_name(name)}-{suffix}", source_name="tibiawiki",
        knowledge_entity_id=entity.uuid, supplied_fields=[], protected_fields=[],
    ))
    db.flush()
    return entity


def test_item_trade_graph_direction_resolution_ambiguity_provenance_and_full_replay(db, item_registry):
    seller = _npc_entity(db, "Captain Bluebear")
    buyer = _npc_entity(db, "Rashid")
    _npc_entity(db, "Shared Trader")
    _npc_entity(db, "Shared Trader", suffix="two")
    raw = fixture("tibiawiki_item_detail.json")
    raw["parse"]["wikitext"]["*"] = raw["parse"]["wikitext"]["*"].replace(
        "| buyfrom = [[A Sweaty Cyclops]]",
        "| buyfrom = Captain Bluebear: 1000, Missing Seller",
    ).replace(
        "| sellto = [[Rashid]]",
        "| sellto = Rashid: 6400, Shared Trader",
    )
    first = _apply_detail(db, raw)
    second = _apply_detail(db, raw)
    assert second.entity_uuid == first.entity_uuid
    relationships = db.query(KnowledgeRelationship).filter(
        KnowledgeRelationship.source_entity_id == first.entity_uuid,
        KnowledgeRelationship.relationship_type_code.in_(("sold_by_npc", "bought_by_npc")),
        KnowledgeRelationship.is_current.is_(True),
    ).all()
    assert len(relationships) == 4
    by_name = {
        row.target_entity.canonical_name if row.target_entity else row.unresolved_name: row
        for row in relationships
    }
    assert by_name["Captain Bluebear"].relationship_type_code == "sold_by_npc"
    assert by_name["Captain Bluebear"].target_entity_id == seller.uuid
    assert by_name["Rashid"].relationship_type_code == "bought_by_npc"
    assert by_name["Rashid"].target_entity_id == buyer.uuid
    assert by_name["Rashid"].source_context["price"] == 6400
    assert by_name["Rashid"].source_context["currency"] == "gold_coin"
    assert by_name["Missing Seller"].resolution_state == "unresolved"
    assert by_name["Shared Trader"].resolution_state == "ambiguous"
    assert len(by_name["Shared Trader"].source_context["candidate_entity_ids"]) == 2
    assert all(row.source_context["source_document_ref"] == "item:111" for row in relationships)


def test_trade_graph_preserves_multiple_qualified_offers_without_arbitrary_price(db, item_registry):
    _npc_entity(db, "Sandra")
    raw = fixture("tibiawiki_item_detail.json")
    raw["parse"]["wikitext"]["*"] = raw["parse"]["wikitext"]["*"].replace(
        "| buyfrom = [[A Sweaty Cyclops]]",
        "| buyfrom = Sandra: 10;urine, Sandra: 20;oil, Sandra;water",
    ).replace("| sellto = [[Rashid]]", "| sellto = --")
    applied = _apply_detail(db, raw)
    relation = db.query(KnowledgeRelationship).filter_by(
        source_entity_id=applied.entity_uuid,
        relationship_type_code="sold_by_npc",
        is_current=True,
    ).one()
    assert relation.source_context["price"] is None
    assert relation.source_context["currency"] is None
    assert relation.source_context["offers"] == [
        {"price": 10, "currency": "gold_coin", "location": None, "qualifier": "urine"},
        {"price": 20, "currency": "gold_coin", "location": None, "qualifier": "oil"},
        {"price": None, "currency": None, "location": None, "qualifier": "water"},
    ]


def test_historical_npc_trade_repair_is_bounded_resumable_and_idempotent(db, item_registry):
    _npc_entity(db, "Captain Bluebear")
    _npc_entity(db, "Rashid")
    raw = fixture("tibiawiki_item_detail.json")
    raw["parse"]["wikitext"]["*"] = raw["parse"]["wikitext"]["*"].replace(
        "| buyfrom = [[A Sweaty Cyclops]]",
        "| buyfrom = Captain Bluebear: 1,000",
    )
    _apply_detail(db, raw)
    KnowledgeDocumentStore.persist(db, KnowledgeDocumentCreate(
        provider_id="tibiawiki",
        provider_document_id="item:111",
        raw_json=raw,
        metadata={"document_kind": "item_detail", "knowledge_job_id": str(uuid4())},
    ))
    db.query(KnowledgeRelationship).filter(
        KnowledgeRelationship.relationship_type_code.in_(("sold_by_npc", "bought_by_npc")),
    ).delete(synchronize_session=False)
    db.flush()

    first = NpcTradeRelationshipRepairService.run_batch(db, limit=1)
    assert first.processed_items == 1 and first.skipped_items == 0
    rows = db.query(KnowledgeRelationship).filter(
        KnowledgeRelationship.relationship_type_code.in_(("sold_by_npc", "bought_by_npc")),
        KnowledgeRelationship.is_current.is_(True),
    ).all()
    assert len(rows) == 2
    assert all(row.source_document_id is not None for row in rows)

    second = NpcTradeRelationshipRepairService.run_batch(db, limit=1)
    assert second.next_item_id == first.next_item_id
    assert db.query(KnowledgeRelationship).filter(
        KnowledgeRelationship.relationship_type_code.in_(("sold_by_npc", "bought_by_npc")),
        KnowledgeRelationship.is_current.is_(True),
    ).count() == 2


def test_ambiguous_item_variant_relationship_is_not_guessed(db, item_registry):
    _apply_detail(db, fixture("tibiawiki_item_detail.json"))
    _apply_detail(db, _variant_raw(external_id=333, title="Magic Sword (Charged)", game_item_id=3289))
    _apply_detail(db, fixture("tibiawiki_item_detail.json"))
    demon_entity = KnowledgeEntityService.create(
        db,
        KnowledgeEntityCreate(entity_type="creature", canonical_name="Demon", language_neutral_id="creature:test:demon"),
    )
    from app.knowledge.services.item_relationships import upsert_drop_relationship

    relationship = upsert_drop_relationship(
        db,
        provider_id="tibiawiki",
        creature_name="Demon",
        item_name="Magic Sword",
        creature_entity_uuid=demon_entity.uuid,
        source_document_id="creature:test",
        source_direction="creature_drops",
    ).relationship
    assert relationship.resolution_state == "ambiguous" and relationship.target_entity_id is None


def worker_database():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory.begin() as db:
        EntityTypeRegistry.register_initial(db)
        ProviderRegistry.register_initial(db)
        provider = db.get(KnowledgeProvider, "tibiawiki")
        provider.enabled = True
        provider.health = "unknown"
        provider.rate_limit = {}
    return engine, factory


def test_end_to_end_item_catalog_persists_raw_cursor_and_idempotent_children():
    engine, factory = worker_database()
    fixture_client = FixtureItemClient()
    adapters = KnowledgeAdapterRegistry((TibiaWikiItemAdapter(fixture_client),))
    with factory.begin() as db:
        parent_id = KnowledgeJobService.enqueue(
            db,
            EnqueueKnowledgeJob(
                provider_id="tibiawiki",
                job_type="item_catalog",
                entity_type="item",
                scope={"batch_limit": 2},
                trigger="manual",
            ),
        ).job.id
    worker = KnowledgeWorker(
        worker_id="item-fixture-worker",
        lease_seconds=60,
        poll_seconds=0.1,
        max_idle_seconds=1,
        session_factory=factory,
        adapters=adapters,
    )
    assert worker.run_once() is True
    with factory() as db:
        parent = db.get(KnowledgeJob, parent_id)
        assert parent.state == "succeeded" and parent.attempts[0].metrics["child_jobs_enqueued"] == 3
        assert db.query(KnowledgeJob).filter_by(parent_job_id=parent_id).count() == 3
        assert db.query(KnowledgeDocument).count() == 1
        assert db.query(KnowledgeProviderCursor).one().cursor["continuation"]
    assert worker.run_once() is True
    with factory() as db:
        assert db.query(Item).filter(Item.knowledge_entity_id.isnot(None)).count() == 1
        assert db.query(KnowledgeDocument).count() == 2
    engine.dispose()


def test_item_renormalize_uses_stored_document_without_network():
    engine, factory = worker_database()
    client = FixtureItemClient()
    worker = KnowledgeWorker(
        worker_id="item-renormalize-worker",
        lease_seconds=60,
        poll_seconds=0.1,
        max_idle_seconds=1,
        session_factory=factory,
        adapters=KnowledgeAdapterRegistry((TibiaWikiItemAdapter(client),)),
    )
    with factory.begin() as db:
        KnowledgeJobService.enqueue(
            db,
            EnqueueKnowledgeJob(
                provider_id="tibiawiki",
                job_type="item_detail",
                entity_type="item",
                payload={"external_id": "111", "page_title": "Magic Sword"},
            ),
        )
    worker.run_once()
    with factory.begin() as db:
        renormalize_id = KnowledgeJobService.enqueue(
            db,
            EnqueueKnowledgeJob(
                provider_id="tibiawiki",
                job_type="item_renormalize",
                entity_type="item",
                payload={"external_id": "111"},
                trigger="renormalize",
            ),
        ).job.id
    worker.run_once()
    with factory() as db:
        assert db.get(KnowledgeJob, renormalize_id).state == "succeeded"
        assert db.query(KnowledgeDocument).count() == 1
    assert client.detail_calls == 1
    engine.dispose()


def test_local_item_api_is_paginated_network_free_and_available_when_provider_is_down(client, db, item_registry, monkeypatch):
    _apply_detail(db, fixture("tibiawiki_item_detail.json"))
    _apply_detail(db, _variant_raw(external_id=222, title="Demon Shield", game_item_id=3420, canonical_name="Demon Shield"))
    provider = db.get(KnowledgeProvider, "tibiawiki")
    provider.enabled = False
    provider.health = "unavailable"
    db.commit()

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("provider network access occurred during a local item read")

    monkeypatch.setattr("app.knowledge.adapters.tibiawiki_creatures.HttpTibiaWikiCreatureClient._request", fail_if_called)
    first = client.get("/api/v1/items/?skip=0&limit=1")
    second = client.get("/api/v1/items/?skip=1&limit=1")
    detail = client.get("/api/v1/items/magic-sword")
    missing = client.get("/api/v1/items/not-a-real-item")
    assert first.status_code == 200 and len(first.json()) == 1
    assert second.status_code == 200 and len(second.json()) == 1
    assert first.json()[0]["item_name"] != second.json()[0]["item_name"]
    assert detail.status_code == 200 and detail.json()["knowledge_entity_id"]
    assert detail.json()["canonical_id"] == detail.json()["knowledge_entity_id"]
    assert detail.json()["source_provider"] == "tibiawiki"
    assert detail.json()["tradeable"] is True
    assert "tradeable" in detail.json()["supplied_fields"]
    assert missing.status_code == 404


def test_item_admin_controls_require_admin_confirmation_and_audit(client, db, item_registry):
    admin = make_user(db, username="item-knowledge-admin", is_superuser=True)
    member = make_user(db, username="item-knowledge-member")
    db.commit()
    admin_headers = {"Authorization": f"Bearer {create_access_token(admin.username)}"}
    member_headers = {"Authorization": f"Bearer {create_access_token(member.username)}"}
    payload = {
        "provider_id": "tibiawiki",
        "job_type": "item_catalog",
        "entity_type": "item",
        "scope": {"batch_limit": 2},
        "payload": {},
    }
    assert client.post("/api/v1/admin/knowledge/jobs", headers=member_headers, json=payload).status_code == 403
    assert client.post("/api/v1/admin/knowledge/jobs", headers=admin_headers, json=payload).status_code == 400
    payload["confirm_catalog_sync"] = True
    created = client.post("/api/v1/admin/knowledge/jobs", headers=admin_headers, json=payload)
    assert created.status_code == 201 and created.json()["item"]["job_type"] == "item_catalog"
    assert db.query(WorkspaceAudit).filter_by(action="knowledge_job_enqueued").count() == 1


def test_placeholder_amount_item_name_is_not_normalized():
    adapter = TibiaWikiItemAdapter(
        FixtureItemClient()
    )

    raw = _variant_raw(
        external_id=999,
        title="Malformed Placeholder",
        game_item_id=999,
        canonical_name="1-?",
    )

    normalized = adapter.normalize(
        _document(raw),
        normalization_context(),
    )

    assert normalized.action == "noop"
    assert normalized.warnings == (
        "invalid_item_placeholder_name",
    )
