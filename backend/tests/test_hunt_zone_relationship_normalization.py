from __future__ import annotations

from uuid import uuid4

import pytest

from app.knowledge.adapters.protocol import CanonicalEntityCandidate, KnowledgeNormalizationResult
from app.knowledge.dto import CreatureKnowledgeDTO, HuntZoneKnowledgeDTO
from app.knowledge.metadata import refresh_search_metadata
from app.knowledge.models import (
    KnowledgeDocument,
    KnowledgeEntity,
    KnowledgeEntityAlias,
    KnowledgeExternalMapping,
    KnowledgeRelationship,
)
from app.knowledge.providers import INITIAL_PROVIDERS
from app.knowledge.registry import EntityTypeRegistry, ProviderRegistry, RelationshipTypeRegistry
from app.knowledge.schemas import KnowledgeEntityCreate
from app.knowledge.services import KnowledgeEntityService
from app.knowledge.services.hunt_zone_normalization import HuntZoneIdentityConflictError
from app.knowledge.services.hunt_zone_relationships import (
    HUNT_ZONE_LOCATION_SCOPE,
    HuntZoneRelationshipRepairService,
    normalize_creature_hunt_zone_relationships,
)
from app.knowledge.services.normalization import KnowledgeNormalizationService
from app.models import Creature, HuntZone, SpawnLocation
from app.models.world_map import WorldMapFloor, WorldMapMarker
from app.services.creature_storage_service import upsert_creature_payload


def _registry(db) -> None:
    EntityTypeRegistry.register_initial(db)
    RelationshipTypeRegistry.register_initial(db)
    for definition in INITIAL_PROVIDERS:
        ProviderRegistry.register(db, definition)
    db.flush()


def _entity(db, entity_type: str, name: str, *, suffix: str | None = None) -> KnowledgeEntity:
    return KnowledgeEntityService.create(db, KnowledgeEntityCreate(
        entity_type=entity_type,
        canonical_name=name,
        language_neutral_id=f"phase3c:{entity_type}:{suffix or name}:{uuid4()}",
    ))


def _document(db, creature: Creature) -> KnowledgeDocument:
    row = KnowledgeDocument(
        provider_id="tibiawiki",
        provider_document_id=f"creature:{creature.external_id}",
        entity_uuid=creature.knowledge_entity_id,
        raw_json={"name": creature.name, "locations": list(creature.locations or [])},
        checksum=uuid4().hex + uuid4().hex,
        content_identity=uuid4().hex + uuid4().hex,
        document_metadata={"knowledge_job_id": None},
    )
    db.add(row)
    db.flush()
    return row


def _zone_result(*, external_id: str, name: str, aliases: tuple[str, ...] = ()):
    dto = HuntZoneKnowledgeDTO(
        external_id=external_id,
        canonical_name=name,
        slug=name.casefold().replace(" ", "-"),
        aliases=aliases,
        source_reference=f"https://tibia.fandom.com/wiki/{name.replace(' ', '_')}",
        supplied_fields=frozenset({"canonical_name", "slug", "source_reference"}),
    )
    return KnowledgeNormalizationResult(
        action="upsert",
        candidate=CanonicalEntityCandidate(
            entity_type="hunt_zone",
            canonical_name=name,
            language_neutral_id=dto.language_neutral_id,
            aliases=aliases,
        ),
        provider_code="tibiawiki",
        external_id=external_id,
        canonical_data=dto.to_canonical_data(),
    )


