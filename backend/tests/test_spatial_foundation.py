from __future__ import annotations

from uuid import uuid4

import pytest

from app.core.security import create_access_token
from app.knowledge.dto import MapPointDTO, MapRegionDTO, RouteDTO, RouteStepDTO
from app.knowledge.models import (
    KnowledgeDocument,
    KnowledgeRelationship,
    SpatialEntityLocationLink,
    SpatialMapPoint,
    SpatialMapRegion,
    SpatialRoute,
)
from app.knowledge.registry import EntityTypeRegistry, ProviderRegistry, RelationshipTypeRegistry
from app.knowledge.schemas import KnowledgeEntityCreate
from app.knowledge.services import KnowledgeEntityService, KnowledgeGraphService, RelationshipInput
from app.knowledge.services import repair_document_provenance
from app.knowledge.services.spatial import (
    link_entity_to_location,
    persist_map_point,
    persist_map_region,
    persist_route,
)
from app.models import TibiaWikiLocation
from app.models.workspace_audit import WorkspaceAudit
from tests.conftest import make_user


@pytest.fixture
def spatial_registry(db):
    EntityTypeRegistry.register_initial(db)
    ProviderRegistry.register_initial(db)
    RelationshipTypeRegistry.register_initial(db)
    db.flush()


def entity(db, entity_type: str, name: str):
    return KnowledgeEntityService.create(db, KnowledgeEntityCreate(
        entity_type=entity_type,
        canonical_name=name,
        language_neutral_id=f"{entity_type}:spatial-test:{uuid4()}",
    ))


def polygon(x: int = 32360, y: int = 32230, z: int = 7):
    return {
        "type": "Polygon",
        "coordinates": [[
            [x, y, z], [x + 20, y, z], [x + 20, y + 20, z],
            [x, y + 20, z], [x, y, z],
        ]],
    }


def test_provider_neutral_dtos_enforce_trusted_complete_bounded_spatial_data():
    assert MapPointDTO("p1", "Temple", 32369, 32241, 7).resolved is True
    assert MapPointDTO("p2", "Unknown").resolved is False
    with pytest.raises(ValueError, match="complete"):
        MapPointDTO("bad", "Partial", 32369, None, 7)
    with pytest.raises(ValueError, match="three-dimensional"):
        MapRegionDTO("bad", "Flat", {"type": "Polygon", "coordinates": [[[1, 2], [2, 2], [1, 2]]]})
    with pytest.raises(ValueError, match="minimum_z"):
        MapRegionDTO("bad-floor", "Wrong Floor", polygon(), minimum_z=6, maximum_z=7)
    with pytest.raises(ValueError, match="ascending"):
        RouteDTO("bad", "Backwards", (RouteStepDTO(2, instruction="Second"), RouteStepDTO(1, instruction="First")))
    with pytest.raises(ValueError, match="250"):
        RouteStepDTO(251, instruction="Too far")


def test_point_region_route_persistence_graph_and_versioning(db, spatial_registry):
    location = entity(db, "location", "Thais Temple")
    destination = entity(db, "location", "Thais Depot")

    point_dto = MapPointDTO("thais-temple", "Thais Temple Marker", 32369, 32241, 7,
                            location_name="Thais Temple", confidence="high")
    point = persist_map_point(db, point_dto)
    assert persist_map_point(db, point_dto).id == point.id
    assert point.location_entity_id == location.uuid and point.version == 1 and point.is_current
    assert str(point.geom).startswith("POINT Z")

    changed = persist_map_point(db, MapPointDTO(
        "thais-temple", "Thais Temple Marker", 32370, 32241, 7,
        location_name="Thais Temple", confidence="high",
    ))
    db.flush()
    db.refresh(point)
    db.refresh(changed)
    assert changed.version == 2 and changed.is_current and point.is_current is False
    assert point.valid_until == changed.valid_from
    links = db.query(SpatialEntityLocationLink).filter_by(external_id="point:thais-temple").order_by(
        SpatialEntityLocationLink.version,
    ).all()
    assert [(row.version, row.is_current) for row in links] == [(1, False), (2, True)]
    assert links[0].valid_until == links[1].valid_from

    region = persist_map_region(db, MapRegionDTO(
        "thais-centre", "Thais Centre", polygon(), location_name="Thais Temple",
        minimum_z=7, maximum_z=7, confidence="medium",
    ))
    assert persist_map_region(db, MapRegionDTO(
        "thais-centre", "Thais Centre", polygon(), location_name="Thais Temple",
        minimum_z=7, maximum_z=7, confidence="medium",
    )).id == region.id
    route_dto = RouteDTO(
        "temple-depot", "Temple to Depot",
        (
            RouteStepDTO(1, "Leave the temple", "Thais Temple", 32369, 32241, 7),
            RouteStepDTO(2, "Enter the depot", "Thais Depot", 32375, 32245, 7),
        ),
        start_location_name="Thais Temple", end_location_name="Thais Depot", confidence="high",
    )
    route = persist_route(db, route_dto)
    assert persist_route(db, route_dto).id == route.id
    changed_route = persist_route(db, RouteDTO(
        "temple-depot", "Temple to Depot",
        (
            RouteStepDTO(1, "Leave the temple", "Thais Temple", 32369, 32241, 7),
            RouteStepDTO(2, "Enter the depot through the east door", "Thais Depot", 32375, 32245, 7),
        ),
        start_location_name="Thais Temple", end_location_name="Thais Depot", confidence="high",
    ))
    db.flush()
    db.refresh(route)
    db.refresh(changed_route)

    assert isinstance(region, SpatialMapRegion) and region.location_entity_id == location.uuid
    assert isinstance(changed_route, SpatialRoute) and [step.sequence for step in changed_route.steps] == [1, 2]
    assert changed_route.version == 2 and changed_route.is_current and route.is_current is False
    assert route.valid_until == changed_route.valid_from
    assert changed_route.start_location_entity_id == location.uuid and changed_route.end_location_entity_id == destination.uuid
    relationships = {(row.relationship_type_code, row.resolution_state) for row in db.query(KnowledgeRelationship).all()}
    assert ("represented_by", "resolved") in relationships
    assert {("starts_at", "resolved"), ("ends_at", "resolved"), ("passes_through", "resolved")} <= relationships


