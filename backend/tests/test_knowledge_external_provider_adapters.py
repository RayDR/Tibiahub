from __future__ import annotations

from dataclasses import replace
from uuid import uuid4

from app.knowledge.adapters import (
    KnowledgeFetchRequest,
    KnowledgeNormalizationContext,
    TibiaDataKnowledgeAdapter,
    TibiaMapsKnowledgeAdapter,
)
from app.knowledge.models import (
    KnowledgeDocument, KnowledgeExternalMapping, KnowledgeProviderObservation, SpatialMapPoint,
)
from app.knowledge.providers import INITIAL_PROVIDERS
from app.knowledge.registry import EntityTypeRegistry, ProviderRegistry
from app.knowledge.schemas import KnowledgeDocumentCreate, KnowledgeEntityCreate
from app.knowledge.services import KnowledgeEntityService
from app.knowledge.services.bootstrap import KnowledgeFullSyncService
from app.knowledge.services.normalization import KnowledgeNormalizationService
from app.knowledge.services.observations import KnowledgeObservationService
from app.knowledge.storage import KnowledgeDocumentStore


def request(provider, job_type, entity_type, *, payload=None):
    return KnowledgeFetchRequest(
        job_id=uuid4(), attempt_id=uuid4(), correlation_id=uuid4(),
        provider_code=provider, job_type=job_type, entity_type=entity_type,
        scope={}, payload=payload or {},
    )


def context(provider, entity_type):
    return KnowledgeNormalizationContext(
        job_id=uuid4(), attempt_id=uuid4(), correlation_id=uuid4(),
        provider_code=provider, entity_type=entity_type,
    )


def registry(db):
    EntityTypeRegistry.register_initial(db)
    for definition in INITIAL_PROVIDERS:
        ProviderRegistry.register(db, definition)
    db.flush()


class TibiaDataFixtureClient:
    def character(self, name):
        return {"character": {"character": {"name": name, "level": 100, "future": {"kept": True}}}}

    def guild(self, name):
        return {"guild": {"name": name, "world": "Antica", "members": []}}

    def worlds(self):
        return {
            "worlds": {
                "regular_worlds": [{"name": "Antica", "status": "online", "future": 42}],
                "tournament_worlds": [],
            },
            "information": {"api_version": 4},
        }

    def world(self, name): return {"world": {"name": name, "status": "online"}}
    def guilds(self, world): return {"guilds": {"world": world, "active": [{"name": "Red Rose"}]}}
    def highscores(self, world, category, vocation, page):
        return {"highscores": {"world": world, "category": category, "vocation": vocation, "page": page, "highscore_list": [{"name": "Knight", "value": 123}]}}
    def killstatistics(self, world): return {"killstatistics": {"world": world, "entries": [{"race": "Rat", "last_day_killed": 10}]}}
    def houses(self, world, town): return {"houses": {"world": world, "town": town, "house_list": [{"name": "Castle"}]}}
    def creatures(self): return {"creatures": {"creature_list": [{"race": "Dragon"}]}}
    def creature(self, race): return {"creature": {"race": race, "hitpoints": 1000}}
    def spells(self): return {"spells": {"spell_list": [{"spell_id": "adori"}]}}
    def spell(self, spell_id): return {"spell": {"spell_id": spell_id, "name": "Flame Strike"}}
    def boostable_bosses(self): return {"boostable_bosses": {"boosted": {"name": "The Pale Worm"}}}


def test_tibiadata_world_catalog_preserves_raw_and_persists_provider_mapping(db):
    registry(db)
    adapter = TibiaDataKnowledgeAdapter(TibiaDataFixtureClient())
    result = adapter.fetch(request("tibiadata", "world_catalog", "world"))
    assert adapter.validate(result).valid
    assert result.documents[0].raw_json["information"] == {"api_version": 4}
    world_document = result.documents[1]
    normalized = adapter.normalize(world_document, context("tibiadata", "world"))
    applied = KnowledgeNormalizationService.apply(db, normalized)
    mapping = db.query(KnowledgeExternalMapping).filter_by(
        provider_id="tibiadata", entity_type_id="world", external_id="antica",
    ).one()
    assert applied.status == "created"
    assert mapping.provider_metadata["fields"]["future"] == 42
    assert "future" in mapping.provider_metadata["supplied_fields"]


