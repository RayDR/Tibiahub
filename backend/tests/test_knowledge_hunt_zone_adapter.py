from __future__ import annotations

from copy import deepcopy
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base
from app.knowledge.adapters import (
    KnowledgeAdapterRegistry,
    KnowledgeDocumentDTO,
    KnowledgeFetchRequest,
    KnowledgeNormalizationContext,
    TibiaWikiHuntZoneAdapter,
)
from app.knowledge.dto import HuntZoneKnowledgeDTO
from app.knowledge.models import KnowledgeDocument, KnowledgeEntity, KnowledgeJob, KnowledgeProvider, KnowledgeRelationship
from app.knowledge.providers import INITIAL_PROVIDERS
from app.knowledge.registry import EntityTypeRegistry, ProviderRegistry
from app.knowledge.schemas import KnowledgeEntityCreate
from app.knowledge.services import EnqueueKnowledgeJob, KnowledgeEntityService, KnowledgeJobService
from app.knowledge.services.normalization import KnowledgeNormalizationService
from app.knowledge.workers.knowledge_worker import KnowledgeWorker
from app.models import HuntZone


IKSUPAN_WIKITEXT = """
{{Infobox Hunt
| name = Iksupan
| implemented = 13.20
| city = Port Hope
| location = Tiquanda
| vocation = All vocations
| lvlknights = 150
| lvlpaladins = 150
| lvlmages = 150
| skknights =
| skpaladins = 100
| skmages =
| defknights =
| defpaladins = 90
| defmages =
| loot = Good
| lootstar = 4
| exp = Good
| expstar = 4
| bestloot1 = [[Iksupan Loot]]
| maps = [[Iksupan Map]]
}}
Access to Iksupan is obtained through the [[Adventures of Galthen Quest]].
{{CreatureList|type=List/Sorted
|Cursed Ape
|Iks Aucar
|Iks Pututu
}}
"""


def raw_detail(wikitext: str = IKSUPAN_WIKITEXT) -> dict:
    return {
        "parse": {"pageid": 1999, "title": "Iksupan", "wikitext": {"*": wikitext}},
        "future_provider_field": {"preserved": True},
    }


class FixtureClient:
    def fetch_catalog(self, *, continuation, limit):
        return {"query": {"categorymembers": [{"pageid": 1999, "title": "Iksupan"}]}}

    def fetch_detail(self, *, external_id, page_title):
        return raw_detail()


def request(suffix: str, *, scope=None, payload=None):
    return KnowledgeFetchRequest(
        job_id=uuid4(), attempt_id=uuid4(), correlation_id=uuid4(),
        provider_code="tibiawiki", job_type=f"hunt_zone_{suffix}", entity_type="hunt_zone",
        scope=scope or {}, payload=payload or {},
    )


def context():
    return KnowledgeNormalizationContext(
        job_id=uuid4(), attempt_id=uuid4(), correlation_id=uuid4(),
        provider_code="tibiawiki", entity_type="hunt_zone",
    )


def detail_document(raw):
    return KnowledgeDocumentDTO(
        "tibiawiki", "hunt_zone:1999", raw,
        metadata={"document_kind": "hunt_zone_detail"},
    )


def registry(db):
    EntityTypeRegistry.register_initial(db)
    for definition in INITIAL_PROVIDERS:
        ProviderRegistry.register(db, definition)
    db.flush()


def test_hunt_zone_parses_real_vocation_fields_without_flattening_or_defaults():
    adapter = TibiaWikiHuntZoneAdapter(FixtureClient())
    result = adapter.fetch(request("detail", payload={"external_id": "1999"}))
    assert adapter.validate(result).valid is True
    assert result.documents[0].raw_json["future_provider_field"] == {"preserved": True}
    dto = HuntZoneKnowledgeDTO.from_canonical_data(adapter.normalize(result.documents[0], context()).canonical_data)
    assert dto.vocation_recommendations["knights"].level == 150
    assert dto.vocation_recommendations["knights"].skill is None
    assert dto.vocation_recommendations["paladins"].skill == 100
    assert dto.vocation_recommendations["paladins"].defense == 90
    assert dto.vocation_recommendations["mages"].level == 150
    assert dto.premium_required is None
    assert dto.creatures == ("Cursed Ape", "Iks Aucar", "Iks Pututu")
    assert dto.access_quests == ("Adventures of Galthen Quest",)
    assert dto.minimum_recommended_level == 150


def test_related_quest_without_explicit_access_evidence_is_not_an_access_quest():
    raw = raw_detail(IKSUPAN_WIKITEXT.replace(
        "Access to Iksupan is obtained through the [[Adventures of Galthen Quest]].",
        "This place is related to the [[Adventures of Galthen Quest]].",
    ))
    adapter = TibiaWikiHuntZoneAdapter(FixtureClient())
    dto = HuntZoneKnowledgeDTO.from_canonical_data(adapter.normalize(detail_document(raw), context()).canonical_data)
    assert dto.access_quests == ()
    assert "access_quests" not in dto.supplied_fields


def test_explicit_false_is_preserved_while_missing_boolean_stays_unknown():
    adapter = TibiaWikiHuntZoneAdapter(FixtureClient())
    missing = HuntZoneKnowledgeDTO.from_canonical_data(
        adapter.normalize(detail_document(raw_detail()), context()).canonical_data,
    )
    explicit = raw_detail(IKSUPAN_WIKITEXT.replace("| vocation = All vocations", "| premium = no\n| vocation = All vocations"))
    supplied = HuntZoneKnowledgeDTO.from_canonical_data(
        adapter.normalize(detail_document(explicit), context()).canonical_data,
    )
    assert missing.premium_required is None
    assert supplied.premium_required is False
    assert "premium_required" in supplied.supplied_fields


