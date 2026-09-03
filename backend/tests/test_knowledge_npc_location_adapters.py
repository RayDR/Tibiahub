from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.hunt_zones import _zone_access
from app.core.security import create_access_token
from app.db.database import Base
from app.knowledge.adapters import (
    KnowledgeAdapterRegistry, KnowledgeDocumentDTO, KnowledgeFetchRequest, KnowledgeNormalizationContext,
    TibiaWikiLocationAdapter, TibiaWikiNpcAdapter,
)
from app.knowledge.dto import LocationKnowledgeDTO, NpcKnowledgeDTO
from app.knowledge.models import (
    KnowledgeDocument, KnowledgeEntity, KnowledgeExternalMapping, KnowledgeJob, KnowledgeProvider, KnowledgeRelationship,
)
from app.knowledge.registry import EntityTypeRegistry, ProviderRegistry
from app.knowledge.schemas import KnowledgeEntityCreate
from app.knowledge.services import EnqueueKnowledgeJob, KnowledgeEntityService, KnowledgeGraphService, KnowledgeJobService
from app.knowledge.services.graph import RelationshipInput
from app.knowledge.services.npc_location_normalization import sync_access_destination
from app.knowledge.services.failures import InvalidNormalizationContractError
from app.knowledge.services.normalization import KnowledgeNormalizationService
from app.knowledge.workers.knowledge_worker import KnowledgeWorker
from app.models import TibiaWikiLocation, TibiaWikiNpc
from app.models.workspace_audit import WorkspaceAudit
from app.knowledge.adapters.tibiawiki_npcs_locations import HttpTibiaWikiNamedEntityClient
from app.knowledge.adapters.tibiawiki_npcs_locations import NPC_CATALOG_CONTINUATION_PRIORITY
from tests.conftest import make_user


FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class FixtureClient:
    def __init__(self, kind: str):
        self.kind = kind

    def fetch_catalog(self, *, continuation: str | None, limit: int) -> dict:
        value = fixture(f"tibiawiki_{self.kind}_catalog.json")
        if continuation:
            value.pop("continue", None)
            value["query"]["categorymembers"] = []
        return value

    def fetch_detail(self, *, external_id: str | None, page_title: str | None) -> dict:
        value = fixture(f"tibiawiki_{self.kind}_detail.json")
        if external_id:
            value["parse"]["pageid"] = int(external_id)
        if page_title:
            value["parse"]["title"] = page_title
        return value


def request(entity_type: str, suffix: str, *, scope: dict | None = None, payload: dict | None = None):
    return KnowledgeFetchRequest(
        job_id=uuid4(), attempt_id=uuid4(), correlation_id=uuid4(), provider_code="tibiawiki",
        job_type=f"{entity_type}_{suffix}", entity_type=entity_type,
        scope=scope or {}, payload=payload or {},
    )


def context(entity_type: str):
    return KnowledgeNormalizationContext(
        job_id=uuid4(), attempt_id=uuid4(), correlation_id=uuid4(),
        provider_code="tibiawiki", entity_type=entity_type,
    )


def test_default_named_entity_client_initializes_shared_http_limits():
    client = HttpTibiaWikiNamedEntityClient("NPCs")

    assert client.category == "NPCs"
    assert client.timeout_seconds == 20.0
    assert client.maximum_bytes > 0


@pytest.fixture
def named_registry(db):
    EntityTypeRegistry.register_initial(db)
    ProviderRegistry.register_initial(db)
    provider = db.get(KnowledgeProvider, "tibiawiki")
    provider.enabled = True
    provider.health = "unknown"
    provider.rate_limit = {}
    db.flush()


def detail_document(entity_type: str, raw: dict):
    return KnowledgeDocumentDTO(
        "tibiawiki", f"{entity_type}:{raw['parse']['pageid']}", raw,
        metadata={"document_kind": f"{entity_type}_detail"},
    )


def apply_detail(db, entity_type: str, raw: dict):
    adapter = TibiaWikiNpcAdapter(FixtureClient("npc")) if entity_type == "npc" else TibiaWikiLocationAdapter(FixtureClient("location"))
    normalized = adapter.normalize(detail_document(entity_type, raw), context(entity_type))
    return KnowledgeNormalizationService.apply(db, normalized)


