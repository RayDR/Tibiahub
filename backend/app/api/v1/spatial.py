"""Local-only, bounded spatial metadata APIs."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.knowledge.models import (
    KnowledgeEntity, KnowledgeRelationship, SpatialEntityLocationLink, SpatialMapPoint, SpatialMapRegion, SpatialRoute,
)
from app.knowledge.services.spatial import PostGISUnavailableError, entities_inside_region, nearby_entities
from app.models.external_data import TibiaWikiLocation
from app.models.world_map import WorldMapFloor, WorldMapMarker
from app.services.text_utils import normalize_search_text


router = APIRouter(prefix="/spatial", tags=["Spatial Knowledge"])


def _point(row: SpatialMapPoint) -> dict:
    supplied = [key for key, value in {
        "name": row.name, "x": row.tibia_x, "y": row.tibia_y, "z": row.tibia_z,
        "location": row.location_entity_id or row.unresolved_location_name,
    }.items() if value is not None]
    return {
        "id": row.id, "name": row.name, "x": row.tibia_x, "y": row.tibia_y, "z": row.tibia_z,
        "canonical_id": row.knowledge_entity_id, "knowledge_entity_id": row.knowledge_entity_id,
        "external_id": row.external_id, "source_provider": row.source_provider_id,
        "source_url": row.source_reference, "supplied_fields": supplied,
        "missing_fields": sorted({"name", "x", "y", "z", "location"} - set(supplied)),
        "data_version": row.version, "last_synced_at": row.updated_at or row.created_at,
        "provider_metadata": dict(row.source_metadata or {}),
        "bounds": {"min_x": row.min_x, "min_y": row.min_y, "max_x": row.max_x, "max_y": row.max_y,
                   "min_z": row.min_z, "max_z": row.max_z},
        "confidence": row.confidence, "verification_state": row.verification_state,
        "unresolved_location_name": row.unresolved_location_name,
        "location": {
            "canonical_id": row.location_entity_id,
            "name": row.location_entity.canonical_name,
        } if row.location_entity else (
            {"canonical_id": None, "name": row.unresolved_location_name}
            if row.unresolved_location_name else None
        ),
    }


def _world_marker_point(row: WorldMapMarker) -> dict:
    """Present an authoritative resolved TibiaMaps marker as a spatial point."""
    floor = row.world_floor
    return {
        "id": f"world-map-marker:{row.id}",
        "name": row.description,
        "x": row.x,
        "y": row.y,
        "z": row.floor,
        "canonical_id": row.resolved_entity_id,
        "knowledge_entity_id": row.resolved_entity_id,
        "external_id": str(row.source_index),
        "source_provider": floor.provider,
        "source_url": floor.upstream_url,
        "supplied_fields": ["name", "x", "y", "z"],
        "missing_fields": ["location"],
        "data_version": 1,
        "last_synced_at": floor.imported_at,
        "provider_metadata": {
            "representation_type": "world_map_marker",
            "upstream_commit": floor.upstream_commit,
            "icon": row.icon,
            "resolution_method": row.resolution_method,
            "raw_data": dict(row.raw_data or {}),
        },
        "bounds": {
            "min_x": row.x,
            "min_y": row.y,
            "max_x": row.x,
            "max_y": row.y,
            "min_z": row.floor,
            "max_z": row.floor,
        },
        "confidence": "high",
        "verification_state": "pending",
        "unresolved_location_name": None,
        "location": None,
    }


def _region(row: SpatialMapRegion) -> dict:
    supplied = [key for key, value in {
        "name": row.name, "min_x": row.min_x, "min_y": row.min_y,
        "max_x": row.max_x, "max_y": row.max_y, "min_z": row.min_z,
        "max_z": row.max_z, "location": row.location_entity_id or row.unresolved_location_name,
    }.items() if value is not None]
    return {
        "id": row.id, "name": row.name,
        "canonical_id": row.knowledge_entity_id, "knowledge_entity_id": row.knowledge_entity_id,
        "external_id": row.external_id, "source_provider": row.source_provider_id,
        "source_url": row.source_reference, "supplied_fields": supplied,
        "missing_fields": sorted({"name", "min_x", "min_y", "max_x", "max_y", "min_z", "max_z", "location"} - set(supplied)),
        "data_version": row.version, "last_synced_at": row.updated_at or row.created_at,
        "provider_metadata": dict(row.source_metadata or {}),
        "bounds": {"min_x": row.min_x, "min_y": row.min_y, "max_x": row.max_x, "max_y": row.max_y,
                   "min_z": row.min_z, "max_z": row.max_z},
        "confidence": row.confidence, "verification_state": row.verification_state,
        "unresolved_location_name": row.unresolved_location_name,
        "location": {
            "canonical_id": row.location_entity_id,
            "name": row.location_entity.canonical_name,
        } if row.location_entity else (
            {"canonical_id": None, "name": row.unresolved_location_name}
            if row.unresolved_location_name else None
        ),
    }


def _route(row: SpatialRoute) -> dict:
    supplied = [key for key, value in {
        "name": row.name, "start_location": row.start_location_entity_id or row.unresolved_start_name,
        "end_location": row.end_location_entity_id or row.unresolved_end_name,
        "steps": row.step_count if row.step_count else None,
    }.items() if value is not None]
    return {
        "id": row.id, "name": row.name, "slug": row.slug, "step_count": row.step_count,
        "canonical_id": row.knowledge_entity_id, "knowledge_entity_id": row.knowledge_entity_id,
        "external_id": row.external_id, "source_provider": row.source_provider_id,
        "source_url": row.source_reference, "supplied_fields": supplied,
        "missing_fields": sorted({"name", "start_location", "end_location", "steps"} - set(supplied)),
        "data_version": row.version, "last_synced_at": row.updated_at or row.created_at,
        "provider_metadata": dict(row.source_metadata or {}),
        "start_location": row.start_location.canonical_name if row.start_location else row.unresolved_start_name,
        "end_location": row.end_location.canonical_name if row.end_location else row.unresolved_end_name,
        "start": {
            "canonical_id": row.start_location_entity_id,
            "name": row.start_location.canonical_name if row.start_location else row.unresolved_start_name,
        },
        "end": {
            "canonical_id": row.end_location_entity_id,
            "name": row.end_location.canonical_name if row.end_location else row.unresolved_end_name,
        },
        "bounds": {"min_x": row.min_x, "min_y": row.min_y, "max_x": row.max_x, "max_y": row.max_y,
                   "min_z": row.min_z, "max_z": row.max_z},
        "confidence": row.confidence, "verification_state": row.verification_state,
        "map_images": list((row.source_metadata or {}).get("map_images") or [])[:100],
    }


def _location_or_404(db: Session, identifier: str) -> TibiaWikiLocation:
    query = db.query(TibiaWikiLocation)
    row = query.filter(or_(
        TibiaWikiLocation.external_id == identifier,
        TibiaWikiLocation.slug == identifier,
        TibiaWikiLocation.normalized_name == normalize_search_text(identifier),
    )).first()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "spatial_location_not_found"})
    return row


@router.get("/locations/{identifier}")
def location_map_data(identifier: str, db: Session = Depends(get_db)):
    location = _location_or_404(db, identifier)
    points = db.query(SpatialMapPoint).filter_by(location_entity_id=location.knowledge_entity_id, is_current=True).filter(SpatialMapPoint.verification_state != "rejected").order_by(SpatialMapPoint.name).limit(100).all()
    regions = db.query(SpatialMapRegion).filter_by(location_entity_id=location.knowledge_entity_id, is_current=True).filter(SpatialMapRegion.verification_state != "rejected").order_by(SpatialMapRegion.name).limit(100).all()
    routes = db.query(SpatialRoute).filter(
        SpatialRoute.is_current.is_(True),
        SpatialRoute.verification_state != "rejected",
        or_(SpatialRoute.start_location_entity_id == location.knowledge_entity_id,
            SpatialRoute.end_location_entity_id == location.knowledge_entity_id),
    ).order_by(SpatialRoute.name).limit(100).all()
    return {"location_entity_id": location.knowledge_entity_id, "points": [_point(row) for row in points],
            "regions": [_region(row) for row in regions], "routes": [_route(row) for row in routes]}


@router.get("/entities/{entity_id}")
def entity_map_references(entity_id: UUID, skip: int = Query(0, ge=0, le=10000), limit: int = Query(25, ge=1, le=100),
                          db: Session = Depends(get_db)):
    entity = db.get(KnowledgeEntity, entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail={"code": "spatial_entity_not_found"})
    rows = db.query(SpatialEntityLocationLink).filter_by(source_entity_id=entity_id, is_current=True).filter(
        SpatialEntityLocationLink.verification_state != "rejected",
    ).order_by(
        SpatialEntityLocationLink.created_at.desc(),
    ).limit(1000).all()
    items = [{
        "id": row.id,
        "location_entity_id": row.location_entity_id,
        "location_name": row.location_entity.canonical_name if row.location_entity else row.unresolved_location_name,
        "map_point": _point(row.map_point) if row.map_point else None,
        "map_region": _region(row.map_region) if row.map_region else None,
        "confidence": row.confidence, "verification_state": row.verification_state,
    } for row in rows]

    # Existing Quest/NPC/Creature graph links become useful immediately without
    # duplicating graph facts or making a provider call during the request.
    relationships = db.query(KnowledgeRelationship).filter(
        KnowledgeRelationship.source_entity_id == entity_id,
        KnowledgeRelationship.relationship_type_code.in_({
            "located_at", "occurs_at_location", "mission_occurs_at_location", "appears_in",
        }),
        KnowledgeRelationship.target_entity_id.isnot(None),
        KnowledgeRelationship.resolution_state == "resolved",
        KnowledgeRelationship.is_current.is_(True),
    ).order_by(KnowledgeRelationship.created_at.desc()).limit(1000).all()
    location_ids = {row.target_entity_id for row in relationships}
    represented: dict[UUID, tuple[list[SpatialMapPoint], list[SpatialMapRegion]]] = {}
    if location_ids:
        points = db.query(SpatialMapPoint).filter(
            SpatialMapPoint.location_entity_id.in_(location_ids), SpatialMapPoint.is_current.is_(True),
            SpatialMapPoint.verification_state != "rejected",
        ).limit(1000).all()
        regions = db.query(SpatialMapRegion).filter(
            SpatialMapRegion.location_entity_id.in_(location_ids), SpatialMapRegion.is_current.is_(True),
            SpatialMapRegion.verification_state != "rejected",
        ).limit(1000).all()
        for location_id in location_ids:
            represented[location_id] = (
                [point for point in points if point.location_entity_id == location_id],
                [region for region in regions if region.location_entity_id == location_id],
            )
    seen = {(str(item["map_point"]["id"]) if item["map_point"] else None,
             str(item["map_region"]["id"]) if item["map_region"] else None) for item in items}

    # Universal search already consumes these exact-resolved coordinates. Detail
    # pages should receive the same provider-backed facts instead of appearing empty.
    marker_entity_ids = {entity_id, *location_ids}
    markers = db.query(WorldMapMarker).join(
        WorldMapFloor, WorldMapMarker.floor_id == WorldMapFloor.id,
    ).filter(
        WorldMapFloor.is_current.is_(True),
        WorldMapMarker.resolution_state == "resolved",
        WorldMapMarker.resolved_entity_id.in_(marker_entity_ids),
    ).order_by(WorldMapMarker.floor, WorldMapMarker.description, WorldMapMarker.id).limit(1000).all()
    relationship_by_target = {row.target_entity_id: row for row in relationships}
    for marker in markers:
        key = (f"world-map-marker:{marker.id}", None)
        if key in seen:
            continue
        seen.add(key)
        relationship = relationship_by_target.get(marker.resolved_entity_id)
        location = relationship.target_entity if relationship else None
        items.append({
            "id": f"world-map-marker-link:{marker.id}",
            "location_entity_id": location.uuid if location else None,
            "location_name": location.canonical_name if location else None,
            "map_point": _world_marker_point(marker),
            "map_region": None,
            "confidence": relationship.confidence if relationship else "high",
            "verification_state": "verified" if relationship and relationship.manual_override else "pending",
        })
    for relationship in relationships:
        point_rows, region_rows = represented.get(relationship.target_entity_id, ([], []))
        location = relationship.target_entity
        for point, region in [*((value, None) for value in point_rows), *((None, value) for value in region_rows)]:
            key = (str(point.id) if point else None, str(region.id) if region else None)
            if key in seen:
                continue
            seen.add(key)
            items.append({
                "id": relationship.id, "location_entity_id": relationship.target_entity_id,
                "location_name": location.canonical_name, "map_point": _point(point) if point else None,
                "map_region": _region(region) if region else None,
                "confidence": relationship.confidence, "verification_state": "verified" if relationship.manual_override else "pending",
            })
    return {"entity_id": entity_id, "items": items[skip:skip + limit], "total": len(items),
            "skip": skip, "limit": limit}


@router.get("/routes/{identifier}")
def route_detail(identifier: str, db: Session = Depends(get_db)):
    query = db.query(SpatialRoute).filter_by(is_current=True).filter(SpatialRoute.verification_state != "rejected")
    try:
        route_id = UUID(identifier)
    except ValueError:
        route_id = None
    route = query.filter(or_(SpatialRoute.id == route_id, SpatialRoute.slug == identifier,
                             SpatialRoute.external_id == identifier)).first()
    if route is None:
        raise HTTPException(status_code=404, detail={"code": "spatial_route_not_found"})
    value = _route(route)
    value["steps"] = [{
        "id": step.id, "sequence": step.sequence, "kind": step.step_kind,
        "instruction": step.instruction,
        "location_name": step.location_entity.canonical_name if step.location_entity else step.unresolved_location_name,
        "location": {
            "canonical_id": step.location_entity_id,
            "name": step.location_entity.canonical_name if step.location_entity else step.unresolved_location_name,
        },
        "x": step.tibia_x, "y": step.tibia_y, "z": step.tibia_z,
        "provider_metadata": dict(step.source_metadata or {}),
    } for step in route.steps[:250]]
    return value


@router.get("/nearby")
def nearby(x: int = Query(ge=0, le=65535), y: int = Query(ge=0, le=65535), z: int = Query(ge=0, le=15),
           distance: int = Query(ge=1, le=200), skip: int = Query(0, ge=0, le=10000), limit: int = Query(25, ge=1, le=100),
           db: Session = Depends(get_db)):
    try:
        return {"items": nearby_entities(db, x=x, y=y, z=z, distance=distance, skip=skip, limit=limit),
                "skip": skip, "limit": limit, "distance": distance}
    except PostGISUnavailableError as exc:
        raise HTTPException(status_code=503, detail={"code": "postgis_unavailable"}) from exc


@router.get("/regions/{region_id}/entities")
def region_entities(region_id: UUID, skip: int = Query(0, ge=0, le=10000), limit: int = Query(25, ge=1, le=100),
                    db: Session = Depends(get_db)):
    try:
        return {"items": entities_inside_region(db, region_id, skip=skip, limit=limit), "skip": skip, "limit": limit}
    except PostGISUnavailableError as exc:
        raise HTTPException(status_code=503, detail={"code": "postgis_unavailable"}) from exc