def test_exact_unresolved_and_fuzzy_safe_relationship_replay_reaches_api(client, db):
    _registry(db)
    zone_entity = _entity(db, "hunt_zone", "Exact Grounds")
    creature_entity = _entity(db, "creature", "Exact Beast")
    zone = HuntZone(name="Exact Grounds", normalized_name="exact grounds", min_level=None)
    creature = Creature(
        name="Exact Beast",
        normalized_name="exact beast",
        slug="exact-beast",
        external_id="7001",
        source_name="tibiawiki",
        knowledge_entity_id=creature_entity.uuid,
        locations=["Exact Grounds", "Exact Ground", "north of Exact Grounds, past the bridge"],
        experience=500,
        is_boss=False,
    )
    db.add_all([zone, creature])
    db.flush()
    db.add(SpawnLocation(creature_id=creature.id, hunt_zone_id=zone.id, quantity="One"))
    document = _document(db, creature)

    first = normalize_creature_hunt_zone_relationships(
        db,
        creature_entity_uuid=creature_entity.uuid,
        creature_name=creature.name,
        locations=tuple(creature.locations),
        provider_id="tibiawiki",
        source_document_id=f"creature:{creature.external_id}",
    )
    db.flush()
    ids = {
        row.id for row in db.query(KnowledgeRelationship).filter_by(
            source_entity_id=creature_entity.uuid,
            source_scope=HUNT_ZONE_LOCATION_SCOPE,
            is_current=True,
        )
    }
    second = normalize_creature_hunt_zone_relationships(
        db,
        creature_entity_uuid=creature_entity.uuid,
        creature_name=creature.name,
        locations=tuple(creature.locations),
        provider_id="tibiawiki",
        source_document_id=f"creature:{creature.external_id}",
    )
    db.commit()

    assert (first.resolved, first.unresolved, first.ambiguous, first.bridges_recovered) == (1, 2, 0, 1)
    assert second.relationships_created == 0 and second.bridges_recovered == 0
    rows = db.query(KnowledgeRelationship).filter_by(
        source_entity_id=creature_entity.uuid,
        source_scope=HUNT_ZONE_LOCATION_SCOPE,
        is_current=True,
    ).all()
    assert {row.id for row in rows} == ids
    assert {row.resolution_state for row in rows} == {"resolved", "unresolved"}
    assert {row.source_document_id for row in rows} == {document.uuid}
    assert {row.source_context["resolution_policy"] for row in rows} == {
        "exact_name_or_verified_alias_only"
    }
    assert db.query(KnowledgeEntity).filter_by(entity_type="hunt_zone").count() == 1
    assert zone.knowledge_entity_id == zone_entity.uuid

    payload = client.get("/api/v1/hunt-zones/exact-grounds").json()
    assert payload["canonical_id"] == str(zone_entity.uuid)
    assert [value["canonical_id"] for value in payload["creatures"]] == [str(creature_entity.uuid)]


def test_ambiguous_exact_zone_identity_stays_ambiguous_without_bridge(db):
    _registry(db)
    first = KnowledgeEntity(
        entity_type="hunt_zone",
        canonical_name="Shared Grounds",
        slug="shared-grounds-a",
        language_neutral_id="phase3c:shared:a",
    )
    second = KnowledgeEntity(
        entity_type="hunt_zone",
        canonical_name="Shared Grounds",
        slug="shared-grounds-b",
        language_neutral_id="phase3c:shared:b",
    )
    creature = _entity(db, "creature", "Shared Beast")
    db.add_all([first, second])
    db.flush()
    refresh_search_metadata(first)
    refresh_search_metadata(second)
    legacy = HuntZone(name="Shared Grounds", normalized_name="shared grounds", min_level=None)
    db.add(legacy)
    db.flush()

    result = normalize_creature_hunt_zone_relationships(
        db,
        creature_entity_uuid=creature.uuid,
        creature_name="Shared Beast",
        locations=("Shared Grounds",),
        provider_id="tibiawiki",
        source_document_id="creature:shared",
    )
    relation = db.query(KnowledgeRelationship).filter_by(
        source_entity_id=creature.uuid,
        source_scope=HUNT_ZONE_LOCATION_SCOPE,
        is_current=True,
    ).one()
    assert result.ambiguous == 1 and result.resolved == 0
    assert relation.resolution_state == "ambiguous" and relation.target_entity_id is None
    assert len(relation.source_context["candidate_entity_ids"]) == 2
    assert legacy.knowledge_entity_id is None