@pytest.mark.parametrize(
    ("entity_type", "adapter", "external_ids"),
    [
        ("npc", TibiaWikiNpcAdapter(FixtureClient("npc")), ["800", "801"]),
        ("location", TibiaWikiLocationAdapter(FixtureClient("location")), ["900", "901"]),
    ],
)
def test_catalogs_are_bounded_paginated_and_preserve_raw_fields(entity_type, adapter, external_ids):
    result = adapter.fetch(request(entity_type, "catalog", scope={"batch_limit": 2}))
    assert adapter.validate(result).classification == "valid"
    assert result.documents[0].raw_json["future_catalog_field"] == {"preserved": True}
    if entity_type == "npc":
        assert [member["external_id"] for member in result.child_jobs[0].payload["members"]] == external_ids
    else:
        assert [child.payload.get("external_id") for child in result.child_jobs[:-1]] == external_ids
    assert result.child_jobs[-1].job_type == f"{entity_type}_catalog"
    assert result.cursor["continuation"]
    with pytest.raises(ValueError, match="batch_limit"):
        adapter.validate_enqueue(f"{entity_type}_catalog", {}, {})


def test_npc_catalog_prioritizes_continuation_and_rejects_non_entity_pages():
    class CatalogClient(FixtureClient):
        def fetch_catalog(self, *, continuation: str | None, limit: int) -> dict:
            return {
                "continue": {"cmcontinue": "page|NEXT"},
                "query": {"categorymembers": [
                    {"pageid": 1, "title": "NPCs"},
                    {"pageid": 2, "title": "Captain Bluebear"},
                    {"pageid": 3, "title": "..."},
                ]},
            }

    result = TibiaWikiNpcAdapter(CatalogClient("npc")).fetch(
        request("npc", "catalog", scope={"batch_limit": 3}),
    )
    assert [member["page_title"] for member in result.child_jobs[0].payload["members"]] == ["Captain Bluebear"]
    assert result.child_jobs[-1].priority == NPC_CATALOG_CONTINUATION_PRIORITY
    assert result.provider_metadata["invalid_members"] == 2


def test_npc_detail_batch_imports_multiple_immutable_documents_and_validates_bounds():
    class BatchClient(FixtureClient):
        def fetch_details(self, *, members: list[dict[str, str]]) -> dict:
            pages = []
            for index, member in enumerate(members):
                pages.append({
                    "pageid": int(member["external_id"]),
                    "title": member["page_title"],
                    "revisions": [{"slots": {"main": {"content": (
                        "{{Infobox NPC\n"
                        f"| name = {member['page_title']}\n"
                        "| job = Trader\n"
                        "| city = Thais\n"
                        "}}"
                    )}}}],
                })
            return {"query": {"pages": pages}}

    adapter = TibiaWikiNpcAdapter(BatchClient("npc"))
    members = [
        {"external_id": "800", "page_title": "First NPC"},
        {"external_id": "801", "page_title": "Second NPC"},
    ]
    adapter.validate_enqueue("npc_detail_batch", {}, {"members": members})
    result = adapter.fetch(request("npc", "detail_batch", payload={"members": members}))
    assert adapter.validate(result).valid
    assert [document.provider_document_id for document in result.documents] == ["npc:800", "npc:801"]
    assert all(document.metadata["batch_fetch"] for document in result.documents)
    with pytest.raises(ValueError, match="between 1 and 50"):
        adapter.validate_enqueue("npc_detail_batch", {}, {"members": []})


def test_npc_detail_batch_preserves_malformed_page_as_raw_only():
    class MalformedBatchClient(FixtureClient):
        def fetch_details(self, *, members: list[dict[str, str]]) -> dict:
            return {
                "query": {
                    "pages": [{
                        "pageid": int(members[0]["external_id"]),
                        "title": members[0]["page_title"],
                        "revisions": [],
                    }],
                },
            }

    adapter = TibiaWikiNpcAdapter(MalformedBatchClient("npc"))
    members = [{"external_id": "991", "page_title": "Malformed Keeper"}]
    result = adapter.fetch(request("npc", "detail_batch", payload={"members": members}))
    assert result.partial is True
    assert len(result.documents) == 1
    assert result.documents[0].provider_document_id == "npc_raw:991"
    assert result.documents[0].metadata["raw_only_reason"] == "malformed_or_insufficient_detail"
    assert adapter.validate(result).valid is True
    assert adapter.normalize(result.documents[0], context("npc")).action == "noop"


