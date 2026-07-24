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
    KnowledgeAdapterRegistry,
    KnowledgeDocumentDTO,
    KnowledgeFetchRequest,
    KnowledgeFetchResult,
    KnowledgeNormalizationContext,
    TibiaWikiQuestAdapter,
)
from app.knowledge.adapters.tibiawiki_quests import MAX_QUEST_PAYLOAD_BYTES
from app.knowledge.dto import QuestKnowledgeDTO
from app.knowledge.models import (
    KnowledgeAccess,
    KnowledgeEntity,
    KnowledgeExternalMapping,
    KnowledgeProvider,
    KnowledgeProviderCursor,
    KnowledgeDocument,
    KnowledgeJob,
    KnowledgeQuestRelation,
    KnowledgeRelationship,
)
from app.knowledge.registry import EntityTypeRegistry, ProviderRegistry
from app.knowledge.schemas import KnowledgeEntityCreate
from app.knowledge.services import EnqueueKnowledgeJob, KnowledgeEntityService, KnowledgeJobService
from app.knowledge.services.normalization import KnowledgeNormalizationService
from app.knowledge.workers.knowledge_worker import KnowledgeWorker
from app.models import Creature, Item, QuestMission, TibiaWikiQuest
from app.models.workspace_audit import WorkspaceAudit
from tests.conftest import make_user


FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class FixtureQuestClient:
    def fetch_catalog(self, *, continuation: str | None, limit: int) -> dict:
        raw = fixture("tibiawiki_quest_catalog.json")
        if continuation:
            raw.pop("continue", None)
            raw["query"]["categorymembers"] = [{"pageid": 702, "ns": 0, "title": "Calassa Quest"}]
        return raw

    def fetch_detail(self, *, external_id: str | None, page_title: str | None) -> dict:
        raw = fixture("tibiawiki_quest_detail.json")
        if external_id:
            raw["parse"]["pageid"] = int(external_id)
        if page_title:
            raw["parse"]["title"] = page_title
        return raw


def request(job_type: str, *, scope: dict | None = None, payload: dict | None = None) -> KnowledgeFetchRequest:
    return KnowledgeFetchRequest(
        job_id=uuid4(), attempt_id=uuid4(), correlation_id=uuid4(), provider_code="tibiawiki",
        job_type=job_type, entity_type="quest", scope=scope or {}, payload=payload or {},
    )


def context() -> KnowledgeNormalizationContext:
    return KnowledgeNormalizationContext(
        job_id=uuid4(), attempt_id=uuid4(), correlation_id=uuid4(),
        provider_code="tibiawiki", entity_type="quest",
    )


@pytest.fixture
def quest_registry(db):
    EntityTypeRegistry.register_initial(db)
    ProviderRegistry.register_initial(db)
    provider = db.get(KnowledgeProvider, "tibiawiki")
    provider.enabled = True
    provider.health = "unknown"
    provider.rate_limit = {}
    db.flush()


def detail_document(raw: dict) -> KnowledgeDocumentDTO:
    return KnowledgeDocumentDTO(
        "tibiawiki", f"quest:{raw['parse']['pageid']}", raw,
        metadata={"document_kind": "quest_detail"},
    )


def apply_detail(db, raw: dict):
    adapter = TibiaWikiQuestAdapter(FixtureQuestClient())
    return KnowledgeNormalizationService.apply(db, adapter.normalize(detail_document(raw), context()))


def entity(db, entity_type: str, name: str, suffix: str = "") -> KnowledgeEntity:
    return KnowledgeEntityService.create(db, KnowledgeEntityCreate(
        entity_type=entity_type, canonical_name=name,
        language_neutral_id=f"{entity_type}:test:{name}:{suffix}",
        allow_name_collision=bool(suffix), slug_suffix=suffix or None,
    ))


def test_quest_catalog_is_bounded_paginated_and_preserves_unknown_fields():
    adapter = TibiaWikiQuestAdapter(FixtureQuestClient())
    result = adapter.fetch(request("quest_catalog", scope={"batch_limit": 2}))
    assert adapter.validate(result).classification == "valid"
    assert result.documents[0].raw_json["future_catalog_field"] == {"preserved": True}
    assert [(child.job_type, child.payload.get("external_id")) for child in result.child_jobs] == [
        ("quest_detail", "700"), ("quest_detail", "701"), ("quest_catalog", None),
    ]
    assert result.cursor["continuation"].startswith("page|")
    assert all(child.allow_completed_recreate for child in result.child_jobs)