def test_hunt_zone_normalization_is_idempotent_and_repairs_supplied_field_gaps(db):
    registry(db)
    creature = KnowledgeEntityService.create(db, KnowledgeEntityCreate(
        entity_type="creature", canonical_name="Cursed Ape", language_neutral_id="creature:test:cursed-ape",
    ))
    quest = KnowledgeEntityService.create(db, KnowledgeEntityCreate(
        entity_type="quest", canonical_name="Adventures of Galthen Quest",
        language_neutral_id="quest:test:adventures-of-galthen",
    ))
    town = KnowledgeEntityService.create(db, KnowledgeEntityCreate(
        entity_type="town", canonical_name="Port Hope", language_neutral_id="town:test:port-hope",
    ))
    adapter = TibiaWikiHuntZoneAdapter(FixtureClient())

    partial = raw_detail(IKSUPAN_WIKITEXT.replace("| lvlknights = 150\n", ""))
    first = KnowledgeNormalizationService.apply(db, adapter.normalize(detail_document(partial), context()))
    db.flush()
    db.expire_all()
    second = KnowledgeNormalizationService.apply(db, adapter.normalize(detail_document(raw_detail()), context()))
    db.flush()
    db.expire_all()
    third = KnowledgeNormalizationService.apply(db, adapter.normalize(detail_document(raw_detail()), context()))
    zone = db.query(HuntZone).one()
    assert first.status == "created"
    assert second.status == "updated" and second.metrics["entities_repaired"] == 1
    assert third.status == "unchanged"
    assert zone.knights_recommended is None and zone.requires_quest is None and zone.requires_premium is None
    assert zone.raw_data["vocation_recommendations"]["knights"]["level"] == 150
    relationships = db.query(KnowledgeRelationship).filter_by(
        source_entity_id=zone.knowledge_entity_id, is_current=True,
    ).all()
    assert {(row.relationship_type_code, row.target_entity_id) for row in relationships} >= {
        ("has_creature", creature.uuid),
        ("requires_hunt_quest", quest.uuid),
        ("located_at", town.uuid),
    }
    assert db.query(KnowledgeEntity).filter_by(entity_type="hunt_zone").count() == 1


def test_catalog_enqueues_repairable_detail_jobs():
    adapter = TibiaWikiHuntZoneAdapter(FixtureClient())
    result = adapter.fetch(request("catalog", scope={"batch_limit": 10}))
    assert result.child_jobs[0].allow_completed_recreate is True
    assert result.child_jobs[0].job_type == "hunt_zone_detail"


def test_hunt_zone_api_projects_local_canonical_provenance_and_completeness(client, db, monkeypatch):
    registry(db)
    adapter = TibiaWikiHuntZoneAdapter(FixtureClient())
    KnowledgeNormalizationService.apply(db, adapter.normalize(detail_document(raw_detail()), context()))
    db.commit()
    monkeypatch.setattr(
        "requests.sessions.Session.request",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("runtime provider call forbidden")),
    )
    response = client.get("/api/v1/hunt-zones/iksupan")
    assert response.status_code == 200
    payload = response.json()
    assert payload["external_id"] == "1999" and payload["source_provider"] == "tibiawiki"
    assert payload["knowledge_entity_id"]
    assert payload["canonical_id"] == payload["knowledge_entity_id"]
    assert payload["vocation_recommendations"]["paladins"] == {
        "level": 150, "skill": 100, "defense": 90,
    }
    assert payload["requires_premium"] is None
    assert payload["knights_recommended"] is None
    assert "premium_required" in payload["missing_fields"] or payload["access"]["premium_required"] is None


def test_hunt_zone_worker_renormalizes_the_immutable_stored_raw_document():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    adapter = TibiaWikiHuntZoneAdapter(FixtureClient())
    with factory.begin() as db:
        registry(db)
        provider = db.get(KnowledgeProvider, "tibiawiki")
        provider.enabled = True
        provider.health = "unknown"
        provider.rate_limit = {}
        KnowledgeJobService.enqueue(db, EnqueueKnowledgeJob(
            provider_id="tibiawiki", job_type="hunt_zone_detail", entity_type="hunt_zone",
            payload={"external_id": "1999"},
        ))
    worker = KnowledgeWorker(
        worker_id="hunt-zone-fixture-worker", lease_seconds=60, poll_seconds=0.1,
        max_idle_seconds=1, session_factory=factory,
        adapters=KnowledgeAdapterRegistry((adapter,)),
    )
    assert worker.run_once() is True
    with factory.begin() as db:
        renormalize = KnowledgeJobService.enqueue(db, EnqueueKnowledgeJob(
            provider_id="tibiawiki", job_type="hunt_zone_renormalize", entity_type="hunt_zone",
            payload={"external_id": "1999"}, trigger="renormalize",
        )).job
        renormalize_id = renormalize.id
    assert worker.run_once() is True
    with factory() as db:
        job = db.get(KnowledgeJob, renormalize_id)
        assert job.state == "succeeded" and job.attempts[0].metrics["normalized"] == 1
        assert db.query(KnowledgeDocument).count() == 1
        document = db.query(KnowledgeDocument).one()
        assert document.raw_json["future_provider_field"] == {"preserved": True}
    engine.dispose()