def test_unresolved_and_ambiguous_references_are_preserved_without_guessing(db, spatial_registry):
    entity(db, "location", "Shared Place")
    entity(db, "area", "Shared Place")
    ambiguous = persist_map_point(db, MapPointDTO(
        "shared", "Shared Marker", 32000, 32000, 7, location_name="Shared Place",
    ))
    unresolved = persist_map_point(db, MapPointDTO(
        "missing", "Unknown Marker", location_name="Neverland",
    ))
    route = persist_route(db, RouteDTO(
        "unknown-route", "Unknown Route", (RouteStepDTO(1, location_name="Nowhere"),),
        start_location_name="Nowhere", end_location_name="Elsewhere",
    ))
    db.flush()

    assert ambiguous.location_entity_id is None and ambiguous.unresolved_location_name == "Shared Place"
    assert ambiguous.verification_state == "ambiguous"
    assert unresolved.geom is None and unresolved.verification_state == "unresolved"
    assert route.start_location_entity_id is None and route.unresolved_start_name == "Nowhere"
    graph_states = {row.unresolved_name: row.resolution_state for row in db.query(KnowledgeRelationship).filter(
        KnowledgeRelationship.relationship_type_code.in_(["starts_at", "ends_at", "passes_through"]),
    )}
    assert graph_states["Nowhere"] == "unresolved" and graph_states["Elsewhere"] == "unresolved"


def test_route_replay_repairs_existing_raw_document_provenance_idempotently(db, spatial_registry):
    route_dto = RouteDTO(
        "route-closure", "Closure Route",
        (RouteStepDTO(1, location_name="Unknown Closure Place"),),
        end_location_name="Unknown Closure Place",
        source_reference="https://example.invalid/route/closure",
    )
    route = persist_route(db, route_dto, provider="tibiawiki")
    document = KnowledgeDocument(
        provider_id="tibiawiki",
        provider_document_id="route:route-closure",
        entity_uuid=route.knowledge_entity_id,
        raw_json={"fixture": True},
        checksum="a" * 64,
        content_identity="b" * 64,
    )
    db.add(document)
    db.flush()

    replayed = persist_route(
        db,
        route_dto,
        provider="tibiawiki",
        source_document_ref="route:route-closure",
    )
    db.flush()

    assert replayed.id == route.id
    assert route.source_document_id == document.uuid
    relationships = db.query(KnowledgeRelationship).filter_by(
        source_entity_id=route.knowledge_entity_id,
        is_current=True,
    ).all()
    assert relationships
    assert {row.source_document_id for row in relationships} == {document.uuid}
    assert {row.source_context["source_document_ref"] for row in relationships} == {
        "route:route-closure"
    }
    assert {row.source_context["source_reference"] for row in relationships} == {
        route_dto.source_reference
    }

    report = repair_document_provenance(db, apply=True)
    assert report.relationships_repaired == 0
    assert report.spatial_routes_repaired == 0


def test_entity_location_link_is_idempotent_and_uses_unified_graph(db, spatial_registry):
    creature = entity(db, "creature", "Rat")
    location = entity(db, "location", "Thais Sewers")
    first = link_entity_to_location(db, source_entity=creature, location_name="Thais Sewers", external_id="rat-sewers")
    second = link_entity_to_location(db, source_entity=creature, location_name="Thais Sewers", external_id="rat-sewers")
    db.flush()
    assert first.id == second.id and first.location_entity_id == location.uuid
    assert db.query(SpatialEntityLocationLink).filter_by(external_id="rat-sewers").count() == 1
    assert db.query(KnowledgeRelationship).filter_by(
        source_entity_id=creature.uuid, relationship_type_code="located_at", is_current=True,
    ).count() == 1