def test_npc_detail_maps_provider_fields_without_leaking_unknown_data():
    adapter = TibiaWikiNpcAdapter(FixtureClient("npc"))
    result = adapter.fetch(request("npc", "detail", payload={"external_id": "800"}))
    assert adapter.validate(result).classification == "valid"
    dto = NpcKnowledgeDTO.from_canonical_data(adapter.normalize(result.documents[0], context("npc")).canonical_data)
    assert dto.canonical_name == "Angus" and dto.location_name == "Port Hope"
    assert [value.name for value in dto.buys] == ["Explorer Brooch", "Rope"]
    assert [value.name for value in dto.destinations] == ["Northport", "Liberty Bay"]
    assert result.documents[0].raw_json["future_envelope_field"] == "retained"


def test_npc_structured_location_travel_and_moving_locations_are_preserved():
    raw = deepcopy(fixture("tibiawiki_npc_detail.json"))
    raw["parse"]["title"] = "Captain Test"
    raw["parse"]["pageid"] = 8800
    raw["parse"]["wikitext"]["*"] = """{{Infobox NPC
| name = Captain Test
| job = Ship Captain
| location = [[Thais]] boat by the harbour.
| city = Thais
| notes = {{TransportList
 |{{TransportCell|Carlin|110}}
 |{{TransportCell|Unknown Port}}
}}
}}"""
    dto = NpcKnowledgeDTO.from_canonical_data(
        TibiaWikiNpcAdapter(FixtureClient("npc")).normalize(
            detail_document("npc", raw), context("npc"),
        ).canonical_data,
    )
    assert dto.location_name == "Thais"
    assert dto.location_text == "Thais boat by the harbour."
    assert dto.location_mode == "static"
    assert [(value.name, value.price, value.currency) for value in dto.destinations] == [
        ("Carlin", 110, "gold_coin"),
        ("Unknown Port", None, None),
    ]

    raw["parse"]["title"] = "Moving Test"
    raw["parse"]["pageid"] = 8801
    raw["parse"]["wikitext"]["*"] = """{{Infobox NPC
| name = Moving Test
| job = Merchant
| location = Travels every day.
| predictloc = dynamic provider expression
| city = Svargrond
| city2 = Liberty Bay
}}"""
    moving = NpcKnowledgeDTO.from_canonical_data(
        TibiaWikiNpcAdapter(FixtureClient("npc")).normalize(
            detail_document("npc", raw), context("npc"),
        ).canonical_data,
    )
    assert moving.location_name is None and moving.location_mode == "moving"
    assert [value.name for value in moving.location_names] == ["Svargrond", "Liberty Bay"]

    raw["parse"]["title"] = "Multiple Static Test"
    raw["parse"]["pageid"] = 8802
    raw["parse"]["wikitext"]["*"] = raw["parse"]["wikitext"]["*"].replace(
        "| predictloc = dynamic provider expression\n",
        "",
    )
    multiple = NpcKnowledgeDTO.from_canonical_data(
        TibiaWikiNpcAdapter(FixtureClient("npc")).normalize(
            detail_document("npc", raw), context("npc"),
        ).canonical_data,
    )
    assert multiple.location_name is None and multiple.location_mode == "multiple"


def test_npc_provider_placeholders_are_not_named_trade_evidence():
    raw = deepcopy(fixture("tibiawiki_npc_detail.json"))
    raw["parse"]["wikitext"]["*"] = raw["parse"]["wikitext"]["*"].replace(
        "[[Explorer Brooch]], [[Rope]]", "--",
    ).replace("[[Shovel]]", "unknown")
    normalized = TibiaWikiNpcAdapter(FixtureClient("npc")).normalize(
        detail_document("npc", raw), context("npc"),
    )
    dto = NpcKnowledgeDTO.from_canonical_data(normalized.canonical_data)
    assert dto.buys == dto.sells == ()
    assert "buys" not in dto.supplied_fields and "sells" not in dto.supplied_fields