def test_quest_detail_extracts_missions_requirements_rewards_and_safe_unparsed_sections():
    adapter = TibiaWikiQuestAdapter(FixtureQuestClient())
    result = adapter.fetch(request("quest_detail", payload={"external_id": "700"}))
    assert adapter.validate(result).classification == "valid"
    dto = QuestKnowledgeDTO.from_canonical_data(adapter.normalize(result.documents[0], context()).canonical_data)
    assert dto.canonical_name == "Explorer Society Quest" and dto.minimum_level == 50
    assert [(value.name, value.amount) for value in dto.required_items] == [("Rope", 2), ("Shovel", 1)]
    assert [value.name for value in dto.rewarded_items] == ["Gold Coin", "Explorer Brooch"]
    assert [value.title for value in dto.missions] == ["Joining the Explorers", "The Calassa Expedition"]
    assert dto.missions[0].objectives == ("Obtain a recommendation.",)
    assert dto.provider_metadata["unparsed_sections"][0]["heading"] == "Historical Notes"
    assert result.documents[0].raw_json["future_envelope_field"] == "retained"


def test_quest_enqueue_and_validation_reject_unsafe_or_malformed_input():
    adapter = TibiaWikiQuestAdapter(FixtureQuestClient())
    with pytest.raises(ValueError, match="batch_limit"):
        adapter.validate_enqueue("quest_catalog", {}, {})
    with pytest.raises(ValueError, match="numeric"):
        adapter.validate_enqueue("quest_detail", {}, {"external_id": "name"})
    adapter.validate_enqueue("quest_detail", {}, {"page_title": "Explorer Society Quest"})
    malformed = KnowledgeFetchResult(documents=(KnowledgeDocumentDTO("tibiawiki", "bad", {"unexpected": True}),))
    assert adapter.validate(malformed).classification == "invalid"
    partial_doc = detail_document(fixture("tibiawiki_quest_partial.json"))
    assert adapter.validate(KnowledgeFetchResult(documents=(partial_doc,), partial=True)).classification == "partial"
    assert adapter.normalize(partial_doc, context()).action == "noop"
    unsafe = deepcopy(fixture("tibiawiki_quest_detail.json"))
    unsafe["parse"]["wikitext"]["*"] += "<script>alert(1)</script>"
    assert adapter.validate(KnowledgeFetchResult(documents=(detail_document(unsafe),))).safe_errors == ("unsafe_text",)
    oversized = KnowledgeDocumentDTO("tibiawiki", "large", {"padding": "x" * (MAX_QUEST_PAYLOAD_BYTES + 1)})
    assert adapter.validate(KnowledgeFetchResult(documents=(oversized,))).classification == "oversized"


def test_quest_normalization_is_idempotent_and_preserves_protected_or_missing_fields(db, quest_registry):
    raw = fixture("tibiawiki_quest_detail.json")
    first = apply_detail(db, raw)
    quest = db.query(TibiaWikiQuest).one()
    assert first.status == "created" and len(quest.missions) == 2 and quest.raw_data is None
    assert db.query(KnowledgeExternalMapping).filter_by(entity_type_id="quest", external_id="700").count() == 1
    version = quest.data_version
    second = apply_detail(db, raw)
    assert second.status == "unchanged" and quest.data_version == version
    quest.protected_fields = ["description"]
    quest.description = "Manual editorial text"
    changed = deepcopy(raw)
    changed["parse"]["wikitext"]["*"] = changed["parse"]["wikitext"]["*"].replace(
        "Join the Explorer Society and complete its expeditions.", "Provider replacement"
    ).replace("|summary=Earn rank", "|summary=Updated rank")
    apply_detail(db, changed)
    assert quest.description == "Manual editorial text"
    assert quest.summary.startswith("Updated rank")
    missing = deepcopy(changed)
    missing["parse"]["wikitext"]["*"] = missing["parse"]["wikitext"]["*"].replace("|summary=Updated rank and reach distant expedition sites.\n", "")
    apply_detail(db, missing)
    assert quest.summary.startswith("Updated rank")


