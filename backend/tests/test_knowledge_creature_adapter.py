from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import replace
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
    KnowledgeValidationResult,
    TibiaWikiCreatureAdapter,
)
from app.knowledge.dto import CreatureKnowledgeDTO
from app.knowledge.models import (
    KnowledgeDocument,
    KnowledgeEntity,
    KnowledgeExternalMapping,
    KnowledgeJob,
    KnowledgeProvider,
    KnowledgeProviderCursor,
)
from app.knowledge.registry import EntityTypeRegistry, ProviderRegistry
from app.knowledge.schemas import KnowledgeEntityCreate
from app.knowledge.services import (
    CreatureIdentityConflictError,
    EnqueueKnowledgeJob,
    KnowledgeEntityService,
    KnowledgeJobService,
)
from app.knowledge.services.entities import DuplicateKnowledgeEntityError
from app.knowledge.services.normalization import KnowledgeNormalizationService
from app.knowledge.workers.knowledge_worker import KnowledgeWorker
from app.models import Creature
from app.models.workspace_audit import WorkspaceAudit
from app.services.bestiary_source import _build_creature_payload
from app.services.text_utils import normalize_search_text
from tests.conftest import make_user


FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class FixtureCreatureClient:
    def __init__(self):
        self.catalog_calls = 0
        self.detail_calls = 0

    def fetch_catalog(self, *, continuation: str | None, limit: int) -> dict:
        self.catalog_calls += 1
        value = fixture("tibiawiki_creature_catalog.json")
        if continuation:
            value.pop("continue", None)
            value["query"]["categorymembers"] = []
        return value

    def fetch_detail(self, *, external_id: str | None, page_title: str | None) -> dict:
        self.detail_calls += 1
        value = fixture("tibiawiki_creature_detail.json")
        if external_id == "654" or page_title == "Dragon":
            value["parse"]["pageid"] = 654
            value["parse"]["title"] = "Dragon"
            value["parse"]["wikitext"]["*"] = value["parse"]["wikitext"]["*"].replace("Demon", "Dragon")
        return value


def request(job_type: str, *, scope: dict | None = None, payload: dict | None = None) -> KnowledgeFetchRequest:
    return KnowledgeFetchRequest(
        job_id=uuid4(),
        attempt_id=uuid4(),
        correlation_id=uuid4(),
        provider_code="tibiawiki",
        job_type=job_type,
        entity_type="creature",
        scope=scope or {},
        payload=payload or {},
    )


def normalization_context() -> KnowledgeNormalizationContext:
    return KnowledgeNormalizationContext(
        job_id=uuid4(),
        attempt_id=uuid4(),
        correlation_id=uuid4(),
        provider_code="tibiawiki",
        entity_type="creature",
    )


@pytest.fixture
def creature_registry(db):
    EntityTypeRegistry.register_initial(db)
    ProviderRegistry.register_initial(db)
    provider = db.get(KnowledgeProvider, "tibiawiki")
    provider.enabled = True
    provider.health = "unknown"
    db.flush()


def test_catalog_adapter_preserves_envelope_and_creates_bounded_children():
    client = FixtureCreatureClient()
    adapter = TibiaWikiCreatureAdapter(client)
    result = adapter.fetch(request("creature_catalog", scope={"batch_limit": 2}))
    assert adapter.validate(result).valid is True
    assert result.documents[0].raw_json["future_catalog_field"] == {"preserved": True}
    assert [(child.job_type, child.payload.get("external_id")) for child in result.child_jobs] == [
        ("creature_detail", "321"),
        ("creature_detail", "654"),
        ("creature_catalog", None),
    ]
    assert result.child_jobs[-1].scope["continuation"] == "page|44454d4f4e|321"
    assert all(child.allow_completed_recreate for child in result.child_jobs)


def test_catalog_marks_invalid_members_as_partial_without_losing_valid_children():
    class PartialCatalogClient(FixtureCreatureClient):
        def fetch_catalog(self, *, continuation: str | None, limit: int) -> dict:
            value = super().fetch_catalog(continuation=continuation, limit=limit)
            value["query"]["categorymembers"].extend(
                [
                    {"pageid": None, "title": "Invalid"},
                    {"pageid": 107180, "title": "List of Creatures by Armor Value"},
                    {"pageid": 64179, "title": "List of Creatures (Ordered)"},
                ]
            )
            return value

    result = TibiaWikiCreatureAdapter(PartialCatalogClient()).fetch(
        request("creature_catalog", scope={"batch_limit": 3})
    )
    assert result.partial is True
    assert result.provider_metadata["invalid_members"] == 3
    assert [child.payload.get("external_id") for child in result.child_jobs[:2]] == ["321", "654"]


def test_adapter_requires_bounded_catalog_and_safe_stable_detail_identifiers():
    adapter = TibiaWikiCreatureAdapter(FixtureCreatureClient())
    with pytest.raises(ValueError, match="batch_limit"):
        adapter.validate_enqueue("creature_catalog", {}, {})
    with pytest.raises(ValueError, match="numeric page IDs"):
        adapter.validate_enqueue("creature_detail", {}, {"external_id": "not-a-page-id"})
    with pytest.raises(ValueError, match="safe"):
        adapter.validate_enqueue("creature_detail", {}, {"page_title": "Demon\nInjected"})
    adapter.validate_enqueue(
        "creature_detail",
        {},
        {"external_id": "321", "page_title": "Demon"},
    )


