"""Public, local-only Tibia map discovery API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, selectinload

from app.db.database import get_db
from app.knowledge.models import KnowledgeRelationship, SpatialEntityLocationLink, SpatialMapPoint, SpatialMapRegion
from app.models.creature import Creature
from app.models.external_data import TibiaWikiLocation, TibiaWikiQuest
from app.models.hunt_zone import HuntZone
from app.models.media_asset import MediaAsset
from app.models.spawn_location import SpawnLocation
from app.services.text_utils import normalize_search_text


router = APIRouter(prefix="/map", tags=["Tibia Map"])


def _bounds(value) -> dict | None:
    if not isinstance(value, dict):
        return None
    keys = {
        "min_x": value.get("min_x", value.get("minX")),
        "min_y": value.get("min_y", value.get("minY")),
        "max_x": value.get("max_x", value.get("maxX")),
        "max_y": value.get("max_y", value.get("maxY")),
    }
    if all(isinstance(candidate, (int, float)) for candidate in keys.values()):
        return keys
    return None


def _zone_result(zone: HuntZone, creature_count: int | None = None) -> dict:
    bounds = _bounds(zone.map_bounds)
    x = zone.location_x if zone.location_x is not None else zone.map_x
    y = zone.location_y if zone.location_y is not None else zone.map_y
    z = zone.location_z if zone.location_z is not None else zone.map_z
    return {
        "id": f"hunt_zone:{zone.id}", "entity_type": "hunt_zone", "entity_id": zone.id,
        "name": zone.name, "slug": zone.slug, "to": f"/hunt-zones/{zone.slug or zone.id}",
        "subtitle": zone.region or zone.city, "x": x, "y": y, "z": z, "bounds": bounds,
        "geometry_status": "mapped" if bounds or (x is not None and y is not None) else "knowledge_only",
        "creature_count": creature_count,
    }


def _spatial_by_entity(db: Session, entity_ids: set) -> dict:
    if not entity_ids:
        return {}
    direct_points = db.query(SpatialMapPoint).filter(
        SpatialMapPoint.knowledge_entity_id.in_(entity_ids), SpatialMapPoint.is_current.is_(True),
        or_(SpatialMapPoint.verification_state == "verified", SpatialMapPoint.confidence.in_({"verified", "high"})),
    ).limit(150).all()
    direct_regions = db.query(SpatialMapRegion).filter(
        SpatialMapRegion.knowledge_entity_id.in_(entity_ids), SpatialMapRegion.is_current.is_(True),
        or_(SpatialMapRegion.verification_state == "verified", SpatialMapRegion.confidence.in_({"verified", "high"})),
    ).limit(150).all()
    links = db.query(SpatialEntityLocationLink).options(
        selectinload(SpatialEntityLocationLink.map_point),
        selectinload(SpatialEntityLocationLink.map_region),
    ).filter(
        SpatialEntityLocationLink.source_entity_id.in_(entity_ids),
        SpatialEntityLocationLink.is_current.is_(True),
        or_(SpatialEntityLocationLink.verification_state == "verified", SpatialEntityLocationLink.confidence.in_({"verified", "high"})),
    ).limit(150).all()
    graph_links = db.query(KnowledgeRelationship).filter(
        KnowledgeRelationship.source_entity_id.in_(entity_ids),
        KnowledgeRelationship.relationship_type_code.in_({"located_at", "occurs_at_location", "mission_occurs_at_location", "appears_in"}),
        KnowledgeRelationship.target_entity_id.isnot(None),
        KnowledgeRelationship.resolution_state == "resolved",
        KnowledgeRelationship.confidence.in_({"verified", "high"}),
        KnowledgeRelationship.is_current.is_(True),
    ).limit(150).all()
    target_ids = {row.target_entity_id for row in graph_links}
    target_points = db.query(SpatialMapPoint).filter(
        SpatialMapPoint.location_entity_id.in_(target_ids), SpatialMapPoint.is_current.is_(True),
        or_(SpatialMapPoint.verification_state == "verified", SpatialMapPoint.confidence.in_({"verified", "high"})),
    ).limit(150).all() if target_ids else []
    target_regions = db.query(SpatialMapRegion).filter(
        SpatialMapRegion.location_entity_id.in_(target_ids), SpatialMapRegion.is_current.is_(True),
        or_(SpatialMapRegion.verification_state == "verified", SpatialMapRegion.confidence.in_({"verified", "high"})),
    ).limit(150).all() if target_ids else []
    found: dict = {}
    for row in direct_points:
        if row.tibia_x is not None and row.tibia_y is not None:
            found.setdefault(row.knowledge_entity_id, {"x": row.tibia_x, "y": row.tibia_y, "z": row.tibia_z, "bounds": None})
    for row in direct_regions:
        if None not in (row.min_x, row.min_y, row.max_x, row.max_y):
            found.setdefault(row.knowledge_entity_id, {"x": (row.min_x + row.max_x) // 2, "y": (row.min_y + row.max_y) // 2, "z": row.min_z, "bounds": {"min_x": row.min_x, "min_y": row.min_y, "max_x": row.max_x, "max_y": row.max_y}})
    for row in links:
        point = row.map_point
        region = row.map_region
        if point and point.tibia_x is not None and point.tibia_y is not None:
            found.setdefault(row.source_entity_id, {"x": point.tibia_x, "y": point.tibia_y, "z": point.tibia_z, "bounds": None})
        elif region and None not in (region.min_x, region.min_y, region.max_x, region.max_y):
            found.setdefault(row.source_entity_id, {"x": (region.min_x + region.max_x) // 2, "y": (region.min_y + region.max_y) // 2, "z": region.min_z, "bounds": {"min_x": region.min_x, "min_y": region.min_y, "max_x": region.max_x, "max_y": region.max_y}})
    points_by_location = {row.location_entity_id: row for row in target_points if row.tibia_x is not None and row.tibia_y is not None}
    regions_by_location = {row.location_entity_id: row for row in target_regions if None not in (row.min_x, row.min_y, row.max_x, row.max_y)}
    for relationship in graph_links:
        point = points_by_location.get(relationship.target_entity_id)
        region = regions_by_location.get(relationship.target_entity_id)
        if point:
            found.setdefault(relationship.source_entity_id, {"x": point.tibia_x, "y": point.tibia_y, "z": point.tibia_z, "bounds": None})
        elif region:
            found.setdefault(relationship.source_entity_id, {"x": (region.min_x + region.max_x) // 2, "y": (region.min_y + region.max_y) // 2, "z": region.min_z, "bounds": {"min_x": region.min_x, "min_y": region.min_y, "max_x": region.max_x, "max_y": region.max_y}})
    return found


@router.get("/bootstrap")
def map_bootstrap(db: Session = Depends(get_db)):
    base_candidates = db.query(HuntZone).join(MediaAsset, HuntZone.map_asset_id == MediaAsset.id).filter(
        MediaAsset.status == "cached", HuntZone.map_bounds.isnot(None),
    ).order_by(HuntZone.id.asc()).limit(60).all()
    def area(zone: HuntZone) -> float:
        bounds = _bounds(zone.map_bounds)
        return 0 if bounds is None else (bounds["max_x"] - bounds["min_x"]) * (bounds["max_y"] - bounds["min_y"])
    base = max(base_candidates, key=area, default=None)
    if base is None:
        base = db.query(HuntZone).join(MediaAsset, HuntZone.map_asset_id == MediaAsset.id).filter(
            MediaAsset.status == "cached",
        ).order_by(HuntZone.id.asc()).first()
    counts = dict(db.query(SpawnLocation.hunt_zone_id, func.count(SpawnLocation.id)).group_by(SpawnLocation.hunt_zone_id).limit(500).all())
    zones = db.query(HuntZone).filter(or_(HuntZone.map_bounds.isnot(None), HuntZone.location_x.isnot(None), HuntZone.map_x.isnot(None))).order_by(HuntZone.name.asc()).limit(150).all()
    return {
        "base_map": None if base is None else {
            "zone_id": base.id, "image_url": f"/api/v1/hunt-zones/{base.id}/map-image?placeholder=false",
            "bounds": _bounds(base.map_bounds), "floor": base.map_z if base.map_z is not None else base.location_z,
            "source": "Local Tibia map cache",
        },
        "hunt_zones": [_zone_result(zone, counts.get(zone.id, 0)) for zone in zones],
    }


@router.get("/search")
def map_search(
    q: str = Query(..., min_length=2, max_length=100),
    layers: str = Query("hunt_zone,creature,boss,quest,location", max_length=150),
    limit: int = Query(30, ge=1, le=60),
    db: Session = Depends(get_db),
):
    requested = {value.strip() for value in layers.split(",")}
    per_type = max(3, min(12, limit // max(1, len(requested))))
    needle = f"%{q.strip()}%"
    results: list[dict] = []
    zones: list[HuntZone] = []
    creatures: list[Creature] = []
    quests: list[TibiaWikiQuest] = []
    locations: list[TibiaWikiLocation] = []
    if "hunt_zone" in requested:
        zones = db.query(HuntZone).filter(or_(HuntZone.name.ilike(needle), HuntZone.city.ilike(needle), HuntZone.region.ilike(needle))).order_by(HuntZone.name.asc()).limit(per_type).all()
        results.extend(_zone_result(zone) for zone in zones)
    if requested.intersection({"creature", "boss"}):
        creature_query = db.query(Creature).options(selectinload(Creature.spawn_locations).selectinload(SpawnLocation.hunt_zone)).filter(Creature.is_hidden.is_(False), Creature.name.ilike(needle))
        if requested == {"boss"} or ("boss" in requested and "creature" not in requested):
            creature_query = creature_query.filter(Creature.is_boss.is_(True))
        elif "boss" not in requested:
            creature_query = creature_query.filter(Creature.is_boss.is_(False))
        creatures = creature_query.order_by(Creature.name.asc()).limit(per_type).all()
    if "quest" in requested:
        quests = db.query(TibiaWikiQuest).filter(TibiaWikiQuest.is_group.is_(False), or_(TibiaWikiQuest.name.ilike(needle), TibiaWikiQuest.location.ilike(needle))).order_by(TibiaWikiQuest.name.asc()).limit(per_type).all()
    if "location" in requested:
        locations = db.query(TibiaWikiLocation).filter(or_(TibiaWikiLocation.name.ilike(needle), TibiaWikiLocation.region.ilike(needle))).order_by(TibiaWikiLocation.name.asc()).limit(per_type).all()
    entity_ids = {row.knowledge_entity_id for row in [*creatures, *quests, *locations] if row.knowledge_entity_id is not None}
    spatial = _spatial_by_entity(db, entity_ids)
    for creature in creatures:
        related = [_zone_result(spawn.hunt_zone) for spawn in creature.spawn_locations[:8] if spawn.hunt_zone]
        geometry = spatial.get(creature.knowledge_entity_id)
        if geometry is None:
            geometry = next(({"x": zone["x"], "y": zone["y"], "z": zone["z"], "bounds": zone["bounds"]} for zone in related if zone["x"] is not None or zone["bounds"]), None)
        results.append({
            "id": f"{'boss' if creature.is_boss else 'creature'}:{creature.id}", "entity_type": "boss" if creature.is_boss else "creature",
            "entity_id": creature.id, "name": creature.name, "slug": creature.slug, "to": f"/creatures/{creature.slug or creature.id}",
            "subtitle": creature.classification, **(geometry or {"x": None, "y": None, "z": None, "bounds": None}),
            "geometry_status": "mapped" if geometry else "knowledge_only", "related_hunt_zones": related,
        })
    for entity_type, rows in (("quest", quests), ("location", locations)):
        for row in rows:
            geometry = spatial.get(row.knowledge_entity_id)
            results.append({
                "id": f"{entity_type}:{row.id}", "entity_type": entity_type, "entity_id": row.id,
                "name": row.name, "slug": row.slug, "to": f"/{'quests' if entity_type == 'quest' else 'locations'}/{row.slug or row.id}",
                "subtitle": (row.location if entity_type == "quest" else row.region),
                **(geometry or {"x": None, "y": None, "z": None, "bounds": None}),
                "geometry_status": "mapped" if geometry else "knowledge_only",
            })
    normalized = normalize_search_text(q)
    results.sort(key=lambda row: (normalize_search_text(row["name"]) != normalized, normalize_search_text(row["name"])))
    return {"query": q, "items": results[:limit], "total": len(results[:limit])}