def test_tibiadata_dynamic_observations_are_append_only_and_replayable(db):
    registry(db)
    adapter = TibiaDataKnowledgeAdapter(TibiaDataFixtureClient())
    payload = {"world": "Antica", "category": "experience", "vocation": "all", "page": 1}
    adapter.validate_enqueue("highscores_current", {}, payload)
    fetched = adapter.fetch(request("tibiadata", "highscores_current", "world", payload=payload))
    assert adapter.validate(fetched).valid
    document = KnowledgeDocumentStore.persist(db, KnowledgeDocumentCreate(
        provider_id="tibiadata", provider_document_id=fetched.documents[0].provider_document_id,
        raw_json=fetched.documents[0].raw_json, version="v4",
    ))
    normalized = adapter.normalize(fetched.documents[0], context("tibiadata", "world"))
    first = KnowledgeObservationService.apply(db, normalized, document=document, entity_uuid=None)
    replay = KnowledgeObservationService.apply(
        db, replace(normalized, observation_version=2), document=document, entity_uuid=None,
    )
    db.flush()
    rows = db.query(KnowledgeProviderObservation).order_by(
        KnowledgeProviderObservation.normalization_version,
    ).all()
    assert first.created and replay.created
    assert [row.normalization_version for row in rows] == [1, 2]
    assert [row.is_current for row in rows] == [False, True]
    assert rows[1].observed_at.replace(tzinfo=None) == document.retrieved_at.replace(tzinfo=None)
    assert rows[1].normalized_payload["highscores"]["world"] == "Antica"


def test_tibiadata_requested_v4_paths_are_executable_and_scope_validated():
    adapter = TibiaDataKnowledgeAdapter(TibiaDataFixtureClient())
    cases = (
        ("character_detail", "character", {"name": "Knight"}),
        ("guild_catalog", "guild", {"world": "Antica"}),
        ("guild_detail", "guild", {"name": "Red Rose"}),
        ("world_detail", "world", {"name": "Antica"}),
        ("highscores_current", "world", {"world": "Antica", "category": "experience", "vocation": "all", "page": 1}),
        ("killstatistics_current", "world", {"world": "Antica"}),
        ("house_catalog", "town", {"world": "Antica", "town": "Thais"}),
        ("creature_detail", "creature", {"name": "Dragon"}),
        ("spell_detail", "spell", {"spell_id": "adori"}),
    )
    for job_type, entity_type, payload in cases:
        adapter.validate_enqueue(job_type, {}, payload)
        result = adapter.fetch(request("tibiadata", job_type, entity_type, payload=payload))
        assert result.documents and adapter.validate(result).valid
    for job_type, entity_type in (
        ("world_catalog", "world"), ("boosted_bosses_current", "boss"),
    ):
        adapter.validate_enqueue(job_type, {}, {})
        result = adapter.fetch(request("tibiadata", job_type, entity_type))
        assert result.documents and adapter.validate(result).valid
    for job_type, entity_type in (("creature_catalog", "creature"), ("spell_catalog", "spell")):
        adapter.validate_enqueue(job_type, {"batch_limit": 25}, {})
        req = request("tibiadata", job_type, entity_type)
        req = replace(req, scope={"batch_limit": 25})
        result = adapter.fetch(req)
        assert result.child_jobs and adapter.validate(result).valid


