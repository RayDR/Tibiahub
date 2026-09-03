"""Public Tibia map API backed exclusively by locally imported world floors."""
from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID

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


def _zone_result(
    db: Session,
    zone: HuntZone,
    creature_count: int | None = None,
    spatial: dict | None = None,
    unresolved: bool = False,
) -> dict:
    spatial = spatial or zone_spatial_presentation(db, zone)
    evidence = [_evidence(
        x=spatial["x"], y=spatial["y"], z=spatial["z"],
        bounds=spatial["bounds"], label=zone.name,
        relationship="hunt_zone_geometry", role="area" if spatial["bounds"] else "direct",
        geometry_source=spatial["geometry_source"], confidence="high",
    )] if spatial["geometry_status"] == "mapped" and spatial["x"] is not None and spatial["y"] is not None else []
    state = evidence[0]["spatial_state"] if evidence else "unresolved" if unresolved else "knowledge_only"
    return {
        "id": f"hunt_zone:{zone.knowledge_entity_id or zone.id}",
        "canonical_entity_id": zone.knowledge_entity_id,
        "entity_type": "hunt_zone", "entity_id": zone.id,
        "name": zone.name, "slug": zone.slug,
        "to": f"/hunt-zones/{zone.slug or zone.id}",
        "navigation_url": f"/hunt-zones/{zone.slug or zone.id}",
        "subtitle": zone.region or zone.city,
        **{key: spatial[key] for key in (
            "x", "y", "z", "bounds", "geometry_status", "geometry_source", "marker_label"
        )},
        "spatial_state": state,
        "spatial_evidence": evidence,
        "location_labels": [zone.name] if evidence else [],
        "creature_count": creature_count,
        "preview": {
            "city": zone.city,
            "region": zone.region,
            "creature_count": creature_count,
            "requires_quest": zone.requires_quest,
        },
    }


SPATIAL_GRAPH_TYPES = {
    "located_at", "occurs_at_location", "mission_occurs_at_location", "starts_at_npc",
    "appears_in",
}