def test_npc_provider_placeholder_replay_repairs_legacy_bridge_idempotently(db, named_registry):
    apply_detail(db, "npc", fixture("tibiawiki_npc_detail.json"))
    row = db.query(TibiaWikiNpc).one()
    row.buys = [{"name": "--", "price": None}]
    row.sells = [{"name": "unknown", "price": None}]
    row.supplied_fields = sorted(set(row.supplied_fields or []) | {"buys", "sells"})
    raw = deepcopy(fixture("tibiawiki_npc_detail.json"))
    raw["parse"]["wikitext"]["*"] = raw["parse"]["wikitext"]["*"].replace(
        "[[Explorer Brooch]], [[Rope]]", "--",
    ).replace("[[Shovel]]", "unknown")
    repaired = apply_detail(db, "npc", raw)
    assert repaired.status == "updated"
    assert row.buys == row.sells == []
    assert "buys" not in row.supplied_fields and "sells" not in row.supplied_fields
    assert apply_detail(db, "npc", raw).status == "unchanged"


def test_location_detail_maps_levels_access_and_named_references():
    adapter = TibiaWikiLocationAdapter(FixtureClient("location"))
    result = adapter.fetch(request("location", "detail", payload={"external_id": "900"}))
    assert adapter.validate(result).classification == "valid"
    dto = LocationKnowledgeDTO.from_canonical_data(adapter.normalize(result.documents[0], context("location")).canonical_data)
    assert dto.canonical_name == "Port Hope" and dto.location_kind == "City" and dto.region == "Tiquanda"
    assert dto.premium_required is True and (dto.minimum_level, dto.maximum_level) == (1, 200)
    assert [value.name for value in dto.npcs] == ["Angus", "Lorek"]
    assert dto.access_notes.startswith("Travel by ship")


def test_location_detail_keeps_iksupan_recommendations_and_body_access_noncanonical():
    raw = deepcopy(fixture("tibiawiki_location_detail.json"))
    raw["parse"]["pageid"] = 1999
    raw["parse"]["title"] = "Iksupan"
    raw["parse"]["wikitext"]["*"] = """
{{Infobox Location
| name = Iksupan
| type = Hunting Place
| lvlknights = 150
| lvlpaladins = 150
| lvlmages = 150
}}
Access to Iksupan is obtained through the [[Adventures of Galthen Quest]].
"""
    adapter = TibiaWikiLocationAdapter(FixtureClient("location"))
    normalized = adapter.normalize(detail_document("location", raw), context("location"))
    dto = LocationKnowledgeDTO.from_canonical_data(normalized.canonical_data)
    assert dto.minimum_level is None
    assert "minimum_level" not in dto.supplied_fields

    assert dto.access_notes is None
    assert "access_notes" not in dto.supplied_fields

    assert dto.quests == ()
    assert "quests" not in dto.supplied_fields

    assert dto.provider_metadata["vocation_level_parameters"] == [
        "lvlknights",
        "lvlmages",
        "lvlpaladins",
    ]
    assert dto.provider_metadata["access_quest_names"] == []


def test_zone_access_keeps_legacy_false_defaults_unknown():
    zone = SimpleNamespace(requires_quest=False, quest=None, requires_premium=False, source_provider="legacy", source_url=None)
    access = _zone_access(zone, None, {})
    assert access.status == "unknown"
    assert access.minimum_level is None
    assert access.premium_required is None
    assert access.quest_required is None


def test_zone_access_projects_canonical_location_and_required_quest_evidence():
    zone = SimpleNamespace(requires_quest=False, quest=None, requires_premium=False, source_provider="legacy", source_url=None)
    location = SimpleNamespace(
        minimum_level=150,
        maximum_level=None,
        premium_required=None,
        access_notes="Access to Iksupan is obtained through the Adventures of Galthen Quest.",
        provider_metadata={"access_quest_names": ["Adventures of Galthen Quest"]},
        source_name="tibiawiki",
        source_url="https://example.test/wiki/Iksupan",
    )
    quest = SimpleNamespace(id=42, slug="adventures-of-galthen-quest", premium_required=True)
    access = _zone_access(zone, location, {"adventures of galthen quest": quest})
    assert access.status == "restricted"
    assert access.minimum_level == 150
    assert access.premium_required is True
    assert access.quest_required is True
    assert access.quests[0].slug == "adventures-of-galthen-quest"



