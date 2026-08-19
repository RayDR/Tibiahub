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
    KnowledgeEntity, KnowledgeRelationship, SpatialEntityLocationLink, SpatialMapPoint,
    SpatialMapRegion, SpatialRoute,
)
from app.models.creature import Creature
from app.models.external_data import Item, TibiaWikiLocation, TibiaWikiNpc, TibiaWikiQuest
from app.models.hunt_zone import HuntZone
from app.models.spawn_location import SpawnLocation
from app.models.world_map import WorldMapFloor, WorldMapMarker
from app.services.map_presentation_service import (
    floor_payload as _floor_payload,
    zone_spatial_presentation,
    zone_spatial_presentations,
)
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


def _best_marker(db: Session, name: str, *, entity_uuid=None, entity_type: str | None = None) -> WorldMapMarker | None:
    normalized = normalize_search_text(name)
    if not normalized:
        return None
    query = db.query(WorldMapMarker).join(WorldMapFloor).filter(
        WorldMapFloor.is_current.is_(True),
        WorldMapMarker.normalized_description == normalized,
        WorldMapMarker.resolution_state == "resolved",
    )
    # Once the local entity has a canonical identity, only a marker explicitly
    # resolved to that identity may place it. Name containment is never enough.
    if entity_uuid is not None:
        query = query.filter(WorldMapMarker.resolved_entity_id == entity_uuid)
    elif entity_type is not None:
        query = query.join(
            KnowledgeEntity, KnowledgeEntity.uuid == WorldMapMarker.resolved_entity_id,
        ).filter(KnowledgeEntity.entity_type == entity_type)
    else:
        return None
    return query.order_by(WorldMapMarker.source_index.asc()).first()


def _zone_result(db: Session, zone: HuntZone, creature_count: int | None = None, spatial: dict | None = None) -> dict:
    spatial = spatial or zone_spatial_presentation(db, zone)
    evidence = [{
        "x": spatial["x"], "y": spatial["y"], "z": spatial["z"],
        "bounds": spatial["bounds"], "label": zone.name,
        "relationship": "hunt_zone_geometry",
        "geometry_source": spatial["geometry_source"],
    }] if spatial["geometry_status"] == "mapped" and spatial["x"] is not None and spatial["y"] is not None else []
    return {
        "id": f"hunt_zone:{zone.id}", "entity_type": "hunt_zone", "entity_id": zone.id,
        "name": zone.name, "slug": zone.slug, "to": f"/hunt-zones/{zone.slug or zone.id}",
        "subtitle": zone.region or zone.city,
        **{key: spatial[key] for key in (
            "x", "y", "z", "bounds", "geometry_status", "geometry_source", "marker_label"
        )},
        "spatial_evidence": evidence,
        "location_labels": [zone.name] if evidence else [],
        "creature_count": creature_count,
    }


SPATIAL_GRAPH_TYPES = {
    "located_at", "occurs_at_location", "mission_occurs_at_location", "starts_at_npc",
}


def _append_evidence(target: dict, entity_id, value: dict) -> None:
    if value.get("x") is None or value.get("y") is None:
        return
    evidence = target.setdefault(entity_id, [])
    identity = (
        value.get("x"), value.get("y"), value.get("z"),
        value.get("relationship"), value.get("label"),
    )
    if not any((row.get("x"), row.get("y"), row.get("z"), row.get("relationship"), row.get("label")) == identity for row in evidence):
        evidence.append(value)