def test_quest_identity_keeps_same_name_provider_variants_separate(db, quest_registry):
    raw = fixture("tibiawiki_quest_detail.json")
    first = apply_detail(db, raw)
    variant = deepcopy(raw); variant["parse"]["pageid"] = 1700
    second = apply_detail(db, variant)
    assert first.entity_uuid != second.entity_uuid
    assert db.query(KnowledgeEntity).filter_by(entity_type="quest", canonical_name="Explorer Society Quest").count() == 2
    assert apply_detail(db, variant).entity_uuid == second.entity_uuid


def test_relationships_resolve_exactly_retain_ambiguity_and_create_access(db, quest_registry):
    rope = entity(db, "item", "Rope")
    item_one = entity(db, "item", "Shovel")
    item_two = entity(db, "item", "Shovel", "variant")
    demon = entity(db, "creature", "Demon")
    boss = entity(db, "creature", "Ferumbras")
    db.add_all([
        Item(name="Rope", normalized_name="rope", knowledge_entity_id=rope.uuid),
        Item(name="Shovel", normalized_name="shovel", knowledge_entity_id=item_one.uuid),
        Creature(name="Demon", normalized_name="demon", knowledge_entity_id=demon.uuid, hitpoints=100, experience=100, is_boss=False),
        Creature(name="Ferumbras", normalized_name="ferumbras", knowledge_entity_id=boss.uuid, hitpoints=100, experience=100, is_boss=True),
    ])
    db.flush()
    applied = apply_detail(db, fixture("tibiawiki_quest_detail.json"))
    relations = db.query(KnowledgeRelationship).filter_by(source_entity_id=applied.entity_uuid, is_current=True).all()
    by_name = {(row.relationship_type_code, row.target_entity.canonical_name if row.target_entity else row.unresolved_name): row for row in relations}
    assert by_name[("requires_item", "Rope")].target_entity_id == rope.uuid
    assert by_name[("requires_item", "Shovel")].resolution_state == "ambiguous"
    assert by_name[("involves_creature", "Demon")].target_entity_id == demon.uuid
    assert by_name[("involves_boss", "Ferumbras")].target_entity_id == boss.uuid
    assert by_name[("starts_at_npc", "Angus")].resolution_state == "unresolved"
    assert by_name[("occurs_at_location", "Port Hope")].resolution_state == "unresolved"
    assert by_name[("unlocks_access", "Calassa Access")].resolution_state == "resolved"
    assert db.query(KnowledgeAccess).one().canonical_name == "Calassa Access"
    count = len(relations)
    apply_detail(db, fixture("tibiawiki_quest_detail.json"))
    assert db.query(KnowledgeRelationship).filter_by(source_entity_id=applied.entity_uuid, is_current=True).count() == count
    assert db.query(KnowledgeQuestRelation).count() == 0
    assert item_two.uuid != item_one.uuid


def test_local_quest_api_orders_missions_filters_and_never_needs_network(client, db, quest_registry, monkeypatch):
    npc = entity(db, "npc", "Angus")
    town = entity(db, "town", "Port Hope")
    apply_detail(db, fixture("tibiawiki_quest_detail.json")); db.commit()
    monkeypatch.setattr("requests.sessions.Session.request", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("network forbidden")))
    listed = client.get("/api/v1/quests/", params={"category": "Exploration", "level": 50, "premium": True})
    assert listed.status_code == 200 and listed.json()[0]["name"] == "Explorer Society Quest"
    detail = client.get("/api/v1/quests/explorer-society-quest")
    assert detail.status_code == 200
    payload = detail.json()
    assert [mission["sequence"] for mission in payload["missions"]] == [1, 2]
    resolved = {
        (relationship["relation_type"], relationship["target_name"]): relationship
        for relationship in payload["relationships"]
        if relationship["resolution_status"] == "resolved"
    }
    assert resolved[("starts_at_npc", "Angus")]["target_slug"] == npc.slug
    assert resolved[("occurs_at_location", "Port Hope")]["target_slug"] == town.slug
    assert resolved[("occurs_at_location", "Port Hope")]["target_entity_type"] == "town"
    assert "raw_data" not in payload and "wikitext" not in json.dumps(payload).lower()
    assert client.get("/api/v1/quests/not-present").status_code == 404