def test_local_apis_are_bounded_network_free_and_steps_are_ordered(client, db, spatial_registry, monkeypatch):
    location = entity(db, "location", "Carlin Depot")
    quest = entity(db, "quest", "Carlin Map Quest")
    db.add(TibiaWikiLocation(
        name="Carlin Depot", normalized_name="carlin depot", slug="carlin-depot",
        external_id="500", source_name="tibiawiki", knowledge_entity_id=location.uuid,
    ))
    point = persist_map_point(db, MapPointDTO(
        "carlin-depot", "Carlin Depot Marker", 32324, 31782, 7,
        location_name="Carlin Depot", confidence="high",
    ))
    route = persist_route(db, RouteDTO(
        "carlin-walk", "Carlin Walk",
        (RouteStepDTO(1, "Start", "Carlin Depot"), RouteStepDTO(2, "Finish", "Carlin Depot")),
        start_location_name="Carlin Depot", end_location_name="Carlin Depot",
    ))
    KnowledgeGraphService.upsert(db, RelationshipInput(
        source_entity_id=quest.uuid, relationship_type="occurs_at_location",
        target_entity_id=location.uuid, source_provider_id="tibiawiki",
    ))
    db.commit()
    monkeypatch.setattr("httpx.get", lambda *_args, **_kwargs: pytest.fail("request-time provider call"))

    location_response = client.get("/api/v1/spatial/locations/carlin-depot")
    assert location_response.status_code == 200 and location_response.json()["points"][0]["id"] == str(point.id)
    assert location_response.json()["points"][0]["canonical_id"]
    assert location_response.json()["points"][0]["source_provider"] == point.source_provider_id
    route_response = client.get(f"/api/v1/spatial/routes/{route.id}")
    assert route_response.status_code == 200
    assert route_response.json()["canonical_id"]
    assert route_response.json()["source_provider"] == route.source_provider_id
    assert [step["sequence"] for step in route_response.json()["steps"]] == [1, 2]
    entity_response = client.get(f"/api/v1/spatial/entities/{location.uuid}")
    assert entity_response.status_code == 200 and entity_response.json()["items"]
    quest_response = client.get(f"/api/v1/spatial/entities/{quest.uuid}")
    assert quest_response.status_code == 200
    assert quest_response.json()["items"][0]["map_point"]["id"] == str(point.id)
    assert client.get("/api/v1/spatial/nearby", params={"x": 1, "y": 1, "z": 7, "distance": 201}).status_code == 422
    assert client.get("/api/v1/spatial/nearby", params={"x": 1, "y": 1, "z": 7, "distance": 10}).status_code == 503


def test_admin_review_verify_reject_and_route_provenance(client, db, spatial_registry):
    location = entity(db, "location", "Venore Depot")
    point = persist_map_point(db, MapPointDTO(
        "venore-depot", "Venore Depot Marker", 32954, 32076, 7,
        location_name="Venore Depot", confidence="high", source_reference="fixture:point",
    ))
    region = persist_map_region(db, MapRegionDTO(
        "venore", "Venore Region", polygon(32940, 32060), location_name="Venore Depot",
    ))
    route = persist_route(db, RouteDTO(
        "venore-route", "Venore Route", (RouteStepDTO(1, location_name="Venore Depot"),),
        start_location_name="Venore Depot", source_reference="fixture:route",
    ))
    admin = make_user(db, username="spatial-admin", is_superuser=True)
    db.commit()
    headers = {"Authorization": f"Bearer {create_access_token(admin.username)}"}

    review = client.get("/api/v1/admin/knowledge/spatial/review?kind=point&verification_state=pending", headers=headers)
    assert review.status_code == 200 and review.json()["total"] == 1
    verified = client.post(
        f"/api/v1/admin/knowledge/spatial/points/{point.id}/verify",
        headers=headers, json={"reason": "Trusted provider coordinates"},
    )
    assert verified.status_code == 200 and verified.json()["verification_state"] == "verified"
    rejected = client.post(
        f"/api/v1/admin/knowledge/spatial/regions/{region.id}/reject",
        headers=headers, json={"reason": "Provider boundary is incomplete"},
    )
    assert rejected.status_code == 200 and rejected.json()["verification_state"] == "rejected"
    provenance = client.get(f"/api/v1/admin/knowledge/spatial/routes/{route.id}/provenance", headers=headers)
    assert provenance.status_code == 200 and provenance.json()["source_reference"] == "fixture:route"
    assert db.query(WorkspaceAudit).filter(WorkspaceAudit.action.like("spatial_record_%")).count() == 2
    assert location.uuid is not None