def test_detail_adapter_parses_provider_shape_into_neutral_dto_and_preserves_unknown_fields():
    adapter = TibiaWikiCreatureAdapter(FixtureCreatureClient())
    result = adapter.fetch(request("creature_detail", payload={"external_id": "321", "page_title": "Demon"}))
    validation = adapter.validate(result)
    assert validation.valid is True and validation.classification == "valid"
    document = result.documents[0]
    assert document.raw_json["future_envelope_field"] == ["preserved"]
    normalized = adapter.normalize(document, normalization_context())
    dto = CreatureKnowledgeDTO.from_canonical_data(normalized.canonical_data)
    assert dto.external_id == "321" and dto.canonical_name == "Demon"
    assert dto.hitpoints == 8200 and dto.experience == 6000 and dto.charm_points == 50
    assert dto.locations == ("Oramond Dungeon", "Goroma")
    assert dto.loot[0].item_name == "Demon Horn"


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
def test_adapter_classifies_empty_provider_error_and_malformed_envelopes(result, classification):
    validation = TibiaWikiCreatureAdapter(FixtureCreatureClient()).validate(result)
    assert validation.valid is False and validation.classification == classification


def test_adapter_classifies_partial_and_rejects_unsafe_text():
    adapter = TibiaWikiCreatureAdapter(FixtureCreatureClient())
    partial = KnowledgeFetchResult(
        documents=(
            KnowledgeDocumentDTO(
                "tibiawiki",
                "creature:321",
                fixture("tibiawiki_creature_partial.json"),
                metadata={"document_kind": "creature_detail"},
            ),
        ),
        partial=True,
    )
    assert adapter.validate(partial).classification == "partial"
    unsafe = deepcopy(partial.documents[0].raw_json)
    unsafe["parse"]["wikitext"]["*"] += "<script>alert(1)</script>"
    invalid = adapter.validate(
        KnowledgeFetchResult(
            documents=(KnowledgeDocumentDTO("tibiawiki", "creature:321", unsafe, metadata={"document_kind": "creature_detail"}),)
        )
    )
    assert invalid.valid is False and invalid.safe_errors == ("unsafe_text",)


def test_partial_detail_normalizes_identity(db, creature_registry):
    adapter = TibiaWikiCreatureAdapter(
        FixtureCreatureClient()
    )
    document = KnowledgeDocumentDTO(
        "tibiawiki",
        "creature:321",
        fixture("tibiawiki_creature_partial.json"),
        metadata={
            "document_kind": "creature_detail",
        },
    )

    normalized = adapter.normalize(
        document,
        normalization_context(),
    )

    assert normalized.action == "upsert"
    assert normalized.external_id == "321"
    assert normalized.warnings == (
        "partial_creature_detail",
    )

    dto = CreatureKnowledgeDTO.from_canonical_data(
        normalized.canonical_data
    )

    assert dto.canonical_name == "Demon"
    assert dto.is_partial is True


def test_adapter_rejects_oversized_payload():
    adapter = TibiaWikiCreatureAdapter(FixtureCreatureClient())
    huge = {"parse": {"blob": "x" * (2 * 1024 * 1024 + 1)}}
    result = KnowledgeFetchResult(documents=(KnowledgeDocumentDTO("tibiawiki", "huge", huge),))
    assert adapter.validate(result).classification == "oversized"


def test_adapter_rejects_out_of_range_numeric_values():
    raw = fixture("tibiawiki_creature_detail.json")
    raw["parse"]["wikitext"]["*"] = raw["parse"]["wikitext"]["*"].replace("8200", "-1")
    result = KnowledgeFetchResult(
        documents=(KnowledgeDocumentDTO("tibiawiki", "creature:321", raw, metadata={"document_kind": "creature_detail"}),)
    )
    validation = TibiaWikiCreatureAdapter(FixtureCreatureClient()).validate(result)
    assert validation.valid is False and validation.safe_errors == ("numeric_range",)


def _apply_detail(db, raw: dict):
    adapter = TibiaWikiCreatureAdapter(FixtureCreatureClient())
    document = KnowledgeDocumentDTO(
        "tibiawiki",
        f"creature:{raw['parse']['pageid']}",
        raw,
        metadata={"document_kind": "creature_detail"},
    )
    return KnowledgeNormalizationService.apply(db, adapter.normalize(document, normalization_context()))


def test_identity_mapping_bridge_reuses_uuid_and_versions_only_canonical_changes(db, creature_registry):
    first = _apply_detail(db, fixture("tibiawiki_creature_detail.json"))
    db.flush()
    creature = db.query(Creature).one()
    entity_id = first.entity_uuid
    assert creature.knowledge_entity_id == entity_id and creature.data_version == 1
    entity = db.get(KnowledgeEntity, entity_id)
    assert entity.search_metadata.normalized_name == "demon"
    assert {alias.normalized_alias for alias in entity.aliases} == {"demon"}
    assert db.query(KnowledgeExternalMapping).filter_by(external_id="321").one().entity_uuid == entity_id
    assert creature.raw_data is None

    unchanged = _apply_detail(db, fixture("tibiawiki_creature_detail.json"))
    assert unchanged.status == "unchanged" and creature.data_version == 1

    updated_raw = fixture("tibiawiki_creature_detail.json")
    updated_raw["parse"]["wikitext"]["*"] = updated_raw["parse"]["wikitext"]["*"].replace("8200", "8300")
    updated = _apply_detail(db, updated_raw)
    assert updated.status == "updated" and creature.hitpoints == 8300 and creature.data_version == 2

    prior_version = creature.data_version
    _apply_detail(db, fixture("tibiawiki_creature_partial.json"))

    # Partiality belongs to individual source fields, not to the whole
    # entity. HP is absent from this document, so preserve the prior HP.
    # Description is explicitly supplied, so accept the new evidence.
    assert creature.hitpoints == 8300
    assert creature.description == "A partial record."
    assert creature.data_version == prior_version + 1