def test_partial_location_renormalize_repairs_existing_only_without_graph_reconciliation(
    db,
    named_registry,
):
    full = _place_fixture(
        page_id=1128,
        name="Edron",
        kind="Location",
        parent="Tiquanda",
    )
    applied = apply_detail(db, "location", full)
    location = db.query(TibiaWikiLocation).one()

    relation = (
        db.query(KnowledgeRelationship)
        .filter_by(
            source_entity_id=applied.entity_uuid,
            relationship_type_code="contained_in",
            is_current=True,
        )
        .one()
    )

    location.access_notes = (
        "South of this area is the Edron Orc Cave. "
        "To access this place you need another tunnel."
    )
    location.provider_metadata = {
        "page_title": "Edron",
        "template_parameters": ["name", "type", "parent"],
        "access_quest_names": [],
        "vocation_level_parameters": [],
    }
    location.supplied_fields = [
        "canonical_name",
        "location_kind",
        "parent_location",
        "access_notes",
        "image_reference",
        "slug",
        "source_reference",
    ]
    initial_version = location.data_version
    db.flush()

    partial_raw = {
        "parse": {
            "title": "Edron",
            "pageid": 1128,
            "wikitext": {
                "*": (
                    "{{Infobox Location\n"
                    "| name = Edron\n"
                    "}}\n"
                    "South of this area is the Edron Orc Cave. "
                    "To access this place you need another tunnel."
                )
            },
        }
    }

    adapter = TibiaWikiLocationAdapter(FixtureClient("location"))

    ordinary = adapter.normalize(
        detail_document("location", partial_raw),
        context("location"),
    )
    assert ordinary.action == "noop"

    renormalize_document = KnowledgeDocumentDTO(
        "tibiawiki",
        "location:1128",
        partial_raw,
        metadata={
            "document_kind": "location_detail",
            "normalization_mode": "renormalize",
        },
    )
    normalized = adapter.normalize(
        renormalize_document,
        context("location"),
    )

    dto = LocationKnowledgeDTO.from_canonical_data(
        normalized.canonical_data
    )
    assert dto.is_partial is True
    assert normalized.action == "upsert"

    repaired = KnowledgeNormalizationService.apply(db, normalized)

    assert repaired.status == "updated"
    assert location.access_notes is None
    assert "access_notes" not in location.supplied_fields
    assert location.data_version == initial_version + 1

    # The partial source omitted parent information, so it must not
    # supersede an existing graph relationship.
    assert db.get(KnowledgeRelationship, relation.id).is_current is True


def test_partial_location_renormalize_cannot_create_new_canonical_entity(
    db,
    named_registry,
):
    raw = {
        "parse": {
            "title": "Unknown Partial Place",
            "pageid": 2999,
            "wikitext": {
                "*": (
                    "{{Infobox Location\n"
                    "| name = Unknown Partial Place\n"
                    "}}"
                )
            },
        }
    }

    adapter = TibiaWikiLocationAdapter(FixtureClient("location"))
    document = KnowledgeDocumentDTO(
        "tibiawiki",
        "location:2999",
        raw,
        metadata={
            "document_kind": "location_detail",
            "normalization_mode": "renormalize",
        },
    )

    normalized = adapter.normalize(
        document,
        context("location"),
    )

    assert normalized.action == "upsert"

    with pytest.raises(InvalidNormalizationContractError):
        KnowledgeNormalizationService.apply(db, normalized)

    assert (
        db.query(KnowledgeEntity)
        .filter_by(canonical_name="Unknown Partial Place")
        .count()
        == 0
    )