def test_historical_repair_is_bounded_replay_safe_and_skips_noncanonical_sources(db):
    _registry(db)
    zone = _entity(db, "hunt_zone", "Replay Grounds")
    canonical_creature = _entity(db, "creature", "Replay Beast")
    domain_zone = HuntZone(name="Replay Grounds", normalized_name="replay grounds", min_level=None)
    bridged = Creature(
        name="Replay Beast",
        normalized_name="replay beast",
        external_id="8001",
        source_name="tibiawiki",
        knowledge_entity_id=canonical_creature.uuid,
        locations=["Replay Grounds"],
    )
    category_row = Creature(
        name="Category Page",
        normalized_name="category page",
        external_id="8002",
        source_name="tibiawiki",
        locations=["Replay Grounds"],
    )
    db.add_all([domain_zone, bridged, category_row])
    db.flush()
    _document(db, bridged)

    first = HuntZoneRelationshipRepairService.run_batch(db, limit=100)
    db.flush()
    relation_ids = {row.id for row in db.query(KnowledgeRelationship).filter_by(
        source_scope=HUNT_ZONE_LOCATION_SCOPE,
        is_current=True,
    )}
    second = HuntZoneRelationshipRepairService.run_batch(db, limit=100)
    db.flush()

    assert first.processed_creatures == 1 and first.skipped_creatures == 1
    assert first.metrics.resolved == 1 and first.metrics.bridges_recovered == 1
    assert second.metrics.relationships_created == 0 and second.metrics.bridges_recovered == 0
    assert {row.id for row in db.query(KnowledgeRelationship).filter_by(
        source_scope=HUNT_ZONE_LOCATION_SCOPE,
        is_current=True,
    )} == relation_ids
    assert domain_zone.knowledge_entity_id == zone.uuid


def test_hunt_zone_provider_mapping_and_alias_replay_reuses_existing_entity(db):
    _registry(db)
    entity = _entity(db, "hunt_zone", "Mapped Grounds")
    first = KnowledgeNormalizationService.apply(
        db,
        _zone_result(
            external_id="9001",
            name="Mapped Grounds",
            aliases=("The Mapped Grounds",),
        ),
    )
    second = KnowledgeNormalizationService.apply(
        db,
        _zone_result(
            external_id="9001",
            name="Mapped Grounds",
            aliases=("The Mapped Grounds",),
        ),
    )
    db.flush()

    mapping = db.query(KnowledgeExternalMapping).filter_by(
        provider_id="tibiawiki",
        entity_type_id="hunt_zone",
        external_id="9001",
    ).one()
    aliases = db.query(KnowledgeEntityAlias).filter_by(entity_uuid=entity.uuid).all()
    assert first.entity_uuid == second.entity_uuid == entity.uuid
    assert mapping.entity_uuid == entity.uuid
    assert sum(alias.normalized_alias == "the mapped grounds" for alias in aliases) == 1
    assert db.query(KnowledgeEntity).filter_by(entity_type="hunt_zone").count() == 1
    assert db.query(HuntZone).count() == 1


def test_ambiguous_provider_zone_identity_fails_without_creating_a_third_entity(db):
    _registry(db)
    for suffix in ("a", "b"):
        row = KnowledgeEntity(
            entity_type="hunt_zone",
            canonical_name="Duplicate Grounds",
            slug=f"duplicate-grounds-{suffix}",
            language_neutral_id=f"phase3c:duplicate:{suffix}",
        )
        db.add(row)
        db.flush()
        refresh_search_metadata(row)

    with pytest.raises(HuntZoneIdentityConflictError):
        KnowledgeNormalizationService.apply(
            db,
            _zone_result(external_id="9999", name="Duplicate Grounds"),
        )
    assert db.query(KnowledgeEntity).filter_by(entity_type="hunt_zone").count() == 2
    assert db.query(KnowledgeExternalMapping).filter_by(entity_type_id="hunt_zone").count() == 0
    assert db.query(HuntZone).count() == 0


