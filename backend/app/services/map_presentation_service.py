"""Local world-map presentation helpers.

These helpers project canonical Hunt Zone geometry onto the current TibiaMaps
floor without changing either coordinate system.  They are intentionally
read-only and are shared by the public map, Hunt catalog, and planner APIs.
"""
from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy.orm import Session

from app.models.hunt_zone import HuntZone
from app.models.world_map import WorldMapFloor, WorldMapMarker


def floor_payload(floor: WorldMapFloor) -> dict:
    return {
        "floor": floor.floor,
        "image_url": f"/api/v1/map/floors/{floor.floor}/image",
        "pathfinding_url": (
            f"/api/v1/map/floors/{floor.floor}/pathfinding"
            if floor.pathfinding_path else None
        ),
        "width": floor.width,
        "height": floor.height,
        "bounds": {
            "min_x": floor.min_x,
            "min_y": floor.min_y,
            "max_x": floor.max_x,
            "max_y": floor.max_y,
        },
        "provider": floor.provider,
        "upstream_url": floor.upstream_url,
        "upstream_commit": floor.upstream_commit,
        "map_sha256": floor.map_sha256,
        "pathfinding_sha256": floor.pathfinding_sha256,
        "license": floor.license_name,
        "attribution": floor.attribution,
    }


def normalized_bounds(value) -> dict | None:
    if not isinstance(value, dict):
        return None
    result = {
        key: value.get(
            key,
            value.get("".join([key.split("_")[0], key.split("_")[1].title()])),
        )
        for key in ("min_x", "min_y", "max_x", "max_y")
    }
    if not all(isinstance(item, (int, float)) for item in result.values()):
        return None
    if result["max_x"] <= result["min_x"] or result["max_y"] <= result["min_y"]:
        return None
    return result


def zone_spatial_presentations(
    db: Session,
    zones: Iterable[HuntZone],
) -> dict[int, dict]:
    """Resolve map-ready geometry for zones in bounded batch queries.

    A TibiaMaps marker is used only when reconciliation explicitly linked it to
    the zone's canonical UUID.  Stored zone coordinates remain a conservative
    legacy fallback; names alone never create geometry.
    """
    rows = list(zones)
    if not rows:
        return {}

    entity_ids = {row.knowledge_entity_id for row in rows if row.knowledge_entity_id}
    marker_by_entity = {}
    if entity_ids:
        markers = (
            db.query(WorldMapMarker)
            .join(WorldMapFloor, WorldMapFloor.id == WorldMapMarker.floor_id)
            .filter(
                WorldMapFloor.is_current.is_(True),
                WorldMapMarker.resolved_entity_id.in_(entity_ids),
                WorldMapMarker.resolution_state == "resolved",
            )
            .order_by(WorldMapMarker.source_index.asc())
            .all()
        )
        for marker in markers:
            marker_by_entity.setdefault(marker.resolved_entity_id, marker)

    floors = {
        row.floor: row
        for row in db.query(WorldMapFloor)
        .filter(WorldMapFloor.is_current.is_(True))
        .all()
    }
    result: dict[int, dict] = {}
    for zone in rows:
        marker = marker_by_entity.get(zone.knowledge_entity_id)
        bounds = normalized_bounds(zone.map_bounds)
        x = marker.x if marker else (
            zone.location_x if zone.location_x is not None else zone.map_x
        )
        y = marker.y if marker else (
            zone.location_y if zone.location_y is not None else zone.map_y
        )
        z = marker.floor if marker else (
            zone.location_z if zone.location_z is not None else zone.map_z
        )
        if (x is None or y is None) and bounds:
            x = int((bounds["min_x"] + bounds["max_x"]) / 2)
            y = int((bounds["min_y"] + bounds["max_y"]) / 2)
        floor = floors.get(z) if z is not None else None
        mapped = bool(
            floor is not None
            and x is not None and y is not None
            and floor.min_x <= x < floor.max_x
            and floor.min_y <= y < floor.max_y
        )
        result[zone.id] = {
            "geometry_status": "mapped" if mapped else "knowledge_only",
            "geometry_source": (
                "tibiamaps_marker"
                if marker else "verified_local" if mapped else None
            ),
            "marker_label": marker.description if marker else None,
            "unmapped_reason": None if mapped else (
                "missing_coordinates" if x is None or y is None
                else "missing_floor" if z is None
                else "floor_unavailable" if floor is None
                else "outside_floor_bounds"
            ),
            "x": x,
            "y": y,
            "z": z,
            "bounds": bounds,
            "world_map": floor_payload(floor) if floor else None,
        }
    return result


def zone_spatial_presentation(db: Session, zone: HuntZone) -> dict:
    return zone_spatial_presentations(db, [zone])[zone.id]
