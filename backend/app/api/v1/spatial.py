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
from app.services.text_utils import normalize_search_text


router = APIRouter(prefix="/spatial", tags=["Spatial Knowledge"])


def _point(row: SpatialMapPoint) -> dict:
    return {
        "id": row.id, "name": row.name, "x": row.tibia_x, "y": row.tibia_y, "z": row.tibia_z,
        "bounds": {"min_x": row.min_x, "min_y": row.min_y, "max_x": row.max_x, "max_y": row.max_y,
                   "min_z": row.min_z, "max_z": row.max_z},
        "confidence": row.confidence, "verification_state": row.verification_state,
        "unresolved_location_name": row.unresolved_location_name,
    }


def _region(row: SpatialMapRegion) -> dict:
    return {
        "id": row.id, "name": row.name,
        "bounds": {"min_x": row.min_x, "min_y": row.min_y, "max_x": row.max_x, "max_y": row.max_y,
                   "min_z": row.min_z, "max_z": row.max_z},
        "confidence": row.confidence, "verification_state": row.verification_state,
        "unresolved_location_name": row.unresolved_location_name,
    }


def _route(row: SpatialRoute) -> dict:
    return {
        "id": row.id, "name": row.name, "slug": row.slug, "step_count": row.step_count,
        "start_location": row.start_location.canonical_name if row.start_location else row.unresolved_start_name,
        "end_location": row.end_location.canonical_name if row.end_location else row.unresolved_end_name,
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
        "x": step.tibia_x, "y": step.tibia_y, "z": step.tibia_z,
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