def test_exact_name_reuses_entity_but_weak_fuzzy_name_does_not(db, creature_registry):
    exact = KnowledgeEntityService.create(
        db,
        KnowledgeEntityCreate(
            entity_type="creature",
            canonical_name="Demon",
            language_neutral_id="creature:legacy:demon",
        ),
    )
    fuzzy = KnowledgeEntityService.create(
        db,
        KnowledgeEntityCreate(
            entity_type="creature",
            canonical_name="Demon Lord",
            language_neutral_id="creature:legacy:demon-lord",
        ),
    )
    db.add(
        Creature(
            name="Demon Lord",
            normalized_name="demon lord",
            slug="demon-lord",
            hitpoints=1,
            experience=1,
            knowledge_entity_id=fuzzy.uuid,
        )
    )
    db.flush()
    applied = _apply_detail(db, fixture("tibiawiki_creature_detail.json"))
    assert applied.entity_uuid == exact.uuid
    assert db.query(KnowledgeEntity).count() == 2


def test_boss_creature_mismatch_is_never_merged(db, creature_registry):
    entity = KnowledgeEntityService.create(
        db,
        KnowledgeEntityCreate(
            entity_type="creature",
            canonical_name="Demon",
            language_neutral_id="creature:legacy:demon",
        ),
    )
    db.add(
        Creature(
            name="Demon",
            normalized_name="demon",
            slug="demon",
            hitpoints=1,
            experience=1,
            is_boss=True,
            knowledge_entity_id=entity.uuid,
        )
    )
    db.flush()
    with pytest.raises(CreatureIdentityConflictError):
        _apply_detail(db, fixture("tibiawiki_creature_detail.json"))


def test_alias_collision_is_reported_not_guessed(db, creature_registry):
    KnowledgeEntityService.create(
        db,
        KnowledgeEntityCreate(
            entity_type="creature",
            canonical_name="Dragon",
            language_neutral_id="creature:legacy:dragon",
            aliases=["The Demon"],
        ),
    )
    raw = fixture("tibiawiki_creature_detail.json")
    raw["parse"]["title"] = "The Demon"
    with pytest.raises(DuplicateKnowledgeEntityError):
        _apply_detail(db, raw)


def test_protected_creature_fields_are_not_overwritten(db, creature_registry):
    _apply_detail(db, fixture("tibiawiki_creature_detail.json"))
    creature = db.query(Creature).one()
    creature.protected_fields = ["hitpoints"]
    db.flush()
    raw = fixture("tibiawiki_creature_detail.json")
    raw["parse"]["wikitext"]["*"] = raw["parse"]["wikitext"]["*"].replace("8200", "9000")
    _apply_detail(db, raw)
    assert creature.hitpoints == 8200


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


def test_end_to_end_catalog_job_persists_raw_document_and_idempotent_children():
    engine, factory = worker_database()
    fixture_client = FixtureCreatureClient()
    adapters = KnowledgeAdapterRegistry((TibiaWikiCreatureAdapter(fixture_client),))
    with factory.begin() as db:
        parent = KnowledgeJobService.enqueue(
            db,
            EnqueueKnowledgeJob(
                provider_id="tibiawiki",
                job_type="creature_catalog",
                entity_type="creature",
                scope={"batch_limit": 2},
                trigger="manual",
            ),
        ).job
        parent_id = parent.id
    worker = KnowledgeWorker(
        worker_id="creature-fixture-worker",
        lease_seconds=60,
        poll_seconds=0.1,
        max_idle_seconds=1,
        session_factory=factory,
        adapters=adapters,
    )
    assert worker.run_once() is True
    with factory() as db:
        parent = db.get(KnowledgeJob, parent_id)
        children = db.query(KnowledgeJob).filter(KnowledgeJob.parent_job_id == parent_id).all()
        assert parent.state == "succeeded" and parent.attempts[0].metrics["child_jobs_enqueued"] == 3
        assert len(children) == 3 and db.query(KnowledgeDocument).count() == 1
        cursor = db.query(KnowledgeProviderCursor).one()
        assert cursor.cursor["continuation"] == "page|44454d4f4e|321"
    assert worker.run_once() is True
    with factory() as db:
        assert db.query(Creature).count() == 1
        assert db.query(KnowledgeEntity).count() == 1
        assert db.query(KnowledgeDocument).count() == 2
        detail = db.query(KnowledgeJob).filter(KnowledgeJob.job_type == "creature_detail", KnowledgeJob.state == "succeeded").one()
        assert detail.parent_job_id == parent_id and detail.correlation_id == parent.correlation_id
        assert detail.attempts[0].metrics["entities_created"] == 1
    engine.dispose()