def worker_database():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory.begin() as db:
        EntityTypeRegistry.register_initial(db); ProviderRegistry.register_initial(db)
        provider = db.get(KnowledgeProvider, "tibiawiki")
        provider.enabled = True; provider.health = "unknown"; provider.rate_limit = {}
    return engine, factory


def test_end_to_end_quest_catalog_persists_cursor_and_idempotent_detail_children():
    engine, factory = worker_database()
    client = FixtureQuestClient()
    worker = KnowledgeWorker(
        worker_id="quest-fixture-worker", lease_seconds=60, poll_seconds=0.1, max_idle_seconds=1,
        session_factory=factory,
        adapters=KnowledgeAdapterRegistry((TibiaWikiQuestAdapter(client),)),
    )
    with factory.begin() as db:
        parent_id = KnowledgeJobService.enqueue(db, EnqueueKnowledgeJob(
            provider_id="tibiawiki", job_type="quest_catalog", entity_type="quest",
            scope={"batch_limit": 2}, trigger="manual",
        )).job.id
    assert worker.run_once() is True
    with factory() as db:
        parent = db.get(KnowledgeJob, parent_id)
        assert parent.state == "succeeded" and parent.attempts[0].metrics["child_jobs_enqueued"] == 3
        assert db.query(KnowledgeJob).filter_by(parent_job_id=parent_id).count() == 3
        assert db.query(KnowledgeDocument).count() == 1
        assert db.query(KnowledgeProviderCursor).one().cursor["continuation"]
    assert worker.run_once() is True
    with factory() as db:
        assert db.query(TibiaWikiQuest).filter(TibiaWikiQuest.knowledge_entity_id.isnot(None)).count() == 1
        assert db.query(QuestMission).count() == 2
        assert db.query(KnowledgeDocument).count() == 2
    engine.dispose()


def test_quest_renormalize_reuses_immutable_document_without_network():
    engine, factory = worker_database()
    fixture_client = FixtureQuestClient()
    worker = KnowledgeWorker(
        worker_id="quest-renormalize-worker", lease_seconds=60, poll_seconds=0.1, max_idle_seconds=1,
        session_factory=factory,
        adapters=KnowledgeAdapterRegistry((TibiaWikiQuestAdapter(fixture_client),)),
    )
    with factory.begin() as db:
        KnowledgeJobService.enqueue(db, EnqueueKnowledgeJob(
            provider_id="tibiawiki", job_type="quest_detail", entity_type="quest",
            payload={"external_id": "700", "page_title": "Explorer Society Quest"},
        ))
    worker.run_once()
    with factory.begin() as db:
        renormalize_id = KnowledgeJobService.enqueue(db, EnqueueKnowledgeJob(
            provider_id="tibiawiki", job_type="quest_renormalize", entity_type="quest",
            payload={"external_id": "700"}, trigger="renormalize",
        )).job.id
    worker.run_once()
    with factory() as db:
        assert db.get(KnowledgeJob, renormalize_id).state == "succeeded"
        assert db.query(KnowledgeDocument).count() == 1
    engine.dispose()


def test_quest_admin_enqueue_requires_admin_confirmation_and_writes_audit(client, db, quest_registry):
    admin = make_user(db, username="quest-knowledge-admin", is_superuser=True)
    member = make_user(db, username="quest-knowledge-member")
    db.commit()
    admin_headers = {"Authorization": f"Bearer {create_access_token(admin.username)}"}
    member_headers = {"Authorization": f"Bearer {create_access_token(member.username)}"}
    payload = {
        "provider_id": "tibiawiki", "job_type": "quest_catalog", "entity_type": "quest",
        "scope": {"batch_limit": 2}, "payload": {},
    }
    assert client.post("/api/v1/admin/knowledge/jobs", headers=member_headers, json=payload).status_code == 403
    assert client.post("/api/v1/admin/knowledge/jobs", headers=admin_headers, json=payload).status_code == 400
    payload["confirm_catalog_sync"] = True
    response = client.post("/api/v1/admin/knowledge/jobs", headers=admin_headers, json=payload)
    assert response.status_code == 201 and response.json()["item"]["job_type"] == "quest_catalog"
    assert db.query(WorkspaceAudit).filter_by(action="knowledge_job_enqueued").count() == 1