def test_normalization_is_idempotent_preserves_protected_fields_and_resolves_exact_graph_refs(db, named_registry):
    quest = KnowledgeEntityService.create(db, KnowledgeEntityCreate(
        entity_type="quest", canonical_name="Explorer Society Quest", language_neutral_id="quest:test:explorer",
    ))
    npc_ref = KnowledgeGraphService.upsert(db, RelationshipInput(
        source_entity_id=quest.uuid, source_scope="quest", relationship_type="starts_at_npc",
        target_entity_type="npc", unresolved_name="Angus", resolution_state="unresolved",
        source_provider_id="tibiawiki", source_document_ref="quest:700",
    )).relationship
    location_ref = KnowledgeGraphService.upsert(db, RelationshipInput(
        source_entity_id=quest.uuid, source_scope="quest", relationship_type="occurs_at_location",
        target_entity_type="location", unresolved_name="Port Hope", resolution_state="unresolved",
        source_provider_id="tibiawiki", source_document_ref="quest:700",
    )).relationship

    npc_applied = apply_detail(db, "npc", fixture("tibiawiki_npc_detail.json"))
    location_applied = apply_detail(db, "location", fixture("tibiawiki_location_detail.json"))
    npc = db.query(TibiaWikiNpc).one()
    location = db.query(TibiaWikiLocation).one()
    assert npc_applied.status == location_applied.status == "created"
    assert npc_applied.metrics["references_resolved"] == 1
    assert location_applied.metrics["references_resolved"] == 2
    assert not db.get(KnowledgeRelationship, npc_ref.id).is_current
    assert not db.get(KnowledgeRelationship, location_ref.id).is_current
    resolved = db.query(KnowledgeRelationship).filter(
        KnowledgeRelationship.is_current.is_(True),
        KnowledgeRelationship.resolution_state == "resolved",
    ).all()
    assert {row.target_entity_id for row in resolved} == {npc.knowledge_entity_id, location.knowledge_entity_id}
    assert db.query(KnowledgeExternalMapping).filter(
        KnowledgeExternalMapping.entity_type_id.in_(["npc", "location", "area", "town"])
    ).count() == 2
    assert location.knowledge_entity.entity_type == "town"

    npc.protected_fields = ["description"]
    npc.description = "Editorial NPC description"
    changed = deepcopy(fixture("tibiawiki_npc_detail.json"))
    changed["parse"]["wikitext"]["*"] = changed["parse"]["wikitext"]["*"].replace(
        "Angus recruits promising explorers.", "Provider replacement"
    )
    again = apply_detail(db, "npc", changed)
    assert again.status == "unchanged" and npc.description == "Editorial NPC description"
    assert apply_detail(db, "location", fixture("tibiawiki_location_detail.json")).status == "unchanged"


def test_ambiguous_exact_names_remain_unresolved(db, named_registry):
    apply_detail(db, "npc", fixture("tibiawiki_npc_detail.json"))
    KnowledgeEntityService.create(db, KnowledgeEntityCreate(
        entity_type="npc", canonical_name="Angus", language_neutral_id="npc:test:variant",
        allow_name_collision=True, slug_suffix="variant",
    ))
    quest = KnowledgeEntityService.create(db, KnowledgeEntityCreate(
        entity_type="quest", canonical_name="Test Quest", language_neutral_id="quest:test:ambiguous",
    ))
    reference = KnowledgeGraphService.upsert(db, RelationshipInput(
        source_entity_id=quest.uuid, relationship_type="references_npc", target_entity_type="npc",
        unresolved_name="Angus", resolution_state="ambiguous", source_provider_id="tibiawiki",
    )).relationship
    raw = fixture("tibiawiki_npc_detail.json")
    raw["parse"]["pageid"] = 1800
    applied = apply_detail(db, "npc", raw)
    assert applied.metrics["references_resolved"] == 0
    assert db.get(KnowledgeRelationship, reference.id).is_current


def _place_fixture(*, page_id: int, name: str, kind: str, parent: str | None = None) -> dict:
    raw = deepcopy(fixture("tibiawiki_location_detail.json"))
    raw["parse"]["pageid"] = page_id
    raw["parse"]["title"] = name
    parent_line = f"| parent = {parent}\n" if parent else ""
    raw["parse"]["wikitext"]["*"] = (
        "{{Infobox Location\n"
        f"| name = {name}\n"
        f"| type = {kind}\n"
        f"{parent_line}"
        f"| description = Local fixture for {name}.\n"
        "}}"
    )
    return raw