def test_failed_detail_child_is_isolated_from_completed_creature():
    class OneFailingDetailClient(FixtureCreatureClient):
        def fetch_detail(self, *, external_id: str | None, page_title: str | None) -> dict:
            if external_id == "654":
                from app.knowledge.services.failures import ProviderHTTPError

                raise ProviderHTTPError(400)
            return super().fetch_detail(external_id=external_id, page_title=page_title)

    engine, factory = worker_database()
    adapters = KnowledgeAdapterRegistry((TibiaWikiCreatureAdapter(OneFailingDetailClient()),))
    with factory.begin() as db:
        parent_id = KnowledgeJobService.enqueue(
            db,
            EnqueueKnowledgeJob(
                provider_id="tibiawiki",
                job_type="creature_catalog",
                entity_type="creature",
                scope={"batch_limit": 2},
                trigger="manual",
            ),
        ).job.id
    worker = KnowledgeWorker(
        worker_id="creature-isolation-worker",
        lease_seconds=60,
        poll_seconds=0.1,
        max_idle_seconds=1,
        session_factory=factory,
        adapters=adapters,
    )
    assert worker.run_once() is True
    assert worker.run_once() is True
    assert worker.run_once() is True
    with factory() as db:
        assert db.get(KnowledgeJob, parent_id).state == "succeeded"
        assert db.query(Creature).filter_by(name="Demon").count() == 1
        failed = db.query(KnowledgeJob).filter_by(job_type="creature_detail", state="failed").one()
        assert failed.payload["external_id"] == "654"
    engine.dispose()


def test_renormalize_job_uses_stored_document_without_provider_fetch():
    engine, factory = worker_database()
    fixture_client = FixtureCreatureClient()
    adapters = KnowledgeAdapterRegistry((TibiaWikiCreatureAdapter(fixture_client),))
    worker = KnowledgeWorker(
        worker_id="creature-renormalize-worker",
        lease_seconds=60,
        poll_seconds=0.1,
        max_idle_seconds=1,
        session_factory=factory,
        adapters=adapters,
    )
    with factory.begin() as db:
        detail_id = KnowledgeJobService.enqueue(
            db,
            EnqueueKnowledgeJob(
                provider_id="tibiawiki",
                job_type="creature_detail",
                entity_type="creature",
                payload={"external_id": "321", "page_title": "Demon"},
            ),
        ).job.id
    worker.run_once()
    with factory.begin() as db:
        renormalize_id = KnowledgeJobService.enqueue(
            db,
            EnqueueKnowledgeJob(
                provider_id="tibiawiki",
                job_type="creature_renormalize",
                entity_type="creature",
                payload={"external_id": "321"},
                trigger="renormalize",
            ),
        ).job.id
    worker.run_once()
    with factory() as db:
        assert db.get(KnowledgeJob, detail_id).state == "succeeded"
        assert db.get(KnowledgeJob, renormalize_id).state == "succeeded"
        assert db.query(KnowledgeDocument).count() == 1
    assert fixture_client.detail_calls == 1
    engine.dispose()



def test_partial_detail_repairs_mediawiki_identity_without_overwriting_content(
    creature_registry,
    db,
):
    adapter = TibiaWikiCreatureAdapter(
        FixtureCreatureClient()
    )

    result = adapter.fetch(
        request(
            "creature_detail",
            payload={
                "external_id": "321",
                "page_title": "Demon",
            },
        )
    )

    normalization = adapter.normalize(
        result.documents[0],
        normalization_context(),
    )

    canonical_data = dict(
        normalization.canonical_data or {}
    )
    canonical_data["is_partial"] = True

    normalization = replace(
        normalization,
        canonical_data=canonical_data,
    )

    existing = Creature(
        name="Demon",
        normalized_name=normalize_search_text("Demon"),
        slug="demon",
        external_id="123456789",
        source_name="tibiawiki",
        hitpoints=9999,
        experience=8888,
        is_boss=False,
        protected_fields=[],
    )
    db.add(existing)
    db.flush()

    KnowledgeNormalizationService.apply(
        db,
        normalization,
    )
    db.flush()

    refreshed = (
        db.query(Creature)
        .filter_by(
            normalized_name=normalize_search_text("Demon")
        )
        .one()
    )

    assert refreshed.external_id == "321"
    assert refreshed.knowledge_entity_id is not None

    # Existing non-empty content remains untouched because this
    # normalization is explicitly partial.
    assert refreshed.hitpoints == 9999
    assert refreshed.experience == 8888



def test_worker_defers_provider_fetch_to_respect_registered_rate_limit():
    engine, factory = worker_database()
    fixture_client = FixtureCreatureClient()
    adapters = KnowledgeAdapterRegistry((TibiaWikiCreatureAdapter(fixture_client),))
    with factory.begin() as db:
        provider = db.get(KnowledgeProvider, "tibiawiki")
        provider.rate_limit = {"requests": 12, "window_seconds": 60}
        provider.last_attempted_at = datetime.now(UTC)
        job_id = KnowledgeJobService.enqueue(
            db,
            EnqueueKnowledgeJob(
                provider_id="tibiawiki",
                job_type="creature_detail",
                entity_type="creature",
                payload={"external_id": "321", "page_title": "Demon"},
            ),
        ).job.id
    worker = KnowledgeWorker(
        worker_id="creature-rate-limit-worker",
        lease_seconds=60,
        poll_seconds=0.1,
        max_idle_seconds=1,
        session_factory=factory,
        adapters=adapters,
    )
    assert worker.run_once() is True
    with factory() as db:
        job = db.get(KnowledgeJob, job_id)
        assert job.state == "pending" and job.attempt_count == 0
        assert job.claimed_at is None and job.worker_id is None
        scheduled_at = job.scheduled_at.replace(tzinfo=UTC) if job.scheduled_at.tzinfo is None else job.scheduled_at
        assert scheduled_at > datetime.now(UTC)
    assert fixture_client.detail_calls == 0
    engine.dispose()


