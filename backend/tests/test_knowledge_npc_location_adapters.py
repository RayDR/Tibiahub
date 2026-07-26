from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

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
from app.knowledge.services.normalization import KnowledgeNormalizationService
from app.knowledge.workers.knowledge_worker import KnowledgeWorker
from app.models import TibiaWikiLocation, TibiaWikiNpc
from app.models.workspace_audit import WorkspaceAudit
from conftest import make_user


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
    assert [child.payload.get("external_id") for child in result.child_jobs[:-1]] == external_ids
    assert result.child_jobs[-1].job_type == f"{entity_type}_catalog"
    assert result.cursor["continuation"]
    with pytest.raises(ValueError, match="batch_limit"):
        adapter.validate_enqueue(f"{entity_type}_catalog", {}, {})


def test_npc_detail_maps_provider_fields_without_leaking_unknown_data():
    adapter = TibiaWikiNpcAdapter(FixtureClient("npc"))
    result = adapter.fetch(request("npc", "detail", payload={"external_id": "800"}))
    assert adapter.validate(result).classification == "valid"
    dto = NpcKnowledgeDTO.from_canonical_data(adapter.normalize(result.documents[0], context("npc")).canonical_data)
    assert dto.canonical_name == "Angus" and dto.location_name == "Port Hope"
    assert [value.name for value in dto.buys] == ["Explorer Brooch", "Rope"]
    assert [value.name for value in dto.destinations] == ["Northport", "Liberty Bay"]
    assert result.documents[0].raw_json["future_envelope_field"] == "retained"


def test_location_detail_maps_levels_access_and_named_references():
    adapter = TibiaWikiLocationAdapter(FixtureClient("location"))
    result = adapter.fetch(request("location", "detail", payload={"external_id": "900"}))
    assert adapter.validate(result).classification == "valid"
    dto = LocationKnowledgeDTO.from_canonical_data(adapter.normalize(result.documents[0], context("location")).canonical_data)
    assert dto.canonical_name == "Port Hope" and dto.location_kind == "City" and dto.region == "Tiquanda"
    assert dto.premium_required is True and (dto.minimum_level, dto.maximum_level) == (1, 200)
    assert [value.name for value in dto.npcs] == ["Angus", "Lorek"]
    assert dto.access_notes.startswith("Travel by ship")


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
    resolved = db.query(KnowledgeRelationship).filter_by(is_current=True).all()
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
    assert "provider_metadata" not in npc.json()
    location = client.get("/api/v1/locations/port-hope")
    assert location.status_code == 200 and location.json()["region"] == "Tiquanda"
    assert location.json()["entity_type"] == "town"
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