def test_named_places_and_access_use_canonical_entities_and_deduplicated_graph(db, named_registry):
    town = apply_detail(db, "location", _place_fixture(page_id=1900, name="Port Hope", kind="Town"))
    area = apply_detail(db, "location", _place_fixture(
        page_id=1901, name="Tiquanda", kind="Region", parent="Port Hope",
    ))
    location = apply_detail(db, "location", _place_fixture(
        page_id=1902, name="Banuta", kind="Hunting Place", parent="Tiquanda",
    ))
    npc = apply_detail(db, "npc", fixture("tibiawiki_npc_detail.json"))
    assert [db.get(KnowledgeEntity, value.entity_uuid).entity_type for value in (town, area, location, npc)] == [
        "town", "area", "location", "npc",
    ]

    access_entity = KnowledgeEntityService.create(db, KnowledgeEntityCreate(
        entity_type="access", canonical_name="Banuta passage", language_neutral_id="access:test:banuta",
    ))
    assert sync_access_destination(
        db, access_entity=access_entity, destination_name="Banuta",
        provider_id="tibiawiki", source_document_ref="quest:test",
    ) == 1
    assert sync_access_destination(
        db, access_entity=access_entity, destination_name="Banuta",
        provider_id="tibiawiki", source_document_ref="quest:test",
    ) == 1

    rows = db.query(KnowledgeRelationship).filter(
        KnowledgeRelationship.relationship_type_code.in_(["located_at", "contained_in", "leads_to"]),
        KnowledgeRelationship.is_current.is_(True),
    ).all()
    assert {(row.source_entity.entity_type, row.relationship_type_code, row.target_entity.entity_type) for row in rows} == {
        ("npc", "located_at", "town"),
        ("area", "contained_in", "town"),
        ("location", "contained_in", "area"),
        ("access", "leads_to", "location"),
    }
    assert len(rows) == 4


def test_npc_location_and_destinations_are_exact_only_replay_safe_and_reviewable(db, named_registry):
    apply_detail(db, "location", _place_fixture(page_id=2900, name="Thais", kind="Town"))
    apply_detail(db, "location", _place_fixture(page_id=2901, name="Carlin", kind="Town"))
    raw = deepcopy(fixture("tibiawiki_npc_detail.json"))
    raw["parse"]["pageid"] = 2800
    raw["parse"]["title"] = "Captain Exact"
    raw["parse"]["wikitext"]["*"] = """{{Infobox NPC
| name = Captain Exact
| job = Ship Captain
| location = [[Thais]] boat by the harbour.
| city = Thais
| notes = {{TransportList
 |{{TransportCell|Carlin|110}}
 |{{TransportCell|Almost Carlin|120}}
}}
}}"""
    first = apply_detail(db, "npc", raw)
    second = apply_detail(db, "npc", raw)
    rows = db.query(KnowledgeRelationship).filter_by(
        source_entity_id=first.entity_uuid, is_current=True,
    ).all()
    assert second.entity_uuid == first.entity_uuid
    assert len(rows) == 3
    by_name = {row.target_entity.canonical_name if row.target_entity else row.unresolved_name: row for row in rows}
    assert by_name["Thais"].relationship_type_code == "located_at"
    assert by_name["Carlin"].relationship_type_code == "travels_to"
    assert by_name["Carlin"].source_context["price"] == 110
    assert by_name["Almost Carlin"].resolution_state == "unresolved"
    assert by_name["Almost Carlin"].source_context["resolution_policy"] == "exact_name_or_alias_only"
    assert not db.query(KnowledgeRelationship).filter(
        KnowledgeRelationship.relationship_type_code.like("%hunt%"),
        KnowledgeRelationship.source_entity_id == first.entity_uuid,
    ).count()


def test_named_place_relationships_preserve_unresolved_and_ambiguous_names(db, named_registry):
    place = KnowledgeEntityService.create(db, KnowledgeEntityCreate(
        entity_type="location", canonical_name="Shared Destination",
        language_neutral_id="location:test:shared-destination",
    ))
    KnowledgeEntityService.create(db, KnowledgeEntityCreate(
        entity_type="town", canonical_name="Shared Destination",
        language_neutral_id="town:test:shared-destination",
    ))
    access = KnowledgeEntityService.create(db, KnowledgeEntityCreate(
        entity_type="access", canonical_name="Test passage", language_neutral_id="access:test:passage",
    ))
    sync_access_destination(
        db, access_entity=access, destination_name="Shared Destination",
        provider_id="tibiawiki", source_document_ref=None,
    )
    ambiguous = db.query(KnowledgeRelationship).filter_by(
        source_entity_id=access.uuid, relationship_type_code="leads_to", is_current=True,
    ).one()
    assert ambiguous.resolution_state == "ambiguous"
    assert ambiguous.unresolved_name == "Shared Destination"
    assert len(ambiguous.source_context["candidate_entity_ids"]) == 2

    sync_access_destination(
        db, access_entity=access, destination_name="Unknown Destination",
        provider_id="tibiawiki", source_document_ref=None,
    )
    unresolved = db.query(KnowledgeRelationship).filter_by(
        source_entity_id=access.uuid, relationship_type_code="leads_to", is_current=True,
    ).one()
    assert unresolved.resolution_state == "unresolved"
    assert unresolved.unresolved_name == "Unknown Destination"
    assert db.get(KnowledgeEntity, place.uuid) is place