def test_local_creature_api_never_calls_provider_and_survives_provider_failure(client, db, creature_registry, monkeypatch):
    _apply_detail(db, fixture("tibiawiki_creature_detail.json"))
    db.add(
        Creature(
            name="Dragon",
            normalized_name="dragon",
            slug="dragon",
            hitpoints=1000,
            experience=700,
        )
    )
    provider = db.get(KnowledgeProvider, "tibiawiki")
    provider.health = "unavailable"
    provider.enabled = False
    db.commit()

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("provider network access occurred during a local read")

    monkeypatch.setattr("app.knowledge.adapters.tibiawiki_creatures.HttpTibiaWikiCreatureClient._request", fail_if_called)
    listed = client.get("/api/v1/creatures/?skip=0&limit=1")
    second_page = client.get("/api/v1/creatures/?skip=1&limit=1")
    detail = client.get("/api/v1/creatures/demon")
    missing = client.get("/api/v1/creatures/not-a-real-creature")
    assert listed.status_code == 200 and listed.json()[0]["name"] == "Demon"
    assert second_page.status_code == 200 and second_page.json()[0]["name"] == "Dragon"
    assert detail.status_code == 200 and detail.json()["knowledge_entity_id"]
    assert detail.json()["canonical_id"] == detail.json()["knowledge_entity_id"]
    assert detail.json()["source_provider"] == "tibiawiki"
    assert "hitpoints" in detail.json()["supplied_fields"]
    assert missing.status_code == 404


def test_admin_controls_require_global_admin_catalog_confirmation_and_audit(client, db, creature_registry):
    admin = make_user(db, username="creature-knowledge-admin", is_superuser=True)
    member = make_user(db, username="creature-knowledge-member")
    db.commit()
    admin_headers = {"Authorization": f"Bearer {create_access_token(admin.username)}"}
    member_headers = {"Authorization": f"Bearer {create_access_token(member.username)}"}
    payload = {
        "provider_id": "tibiawiki",
        "job_type": "creature_catalog",
        "entity_type": "creature",
        "scope": {"batch_limit": 2},
        "payload": {},
    }
    assert client.post("/api/v1/admin/knowledge/jobs", headers=member_headers, json=payload).status_code == 403
    assert client.post("/api/v1/admin/knowledge/jobs", headers=admin_headers, json=payload).status_code == 400
    payload["confirm_catalog_sync"] = True
    created = client.post("/api/v1/admin/knowledge/jobs", headers=admin_headers, json=payload)
    assert created.status_code == 201 and created.json()["item"]["job_type"] == "creature_catalog"
    assert db.query(WorkspaceAudit).filter_by(action="knowledge_job_enqueued").count() == 1
def test_creature_semantics_keep_behaviour_strategy_and_notes_separate(
    db,
    creature_registry,
):
    raw = fixture("tibiawiki_creature_detail.json")
    wikitext = raw["parse"]["wikitext"]["*"]

    marker = "| strategy = Keep your distance and use ice attacks."

    assert marker in wikitext

    raw["parse"]["wikitext"]["*"] = wikitext.replace(
        marker,
        (
            "| behaviour = Fights in close combat and retreats at low health.\n"
            "| strategy = Keep your distance and use ice attacks.\n"
            "| notes = Appears in this regression fixture only."
        ),
    )

    _apply_detail(db, raw)

    creature = db.query(Creature).one()

    assert creature.behavior == (
        "Fights in close combat and retreats at low health."
    )
    assert creature.strategy == (
        "Keep your distance and use ice attacks."
    )
    assert creature.notes == (
        "Appears in this regression fixture only."
    )

    # Bestiary text remains the overview when both bestiary text and notes
    # exist. Notes are preserved separately rather than discarded.
    assert creature.description == "A powerful demonic creature."


def test_unknown_provider_numeric_values_clear_only_legacy_zero_sentinels(
    db,
    creature_registry,
):
    _apply_detail(
        db,
        fixture("tibiawiki_creature_detail.json"),
    )

    creature = db.query(Creature).one()

    # Simulate values created by the historical compatibility path.
    creature.hitpoints = 0
    creature.experience = 0
    creature.armor = 0
    creature.speed = 0
    db.flush()

    raw = fixture("tibiawiki_creature_detail.json")
    wikitext = raw["parse"]["wikitext"]["*"]

    replacements = {
        "| hp = 8200": "| hp = ?",
        "| exp = 6000": "| exp = ?",
        "| armor = 55": "| armor = ?",
        "| speed = 280": "| speed = ?",
    }

    for old, new in replacements.items():
        assert old in wikitext
        wikitext = wikitext.replace(old, new)

    raw["parse"]["wikitext"]["*"] = wikitext

    _apply_detail(db, raw)

    assert creature.hitpoints is None
    assert creature.experience is None
    assert creature.armor is None
    assert creature.speed is None

    assert {"hitpoints", "experience"}.issubset(
        set(creature.missing_fields or [])
    )


