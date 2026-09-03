"""Bounded PostgreSQL/PostGIS persistence and read services."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.knowledge.dto.spatial import MAX_ROUTE_STEPS, MapPointDTO, MapRegionDTO, RouteDTO
from app.knowledge.indexing import normalize_name
from app.knowledge.models import (
    KnowledgeDocument, KnowledgeEntity, KnowledgeExternalMapping, KnowledgeRelationship,
    SpatialEntityLocationLink,
    SpatialMapPoint, SpatialMapRegion, SpatialRoute, SpatialRouteStep,
)
from app.knowledge.schemas import KnowledgeEntityCreate
from app.knowledge.services.entities import KnowledgeEntityService
from app.knowledge.services.graph import KnowledgeGraphService, RelationshipInput
from app.knowledge.services.item_relationships import exact_entity_candidates
from app.knowledge.services.npc_location_normalization import exact_place_candidates
from app.services.text_utils import slugify


MAX_NEARBY_DISTANCE = 200
MAX_SPATIAL_PAGE_SIZE = 100
MAX_SPATIAL_OFFSET = 10_000


class PostGISUnavailableError(RuntimeError):
    pass


def postgis_status(db: Session) -> dict[str, str | bool | None]:
    if db.bind is None or db.bind.dialect.name != "postgresql":
        return {"available": False, "installed": False, "version": None}
    available = bool(db.execute(text("SELECT EXISTS (SELECT 1 FROM pg_available_extensions WHERE name='postgis')")).scalar_one())
    installed = bool(db.execute(text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname='postgis')")).scalar_one())
    version = db.execute(text("SELECT extversion FROM pg_extension WHERE extname='postgis'")).scalar_one_or_none()
    return {"available": available, "installed": installed, "version": version}


def require_postgis(db: Session) -> None:
    if not postgis_status(db)["installed"]:
        raise PostGISUnavailableError("PostGIS is not installed in the TibiaHub database")


def _mapped_entity(db: Session, provider: str, entity_type: str, external_id: str, name: str) -> KnowledgeEntity:
    mapping = db.query(KnowledgeExternalMapping).filter_by(provider_id=provider, entity_type_id=entity_type, external_id=external_id).first()
    if mapping is not None:
        return mapping.entity
    candidates = exact_entity_candidates(db, entity_type, name)
    available = [candidate for candidate in candidates if db.query(KnowledgeExternalMapping).filter_by(
        provider_id=provider, entity_type_id=entity_type, entity_uuid=candidate.uuid,
    ).first() is None]
    if len(available) > 1:
        raise ValueError("Ambiguous canonical spatial identity")
    entity = available[0] if len(available) == 1 else KnowledgeEntityService.create(db, KnowledgeEntityCreate(
        entity_type=entity_type, canonical_name=name,
        language_neutral_id=f"{entity_type}:{provider}:{external_id}", source_priority=20,
        allow_name_collision=bool(candidates), slug_suffix=external_id if candidates else None,
    ))
    db.add(KnowledgeExternalMapping(
        provider_id=provider, entity_type_id=entity_type, external_id=external_id,
        entity_uuid=entity.uuid, provider_metadata={},
    ))
    db.flush()
    return entity


def _place(
    db: Session, name: str | None, entity_type: str | None = None,
) -> tuple[KnowledgeEntity | None, str]:
    if not name:
        return None, "unresolved"
    matches = (
        exact_entity_candidates(db, entity_type, name)
        if entity_type is not None
        else exact_place_candidates(db, name)
    )
    return (matches[0], "resolved") if len(matches) == 1 else (None, "ambiguous" if len(matches) > 1 else "unresolved")


def _graph_named_place(db: Session, *, source: KnowledgeEntity, relationship_type: str, name: str,
                       provider: str, document: str | None, scope: str):
    target, state = _place(db, name)
    return KnowledgeGraphService.upsert(db, RelationshipInput(
        source_entity_id=source.uuid, source_scope=scope, relationship_type=relationship_type,
        target_entity_id=target.uuid if target else None,
        target_entity_type=target.entity_type if target else "location",
        unresolved_name=name, resolution_state=state, confidence="high",
        source_provider_id=provider, source_document_ref=document,
        source_context={"context": f"spatial.{scope}", "resolution_policy": "exact_name_or_alias_only"},
    )).relationship


def _retire(row, transition_at: datetime) -> None:
    row.is_current = False
    row.valid_until = transition_at


def _version_transition(current) -> dict[str, datetime]:
    if current is None:
        return {}
    transition_at = datetime.now(UTC)
    _retire(current, transition_at)
    return {"valid_from": transition_at}


def _source_metadata(dto) -> dict:
    metadata = dict(dto.provider_metadata)
    canonical = json.dumps(asdict(dto), sort_keys=True, separators=(",", ":"), default=str)
    metadata["spatial_content_sha256"] = sha256(canonical.encode("utf-8")).hexdigest()
    return metadata


def _source_document(
    db: Session,
    *,
    provider: str,
    reference: str | None,
    entity_id: UUID,
) -> KnowledgeDocument | None:
    if not reference:
        return None
    document = (
        db.query(KnowledgeDocument)
        .filter_by(provider_id=provider, provider_document_id=reference)
        .order_by(KnowledgeDocument.retrieved_at.desc())
        .first()
    )
    return document if document is not None and document.entity_uuid in (None, entity_id) else None


def _replace_representation_link(db: Session, *, row, source_entity_id: UUID,
                                 location_entity_id: UUID, relationship_id: UUID,
                                 external_id: str, provider: str,
                                 source_document_id: UUID | None,
                                 source_reference: str | None,
                                 source_metadata: dict, confidence: str,
                                 map_point_id: UUID | None = None,
                                 map_region_id: UUID | None = None) -> None:
    current = db.query(SpatialEntityLocationLink).filter_by(
        source_provider_id=provider, external_id=external_id, is_current=True,
    ).first()
    transition = _version_transition(current)
    db.add(SpatialEntityLocationLink(
        source_entity_id=source_entity_id, location_entity_id=location_entity_id,
        map_point_id=map_point_id, map_region_id=map_region_id,
        graph_relationship_id=relationship_id, external_id=external_id,
        source_provider_id=provider, source_document_id=source_document_id,
        source_reference=source_reference,
        source_metadata=source_metadata, confidence=confidence,
        verification_state=row.verification_state, version=row.version,
        **transition,
    ))


def persist_map_point(
    db: Session,
    dto: MapPointDTO,
    *,
    provider: str = "tibiamaps",
    source_document_ref: str | None = None,
) -> SpatialMapPoint:
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        require_postgis(db)
    entity = _mapped_entity(db, provider, "map_point", dto.external_id, dto.name)
    document = _source_document(
        db, provider=provider, reference=source_document_ref, entity_id=entity.uuid,
    )
    current = db.query(SpatialMapPoint).filter_by(knowledge_entity_id=entity.uuid, is_current=True).first()
    location, state = _place(db, dto.location_name, dto.location_entity_type)
    metadata = _source_metadata(dto)
    if current and current.source_metadata.get("spatial_content_sha256") == metadata["spatial_content_sha256"]:
        if document is not None and current.source_document_id != document.uuid:
            current.source_document_id = document.uuid
        return current
    version = (current.version + 1) if current else 1
    transition = _version_transition(current)
    row = SpatialMapPoint(
        knowledge_entity_id=entity.uuid, location_entity_id=location.uuid if location else None,
        external_id=dto.external_id, name=dto.name, tibia_x=dto.x, tibia_y=dto.y, tibia_z=dto.z,
        min_x=dto.x, min_y=dto.y, max_x=dto.x, max_y=dto.y, min_z=dto.z, max_z=dto.z,
        unresolved_location_name=None if location else dto.location_name,
        normalized_unresolved_location_name=normalize_name(dto.location_name or "") or None,
        source_provider_id=provider, source_document_id=document.uuid if document else None,
        source_reference=dto.source_reference,
        source_metadata=metadata, confidence=dto.confidence,
        verification_state=(state if dto.location_name and location is None else
                            ("pending" if dto.resolved else "unresolved")),
        version=version,
        **transition,
    )
    if dto.resolved:
        row.geom = (
            func.ST_SetSRID(func.ST_MakePoint(dto.x, dto.y, dto.z), 0)
            if db.bind is not None and db.bind.dialect.name == "postgresql"
            else f"POINT Z ({dto.x} {dto.y} {dto.z})"
        )
    db.add(row); db.flush()
    if location:
        relationship = KnowledgeGraphService.upsert(db, RelationshipInput(
            source_entity_id=location.uuid, source_scope="map_representation", relationship_type="represented_by",
            target_entity_id=entity.uuid, resolution_state="resolved", confidence=dto.confidence,
            source_provider_id=provider,
            source_document_ref=source_document_ref or dto.source_reference,
            source_context={"context": "spatial.map_point"},
        )).relationship
        _replace_representation_link(
            db, row=row, source_entity_id=location.uuid, location_entity_id=location.uuid,
            relationship_id=relationship.id, external_id=f"point:{dto.external_id}",
            provider=provider, source_document_id=document.uuid if document else None,
            source_reference=dto.source_reference,
            source_metadata=metadata, confidence=dto.confidence,
            map_point_id=row.id,
        )
    return row


def persist_map_region(
    db: Session,
    dto: MapRegionDTO,
    *,
    provider: str = "tibiamaps",
    source_document_ref: str | None = None,
) -> SpatialMapRegion:
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        require_postgis(db)
    entity = _mapped_entity(db, provider, "map_region", dto.external_id, dto.name)
    document = _source_document(
        db, provider=provider, reference=source_document_ref, entity_id=entity.uuid,
    )
    current = db.query(SpatialMapRegion).filter_by(knowledge_entity_id=entity.uuid, is_current=True).first()
    location, state = _place(db, dto.location_name, dto.location_entity_type)
    metadata = _source_metadata(dto)
    if current and current.source_metadata.get("spatial_content_sha256") == metadata["spatial_content_sha256"]:
        if document is not None and current.source_document_id != document.uuid:
            current.source_document_id = document.uuid
        return current
    transition = _version_transition(current)
    geometry_bounds = dto.geometry_bounds
    row = SpatialMapRegion(
        knowledge_entity_id=entity.uuid, location_entity_id=location.uuid if location else None,
        external_id=dto.external_id, name=dto.name,
        min_x=geometry_bounds[0] if geometry_bounds else None,
        min_y=geometry_bounds[1] if geometry_bounds else None,
        min_z=dto.minimum_z if dto.minimum_z is not None else (geometry_bounds[2] if geometry_bounds else None),
        max_x=geometry_bounds[3] if geometry_bounds else None,
        max_y=geometry_bounds[4] if geometry_bounds else None,
        max_z=dto.maximum_z if dto.maximum_z is not None else (geometry_bounds[5] if geometry_bounds else None),
        unresolved_location_name=None if location else dto.location_name,
        normalized_unresolved_location_name=normalize_name(dto.location_name or "") or None,
        source_provider_id=provider, source_document_id=document.uuid if document else None,
        source_reference=dto.source_reference,
        source_metadata=metadata, confidence=dto.confidence,
        verification_state=(state if dto.location_name and location is None else
                            ("pending" if dto.geometry else "unresolved")),
        version=(current.version + 1) if current else 1,
        **transition,
    )
    if dto.geometry:
        row.geom = (
            func.ST_Multi(func.ST_SetSRID(func.ST_GeomFromGeoJSON(json.dumps(dto.geometry)), 0))
            if db.bind is not None and db.bind.dialect.name == "postgresql"
            else json.dumps(dto.geometry, separators=(",", ":"))
        )
    db.add(row); db.flush()
    if dto.geometry and db.bind is not None and db.bind.dialect.name == "postgresql":
        db.execute(text("""
            UPDATE spatial_map_regions
            SET min_x=floor(ST_XMin(Box3D(geom)))::integer,
                min_y=floor(ST_YMin(Box3D(geom)))::integer,
                max_x=ceil(ST_XMax(Box3D(geom)))::integer,
                max_y=ceil(ST_YMax(Box3D(geom)))::integer
            WHERE id=:id
        """), {"id": row.id})
        db.refresh(row)
    if location:
        relationship = KnowledgeGraphService.upsert(db, RelationshipInput(
            source_entity_id=location.uuid, source_scope="map_representation", relationship_type="represented_by",
            target_entity_id=entity.uuid, resolution_state="resolved", confidence=dto.confidence,
            source_provider_id=provider,
            source_document_ref=source_document_ref or dto.source_reference,
            source_context={"context": "spatial.map_region"},
        )).relationship
        _replace_representation_link(
            db, row=row, source_entity_id=location.uuid, location_entity_id=location.uuid,
            relationship_id=relationship.id, external_id=f"region:{dto.external_id}",
            provider=provider, source_document_id=document.uuid if document else None,
            source_reference=dto.source_reference,
            source_metadata=metadata, confidence=dto.confidence,
            map_region_id=row.id,
        )
    return row


def persist_route(
    db: Session,
    dto: RouteDTO,
    *,
    provider: str = "tibiamaps",
    source_document_ref: str | None = None,
) -> SpatialRoute:
    if len(dto.steps) > MAX_ROUTE_STEPS:
        raise ValueError("Route step limit exceeded")
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        require_postgis(db)
    entity = _mapped_entity(db, provider, "route", dto.external_id, dto.name)
    document = _source_document(
        db, provider=provider, reference=source_document_ref, entity_id=entity.uuid,
    )
    current = db.query(SpatialRoute).filter_by(knowledge_entity_id=entity.uuid, is_current=True).first()
    metadata = _source_metadata(dto)
    if current and current.source_metadata.get("spatial_content_sha256") == metadata["spatial_content_sha256"]:
        if document is not None:
            for route in db.query(SpatialRoute).filter_by(
                knowledge_entity_id=entity.uuid,
                source_provider_id=provider,
                external_id=dto.external_id,
            ):
                if route.source_document_id is None:
                    route.source_document_id = document.uuid
            for relationship in db.query(KnowledgeRelationship).filter_by(
                source_entity_id=entity.uuid,
                source_provider_id=provider,
                is_current=True,
            ):
                if relationship.source_document_id is None:
                    context = dict(relationship.source_context or {})
                    prior_reference = context.get("source_document_ref")
                    if prior_reference and prior_reference != document.provider_document_id:
                        context.setdefault("source_reference", prior_reference)
                    context["source_document_ref"] = document.provider_document_id
                    relationship.source_context = context
                    relationship.source_document_id = document.uuid
        return current
    transition = _version_transition(current)
    start, _ = _place(db, dto.start_location_name)
    end, _ = _place(db, dto.end_location_name)
    row = SpatialRoute(
        knowledge_entity_id=entity.uuid, external_id=dto.external_id, name=dto.name, slug=slugify(dto.name),
        start_location_entity_id=start.uuid if start else None, end_location_entity_id=end.uuid if end else None,
        unresolved_start_name=None if start else dto.start_location_name,
        unresolved_end_name=None if end else dto.end_location_name,
        step_count=len(dto.steps), source_provider_id=provider,
        source_document_id=document.uuid if document else None,
        source_reference=dto.source_reference,
        source_metadata=metadata, confidence=dto.confidence,
        verification_state="pending" if dto.steps else "unresolved",
        version=(current.version + 1) if current else 1,
        **transition,
    )
    db.add(row); db.flush()
    coordinate_steps = []
    for step in dto.steps:
        location, _state = _place(db, step.location_name)
        value = SpatialRouteStep(
            route_id=row.id, sequence=step.sequence, step_kind=step.step_kind,
            instruction=step.instruction, location_entity_id=location.uuid if location else None,
            unresolved_location_name=None if location else step.location_name,
            tibia_x=step.x, tibia_y=step.y, tibia_z=step.z, source_metadata=dict(step.provider_metadata),
        )
        if step.x is not None:
            value.geom = (
                func.ST_SetSRID(func.ST_MakePoint(step.x, step.y, step.z), 0)
                if db.bind is not None and db.bind.dialect.name == "postgresql"
                else f"POINT Z ({step.x} {step.y} {step.z})"
            )
        db.add(value); db.flush()
        if step.x is not None:
            coordinate_steps.append(step)
        if step.location_name:
            _graph_named_place(db, source=entity, relationship_type="passes_through", name=step.location_name,
                               provider=provider, document=source_document_ref or dto.source_reference,
                               scope=f"step:{step.sequence}")
    for relation, name in (("starts_at", dto.start_location_name), ("ends_at", dto.end_location_name)):
        if name:
            _graph_named_place(db, source=entity, relationship_type=relation, name=name,
                               provider=provider, document=source_document_ref or dto.source_reference,
                               scope=relation)
    if len(coordinate_steps) == len(dto.steps) and len(coordinate_steps) >= 2 and db.bind is not None and db.bind.dialect.name == "postgresql":
        points = ",".join(f"{step.x} {step.y} {step.z}" for step in coordinate_steps)
        db.execute(text("""
            UPDATE spatial_routes SET geom=ST_GeomFromText(:wkt,0),
                min_x=:min_x,min_y=:min_y,max_x=:max_x,max_y=:max_y,min_z=:min_z,max_z=:max_z
            WHERE id=:id
        """), {
            "wkt": f"LINESTRING Z ({points})", "id": row.id,
            "min_x": min(step.x for step in coordinate_steps), "min_y": min(step.y for step in coordinate_steps),
            "max_x": max(step.x for step in coordinate_steps), "max_y": max(step.y for step in coordinate_steps),
            "min_z": min(step.z for step in coordinate_steps), "max_z": max(step.z for step in coordinate_steps),
        })
        db.refresh(row)
    return row


def link_entity_to_location(db: Session, *, source_entity: KnowledgeEntity, location_name: str,
                            external_id: str, provider: str = "tibiamaps",
                            map_point_id: UUID | None = None, map_region_id: UUID | None = None) -> SpatialEntityLocationLink:
    location, state = _place(db, location_name)
    relationship = _graph_named_place(db, source=source_entity, relationship_type="located_at", name=location_name,
                                      provider=provider, document=None, scope="spatial_location")
    row = db.query(SpatialEntityLocationLink).filter_by(source_provider_id=provider, external_id=external_id, is_current=True).first()
    if row is None:
        row = SpatialEntityLocationLink(source_provider_id=provider, external_id=external_id, source_entity_id=source_entity.uuid)
        db.add(row)
    row.location_entity_id = location.uuid if location else None
    row.unresolved_location_name = None if location else location_name
    row.normalized_unresolved_location_name = normalize_name(location_name)
    row.map_point_id = map_point_id; row.map_region_id = map_region_id
    row.graph_relationship_id = relationship.id
    row.confidence = "high"; row.verification_state = "pending" if state == "resolved" else state
    db.flush()
    return row


def nearby_entities(db: Session, *, x: int, y: int, z: int, distance: int, skip: int, limit: int) -> list[dict]:
    if (not 1 <= distance <= MAX_NEARBY_DISTANCE or not 1 <= limit <= MAX_SPATIAL_PAGE_SIZE
            or not 0 <= skip <= MAX_SPATIAL_OFFSET):
        raise ValueError("Spatial query bounds exceeded")
    require_postgis(db)
    rows = db.execute(text("""
        SELECT link.source_entity_id, entity.canonical_name, entity.entity_type, entity.slug,
               point.tibia_x, point.tibia_y, point.tibia_z,
               ST_3DDistance(point.geom, ST_SetSRID(ST_MakePoint(:x,:y,:z),0)) AS distance
        FROM spatial_entity_location_links AS link
        JOIN spatial_map_points AS point ON point.id=link.map_point_id AND point.is_current
        JOIN knowledge_entities AS entity ON entity.uuid=link.source_entity_id
        WHERE link.is_current AND link.verification_state <> 'rejected'
          AND point.verification_state <> 'rejected' AND point.tibia_z=:z
          AND ST_3DDWithin(point.geom, ST_SetSRID(ST_MakePoint(:x,:y,:z),0), :distance)
        ORDER BY distance, entity.canonical_name OFFSET :skip LIMIT :limit
    """), {"x": x, "y": y, "z": z, "distance": distance, "skip": skip, "limit": limit}).mappings()
    return [dict(row) for row in rows]


def entities_inside_region(db: Session, region_id: UUID, *, skip: int, limit: int) -> list[dict]:
    if not 1 <= limit <= MAX_SPATIAL_PAGE_SIZE or not 0 <= skip <= MAX_SPATIAL_OFFSET:
        raise ValueError("Spatial query bounds exceeded")
    require_postgis(db)
    rows = db.execute(text("""
        SELECT link.source_entity_id, entity.canonical_name, entity.entity_type, entity.slug
        FROM spatial_map_regions AS region
        JOIN spatial_entity_location_links AS link ON link.is_current
        JOIN spatial_map_points AS point ON point.id=link.map_point_id AND point.is_current
        JOIN knowledge_entities AS entity ON entity.uuid=link.source_entity_id
        WHERE region.id=:region_id AND region.is_current AND region.verification_state <> 'rejected'
          AND link.verification_state <> 'rejected' AND point.verification_state <> 'rejected'
          AND ST_Covers(region.geom, point.geom)
        ORDER BY entity.canonical_name OFFSET :skip LIMIT :limit
    """), {"region_id": region_id, "skip": skip, "limit": limit}).mappings()
    return [dict(row) for row in rows]