MAP_LAYERS = {"location", "npc", "creature", "boss", "quest", "hunt_zone"}
SPATIAL_ROLE = {
    "located_at": "location",
    "occurs_at_location": "location",
    "mission_occurs_at_location": "mission",
    "starts_at_npc": "start",
    "appears_in": "appearance",
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


def _evidence(
    *,
    x: int,
    y: int,
    z: int | None,
    label: str,
    geometry_source: str,
    bounds: dict | None = None,
    relationship: str | None = None,
    role: str = "direct",
    source_provider: str | None = None,
    confidence: str | None = None,
) -> dict:
    return {
        "x": x,
        "y": y,
        "z": z,
        "bounds": bounds,
        "label": label,
        "relationship": relationship,
        "role": role,
        "spatial_state": "resolved_area" if bounds else "resolved_point",
        "geometry_source": geometry_source,
        "source_provider": source_provider,
        "confidence": confidence,
    }


def _unresolved_spatial_entity_ids(db: Session, entity_ids: set[UUID]) -> set[UUID]:
    if not entity_ids:
        return set()
    relationship_ids = {
        row[0]
        for row in db.query(KnowledgeRelationship.source_entity_id).filter(
            KnowledgeRelationship.source_entity_id.in_(entity_ids),
            KnowledgeRelationship.relationship_type_code.in_(SPATIAL_GRAPH_TYPES),
            KnowledgeRelationship.resolution_state.in_({"unresolved", "ambiguous"}),
            KnowledgeRelationship.is_current.is_(True),
        ).all()
    }
    link_ids = {
        row[0]
        for row in db.query(SpatialEntityLocationLink.source_entity_id).filter(
            SpatialEntityLocationLink.source_entity_id.in_(entity_ids),
            SpatialEntityLocationLink.is_current.is_(True),
            SpatialEntityLocationLink.verification_state.in_({"unresolved", "ambiguous"}),
        ).all()
    }
    return relationship_ids | link_ids


def _geometry(
    entity_id: UUID | None,
    spatial: dict,
    unresolved_ids: set[UUID],
) -> dict:
    values = spatial.get(entity_id, []) if entity_id else []
    first = values[0] if values else {"x": None, "y": None, "z": None, "bounds": None}
    state = (
        first.get("spatial_state")
        if values
        else "unresolved"
        if entity_id in unresolved_ids
        else "knowledge_only"
    )
    return {
        **{key: first.get(key) for key in ("x", "y", "z", "bounds")},
        "geometry_status": "mapped" if values else "knowledge_only",
        "spatial_state": state,
        "geometry_source": first.get("geometry_source"),
        "spatial_evidence": values,
        "location_labels": list(dict.fromkeys(value["label"] for value in values if value.get("label"))),
    }


def _canonical_result(
    *,
    entity_type: str,
    row: Any,
    geometry: dict,
    subtitle: str | None,
    navigation_url: str,
    image_url: str | None = None,
    preview: dict | None = None,
) -> dict:
    canonical_id = row.knowledge_entity_id
    return {
        "id": f"{entity_type}:{canonical_id}",
        "canonical_entity_id": canonical_id,
        "entity_type": entity_type,
        "entity_id": row.id,
        "name": row.name,
        "slug": row.slug,
        "to": navigation_url,
        "navigation_url": navigation_url,
        "subtitle": subtitle,
        "image_url": image_url,
        "preview": preview or {},
        **geometry,
    }


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
            value = _evidence(
                x=row.tibia_x, y=row.tibia_y, z=row.tibia_z, label=row.name,
                geometry_source="spatial_point", source_provider=row.source_provider_id,
                confidence=row.confidence,
            )
            _append_evidence(found, row.knowledge_entity_id, value)
            if row.location_entity_id:
                _append_evidence(found, row.location_entity_id, value)
    for row in regions:
        if None not in (row.min_x, row.min_y, row.max_x, row.max_y):
            value = _evidence(
                x=(row.min_x + row.max_x) // 2,
                y=(row.min_y + row.max_y) // 2,
                z=row.min_z,
                bounds={"min_x": row.min_x, "min_y": row.min_y, "max_x": row.max_x, "max_y": row.max_y},
                label=row.name,
                geometry_source="spatial_region",
                source_provider=row.source_provider_id,
                confidence=row.confidence,
            )
            _append_evidence(found, row.knowledge_entity_id, value)
            if row.location_entity_id:
                _append_evidence(found, row.location_entity_id, value)
    for row in links:
        point, region = row.map_point, row.map_region
        point_trusted = point and point.is_current and (point.verification_state == "verified" or point.confidence in {"verified", "high"})
        region_trusted = region and region.is_current and (region.verification_state == "verified" or region.confidence in {"verified", "high"})
        if point_trusted and point.tibia_x is not None and point.tibia_y is not None:
            _append_evidence(found, row.source_entity_id, _evidence(
                x=point.tibia_x, y=point.tibia_y, z=point.tibia_z,
                label=point.name, geometry_source="spatial_link",
                source_provider=row.source_provider_id, confidence=row.confidence,
            ))
        elif region_trusted and None not in (region.min_x, region.min_y, region.max_x, region.max_y):
            _append_evidence(found, row.source_entity_id, _evidence(
                x=(region.min_x + region.max_x) // 2,
                y=(region.min_y + region.max_y) // 2,
                z=region.min_z,
                bounds={"min_x": region.min_x, "min_y": region.min_y, "max_x": region.max_x, "max_y": region.max_y},
                label=region.name,
                geometry_source="spatial_link",
                source_provider=row.source_provider_id,
                confidence=row.confidence,
            ))
    for marker in markers:
        _append_evidence(found, marker.resolved_entity_id, _evidence(
            x=marker.x, y=marker.y, z=marker.floor, label=marker.description,
            geometry_source="tibiamaps_marker", source_provider="tibiamaps",
            confidence="high",
        ))
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
                        "role": SPATIAL_ROLE.get(chain[0], "related"),
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
    spawns = db.query(SpawnLocation).join(HuntZone).options(selectinload(SpawnLocation.hunt_zone)).filter(
        SpawnLocation.creature_id.in_(by_id),
        HuntZone.knowledge_entity_id.isnot(None),
    ).limit(500).all()
    zones = {row.hunt_zone.id: row.hunt_zone for row in spawns if row.hunt_zone}
    presentations = zone_spatial_presentations(db, zones.values())
    found: dict = {}
    for spawn in spawns:
        spatial = presentations.get(spawn.hunt_zone_id)
        if not spatial or spatial["geometry_status"] != "mapped":
            continue
        _append_evidence(found, by_id[spawn.creature_id], _evidence(
            x=spatial["x"], y=spatial["y"], z=spatial["z"],
            bounds=spatial["bounds"], label=spawn.hunt_zone.name,
            relationship="spawn_in_hunt_zone", role="appearance",
            geometry_source=spatial["geometry_source"], confidence="high",
        ))
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


def _rows_for_layer(db: Session, layer: str):
    if layer == "location":
        return db.query(TibiaWikiLocation).filter(TibiaWikiLocation.knowledge_entity_id.isnot(None)).order_by(TibiaWikiLocation.name).all()
    if layer == "npc":
        return db.query(TibiaWikiNpc).filter(TibiaWikiNpc.knowledge_entity_id.isnot(None)).order_by(TibiaWikiNpc.name).all()
    if layer == "quest":
        return db.query(TibiaWikiQuest).filter(
            TibiaWikiQuest.knowledge_entity_id.isnot(None), TibiaWikiQuest.is_group.is_(False),
        ).order_by(TibiaWikiQuest.name).all()
    if layer in {"creature", "boss"}:
        query = db.query(Creature).filter(
            Creature.knowledge_entity_id.isnot(None), Creature.is_hidden.is_(False),
            Creature.is_boss.is_(layer == "boss"),
        )
        return query.order_by(Creature.name).all()
    if layer == "hunt_zone":
        return db.query(HuntZone).filter(HuntZone.knowledge_entity_id.isnot(None)).order_by(HuntZone.name).all()
    raise HTTPException(status_code=422, detail={"code": "unsupported_map_layer"})


def _entity_results(
    db: Session,
    entity_type: str,
    rows: list,
    *,
    resolved_only: bool = False,
    floor: int | None = None,
) -> list[dict]:
    entity_ids = {row.knowledge_entity_id for row in rows if row.knowledge_entity_id}
    spatial = _spatial_evidence_by_entity(db, entity_ids)
    unresolved_ids = _unresolved_spatial_entity_ids(db, entity_ids)
    if entity_type in {"creature", "boss"}:
        for entity_id, evidence in _zone_evidence_for_creatures(db, entity_ids).items():
            for value in evidence:
                _append_evidence(spatial, entity_id, value)

    results: list[dict] = []
    if entity_type == "hunt_zone":
        presentations = zone_spatial_presentations(db, rows)
        for row in rows:
            result = _zone_result(
                db, row, spatial=presentations[row.id],
                unresolved=row.knowledge_entity_id in unresolved_ids,
            )
            if resolved_only and result["geometry_status"] != "mapped":
                continue
            if floor is not None and result["z"] != floor:
                continue
            results.append(result)
        return results

    for row in rows:
        values = spatial.get(row.knowledge_entity_id, [])
        if floor is not None:
            values = [value for value in values if value.get("z") in {None, floor}]
        row_spatial = {row.knowledge_entity_id: values} if values else {}
        geometry = _geometry(row.knowledge_entity_id, row_spatial, unresolved_ids)
        if resolved_only and geometry["geometry_status"] != "mapped":
            continue
        if entity_type in {"creature", "boss"}:
            result = _canonical_result(
                entity_type="boss" if row.is_boss else "creature",
                row=row,
                geometry=geometry,
                subtitle=row.classification,
                navigation_url=f"/creatures/{row.slug or row.id}",
                image_url=f"/api/v1/creatures/{row.id}/image",
                preview={
                    "classification": row.classification,
                    "difficulty": row.difficulty,
                    "is_boss": bool(row.is_boss),
                },
            )
        elif entity_type == "npc":
            result = _canonical_result(
                entity_type="npc", row=row, geometry=geometry,
                subtitle=row.location_name or row.occupation,
                navigation_url=f"/npcs/{row.knowledge_entity_id}", image_url=None,
                preview={
                    "location": row.location_name,
                    "occupation": row.occupation,
                    "quest_count": len(row.related_quests or []),
                    "trades": bool(row.buys or row.sells),
                },
            )
        elif entity_type == "quest":
            result = _canonical_result(
                entity_type="quest", row=row, geometry=geometry,
                subtitle=row.location,
                navigation_url=f"/quests/{row.slug or row.id}", image_url=row.image_url,
                preview={
                    "location": row.location,
                    "minimum_level": row.min_level,
                    "difficulty": row.difficulty,
                    "starting_npcs": list(row.starting_npcs or [])[:3],
                },
            )
        else:
            result = _canonical_result(
                entity_type="location", row=row, geometry=geometry,
                subtitle=row.region,
                navigation_url=f"/locations/{row.slug or row.id}", image_url=row.image_url,
                preview={
                    "location_kind": row.location_kind,
                    "region": row.region,
                    "parent_location": row.parent_location,
                },
            )
        results.append(result)
    return results


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
            evidence = _evidence(
                x=marker.x, y=marker.y, z=marker.floor, label=name,
                geometry_source="tibiamaps_marker", source_provider="tibiamaps", confidence="high",
            )
            towns.append({
                "id": f"town:{marker.resolved_entity_id}",
                "canonical_entity_id": marker.resolved_entity_id,
                "entity_type": "town",
                "entity_id": None,
                "name": name,
                "slug": normalize_search_text(name).replace(" ", "-"),
                "to": None,
                "navigation_url": None,
                "subtitle": None,
                "image_url": None,
                "x": marker.x, "y": marker.y, "z": marker.floor,
                "bounds": None,
                "geometry_status": "mapped",
                "spatial_state": "resolved_point",
                "geometry_source": "tibiamaps_marker",
                "spatial_evidence": [evidence],
                "location_labels": [name],
                "preview": {},
            })
    default_results = _entity_results(
        db, "location", _rows_for_layer(db, "location"), resolved_only=True,
    )
    default_results.sort(key=lambda row: (
        row["name"] not in KNOWN_TOWNS,
        KNOWN_TOWNS.index(row["name"]) if row["name"] in KNOWN_TOWNS else len(KNOWN_TOWNS),
        row["name"],
    ))
    return {
        "world_map": _floor_payload(selected) if selected else None,
        "available_floors": [row.floor for row in floors],
        "towns": towns,
        "default_results": default_results[:40],
    }


@router.get("/layers/{layer}")
def map_layer(
    layer: str,
    floor: int | None = Query(None, ge=0, le=15),
    limit: int = Query(250, ge=1, le=250),
    db: Session = Depends(get_db),
):
    if layer not in MAP_LAYERS:
        raise HTTPException(status_code=422, detail={"code": "unsupported_map_layer"})
    rows = _rows_for_layer(db, layer)
    items = _entity_results(db, layer, rows, resolved_only=True, floor=floor)
    return {
        "layer": layer,
        "floor": floor,
        "items": items[:limit],
        "total": len(items),
        "has_more": len(items) > limit,
    }


@router.get("/hunt-zones/{zone_identifier}/context")
def hunt_zone_context(zone_identifier: str, db: Session = Depends(get_db)):
    query = db.query(HuntZone).options(selectinload(HuntZone.creature_spawns).selectinload(SpawnLocation.creature))
    zone = query.filter(HuntZone.id == int(zone_identifier)).first() if zone_identifier.isdigit() else query.filter(or_(HuntZone.slug == zone_identifier, HuntZone.normalized_name == normalize_search_text(zone_identifier.replace("-", " ")))).order_by(HuntZone.knowledge_entity_id.is_(None), HuntZone.id).first()
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
    requested = {value.strip() for value in layers.split(",")} & (MAP_LAYERS | {"item"})
    per_type, needle = max(3, min(12, limit // max(1, len(requested)))), f"%{q.strip()}%"
    results: list[dict] = []
    zones = db.query(HuntZone).filter(
        HuntZone.knowledge_entity_id.isnot(None),
        or_(HuntZone.name.ilike(needle), HuntZone.city.ilike(needle), HuntZone.region.ilike(needle)),
    ).order_by(HuntZone.name).limit(per_type).all() if "hunt_zone" in requested else []
    results.extend(_entity_results(db, "hunt_zone", zones))
    creatures = []
    if requested.intersection({"creature", "boss"}):
        creature_query = db.query(Creature).filter(
            Creature.knowledge_entity_id.isnot(None),
            Creature.is_hidden.is_(False), Creature.name.ilike(needle),
        )
        if "boss" in requested and "creature" not in requested: creature_query = creature_query.filter(Creature.is_boss.is_(True))
        elif "boss" not in requested: creature_query = creature_query.filter(Creature.is_boss.is_(False))
        creatures = creature_query.order_by(Creature.name).limit(per_type).all()
    items = db.query(Item).filter(
        Item.knowledge_entity_id.isnot(None), Item.name.ilike(needle),
    ).order_by(Item.name).limit(per_type).all() if "item" in requested else []
    quests = db.query(TibiaWikiQuest).filter(
        TibiaWikiQuest.knowledge_entity_id.isnot(None), TibiaWikiQuest.is_group.is_(False),
        or_(TibiaWikiQuest.name.ilike(needle), TibiaWikiQuest.location.ilike(needle)),
    ).order_by(TibiaWikiQuest.name).limit(per_type).all() if "quest" in requested else []
    npcs = db.query(TibiaWikiNpc).filter(
        TibiaWikiNpc.knowledge_entity_id.isnot(None),
        or_(TibiaWikiNpc.name.ilike(needle), TibiaWikiNpc.location_name.ilike(needle), TibiaWikiNpc.occupation.ilike(needle)),
    ).order_by(TibiaWikiNpc.name).limit(per_type).all() if "npc" in requested else []
    locations = db.query(TibiaWikiLocation).filter(
        TibiaWikiLocation.knowledge_entity_id.isnot(None),
        or_(TibiaWikiLocation.name.ilike(needle), TibiaWikiLocation.region.ilike(needle)),
    ).order_by(TibiaWikiLocation.name).limit(per_type).all() if "location" in requested else []

    results.extend(_entity_results(db, "creature", creatures))
    results.extend(_entity_results(db, "quest", quests))
    results.extend(_entity_results(db, "npc", npcs))
    results.extend(_entity_results(db, "location", locations))

    item_ids = {row.knowledge_entity_id for row in items if row.knowledge_entity_id}
    # Items are not spatial entities. Only a resolved semantic path such as
    # dropped_by -> Creature -> trusted geometry may place an Item search result.
    item_spatial: dict = {}
    item_unresolved = _unresolved_spatial_entity_ids(db, item_ids)
    drop_creatures = _item_drop_creatures(db, item_ids)
    dropped_creature_ids = set().union(*drop_creatures.values()) if drop_creatures else set()
    creature_spatial = _spatial_evidence_by_entity(db, dropped_creature_ids)
    zone_creature_spatial = _zone_evidence_for_creatures(db, dropped_creature_ids)
    for item_id, related_creatures in drop_creatures.items():
        for creature_id in related_creatures:
            for value in [*creature_spatial.get(creature_id, []), *zone_creature_spatial.get(creature_id, [])]:
                _append_evidence(item_spatial, item_id, {
                    **value,
                    "relationship": f"dropped_by → {value.get('relationship') or 'mapped_creature'}",
                    "role": "obtained_from",
                })
    for item in items:
        results.append(_canonical_result(
            entity_type="item", row=item,
            geometry=_geometry(item.knowledge_entity_id, item_spatial, item_unresolved),
            subtitle=item.category or item.type,
            navigation_url=f"/items/{item.slug or item.id}",
            image_url=f"/api/v1/items/{item.id}/image",
            preview={"relationship_context": "obtained_from" if item_spatial.get(item.knowledge_entity_id) else None},
        ))
    normalized = normalize_search_text(q)
    results.sort(key=lambda row: (normalize_search_text(row["name"]) != normalized, normalize_search_text(row["name"])))
    return {"query": q, "items": results[:limit], "total": min(len(results), limit)}