def test_legitimate_provider_zero_is_not_treated_as_unknown(
    db,
    creature_registry,
):
    raw = fixture("tibiawiki_creature_detail.json")
    wikitext = raw["parse"]["wikitext"]["*"]

    replacements = {
        "| hp = 8200": "| hp = 0",
        "| exp = 6000": "| exp = 0",
        "| armor = 55": "| armor = 0",
        "| speed = 280": "| speed = 0",
    }

    for old, new in replacements.items():
        assert old in wikitext
        wikitext = wikitext.replace(old, new)

    raw["parse"]["wikitext"]["*"] = wikitext

    _apply_detail(db, raw)

    creature = db.query(Creature).one()

    assert creature.hitpoints == 0
    assert creature.experience == 0
    assert creature.armor == 0
    assert creature.speed == 0

    assert "hitpoints" not in (creature.missing_fields or [])
    assert "experience" not in (creature.missing_fields or [])
def test_partial_creature_updates_supplied_behaviour_and_strategy(
    db,
    creature_registry,
):
    raw = fixture("tibiawiki_creature_detail.json")

    # First simulate the historical semantic error where strategy was stored
    # as behavior.
    _apply_detail(db, raw)
    creature = db.query(Creature).one()
    creature.behavior = "Old strategy incorrectly stored as behavior."
    db.flush()

    wikitext = raw["parse"]["wikitext"]["*"]

    strategy_line = (
        "| strategy = Keep your distance and use ice attacks."
    )

    assert strategy_line in wikitext

    # Remove loot so the document is genuinely partial while still supplying
    # valid combat semantics.
    wikitext = wikitext.replace(
        strategy_line,
        (
            "| behaviour = Fights in close combat and retreats at low health.\n"
            "| strategy = Keep your distance and use ice attacks."
        ),
    )

    wikitext = wikitext.replace(
        "{{Loot Item|1-3|Demon Horn|Rare}}",
        "",
    )

    raw["parse"]["wikitext"]["*"] = wikitext

    _apply_detail(db, raw)

    assert "loot" in (creature.missing_fields or [])

    # The unrelated missing loot field must not prevent valid supplied
    # semantics from repairing the canonical row.
    assert creature.behavior == (
        "Fights in close combat and retreats at low health."
    )
    assert creature.strategy == (
        "Keep your distance and use ice attacks."
    )

    # Fields explicitly supplied by this partial document remain authoritative.
    assert creature.hitpoints == 8200
    assert creature.experience == 6000
def test_creature_source_cleans_nonsemantic_notes_markup():
    young_goanna = _build_creature_payload(
        "Young Goanna",
        """
{{Infobox Creature
| name = Young Goanna
| hp = 6950
| exp = 5250
| notes = <gallery captionalign="center" mode="nolines">Young Goanna Artwork.jpg|Official [[Creature Artwork]]</gallery> They are a younger version of the [[Adult Goanna]].
| location = [[Kilmaresh Central Steppe]]
}}
""",
    )

    assert young_goanna["notes"] == (
        "They are a younger version of the Adult Goanna."
    )

    artwork_only = _build_creature_payload(
        "White Weretiger",
        """
{{Infobox Creature
| name = White Weretiger
| hp = 6100
| exp = 5200
| notes = <gallery captionalign="center" mode="nolines">Weretiger Artwork.jpg|Official [[Creature Artwork]]</gallery>
| location = [[Oskayaat]]
}}
""",
    )

    assert artwork_only["notes"] is None

    dangling_comment = _build_creature_payload(
        "Achad",
        """
{{Infobox Creature
| name = Achad
| hp = 185
| exp = 70
| notes = Greenhorn challenger.<br /><!--
| behaviour = Fights until death in close combat.
| strategy = Kill it normally.
| location = [[Svargrond Arena]]
}}
""",
    )

    assert dangling_comment["notes"] == (
        "Greenhorn challenger."
    )

    semantic_empty = _build_creature_payload(
        "A Greedy Eye",
        """
{{Infobox Creature
| name = A Greedy Eye
| hp = ?
| exp = ?
| notes = None.
| location = [[Somewhere]]
}}
""",
    )

    assert semantic_empty["notes"] is None


def test_creature_source_deduplicates_and_sanitizes_locations():
    cocoon = _build_creature_payload(
        "Cocoon",
        """
{{Infobox Creature
| name = Cocoon
| hp = ?
| exp = ?
| location = [[Vengoth]] in the lair of [[Devovorga]] after having killed all the sub-bosses and damaged [[Devovorga]] enough.
}}
""",
    )

    assert cocoon["locations"] == [
        "Vengoth",
        "Devovorga",
    ]

    feroxa = _build_creature_payload(
        "Feroxa",
        """
{{Infobox Creature
| name = Feroxa
| hp = 150000
| exp = ?
| location = Behind the teleport, {{Mapper Coords|130.177|123.42|11|8|text=here}}.
}}
""",
    )

    assert feroxa["locations"] == [
        "Behind the teleport",
    ]