def test_zone_normalization_reconciles_only_exact_tibiamaps_marker(client, db):
    _registry(db)
    floor = WorldMapFloor(
        provider="tibiamaps/tibia-map-data",
        upstream_commit="c" * 40,
        upstream_url="https://github.com/tibiamaps/tibia-map-data",
        license_name="MIT",
        attribution="test fixture",
        floor=7,
        map_path="/tmp/phase3c-floor.png",
        map_sha256="d" * 64,
        width=2560,
        height=2048,
        min_x=31744,
        min_y=30976,
        max_x=34304,
        max_y=33024,
        source_metadata={},
        is_current=True,
    )
    db.add(floor)
    db.flush()
    exact = WorldMapMarker(
        floor_id=floor.id,
        source_index=1,
        description="Marker Grounds",
        normalized_description="marker grounds",
        x=32200,
        y=32000,
        floor=7,
        raw_data={},
        resolution_state="unresolved",
    )
    near = WorldMapMarker(
        floor_id=floor.id,
        source_index=2,
        description="Marker Ground",
        normalized_description="marker ground",
        x=32201,
        y=32001,
        floor=7,
        raw_data={},
        resolution_state="unresolved",
    )
    db.add_all([exact, near])
    db.flush()

    applied = KnowledgeNormalizationService.apply(
        db,
        _zone_result(external_id="9100", name="Marker Grounds"),
    )
    db.commit()

    assert applied.metrics["world_map_markers_reconciled"] == 1
    assert exact.resolution_state == "resolved" and exact.resolved_entity_id == applied.entity_uuid
    assert exact.resolution_method == "exact_canonical_name_or_alias"
    assert near.resolution_state == "unresolved" and near.resolved_entity_id is None
    payload = client.get("/api/v1/hunt-zones/marker-grounds").json()
    assert payload["spatial_state"] == "resolved_point"
    assert payload["spatial"]["geometry_source"] == "tibiamaps_marker"
    assert payload["spatial"]["z"] == 7


def test_creature_normalization_pipeline_reconciles_zone_locations_on_replay(db):
    _registry(db)
    zone = _entity(db, "hunt_zone", "Pipeline Grounds")
    db.add(HuntZone(name="Pipeline Grounds", normalized_name="pipeline grounds", min_level=None))
    db.flush()
    dto = CreatureKnowledgeDTO(
        external_id="9200",
        canonical_name="Pipeline Beast",
        slug="pipeline-beast",
        locations=("Pipeline Grounds", "Pipeline Ground"),
        provider_metadata={},
        provided_fields=frozenset({"locations"}),
    )
    normalization = KnowledgeNormalizationResult(
        action="upsert",
        candidate=CanonicalEntityCandidate(
            entity_type="creature",
            canonical_name=dto.canonical_name,
            language_neutral_id=dto.language_neutral_id,
        ),
        provider_code="tibiawiki",
        external_id=dto.external_id,
        canonical_data=dto.to_canonical_data(),
    )

    first = KnowledgeNormalizationService.apply(db, normalization)
    second = KnowledgeNormalizationService.apply(db, normalization)
    rows = db.query(KnowledgeRelationship).filter_by(
        source_entity_id=first.entity_uuid,
        source_scope=HUNT_ZONE_LOCATION_SCOPE,
        is_current=True,
    ).all()

    assert first.metrics["hunt_zone_relationships_resolved"] == 1
    assert first.metrics["hunt_zone_relationships_unresolved"] == 1
    assert second.metrics["hunt_zone_relationships_created"] == 0
    assert len(rows) == 2
    assert db.query(HuntZone).one().knowledge_entity_id == zone.uuid


def test_legacy_creature_storage_only_creates_zone_bridge_for_exact_canonical_identity(db):
    _registry(db)
    zone = _entity(db, "hunt_zone", "Storage Grounds")
    creature = upsert_creature_payload(db, {
        "id": 9300,
        "name": "Storage Beast",
        "locations": ["Storage Grounds", "Storage Ground"],
        "hitpoints": 100,
        "experience": 100,
    })
    db.flush()

    rows = db.query(HuntZone).all()
    assert [(row.name, row.knowledge_entity_id) for row in rows] == [
        ("Storage Grounds", zone.uuid),
    ]
    spawns = db.query(SpawnLocation).filter_by(creature_id=creature.id).all()
    assert [spawn.hunt_zone.name for spawn in spawns] == ["Storage Grounds"]
    assert creature.locations == ["Storage Grounds", "Storage Ground"]