def test_tibiamaps_staged_point_is_raw_preserving_and_idempotent(db):
    registry(db)
    zone = KnowledgeEntityService.create(db, KnowledgeEntityCreate(
        entity_type="hunt_zone", canonical_name="Iksupan", language_neutral_id="hunt-zone:test:iksupan",
    ))
    adapter = TibiaMapsKnowledgeAdapter()
    raw = {
        "external_id": "marker:7:123",
        "name": "Port Hope marker",
        "x": 32595,
        "y": 32744,
        "z": 7,
        "location_name": "Iksupan",
        "location_entity_type": "hunt_zone",
        "confidence": "high",
        "source_reference": "https://github.com/tibiamaps/tibia-map-data",
        "provider_metadata": {"upstream_commit": "a" * 40, "raw_marker": {"icon": "temple"}},
        "upstream_commit": "a" * 40,
    }
    fetched = adapter.fetch(request(
        "tibiamaps", "map_point_import", "map_point", payload={"document": raw},
    ))
    assert adapter.validate(fetched).valid
    normalized = adapter.normalize(fetched.documents[0], context("tibiamaps", "map_point"))
    first = KnowledgeNormalizationService.apply(db, normalized)
    second = KnowledgeNormalizationService.apply(db, normalized)
    assert first.status == "created" and second.status == "unchanged"
    point = db.query(SpatialMapPoint).one()
    assert point.tibia_x == 32595
    assert point.source_metadata["raw_marker"] == {"icon": "temple"}
    assert point.location_entity_id == zone.uuid


class NoNetworkTibiaDataClient:
    def character(self, _name):
        raise AssertionError("renormalization must not call TibiaData")

    guild = character
    worlds = character


def test_tibiadata_stored_document_repairs_an_incomplete_canonical_entity(db):
    registry(db)
    entity = KnowledgeEntityService.create(db, KnowledgeEntityCreate(
        entity_type="character", canonical_name="Replay Knight",
        language_neutral_id="character:tibiadata:replay knight",
    ))
    mapping = KnowledgeExternalMapping(
        provider_id="tibiadata", entity_type_id="character", external_id="replay knight",
        entity_uuid=entity.uuid,
        provider_metadata={"fields": {"name": "Replay Knight"}, "supplied_fields": ["name"], "data_version": 1},
    )
    db.add(mapping)
    raw = {"character": {"character": {"name": "Replay Knight", "level": 321, "world": "Antica"}}}
    KnowledgeDocumentStore.persist(db, KnowledgeDocumentCreate(
        provider_id="tibiadata", provider_document_id="character:replay knight",
        entity_uuid=entity.uuid, raw_json=raw, version="v4",
    ))

    queued = KnowledgeFullSyncService.enqueue_renormalization(
        db, provider_id="tibiadata", entity_type="character", limit=10,
    )
    assert queued.created_count == 1
    assert queued.jobs[0].job_type == "character_renormalize"

    adapter = TibiaDataKnowledgeAdapter(NoNetworkTibiaDataClient())
    fetched = adapter.fetch(request(
        "tibiadata", "character_renormalize", "character",
        payload={"external_id": "replay knight", "_stored_document": raw},
    ))
    applied = KnowledgeNormalizationService.apply(
        db, adapter.normalize(fetched.documents[0], context("tibiadata", "character")),
    )
    db.flush()
    assert applied.status == "updated"
    assert mapping.provider_metadata["fields"]["level"] == 321
    assert mapping.provider_metadata["fields"]["world"] == "Antica"


def test_tibiamaps_renormalization_reuses_stored_staged_document_without_network(db):
    registry(db)
    raw = {"external_id": "marker:1", "name": "Replay marker", "x": 32000, "y": 32001, "z": 7}
    KnowledgeDocumentStore.persist(db, KnowledgeDocumentCreate(
        provider_id="tibiamaps", provider_document_id="map_point:marker:1", raw_json=raw, version="1",
    ))
    queued = KnowledgeFullSyncService.enqueue_renormalization(
        db, provider_id="tibiamaps", entity_type="map_point", limit=10,
    )
    assert queued.created_count == 1
    adapter = TibiaMapsKnowledgeAdapter()
    fetched = adapter.fetch(request(
        "tibiamaps", "map_point_renormalize", "map_point",
        payload={"external_id": "marker:1", "_stored_document": raw},
    ))
    normalized = adapter.normalize(fetched.documents[0], context("tibiamaps", "map_point"))
    applied = KnowledgeNormalizationService.apply(db, normalized)
    assert applied.status == "created"
    assert db.query(SpatialMapPoint).filter_by(external_id="marker:1").one().tibia_x == 32000