def test_field_aware_partial_updates_supplied_fields_while_preserving_missing_fields(
    creature_registry,
    db,
):
    adapter = TibiaWikiCreatureAdapter(
        FixtureCreatureClient()
    )

    result = adapter.fetch(
        request(
            "creature_detail",
            payload={
                "external_id": "321",
                "page_title": "Demon",
            },
        )
    )

    normalization = adapter.normalize(
        result.documents[0],
        normalization_context(),
    )

    canonical_data = deepcopy(
        normalization.canonical_data or {}
    )

    # Simulate a partial document whose provider contract explicitly
    # says hitpoints are missing, while behavior and strategy are
    # genuinely supplied.
    canonical_data["is_partial"] = True

    provider_metadata = dict(
        canonical_data.get(
            "provider_metadata"
        )
        or {}
    )

    provider_metadata["missing_fields"] = [
        "hitpoints",
    ]

    canonical_data[
        "provider_metadata"
    ] = provider_metadata

    provided_fields = set(
        canonical_data.get(
            "provided_fields"
        )
        or []
    )

    provided_fields.discard("hitpoints")
    provided_fields.update(
        {
            "behavior",
            "strategy",
        }
    )

    canonical_data[
        "provided_fields"
    ] = sorted(provided_fields)

    canonical_data["hitpoints"] = None
    canonical_data[
        "behavior"
    ] = "Updated behavior"
    canonical_data[
        "strategy"
    ] = "Updated strategy"

    normalization = replace(
        normalization,
        canonical_data=canonical_data,
        warnings=(
            "partial_creature_detail",
        ),
    )

    existing = Creature(
        name="Demon",
        normalized_name=normalize_search_text(
            "Demon"
        ),
        slug="demon",
        external_id="321",
        source_name="tibiawiki",
        hitpoints=9999,
        experience=8888,
        behavior="Old behavior",
        strategy="Old strategy",
        is_boss=False,
        protected_fields=[],
    )

    db.add(existing)
    db.flush()

    KnowledgeNormalizationService.apply(
        db,
        normalization,
    )

    db.flush()
    db.refresh(existing)

    # Missing source field survives.
    assert existing.hitpoints == 9999

    # Explicitly supplied fields may repair canonical content even
    # though the entity as a whole is partial.
    assert existing.behavior == "Updated behavior"
    assert existing.strategy == "Updated strategy"

def test_creature_parser_marks_explicit_clear_without_clearing_lsth_reference():
    from app.services.bestiary_source import _build_creature_payload

    payload = _build_creature_payload(
        "Semantic Probe",
        """{{Infobox Creature
| name = Semantic Probe
| hp = 10
| exp = 20
| behaviour = Unknown.
| strategy = {{#lsth:Rotten Blood Quest/Spoiler|Bakragore}}
| notes = None.
| location = ?
}}""",
    )

    assert payload["behavior"] is None
    assert payload["strategy"] is None
    assert payload["notes"] is None
    assert payload["locations"] == []

    assert set(payload["source_clear_fields"]) == {
        "behavior",
        "description",
        "notes",
        "locations",
    }

    assert payload["strategy_transclusion"] == {
        "page": "Rotten Blood Quest/Spoiler",
        "section": "Bakragore",
    }

    assert "strategy" not in payload["source_clear_fields"]


def test_strategy_section_cleanup_removes_visual_markup_but_preserves_dialogue():
    from app.services.bestiary_source import (
        _extract_wiki_section,
        _strip_strategy_section_markup,
    )

    wikitext = """== Other ==
Ignore me.

== Grand Master Oberon ==
[[File:Oberon.gif|right]]
{{FightTips
|{{FightTip|type=equip|element=Physical}}
}}
This battle is both physical and verbal.

{| class="wikitable"
! Boss !! Reply
|-
| {{Sound|The world will suffer for its idle laziness!}}
| Are you ever going to fight or do you prefer talking!
|}

[[File:Example.png|thumb|300px]]

== Next ==
Do not include me.
"""

    section = _extract_wiki_section(
        wikitext,
        "Grand Master Oberon",
    )

    assert section is not None

    cleaned = _strip_strategy_section_markup(
        section
    )

    assert "This battle is both physical and verbal." in cleaned
    assert "The world will suffer for its idle laziness!" in cleaned
    assert "Are you ever going to fight or do you prefer talking!" in cleaned

    assert "Oberon.gif" not in cleaned
    assert "Example.png" not in cleaned
    assert "thumb" not in cleaned
    assert "right" not in cleaned
    assert "wikitable" not in cleaned
    assert "Do not include me." not in cleaned


def test_creature_explicit_clear_and_strategy_transclusion_contract(
    creature_registry,
    db,
):
    from copy import deepcopy
    from dataclasses import replace

    from app.knowledge.services.normalization import (
        KnowledgeNormalizationService,
    )
    from app.models import Creature
    from app.services.text_utils import (
        normalize_search_text,
    )

    adapter = TibiaWikiCreatureAdapter(
        FixtureCreatureClient()
    )

    result = adapter.fetch(
        request(
            "creature_detail",
            payload={
                "external_id": "321",
                "page_title": "Demon",
            },
        )
    )

    normalization = adapter.normalize(
        result.documents[0],
        normalization_context(),
    )

    canonical_data = deepcopy(
        normalization.canonical_data or {}
    )

    canonical_data["is_partial"] = True
    canonical_data["behavior"] = None
    canonical_data["strategy"] = "Legacy tactical strategy"
    canonical_data["description"] = None
    canonical_data["locations"] = []

    provided = set(
        canonical_data.get("provided_fields")
        or []
    )

    provided.discard("behavior")
    provided.discard("description")
    provided.discard("locations")
    provided.add("strategy")

    canonical_data["provided_fields"] = sorted(
        provided
    )

    metadata = dict(
        canonical_data.get(
            "provider_metadata"
        )
        or {}
    )

    metadata["missing_fields"] = [
        "loot",
        "locations",
    ]

    metadata["source_clear_fields"] = [
        "description",
        "locations",
    ]

    metadata["strategy_transclusion"] = None

    canonical_data["provider_metadata"] = metadata

    normalization = replace(
        normalization,
        canonical_data=canonical_data,
        warnings=(
            "partial_creature_detail",
        ),
    )

    existing = Creature(
        name="Demon",
        normalized_name=normalize_search_text(
            "Demon"
        ),
        slug="demon",
        external_id="321",
        source_name="tibiawiki",
        hitpoints=9999,
        experience=8888,
        behavior="Legacy tactical strategy",
        strategy=None,
        description="None.",
        locations=["Unknown"],
        is_boss=False,
        protected_fields=[],
    )

    db.add(existing)
    db.flush()

    KnowledgeNormalizationService.apply(
        db,
        normalization,
    )

    db.flush()
    db.refresh(existing)

    # Numeric source data marked missing by this synthetic partial payload is
    # outside this regression's semantic-clear contract.
    assert existing.behavior is None
    assert existing.strategy == "Legacy tactical strategy"
    assert existing.description is None
    assert existing.locations == []