def test_local_npc_and_location_apis_never_call_provider(client, db, named_registry, monkeypatch):
    apply_detail(db, "npc", fixture("tibiawiki_npc_detail.json"))
    apply_detail(db, "location", fixture("tibiawiki_location_detail.json"))
    db.commit()
    monkeypatch.setattr("requests.sessions.Session.request", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("network forbidden")))
    assert client.get("/api/v1/npcs/", params={"search": "Angus"}).json()[0]["name"] == "Angus"
    npc = client.get("/api/v1/npcs/angus")
    assert npc.status_code == 200 and npc.json()["occupation"] == "Recruiter"
    assert npc.json()["canonical_id"] == npc.json()["knowledge_entity_id"]
    assert npc.json()["source_provider"] == "tibiawiki"
    assert "occupation" in npc.json()["supplied_fields"]
    assert "provider_metadata" not in npc.json()
    location = client.get("/api/v1/locations/port-hope")
    assert location.status_code == 200 and location.json()["region"] == "Tiquanda"
    assert location.json()["entity_type"] == "town"
    assert location.json()["canonical_id"] == location.json()["knowledge_entity_id"]
    assert client.get("/api/v1/locations/not-present").status_code == 404


def test_admin_catalog_enqueue_requires_confirmation(client, db, named_registry):
    admin = make_user(db, username="named-knowledge-admin", is_superuser=True)
    db.commit()
    headers = {"Authorization": f"Bearer {create_access_token(admin.username)}"}
    payload = {
        "provider_id": "tibiawiki", "job_type": "npc_catalog", "entity_type": "npc",
        "scope": {"batch_limit": 2}, "payload": {},
    }
    assert client.post("/api/v1/admin/knowledge/jobs", headers=headers, json=payload).status_code == 400
    payload["confirm_catalog_sync"] = True
    response = client.post("/api/v1/admin/knowledge/jobs", headers=headers, json=payload)
    assert response.status_code == 201
    assert db.query(WorkspaceAudit).filter_by(action="knowledge_job_enqueued").count() == 1


@pytest.mark.parametrize(
    ("entity_type", "adapter", "external_id", "model"),
    [
        ("npc", TibiaWikiNpcAdapter(FixtureClient("npc")), "800", TibiaWikiNpc),
        ("location", TibiaWikiLocationAdapter(FixtureClient("location")), "900", TibiaWikiLocation),
    ],
)
def test_worker_detail_and_renormalize_reuse_one_immutable_document(entity_type, adapter, external_id, model):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory.begin() as db:
        EntityTypeRegistry.register_initial(db)
        ProviderRegistry.register_initial(db)
        provider = db.get(KnowledgeProvider, "tibiawiki")
        provider.enabled = True
        provider.health = "unknown"
        provider.rate_limit = {}
        KnowledgeJobService.enqueue(db, EnqueueKnowledgeJob(
            provider_id="tibiawiki", job_type=f"{entity_type}_detail", entity_type=entity_type,
            payload={"external_id": external_id},
        ))
    worker = KnowledgeWorker(
        worker_id=f"{entity_type}-fixture-worker", lease_seconds=60, poll_seconds=0.1,
        max_idle_seconds=1, session_factory=factory,
        adapters=KnowledgeAdapterRegistry((adapter,)),
    )
    assert worker.run_once() is True
    with factory.begin() as db:
        renormalize = KnowledgeJobService.enqueue(db, EnqueueKnowledgeJob(
            provider_id="tibiawiki", job_type=f"{entity_type}_renormalize", entity_type=entity_type,
            payload={"external_id": external_id}, trigger="renormalize",
        )).job
        renormalize_id = renormalize.id
    assert worker.run_once() is True
    with factory() as db:
        assert db.get(KnowledgeJob, renormalize_id).state == "succeeded"
        assert db.query(model).count() == 1
        assert db.query(KnowledgeDocument).count() == 1
    engine.dispose()
