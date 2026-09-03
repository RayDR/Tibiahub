from __future__ import annotations

import asyncio
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
    KnowledgeNormalizationContext,
    TibiaWikiHuntZoneAdapter,
)
from app.knowledge.dto import HuntZoneKnowledgeDTO
from app.knowledge.models import (
    KnowledgeDocument,
    KnowledgeEntity,
    KnowledgeEntityAlias,
    KnowledgeExternalMapping,
    KnowledgeJob,
    KnowledgeProvider,
    KnowledgeRelationship,
)
from app.knowledge.providers import INITIAL_PROVIDERS
from app.knowledge.registry import EntityTypeRegistry, ProviderRegistry
from app.knowledge.schemas import KnowledgeEntityCreate
from app.knowledge.services import EnqueueKnowledgeJob, KnowledgeEntityService, KnowledgeJobService
from app.knowledge.services.normalization import KnowledgeNormalizationService
from app.knowledge.services.hunt_zone_normalization import HuntZoneIdentityConflictError
from app.knowledge.workers.knowledge_worker import KnowledgeWorker
from app.models import Creature, HuntZone, SpawnLocation
from app.models.world_map import WorldMapFloor, WorldMapMarker
from app.services.external_sync_service import ExternalSyncService
from app.services.sync_service import SyncService
from tests.conftest import make_user


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