def test_creature_parser_distinguishes_blank_from_explicit_empty_source():
    from app.services.bestiary_source import _build_creature_payload

    payload = _build_creature_payload(
        "Blank Behavior Probe",
        """{{Infobox Creature
| name = Blank Behavior Probe
| hp = 10
| exp = 20
| behaviour =
| strategy = Unknown.
| notes =
| location =
}}""",
    )

    assert payload["behavior"] is None
    assert payload["strategy"] is None
    assert payload["notes"] is None
    assert payload["locations"] == []

    # Unknown. is explicit semantic-empty evidence.
    assert set(
        payload["source_clear_fields"]
    ) == {
        "strategy",
    }

    # Blank parameters are weaker evidence and must not erase useful
    # canonical prose.
    assert set(
        payload["source_blank_fields"]
    ) == {
        "behavior",
        "description",
        "notes",
        "locations",
    }


def test_creature_detail_prefers_exact_mediawiki_file_evidence():
    from app.knowledge.adapters.tibiawiki_creatures import (
        _detail_parts,
    )

    raw = {
        "parse": {
            "pageid": 107847,
            "title": "Blooming Tower (Dark)",
            "wikitext": {
                "*": """{{Infobox Creature
| name = Blooming Tower
| actualname = Blooming Tower
| hp = 100
| exp = 0
}}"""
            },
            "images": [
                "Some Interface Icon.png",
                "Blooming Tower (Dark).gif",
                "Blooming Tower Soul Core.gif",
            ],
        }
    }

    external_id, page_title, _wikitext, payload = (
        _detail_parts(raw)
    )

    assert external_id == "107847"
    assert page_title == "Blooming Tower (Dark)"

    assert (
        payload["image_file_reference"]
        == "Blooming Tower (Dark).gif"
    )

    assert (
        payload["image_url"]
        == "https://tibia.fandom.com/wiki/"
        "Special:FilePath/Blooming_Tower_(Dark).gif"
    )

    assert (
        payload["image_evidence"]
        == "page_images_exact"
    )


def test_creature_detail_rejects_related_but_nonexact_images():
    from app.knowledge.adapters.tibiawiki_creatures import (
        _detail_parts,
    )

    raw = {
        "parse": {
            "pageid": 999999,
            "title": "Example Creature",
            "wikitext": {
                "*": """{{Infobox Creature
| name = Example Creature
| hp = 100
| exp = 50
}}"""
            },
            "images": [
                "Example Creature Soul Core.gif",
                "Example Creature Map.png",
                "Some Interface Icon.png",
            ],
        }
    }

    _external_id, _page_title, _wikitext, payload = (
        _detail_parts(raw)
    )

    assert payload["image_file_reference"] is None

    # Compatibility fallback remains available when exact File evidence
    # is absent, but its provenance is no longer confused with evidence.
    assert (
        payload["image_evidence"]
        == "synthetic_name_fallback"
    )

    assert payload["image_url"].endswith(
        "/Special:FilePath/Example_Creature.gif"
    )


def test_synthetic_creature_image_fallback_is_not_authoritative():
    from app.knowledge.dto import CreatureKnowledgeDTO
    from app.services.bestiary_source import _build_creature_payload

    wikitext = """{{Infobox Creature
| name = Example Creature
| hp = 100
| exp = 50
}}"""

    synthetic = _build_creature_payload(
        "Example Creature",
        wikitext,
    )

    assert (
        synthetic["image_evidence"]
        == "synthetic_name_fallback"
    )
    assert synthetic["image_url"].endswith(
        "/Special:FilePath/Example_Creature.gif"
    )
    # Synthetic media does not make the creature detail partial.
    # Authority is controlled independently through provided_fields.
    assert "image_url" not in synthetic["missing_fields"]

    synthetic_dto = (
        CreatureKnowledgeDTO.from_tibiawiki_payload(
            synthetic,
            external_id="123",
            page_title="Example Creature",
        )
    )

    # The compatibility URL may remain available in the DTO, but the
    # normalizer must not treat it as authoritative provider evidence.
    assert synthetic_dto.image_reference is not None
    assert (
        "image_reference"
        not in synthetic_dto.provided_fields
    )

    exact = _build_creature_payload(
        "Example Creature",
        wikitext,
        image_reference="Example_Creature.gif",
    )

    assert exact["image_evidence"] == "page_images_exact"
    assert (
        exact["image_file_reference"]
        == "Example_Creature.gif"
    )
    assert "image_url" not in exact["missing_fields"]

    exact_dto = (
        CreatureKnowledgeDTO.from_tibiawiki_payload(
            exact,
            external_id="123",
            page_title="Example Creature",
        )
    )

    assert (
        "image_reference"
        in exact_dto.provided_fields
    )
