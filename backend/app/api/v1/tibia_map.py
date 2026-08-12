"""Public Tibia map API backed exclusively by locally imported world floors."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.db.database import get_db
from app.knowledge.models import (
    KnowledgeRelationship, SpatialEntityLocationLink, SpatialMapPoint,
    SpatialMapRegion, SpatialRoute,
)
from app.models.creature import Creature
from app.models.external_data import TibiaWikiLocation, TibiaWikiQuest
from app.models.hunt_zone import HuntZone
from app.models.spawn_location import SpawnLocation
from app.models.world_map import WorldMapFloor, WorldMapMarker
from app.services.text_utils import normalize_search_text

router = APIRouter(prefix="/map", tags=["Tibia Map"])

KNOWN_TOWNS = (
    "Ab'Dendriel", "Ankrahmun", "Carlin", "Darashia", "Edron", "Farmine",
    "Gray Beach", "Issavi", "Kazordoon", "Liberty Bay", "Port Hope",
    "Rathleton", "Roshamuul", "Svargrond", "Thais", "Venore", "Yalahar",
)


def _safe_floor_file(floor: WorldMapFloor, attribute: str) -> Path:
    root = Path(settings.WORLD_MAP_STORAGE_ROOT).resolve()
    path = Path(getattr(floor, attribute) or "").resolve()
    if (path != root and root not in path.parents) or not path.is_file():
        raise HTTPException(status_code=404, detail="Locally cached world-map asset unavailable")
    return path


def _floor_payload(floor: WorldMapFloor) -> dict:
    return {
        "floor": floor.floor,
        "image_url": f"/api/v1/map/floors/{floor.floor}/image",
        "pathfinding_url": f"/api/v1/map/floors/{floor.floor}/pathfinding" if floor.pathfinding_path else None,
        "width": floor.width, "height": floor.height,
        "bounds": {"min_x": floor.min_x, "min_y": floor.min_y, "max_x": floor.max_x, "max_y": floor.max_y},
        "provider": floor.provider, "upstream_url": floor.upstream_url,
        "upstream_commit": floor.upstream_commit, "map_sha256": floor.map_sha256,
        "pathfinding_sha256": floor.pathfinding_sha256, "license": floor.license_name,
        "attribution": floor.attribution,
    }


def _bounds(value) -> dict | None:
    if not isinstance(value, dict):
        return None
    result = {key: value.get(key, value.get("".join([key.split("_")[0], key.split("_")[1].title()]))) for key in ("min_x", "min_y", "max_x", "max_y")}
    return result if all(isinstance(item, (int, float)) for item in result.values()) else None


def _best_marker(db: Session, name: str) -> WorldMapMarker | None:
    normalized = normalize_search_text(name)
    if not normalized:
        return None
    candidates = db.query(WorldMapMarker).join(WorldMapFloor).filter(
        WorldMapFloor.is_current.is_(True),
        WorldMapMarker.normalized_description.ilike(f"%{normalized}%"),
    ).limit(40).all()

    def rank(marker: WorldMapMarker) -> tuple:
        value = marker.normalized_description
        prefix = value.startswith(("to ", "teleport to "))
        if value == normalized:
            score = 0
        elif not prefix and value.startswith(normalized + " "):
            score = 1
        elif not prefix:
            score = 2
        else:
            score = 3
        return score, len(value), marker.source_index

    return min(candidates, key=rank, default=None)


def _zone_result(db: Session, zone: HuntZone, creature_count: int | None = None) -> dict:
    marker = _best_marker(db, zone.name)
    bounds = _bounds(zone.map_bounds)
    # WorldMapMarker is preferred because it uses the same coordinate contract
    # as the floor PNG. Legacy hunt-zone geometry remains a verified fallback.
    x = marker.x if marker else (zone.location_x if zone.location_x is not None else zone.map_x)
    y = marker.y if marker else (zone.location_y if zone.location_y is not None else zone.map_y)
    z = marker.floor if marker else (zone.location_z if zone.location_z is not None else zone.map_z)
    return {
        "id": f"hunt_zone:{zone.id}", "entity_type": "hunt_zone", "entity_id": zone.id,
        "name": zone.name, "slug": zone.slug, "to": f"/hunt-zones/{zone.slug or zone.id}",
        "subtitle": zone.region or zone.city, "x": x, "y": y, "z": z, "bounds": bounds,
        "geometry_status": "mapped" if bounds or (x is not None and y is not None) else "knowledge_only",
        "geometry_source": "tibiamaps_marker" if marker else ("verified_local" if bounds or x is not None else None),
        "marker_label": marker.description if marker else None, "creature_count": creature_count,
    }


def _spatial_by_entity(db: Session, entity_ids: set) -> dict:
    if not entity_ids:
        return {}
    verified = or_(SpatialMapPoint.verification_state == "verified", SpatialMapPoint.confidence.in_({"verified", "high"}))
    points = db.query(SpatialMapPoint).filter(SpatialMapPoint.knowledge_entity_id.in_(entity_ids), SpatialMapPoint.is_current.is_(True), verified).limit(150).all()
    regions = db.query(SpatialMapRegion).filter(
        SpatialMapRegion.knowledge_entity_id.in_(entity_ids), SpatialMapRegion.is_current.is_(True),
        or_(SpatialMapRegion.verification_state == "verified", SpatialMapRegion.confidence.in_({"verified", "high"})),
    ).limit(150).all()
    links = db.query(SpatialEntityLocationLink).options(selectinload(SpatialEntityLocationLink.map_point), selectinload(SpatialEntityLocationLink.map_region)).filter(
        SpatialEntityLocationLink.source_entity_id.in_(entity_ids), SpatialEntityLocationLink.is_current.is_(True),
        or_(SpatialEntityLocationLink.verification_state == "verified", SpatialEntityLocationLink.confidence.in_({"verified", "high"})),
    ).limit(150).all()
    graph = db.query(KnowledgeRelationship).filter(
        KnowledgeRelationship.source_entity_id.in_(entity_ids), KnowledgeRelationship.relationship_type_code.in_({"located_at", "occurs_at_location", "mission_occurs_at_location", "appears_in"}),
        KnowledgeRelationship.target_entity_id.isnot(None), KnowledgeRelationship.resolution_state == "resolved",
        KnowledgeRelationship.confidence.in_({"verified", "high"}), KnowledgeRelationship.is_current.is_(True),
    ).limit(150).all()
    target_ids = {row.target_entity_id for row in graph}
    target_points = db.query(SpatialMapPoint).filter(SpatialMapPoint.location_entity_id.in_(target_ids), SpatialMapPoint.is_current.is_(True), verified).limit(150).all() if target_ids else []
    found: dict = {}
    for row in points:
        if row.tibia_x is not None and row.tibia_y is not None:
            found.setdefault(row.knowledge_entity_id, {"x": row.tibia_x, "y": row.tibia_y, "z": row.tibia_z, "bounds": None})
    for row in regions:
        if None not in (row.min_x, row.min_y, row.max_x, row.max_y):
            found.setdefault(row.knowledge_entity_id, {"x": (row.min_x + row.max_x) // 2, "y": (row.min_y + row.max_y) // 2, "z": row.min_z, "bounds": {"min_x": row.min_x, "min_y": row.min_y, "max_x": row.max_x, "max_y": row.max_y}})
    for row in links:
        point, region = row.map_point, row.map_region
        if point and point.tibia_x is not None and point.tibia_y is not None:
            found.setdefault(row.source_entity_id, {"x": point.tibia_x, "y": point.tibia_y, "z": point.tibia_z, "bounds": None})
        elif region and None not in (region.min_x, region.min_y, region.max_x, region.max_y):
            found.setdefault(row.source_entity_id, {"x": (region.min_x + region.max_x) // 2, "y": (region.min_y + region.max_y) // 2, "z": region.min_z, "bounds": {"min_x": region.min_x, "min_y": region.min_y, "max_x": region.max_x, "max_y": region.max_y}})
    targets = {row.location_entity_id: row for row in target_points if row.tibia_x is not None}
    for relationship in graph:
        point = targets.get(relationship.target_entity_id)
        if point:
            found.setdefault(relationship.source_entity_id, {"x": point.tibia_x, "y": point.tibia_y, "z": point.tibia_z, "bounds": None})
    return found


@router.get("/floors/{floor}/image")
def floor_image(floor: int, db: Session = Depends(get_db)):
    record = db.query(WorldMapFloor).filter_by(floor=floor, is_current=True).first()
    if record is None:
        raise HTTPException(status_code=404, detail="World-map floor not imported")
    return FileResponse(_safe_floor_file(record, "map_path"), media_type="image/png", headers={"Cache-Control": "public, max-age=86400, immutable", "X-Map-Source": "local-world-map-cache", "X-Upstream-Commit": record.upstream_commit})


@router.get("/floors/{floor}/pathfinding")
def floor_pathfinding(floor: int, db: Session = Depends(get_db)):
    record = db.query(WorldMapFloor).filter_by(floor=floor, is_current=True).first()
    if record is None or not record.pathfinding_path:
        raise HTTPException(status_code=404, detail="Pathfinding layer not imported")
    return FileResponse(_safe_floor_file(record, "pathfinding_path"), media_type="image/png", headers={"Cache-Control": "public, max-age=86400, immutable", "X-Map-Source": "local-world-map-cache"})


@router.get("/bootstrap")
def map_bootstrap(floor: int = Query(7, ge=0, le=15), db: Session = Depends(get_db)):
    floors = db.query(WorldMapFloor).filter(WorldMapFloor.is_current.is_(True)).order_by(WorldMapFloor.floor).all()
    selected = next((row for row in floors if row.floor == floor), None)
    towns = []
    for name in KNOWN_TOWNS:
        marker = _best_marker(db, name)
        if marker:
            towns.append({"id": f"town:{normalize_search_text(name).replace(' ', '-')}", "entity_type": "town", "name": name, "x": marker.x, "y": marker.y, "z": marker.floor, "geometry_status": "mapped"})
    return {"world_map": _floor_payload(selected) if selected else None, "available_floors": [row.floor for row in floors], "towns": towns}


@router.get("/hunt-zones/{zone_identifier}/context")
def hunt_zone_context(zone_identifier: str, db: Session = Depends(get_db)):
    query = db.query(HuntZone).options(selectinload(HuntZone.creature_spawns).selectinload(SpawnLocation.creature))
    zone = query.filter(HuntZone.id == int(zone_identifier)).first() if zone_identifier.isdigit() else query.filter(or_(HuntZone.slug == zone_identifier, HuntZone.normalized_name == normalize_search_text(zone_identifier.replace("-", " ")))).first()
    if zone is None:
        raise HTTPException(status_code=404, detail="Hunt zone not found")
    zone_payload = _zone_result(db, zone, len(zone.creature_spawns))
    creatures = [spawn.creature for spawn in zone.creature_spawns if spawn.creature and not spawn.creature.is_hidden]
    spatial = _spatial_by_entity(db, {row.knowledge_entity_id for row in creatures if row.knowledge_entity_id})
    markers = []
    creature_cards = []
    for creature in creatures:
        geometry = spatial.get(creature.knowledge_entity_id)
        matches_selected_hunt = False
        if geometry and (geometry.get("z") is None or geometry.get("z") == zone_payload.get("z")):
            zone_bounds = zone_payload.get("bounds")
            if zone_bounds:
                matches_selected_hunt = zone_bounds["min_x"] <= geometry["x"] <= zone_bounds["max_x"] and zone_bounds["min_y"] <= geometry["y"] <= zone_bounds["max_y"]
            elif zone_payload.get("x") is not None and zone_payload.get("y") is not None:
                # A creature may occur in several Hunts. Do not present an
                # unrelated same-floor spatial point as this Hunt's spawn pin.
                matches_selected_hunt = abs(geometry["x"] - zone_payload["x"]) <= 512 and abs(geometry["y"] - zone_payload["y"]) <= 512
        card = {"id": creature.id, "name": creature.name, "slug": creature.slug, "image_url": f"/api/v1/creatures/{creature.id}/image", "hitpoints": creature.hitpoints, "experience": creature.experience, "geometry_status": "mapped" if matches_selected_hunt else "knowledge_only"}
        creature_cards.append(card)
        if matches_selected_hunt:
            markers.append({**card, **geometry, "entity_type": "creature"})
    needle = f"%{normalize_search_text(zone.name)}%"
    routes = db.query(SpatialRoute).options(selectinload(SpatialRoute.steps)).filter(
        SpatialRoute.is_current.is_(True),
        or_(SpatialRoute.verification_state == "verified", SpatialRoute.confidence.in_({"verified", "high"})),
        or_(func.lower(SpatialRoute.name).like(needle), func.lower(SpatialRoute.unresolved_end_name).like(needle)),
    ).limit(12).all()
    route_payload = []
    for route in routes:
        points = [{"x": step.tibia_x, "y": step.tibia_y, "z": step.tibia_z, "instruction": step.instruction} for step in route.steps if step.tibia_x is not None and step.tibia_y is not None]
        if len(points) >= 2:
            route_payload.append({"id": str(route.id), "name": route.name, "points": points, "provenance": route.source_reference, "verification_state": route.verification_state, "confidence": route.confidence})
    return {"hunt_zone": zone_payload, "creatures": creature_cards, "markers": markers, "routes": route_payload}


@router.get("/search")
def map_search(q: str = Query(..., min_length=2, max_length=100), layers: str = Query("hunt_zone,creature,boss,quest,location", max_length=150), limit: int = Query(30, ge=1, le=60), db: Session = Depends(get_db)):
    requested = {value.strip() for value in layers.split(",")}
    per_type, needle = max(3, min(12, limit // max(1, len(requested)))), f"%{q.strip()}%"
    results: list[dict] = []
    zones = db.query(HuntZone).filter(or_(HuntZone.name.ilike(needle), HuntZone.city.ilike(needle), HuntZone.region.ilike(needle))).order_by(HuntZone.name).limit(per_type).all() if "hunt_zone" in requested else []
    results.extend(_zone_result(db, zone) for zone in zones)
    creatures = []
    if requested.intersection({"creature", "boss"}):
        creature_query = db.query(Creature).filter(Creature.is_hidden.is_(False), Creature.name.ilike(needle))
        if "boss" in requested and "creature" not in requested: creature_query = creature_query.filter(Creature.is_boss.is_(True))
        elif "boss" not in requested: creature_query = creature_query.filter(Creature.is_boss.is_(False))
        creatures = creature_query.order_by(Creature.name).limit(per_type).all()
    quests = db.query(TibiaWikiQuest).filter(TibiaWikiQuest.is_group.is_(False), or_(TibiaWikiQuest.name.ilike(needle), TibiaWikiQuest.location.ilike(needle))).order_by(TibiaWikiQuest.name).limit(per_type).all() if "quest" in requested else []
    locations = db.query(TibiaWikiLocation).filter(or_(TibiaWikiLocation.name.ilike(needle), TibiaWikiLocation.region.ilike(needle))).order_by(TibiaWikiLocation.name).limit(per_type).all() if "location" in requested else []
    spatial = _spatial_by_entity(db, {row.knowledge_entity_id for row in [*creatures, *quests, *locations] if row.knowledge_entity_id})
    for creature in creatures:
        geometry = spatial.get(creature.knowledge_entity_id)
        results.append({"id": f"{'boss' if creature.is_boss else 'creature'}:{creature.id}", "entity_type": "boss" if creature.is_boss else "creature", "entity_id": creature.id, "name": creature.name, "slug": creature.slug, "to": f"/creatures/{creature.slug or creature.id}", "subtitle": creature.classification, "image_url": f"/api/v1/creatures/{creature.id}/image", **(geometry or {"x": None, "y": None, "z": None, "bounds": None}), "geometry_status": "mapped" if geometry else "knowledge_only"})
    for entity_type, rows in (("quest", quests), ("location", locations)):
        for row in rows:
            geometry = spatial.get(row.knowledge_entity_id)
            results.append({"id": f"{entity_type}:{row.id}", "entity_type": entity_type, "entity_id": row.id, "name": row.name, "slug": row.slug, "to": f"/{'quests' if entity_type == 'quest' else 'locations'}/{row.slug or row.id}", "subtitle": row.location if entity_type == "quest" else row.region, **(geometry or {"x": None, "y": None, "z": None, "bounds": None}), "geometry_status": "mapped" if geometry else "knowledge_only"})
    normalized = normalize_search_text(q)
    results.sort(key=lambda row: (normalize_search_text(row["name"]) != normalized, normalize_search_text(row["name"])))
    return {"query": q, "items": results[:limit], "total": min(len(results), limit)}