def _direct_spatial_evidence(db: Session, entity_ids: set) -> dict:
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
    markers = db.query(WorldMapMarker).join(WorldMapFloor).filter(
        WorldMapFloor.is_current.is_(True),
        WorldMapMarker.resolved_entity_id.in_(entity_ids),
        WorldMapMarker.resolution_state == "resolved",
    ).order_by(WorldMapMarker.source_index.asc()).limit(300).all()
    found: dict = {}
    for row in points:
        if row.tibia_x is not None and row.tibia_y is not None:
            value = {"x": row.tibia_x, "y": row.tibia_y, "z": row.tibia_z, "bounds": None, "label": row.name, "geometry_source": "spatial_point"}
            _append_evidence(found, row.knowledge_entity_id, value)
            if row.location_entity_id:
                _append_evidence(found, row.location_entity_id, value)
    for row in regions:
        if None not in (row.min_x, row.min_y, row.max_x, row.max_y):
            value = {"x": (row.min_x + row.max_x) // 2, "y": (row.min_y + row.max_y) // 2, "z": row.min_z, "bounds": {"min_x": row.min_x, "min_y": row.min_y, "max_x": row.max_x, "max_y": row.max_y}, "label": row.name, "geometry_source": "spatial_region"}
            _append_evidence(found, row.knowledge_entity_id, value)
            if row.location_entity_id:
                _append_evidence(found, row.location_entity_id, value)
    for row in links:
        point, region = row.map_point, row.map_region
        point_trusted = point and point.is_current and (point.verification_state == "verified" or point.confidence in {"verified", "high"})
        region_trusted = region and region.is_current and (region.verification_state == "verified" or region.confidence in {"verified", "high"})
        if point_trusted and point.tibia_x is not None and point.tibia_y is not None:
            _append_evidence(found, row.source_entity_id, {"x": point.tibia_x, "y": point.tibia_y, "z": point.tibia_z, "bounds": None, "label": point.name, "geometry_source": "spatial_link"})
        elif region_trusted and None not in (region.min_x, region.min_y, region.max_x, region.max_y):
            _append_evidence(found, row.source_entity_id, {"x": (region.min_x + region.max_x) // 2, "y": (region.min_y + region.max_y) // 2, "z": region.min_z, "bounds": {"min_x": region.min_x, "min_y": region.min_y, "max_x": region.max_x, "max_y": region.max_y}, "label": region.name, "geometry_source": "spatial_link"})
    for marker in markers:
        _append_evidence(found, marker.resolved_entity_id, {"x": marker.x, "y": marker.y, "z": marker.floor, "bounds": None, "label": marker.description, "geometry_source": "tibiamaps_marker"})
    return found


def _spatial_evidence_by_entity(db: Session, entity_ids: set) -> dict:
    """Return direct or conservatively related map evidence, up to two hops."""
    found = _direct_spatial_evidence(db, entity_ids)
    paths = [(origin, origin, []) for origin in entity_ids]
    for _depth in range(2):
        frontier = {node for _origin, node, _path in paths}
        if not frontier:
            break
        relationships = db.query(KnowledgeRelationship).filter(
            KnowledgeRelationship.source_entity_id.in_(frontier),
            KnowledgeRelationship.relationship_type_code.in_(SPATIAL_GRAPH_TYPES),
            KnowledgeRelationship.target_entity_id.isnot(None),
            KnowledgeRelationship.resolution_state == "resolved",
            KnowledgeRelationship.confidence.in_({"verified", "high"}),
            KnowledgeRelationship.is_current.is_(True),
        ).limit(500).all()
        target_ids = {row.target_entity_id for row in relationships}
        target_geometry = _direct_spatial_evidence(db, target_ids)
        names = {
            row.uuid: row.canonical_name
            for row in db.query(KnowledgeEntity).filter(KnowledgeEntity.uuid.in_(target_ids)).all()
        } if target_ids else {}
        by_source: dict = {}
        for relationship in relationships:
            by_source.setdefault(relationship.source_entity_id, []).append(relationship)
        next_paths = []
        for origin, node, path in paths:
            for relationship in by_source.get(node, []):
                chain = [*path, relationship.relationship_type_code]
                for geometry in target_geometry.get(relationship.target_entity_id, []):
                    _append_evidence(found, origin, {
                        **geometry,
                        "label": names.get(relationship.target_entity_id) or geometry.get("label"),
                        "relationship": " → ".join(chain),
                    })
                next_paths.append((origin, relationship.target_entity_id, chain))
        paths = next_paths
    return found


def _spatial_by_entity(db: Session, entity_ids: set) -> dict:
    return {
        entity_id: values[0]
        for entity_id, values in _spatial_evidence_by_entity(db, entity_ids).items()
        if values
    }


def _zone_evidence_for_creatures(db: Session, creature_entity_ids: set) -> dict:
    if not creature_entity_ids:
        return {}
    creatures = db.query(Creature).filter(Creature.knowledge_entity_id.in_(creature_entity_ids)).all()
    by_id = {row.id: row.knowledge_entity_id for row in creatures}
    spawns = db.query(SpawnLocation).options(selectinload(SpawnLocation.hunt_zone)).filter(
        SpawnLocation.creature_id.in_(by_id),
    ).limit(500).all()
    zones = {row.hunt_zone.id: row.hunt_zone for row in spawns if row.hunt_zone}
    presentations = zone_spatial_presentations(db, zones.values())
    found: dict = {}
    for spawn in spawns:
        spatial = presentations.get(spawn.hunt_zone_id)
        if not spatial or spatial["geometry_status"] != "mapped":
            continue
        _append_evidence(found, by_id[spawn.creature_id], {
            "x": spatial["x"], "y": spatial["y"], "z": spatial["z"],
            "bounds": spatial["bounds"], "label": spawn.hunt_zone.name,
            "relationship": "spawn_in_hunt_zone",
            "geometry_source": spatial["geometry_source"],
        })
    return found


def _item_drop_creatures(db: Session, item_entity_ids: set) -> dict:
    if not item_entity_ids:
        return {}
    relationships = db.query(KnowledgeRelationship).filter(
        KnowledgeRelationship.is_current.is_(True),
        KnowledgeRelationship.resolution_state == "resolved",
        KnowledgeRelationship.confidence.in_({"verified", "high"}),
        or_(
            (KnowledgeRelationship.source_entity_id.in_(item_entity_ids)) & (KnowledgeRelationship.relationship_type_code == "dropped_by"),
            (KnowledgeRelationship.target_entity_id.in_(item_entity_ids)) & (KnowledgeRelationship.relationship_type_code == "drops"),
        ),
    ).limit(500).all()
    found: dict = {}
    for row in relationships:
        if row.relationship_type_code == "dropped_by":
            found.setdefault(row.source_entity_id, set()).add(row.target_entity_id)
        else:
            found.setdefault(row.target_entity_id, set()).add(row.source_entity_id)
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
        marker = _best_marker(db, name, entity_type="town")
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
def map_search(q: str = Query(..., min_length=2, max_length=100), layers: str = Query("hunt_zone,creature,boss,item,quest,npc,location", max_length=150), limit: int = Query(30, ge=1, le=60), db: Session = Depends(get_db)):
    requested = {value.strip() for value in layers.split(",")}
    per_type, needle = max(3, min(12, limit // max(1, len(requested)))), f"%{q.strip()}%"
    results: list[dict] = []
    zones = db.query(HuntZone).filter(or_(HuntZone.name.ilike(needle), HuntZone.city.ilike(needle), HuntZone.region.ilike(needle))).order_by(HuntZone.name).limit(per_type).all() if "hunt_zone" in requested else []
    zone_spatial = zone_spatial_presentations(db, zones)
    results.extend(_zone_result(db, zone, spatial=zone_spatial[zone.id]) for zone in zones)
    creatures = []
    if requested.intersection({"creature", "boss"}):
        creature_query = db.query(Creature).filter(Creature.is_hidden.is_(False), Creature.name.ilike(needle))
        if "boss" in requested and "creature" not in requested: creature_query = creature_query.filter(Creature.is_boss.is_(True))
        elif "boss" not in requested: creature_query = creature_query.filter(Creature.is_boss.is_(False))
        creatures = creature_query.order_by(Creature.name).limit(per_type).all()
    items = db.query(Item).filter(Item.name.ilike(needle)).order_by(Item.name).limit(per_type).all() if "item" in requested else []
    quests = db.query(TibiaWikiQuest).filter(TibiaWikiQuest.is_group.is_(False), or_(TibiaWikiQuest.name.ilike(needle), TibiaWikiQuest.location.ilike(needle))).order_by(TibiaWikiQuest.name).limit(per_type).all() if "quest" in requested else []
    npcs = db.query(TibiaWikiNpc).filter(or_(TibiaWikiNpc.name.ilike(needle), TibiaWikiNpc.location_name.ilike(needle), TibiaWikiNpc.occupation.ilike(needle))).order_by(TibiaWikiNpc.name).limit(per_type).all() if "npc" in requested else []
    locations = db.query(TibiaWikiLocation).filter(or_(TibiaWikiLocation.name.ilike(needle), TibiaWikiLocation.region.ilike(needle))).order_by(TibiaWikiLocation.name).limit(per_type).all() if "location" in requested else []
    entity_rows = [*creatures, *items, *quests, *npcs, *locations]
    entity_ids = {row.knowledge_entity_id for row in entity_rows if row.knowledge_entity_id}
    spatial = _spatial_evidence_by_entity(db, entity_ids)

    creature_ids = {row.knowledge_entity_id for row in creatures if row.knowledge_entity_id}
    for entity_id, evidence in _zone_evidence_for_creatures(db, creature_ids).items():
        for value in evidence:
            _append_evidence(spatial, entity_id, value)

    item_ids = {row.knowledge_entity_id for row in items if row.knowledge_entity_id}
    drop_creatures = _item_drop_creatures(db, item_ids)
    dropped_creature_ids = set().union(*drop_creatures.values()) if drop_creatures else set()
    creature_spatial = _spatial_evidence_by_entity(db, dropped_creature_ids)
    zone_creature_spatial = _zone_evidence_for_creatures(db, dropped_creature_ids)
    for item_id, related_creatures in drop_creatures.items():
        for creature_id in related_creatures:
            for value in [*creature_spatial.get(creature_id, []), *zone_creature_spatial.get(creature_id, [])]:
                _append_evidence(spatial, item_id, {
                    **value,
                    "relationship": f"dropped_by → {value.get('relationship') or 'mapped_creature'}",
                })

    def geometry(entity_id):
        evidence = spatial.get(entity_id, []) if entity_id else []
        first = evidence[0] if evidence else {"x": None, "y": None, "z": None, "bounds": None}
        return {
            **{key: first.get(key) for key in ("x", "y", "z", "bounds")},
            "geometry_status": "mapped" if evidence else "knowledge_only",
            "geometry_source": first.get("geometry_source"),
            "spatial_evidence": evidence,
            "location_labels": list(dict.fromkeys(value["label"] for value in evidence if value.get("label"))),
        }

    for creature in creatures:
        results.append({"id": f"{'boss' if creature.is_boss else 'creature'}:{creature.id}", "entity_type": "boss" if creature.is_boss else "creature", "entity_id": creature.id, "name": creature.name, "slug": creature.slug, "to": f"/creatures/{creature.slug or creature.id}", "subtitle": creature.classification, "image_url": f"/api/v1/creatures/{creature.id}/image", **geometry(creature.knowledge_entity_id)})
    for item in items:
        results.append({"id": f"item:{item.id}", "entity_type": "item", "entity_id": item.id, "name": item.name, "slug": item.slug, "to": f"/items/{item.slug or item.id}", "subtitle": item.category or item.type, **geometry(item.knowledge_entity_id)})
    for entity_type, rows in (("quest", quests), ("npc", npcs), ("location", locations)):
        for row in rows:
            path = "quests" if entity_type == "quest" else "npcs" if entity_type == "npc" else "locations"
            subtitle = row.location if entity_type == "quest" else row.location_name if entity_type == "npc" else row.region
            results.append({"id": f"{entity_type}:{row.id}", "entity_type": entity_type, "entity_id": row.id, "name": row.name, "slug": row.slug, "to": f"/{path}/{row.slug or row.id}", "subtitle": subtitle, **geometry(row.knowledge_entity_id)})
    normalized = normalize_search_text(q)
    results.sort(key=lambda row: (normalize_search_text(row["name"]) != normalized, normalize_search_text(row["name"])))
    return {"query": q, "items": results[:limit], "total": min(len(results), limit)}