def named_raw_detail(page_id: int, title: str, *, body: str = "", image: str | None = None) -> dict:
    image_field = f"| image = {image}\n" if image is not None else ""
    wikitext = f"""{{{{Infobox Hunt
| name = {title}
{image_field}| city = Edron
| location = North of Edron
| vocation = All vocations
| lvlknights = 100
}}}}
{body}
{{{{CreatureList|type=List/Sorted
|Cursed Ape
|Missing Beast
}}}}
"""
    return {
        "parse": {"pageid": page_id, "title": title, "wikitext": {"*": wikitext}},
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


def test_catalog_excludes_namespace_and_non_entity_landing_pages_without_failing_batch():
    class MixedCatalogClient(FixtureClient):
        def fetch_catalog(self, *, continuation, limit):
            return {"query": {"categorymembers": [
                {"pageid": 10288, "title": "Hunting Places"},
                {"pageid": 110302, "title": "User:Sandbox Hunt"},
                {"pageid": 2001, "title": "Structured Grounds"},
            ]}}

    result = TibiaWikiHuntZoneAdapter(MixedCatalogClient()).fetch(
        request("catalog", scope={"batch_limit": 10}),
    )
    assert result.partial is True
    assert result.provider_metadata["invalid_members"] == 2
    assert [(child.payload["external_id"], child.payload["page_title"]) for child in result.child_jobs] == [
        ("2001", "Structured Grounds"),
    ]


def test_category_membership_without_hunt_infobox_is_retained_as_raw_only(db):
    registry(db)
    raw = {
        "parse": {
            "pageid": 10288,
            "title": "Hunting Places",
            "wikitext": {"*": "This is a directory of hunting places."},
        },
    }
    normalized = TibiaWikiHuntZoneAdapter(FixtureClient()).normalize(detail_document(raw), context())
    applied = KnowledgeNormalizationService.apply(db, normalized)
    assert normalized.action == "noop"
    assert normalized.warnings == ("unstructured_hunt_zone_page",)
    assert applied.entity_uuid is None
    assert db.query(KnowledgeEntity).filter_by(entity_type="hunt_zone").count() == 0


def test_provider_zone_does_not_promote_or_overwrite_same_name_legacy_bridge(client, db):
    registry(db)
    legacy = HuntZone(
        name="Structured Grounds",
        normalized_name="structured grounds",
        slug="structured-grounds",
        source_provider="tibiamaps",
        raw_data={"source_provider": "tibiamaps"},
    )
    creature = Creature(name="Legacy Beast", normalized_name="legacy beast", slug="legacy-beast")
    db.add_all([legacy, creature]); db.flush()
    db.add(SpawnLocation(creature_id=creature.id, hunt_zone_id=legacy.id, quantity="Unknown"))
    normalized = TibiaWikiHuntZoneAdapter(FixtureClient()).normalize(
        detail_document(named_raw_detail(2001, "Structured Grounds")),
        context(),
    )
    applied = KnowledgeNormalizationService.apply(db, normalized)
    db.flush()

    rows = db.query(HuntZone).filter_by(normalized_name="structured grounds").order_by(HuntZone.id).all()
    assert len(rows) == 2
    assert rows[0].id == legacy.id and rows[0].knowledge_entity_id is None
    assert rows[0].source_provider == "tibiamaps" and len(rows[0].creature_spawns) == 1
    assert rows[1].knowledge_entity_id == applied.entity_uuid
    assert rows[1].source_provider == "tibiawiki" and rows[1].external_id == "2001"
    detail = client.get("/api/v1/hunt-zones/structured-grounds")
    assert detail.status_code == 200
    assert detail.json()["canonical_id"] == str(applied.entity_uuid)
    listed = client.get("/api/v1/hunt-zones/", params={"search": "Structured Grounds"})
    assert listed.status_code == 200
    assert any(row["canonical_id"] == str(applied.entity_uuid) for row in listed.json())


def test_provider_defined_similar_and_exact_name_records_do_not_fuzzy_merge(db):
    registry(db)
    adapter = TibiaWikiHuntZoneAdapter(FixtureClient())
    results = []
    for page_id, title in (
        (2101, "Dragon Cave"),
        (2102, "Dragon Cave Lower"),
        (2103, "Dragon Cave"),
    ):
        results.append(KnowledgeNormalizationService.apply(
            db,
            adapter.normalize(detail_document(named_raw_detail(page_id, title)), context()),
        ))
    db.flush()

    assert len({result.entity_uuid for result in results}) == 3
    mappings = db.query(KnowledgeExternalMapping).filter_by(entity_type_id="hunt_zone").all()
    assert {mapping.external_id for mapping in mappings} == {"2101", "2102", "2103"}
    exact = db.query(KnowledgeEntity).filter_by(entity_type="hunt_zone", canonical_name="Dragon Cave").all()
    assert len(exact) == 2
    assert len({entity.slug for entity in exact}) == 2


def test_provider_rename_keeps_uuid_mapping_and_prior_name_alias(db):
    registry(db)
    adapter = TibiaWikiHuntZoneAdapter(FixtureClient())
    first = KnowledgeNormalizationService.apply(
        db,
        adapter.normalize(detail_document(named_raw_detail(2201, "Old Grounds")), context()),
    )
    second = KnowledgeNormalizationService.apply(
        db,
        adapter.normalize(detail_document(named_raw_detail(2201, "Renamed Grounds")), context()),
    )
    db.flush()

    assert second.entity_uuid == first.entity_uuid
    entity = db.get(KnowledgeEntity, first.entity_uuid)
    assert entity.canonical_name == "Renamed Grounds"
    assert {alias.alias for alias in entity.aliases} >= {"Old Grounds", "Renamed Grounds"}
    assert db.query(KnowledgeExternalMapping).filter_by(external_id="2201").count() == 1
    assert db.query(HuntZone).filter_by(knowledge_entity_id=entity.uuid).one().name == "Renamed Grounds"


def test_explicit_provider_alias_replay_is_deduplicated(db):
    registry(db)
    raw = named_raw_detail(2251, "Canonical Grounds")
    raw["parse"]["title"] = "Provider Grounds Page"
    adapter = TibiaWikiHuntZoneAdapter(FixtureClient())
    normalized = adapter.normalize(detail_document(raw), context())
    first = KnowledgeNormalizationService.apply(db, normalized)
    relationship_count = db.query(KnowledgeRelationship).filter_by(
        source_entity_id=first.entity_uuid,
        is_current=True,
    ).count()
    second = KnowledgeNormalizationService.apply(db, normalized)
    db.flush()
    aliases = db.query(KnowledgeEntityAlias).filter_by(entity_uuid=first.entity_uuid).all()
    assert second.entity_uuid == first.entity_uuid and second.aliases_created == 0
    assert {alias.alias for alias in aliases} == {"Canonical Grounds", "Provider Grounds Page"}
    assert db.query(KnowledgeRelationship).filter_by(
        source_entity_id=first.entity_uuid,
        is_current=True,
    ).count() == relationship_count


def test_multiple_unmapped_exact_candidates_are_ambiguous_and_not_auto_resolved(db):
    registry(db)
    first = KnowledgeEntityService.create(db, KnowledgeEntityCreate(
        entity_type="hunt_zone",
        canonical_name="Collision Grounds",
        language_neutral_id="hunt-zone:manual:collision-one",
    ))
    second = KnowledgeEntityService.create(db, KnowledgeEntityCreate(
        entity_type="hunt_zone",
        canonical_name="Collision Grounds",
        language_neutral_id="hunt-zone:manual:collision-two",
        allow_name_collision=True,
        slug_suffix="two",
    ))
    with pytest.raises(HuntZoneIdentityConflictError) as error:
        KnowledgeNormalizationService.apply(
            db,
            TibiaWikiHuntZoneAdapter(FixtureClient()).normalize(
                detail_document(named_raw_detail(2252, "Collision Grounds")), context(),
            ),
        )
    assert getattr(error.value, "code", None) == "hunt_zone_identity_conflict"
    assert db.query(KnowledgeEntity).filter_by(entity_type="hunt_zone").count() == 2
    assert db.query(KnowledgeExternalMapping).filter_by(entity_type_id="hunt_zone").count() == 0
    assert {first.uuid, second.uuid}


def test_explicit_provider_media_and_nullable_metadata_are_preserved(client, db):
    registry(db)
    raw = named_raw_detail(2301, "Illustrated Grounds", image="Cursed Ape")
    normalized = TibiaWikiHuntZoneAdapter(FixtureClient()).normalize(detail_document(raw), context())
    dto = HuntZoneKnowledgeDTO.from_canonical_data(normalized.canonical_data)
    assert dto.image_reference.endswith("/Special:FilePath/Cursed_Ape.gif")
    assert "image_reference" in dto.supplied_fields
    assert dto.premium_required is None
    assert dto.experience_rating is None and dto.loot_rating is None
    KnowledgeNormalizationService.apply(db, normalized)
    db.commit()
    media = client.get("/api/v1/hunt-zones/illustrated-grounds").json()["representative_media"]
    assert media["status"] == "reference_only"
    assert media["kind"] == "provider_image_reference" and media["url"] is None


def test_city_relationship_does_not_create_geometry_and_location_prose_stays_text(db):
    registry(db)
    town = KnowledgeEntityService.create(db, KnowledgeEntityCreate(
        entity_type="location", canonical_name="Edron", language_neutral_id="location:test:edron",
    ))
    applied = KnowledgeNormalizationService.apply(
        db,
        TibiaWikiHuntZoneAdapter(FixtureClient()).normalize(
            detail_document(named_raw_detail(2401, "City Only Grounds")), context(),
        ),
    )
    db.flush()
    zone = db.query(HuntZone).filter_by(knowledge_entity_id=applied.entity_uuid).one()
    relationships = db.query(KnowledgeRelationship).filter_by(
        source_entity_id=applied.entity_uuid,
        is_current=True,
    ).all()
    assert any(row.relationship_type_code == "located_at" and row.target_entity_id == town.uuid for row in relationships)
    assert not any(row.unresolved_name == "North of Edron" for row in relationships)
    assert zone.region == "North of Edron"
    assert zone.map_x is None and zone.map_y is None and zone.map_z is None and zone.map_bounds is None


def test_expanded_mapper_link_is_not_promoted_to_location_text_or_geometry():
    raw = named_raw_detail(2402, "Mapped Prose Grounds")
    raw["parse"]["wikitext"]["*"] = raw["parse"]["wikitext"]["*"].replace(
        "| location = North of Edron",
        "| location = Tiquanda, [https://tibia.fandom.com/wiki/Mapper?coords=123-456-7-4-1-1 here]",
    )
    dto = HuntZoneKnowledgeDTO.from_canonical_data(
        TibiaWikiHuntZoneAdapter(FixtureClient()).normalize(detail_document(raw), context()).canonical_data,
    )
    assert dto.location == "Tiquanda"
    assert "coords=" not in dto.location


def _floor(db) -> WorldMapFloor:
    floor = WorldMapFloor(
        provider="tibiamaps/tibia-map-data",
        upstream_commit="f" * 40,
        upstream_url="https://github.com/tibiamaps/tibia-map-data",
        license_name="MIT",
        attribution="fixture",
        floor=7,
        map_path="/tmp/floor-7.png",
        map_sha256="a" * 64,
        width=2560,
        height=2048,
        min_x=31744,
        min_y=30976,
        max_x=34304,
        max_y=33024,
        source_metadata={},
        is_current=True,
    )
    db.add(floor); db.flush()
    return floor


def _unresolved_marker(db, floor: WorldMapFloor, name: str, index: int = 1) -> WorldMapMarker:
    marker = WorldMapMarker(
        floor_id=floor.id,
        source_index=index,
        description=name,
        normalized_description=name.casefold(),
        x=32100,
        y=32000,
        floor=7,
        raw_data={},
        resolution_state="unresolved",
    )
    db.add(marker); db.flush()
    return marker


def test_exact_tibiamaps_marker_is_enriched_but_near_name_is_not(client, db):
    registry(db)
    floor = _floor(db)
    exact = _unresolved_marker(db, floor, "Marker Grounds")
    near = _unresolved_marker(db, floor, "Marker Grounds Lower", 2)
    applied = KnowledgeNormalizationService.apply(
        db,
        TibiaWikiHuntZoneAdapter(FixtureClient()).normalize(
            detail_document(named_raw_detail(2501, "Marker Grounds")), context(),
        ),
    )
    db.flush()
    assert exact.resolution_state == "resolved" and exact.resolved_entity_id == applied.entity_uuid
    assert exact.resolution_method == "exact_canonical_name_or_alias"
    assert near.resolution_state == "unresolved" and near.resolved_entity_id is None
    map_payload = client.get("/api/v1/map/layers/hunt_zone").json()
    assert map_payload["total"] == 1
    assert map_payload["items"][0]["canonical_entity_id"] == str(applied.entity_uuid)
    assert map_payload["items"][0]["spatial_state"] == "resolved_point"


def test_cross_type_exact_marker_collision_remains_ambiguous(db):
    registry(db)
    KnowledgeEntityService.create(db, KnowledgeEntityCreate(
        entity_type="location",
        canonical_name="Shared Grounds",
        language_neutral_id="location:test:shared-grounds",
    ))
    marker = _unresolved_marker(db, _floor(db), "Shared Grounds")
    KnowledgeNormalizationService.apply(
        db,
        TibiaWikiHuntZoneAdapter(FixtureClient()).normalize(
            detail_document(named_raw_detail(2502, "Shared Grounds")), context(),
        ),
    )
    db.flush()
    assert marker.resolution_state == "ambiguous"
    assert marker.resolved_entity_id is None and marker.resolution_method is None


def test_unresolved_zone_relationship_is_visible_in_existing_knowledge_review(client, db):
    registry(db)
    applied = KnowledgeNormalizationService.apply(
        db,
        TibiaWikiHuntZoneAdapter(FixtureClient()).normalize(
            detail_document(named_raw_detail(2601, "Review Grounds")), context(),
        ),
    )
    admin = make_user(db, username="hunt-review-admin", is_superuser=True)
    db.commit()
    response = client.get(
        "/api/v1/admin/knowledge/relationships/review",
        params={"resolution_state": "unresolved", "provider_id": "tibiawiki"},
        headers={"Authorization": f"Bearer {create_access_token(admin.username)}"},
    )
    assert response.status_code == 200
    rows = [row for row in response.json()["items"] if row["source_entity_id"] == str(applied.entity_uuid)]
    assert rows
    assert {row["source_type"] for row in rows} == {"hunt_zone"}
    assert {row["unresolved_name"] for row in rows} >= {"Missing Beast"}


def test_manual_hunt_catalog_requires_explicit_confirmation(client, db):
    registry(db)
    provider = db.get(KnowledgeProvider, "tibiawiki")
    provider.enabled = True
    admin = make_user(db, username="hunt-catalog-admin", is_superuser=True)
    db.commit()
    payload = {
        "provider_id": "tibiawiki",
        "job_type": "hunt_zone_catalog",
        "entity_type": "hunt_zone",
        "scope": {"batch_limit": 10},
        "payload": {},
    }
    headers = {"Authorization": f"Bearer {create_access_token(admin.username)}"}
    rejected = client.post("/api/v1/admin/knowledge/jobs", json=payload, headers=headers)
    assert rejected.status_code == 400
    assert rejected.json()["detail"]["code"] == "knowledge_catalog_confirmation_required"
    payload["confirm_catalog_sync"] = True
    accepted = client.post("/api/v1/admin/knowledge/jobs", json=payload, headers=headers)
    assert accepted.status_code == 201


def test_legacy_direct_hunting_place_sync_cannot_bypass_knowledge(db):
    before = db.query(HuntZone).count()
    result = asyncio.run(ExternalSyncService.sync_hunting_places(db))
    assert result["status"] == "deprecated"
    assert result["reason"] == "Use the durable tibiawiki hunt_zone_catalog Knowledge job"
    assert db.query(HuntZone).count() == before
    with pytest.raises(ValueError, match="Direct HuntZone upserts are disabled"):
        SyncService._upsert_hunt_zone(db, {"name": "Unsafe Category Title"})
    assert db.query(HuntZone).count() == before


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
        relationships = db.query(KnowledgeRelationship).filter_by(
            source_entity_id=document.entity_uuid,
            is_current=True,
        ).all()
        assert relationships
        assert {row.source_document_id for row in relationships} == {document.uuid}
        assert {str(row.source_job_id) for row in relationships} == {
            document.document_metadata["knowledge_job_id"],
        }
    engine.dispose()
