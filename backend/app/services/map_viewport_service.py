"""Read-only, evidence-backed map projection for a bounded viewport."""
from __future__ import annotations

import base64
import json
import re
from collections import defaultdict
from itertools import zip_longest
from typing import Any
from uuid import UUID

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.knowledge.models import (
    KnowledgeRelationship,
    SpatialEntityLocationLink,
    SpatialMapPoint,
    SpatialMapRegion,
)
from app.models.creature import Creature
from app.models.external_data import TibiaWikiLocation, TibiaWikiNpc, TibiaWikiQuest
from app.models.hunt_zone import HuntZone
from app.models.media_asset import MediaAsset
from app.models.spawn_location import SpawnLocation
from app.models.world_map import WorldMapFloor, WorldMapMarker
from app.services import media_asset_service


MAP_VIEWPORT_LAYERS = frozenset({"location", "npc", "creature", "boss", "quest", "hunt_zone"})
SPATIAL_GRAPH_TYPES = frozenset({
    "located_at", "occurs_at_location", "mission_occurs_at_location", "starts_at_npc",
    "appears_in",
})
SPATIAL_ROLES = {
    "located_at": "location",
    "occurs_at_location": "location",
    "mission_occurs_at_location": "mission",
    "starts_at_npc": "start",
    "appears_in": "appearance",
}
TRUSTED_CONFIDENCE = frozenset({"verified", "high"})
MAX_LIMIT = 200
MAX_EVIDENCE_ROWS = 2000
CURSOR_PATTERN = re.compile(r"^(?:boss|creature|hunt_zone|location|npc|quest):([0-9a-f-]{36})$")


def parse_layers(value: str) -> tuple[str, ...]:
    requested = tuple(dict.fromkeys(part.strip() for part in value.split(",") if part.strip()))
    if not requested or any(layer not in MAP_VIEWPORT_LAYERS for layer in requested):
        raise ValueError("unsupported_map_layer")
    return tuple(sorted(requested))


def density_limit(zoom: float, requested: int) -> int:
    """Zoom changes response density only; it never changes spatial truth."""
    cap = 40 if zoom < -2 else 80 if zoom < 0 else 120 if zoom < 2 else MAX_LIMIT
    return min(requested, cap, MAX_LIMIT)


def _trusted(model):
    return and_(
        model.verification_state.notin_({"unresolved", "ambiguous", "rejected"}),
        or_(model.verification_state == "verified", model.confidence.in_(TRUSTED_CONFIDENCE)),
    )


def _evidence(
    *, x: int, y: int, floor: int, label: str, geometry_source: str,
    bounds: dict[str, int] | None = None, relationship: str | None = None,
    role: str = "direct", source_provider: str | None = None,
    confidence: str | None = None,
) -> dict[str, Any]:
    return {
        "x": x, "y": y, "z": floor, "bounds": bounds, "label": label,
        "relationship": relationship, "role": role,
        "spatial_state": "resolved_area" if bounds else "resolved_point",
        "geometry_source": geometry_source, "source_provider": source_provider,
        "confidence": confidence,
    }


def _add(found: dict[UUID, list[dict[str, Any]]], entity_id: UUID | None, value: dict[str, Any]) -> None:
    if entity_id is None:
        return
    identity = (
        value["x"], value["y"], value["z"],
        json.dumps(value.get("bounds"), sort_keys=True), value.get("geometry_source"),
        value.get("relationship"), value.get("role"), value.get("source_provider"),
    )
    if not any((
        row["x"], row["y"], row["z"], json.dumps(row.get("bounds"), sort_keys=True),
        row.get("geometry_source"), row.get("relationship"), row.get("role"), row.get("source_provider"),
    ) == identity for row in found[entity_id]):
        found[entity_id].append(value)


def _bounded_direct_evidence(
    db: Session, *, min_x: int, min_y: int, max_x: int, max_y: int, floor: int,
) -> dict[UUID, list[dict[str, Any]]]:
    found: dict[UUID, list[dict[str, Any]]] = defaultdict(list)
    markers = (
        db.query(WorldMapMarker)
        .join(WorldMapFloor, WorldMapFloor.id == WorldMapMarker.floor_id)
        .filter(
            WorldMapFloor.is_current.is_(True), WorldMapMarker.floor == floor,
            WorldMapMarker.x >= min_x, WorldMapMarker.x < max_x,
            WorldMapMarker.y >= min_y, WorldMapMarker.y < max_y,
            WorldMapMarker.resolution_state == "resolved",
            WorldMapMarker.resolved_entity_id.isnot(None),
        )
        .order_by(WorldMapMarker.x, WorldMapMarker.y, WorldMapMarker.source_index)
        .limit(MAX_EVIDENCE_ROWS).all()
    )
    for row in markers:
        _add(found, row.resolved_entity_id, _evidence(
            x=row.x, y=row.y, floor=row.floor, label=row.description,
            geometry_source="tibiamaps_marker", source_provider="tibiamaps", confidence="high",
        ))

    points = (
        db.query(SpatialMapPoint)
        .filter(
            SpatialMapPoint.is_current.is_(True), _trusted(SpatialMapPoint),
            SpatialMapPoint.tibia_z == floor,
            SpatialMapPoint.tibia_x >= min_x, SpatialMapPoint.tibia_x < max_x,
            SpatialMapPoint.tibia_y >= min_y, SpatialMapPoint.tibia_y < max_y,
        )
        .order_by(SpatialMapPoint.tibia_x, SpatialMapPoint.tibia_y, SpatialMapPoint.id)
        .limit(MAX_EVIDENCE_ROWS).all()
    )
    for row in points:
        value = _evidence(
            x=row.tibia_x, y=row.tibia_y, floor=row.tibia_z, label=row.name,
            geometry_source="spatial_point", source_provider=row.source_provider_id,
            confidence=row.confidence,
        )
        _add(found, row.knowledge_entity_id, value)
        _add(found, row.location_entity_id, value)

    regions = (
        db.query(SpatialMapRegion)
        .filter(
            SpatialMapRegion.is_current.is_(True), _trusted(SpatialMapRegion),
            SpatialMapRegion.min_z <= floor, SpatialMapRegion.max_z >= floor,
            SpatialMapRegion.min_x < max_x, SpatialMapRegion.max_x >= min_x,
            SpatialMapRegion.min_y < max_y, SpatialMapRegion.max_y >= min_y,
        )
        .order_by(SpatialMapRegion.min_x, SpatialMapRegion.min_y, SpatialMapRegion.id)
        .limit(MAX_EVIDENCE_ROWS).all()
    )
    for row in regions:
        bounds = {"min_x": row.min_x, "min_y": row.min_y, "max_x": row.max_x, "max_y": row.max_y}
        value = _evidence(
            x=(row.min_x + row.max_x) // 2, y=(row.min_y + row.max_y) // 2,
            floor=floor, bounds=bounds, label=row.name, geometry_source="spatial_region",
            source_provider=row.source_provider_id, confidence=row.confidence,
        )
        _add(found, row.knowledge_entity_id, value)
        _add(found, row.location_entity_id, value)

    # Explicit location links can map another entity onto an already bounded,
    # trusted point/region without loading unrelated spatial records.
    point_links = (
        db.query(SpatialEntityLocationLink, SpatialMapPoint)
        .join(SpatialMapPoint, SpatialMapPoint.id == SpatialEntityLocationLink.map_point_id)
        .filter(
            SpatialEntityLocationLink.is_current.is_(True), _trusted(SpatialEntityLocationLink),
            SpatialMapPoint.is_current.is_(True), _trusted(SpatialMapPoint),
            SpatialMapPoint.tibia_z == floor,
            SpatialMapPoint.tibia_x >= min_x, SpatialMapPoint.tibia_x < max_x,
            SpatialMapPoint.tibia_y >= min_y, SpatialMapPoint.tibia_y < max_y,
        ).limit(MAX_EVIDENCE_ROWS).all()
    )
    for link, point in point_links:
        _add(found, link.source_entity_id, _evidence(
            x=point.tibia_x, y=point.tibia_y, floor=point.tibia_z, label=point.name,
            geometry_source="spatial_link", relationship="explicit_location_link", role="location",
            source_provider=link.source_provider_id, confidence=link.confidence,
        ))
    region_links = (
        db.query(SpatialEntityLocationLink, SpatialMapRegion)
        .join(SpatialMapRegion, SpatialMapRegion.id == SpatialEntityLocationLink.map_region_id)
        .filter(
            SpatialEntityLocationLink.is_current.is_(True), _trusted(SpatialEntityLocationLink),
            SpatialMapRegion.is_current.is_(True), _trusted(SpatialMapRegion),
            SpatialMapRegion.min_z <= floor, SpatialMapRegion.max_z >= floor,
            SpatialMapRegion.min_x < max_x, SpatialMapRegion.max_x >= min_x,
            SpatialMapRegion.min_y < max_y, SpatialMapRegion.max_y >= min_y,
        ).limit(MAX_EVIDENCE_ROWS).all()
    )
    for link, region in region_links:
        bounds = {"min_x": region.min_x, "min_y": region.min_y, "max_x": region.max_x, "max_y": region.max_y}
        _add(found, link.source_entity_id, _evidence(
            x=(region.min_x + region.max_x) // 2, y=(region.min_y + region.max_y) // 2,
            floor=floor, bounds=bounds, label=region.name, geometry_source="spatial_link",
            relationship="explicit_location_link", role="location",
            source_provider=link.source_provider_id, confidence=link.confidence,
        ))

    direct_ids = set(found)
    if direct_ids:
        linked = (
            db.query(SpatialEntityLocationLink)
            .filter(
                SpatialEntityLocationLink.is_current.is_(True), _trusted(SpatialEntityLocationLink),
                SpatialEntityLocationLink.location_entity_id.in_(direct_ids),
            ).limit(MAX_EVIDENCE_ROWS).all()
        )
        for link in linked:
            for value in found.get(link.location_entity_id, ()):
                _add(found, link.source_entity_id, {
                    **value, "relationship": "explicit_location_link", "role": "location",
                    "geometry_source": "spatial_link",
                })
    return found


def _expand_relationships(db: Session, found: dict[UUID, list[dict[str, Any]]]) -> None:
    """Reverse-walk trusted resolved relationships, at most two bounded hops."""
    frontier = set(found)
    for _depth in range(2):
        if not frontier:
            break
        relationships = (
            db.query(KnowledgeRelationship)
            .filter(
                KnowledgeRelationship.target_entity_id.in_(frontier),
                KnowledgeRelationship.relationship_type_code.in_(SPATIAL_GRAPH_TYPES),
                KnowledgeRelationship.resolution_state == "resolved",
                KnowledgeRelationship.confidence.in_(TRUSTED_CONFIDENCE),
                KnowledgeRelationship.is_current.is_(True),
            )
            .order_by(KnowledgeRelationship.source_entity_id, KnowledgeRelationship.id)
            .limit(MAX_EVIDENCE_ROWS).all()
        )
        next_frontier: set[UUID] = set()
        for row in relationships:
            for value in found.get(row.target_entity_id, ()):
                _add(found, row.source_entity_id, {
                    **value,
                    "relationship": row.relationship_type_code,
                    "role": SPATIAL_ROLES.get(row.relationship_type_code, "related"),
                })
            next_frontier.add(row.source_entity_id)
        frontier = next_frontier


def _expand_zone_spawns(db: Session, found: dict[UUID, list[dict[str, Any]]]) -> None:
    zone_entities = set(found)
    if not zone_entities:
        return
    rows = (
        db.query(SpawnLocation, HuntZone, Creature)
        .join(HuntZone, HuntZone.id == SpawnLocation.hunt_zone_id)
        .join(Creature, Creature.id == SpawnLocation.creature_id)
        .filter(
            HuntZone.knowledge_entity_id.in_(zone_entities),
            Creature.knowledge_entity_id.isnot(None), Creature.is_hidden.is_(False),
        ).limit(MAX_EVIDENCE_ROWS).all()
    )
    for _spawn, zone, creature in rows:
        for value in found.get(zone.knowledge_entity_id, ()):
            _add(found, creature.knowledge_entity_id, {
                **value, "relationship": "spawn_in_hunt_zone", "role": "appearance",
            })


def _media_urls(db: Session, rows: list[Any]) -> dict[tuple[type, int], str]:
    """Return URLs only for already verified local files; never provider URLs."""
    keyed: dict[str, list[tuple[Any, str]]] = defaultdict(list)
    linked_ids: set[int] = set()
    for row in rows:
        if isinstance(row, Creature):
            keyed[media_asset_service.build_creature_asset_key(row)].append((row, "creatures"))
            if row.image_asset_id:
                linked_ids.add(row.image_asset_id)
        elif isinstance(row, TibiaWikiNpc):
            keyed[media_asset_service.build_canonical_npc_asset_key(row.knowledge_entity_id)].append((row, "npcs"))
            keyed[media_asset_service.build_legacy_npc_asset_key(row)].append((row, "npcs"))
        elif isinstance(row, TibiaWikiLocation):
            keyed[media_asset_service.build_location_asset_key(row)].append((row, "locations"))
    if not keyed and not linked_ids:
        return {}
    query_filter = [MediaAsset.asset_key.in_(set(keyed))]
    if linked_ids:
        query_filter.append(MediaAsset.id.in_(linked_ids))
    assets = db.query(MediaAsset).filter(or_(*query_filter), MediaAsset.status == "cached").all()
    urls: dict[tuple[type, int], str] = {}
    for asset in assets:
        if not asset.file_exists():
            continue
        targets = list(keyed.get(asset.asset_key, ()))
        targets.extend(
                (row, "creatures") for row in rows
                if isinstance(row, Creature) and row.image_asset_id == asset.id
        )
        for target in targets:
            row, namespace = target
            urls[(type(row), row.id)] = f"/api/v1/{namespace}/{row.knowledge_entity_id if namespace != 'creatures' else row.id}/image?placeholder=false"
    return urls


def _domain_rows(db: Session, entity_ids: set[UUID], layers: tuple[str, ...]) -> list[tuple[str, Any]]:
    rows: list[tuple[str, Any]] = []
    if "location" in layers:
        rows.extend(("location", row) for row in db.query(TibiaWikiLocation).filter(TibiaWikiLocation.knowledge_entity_id.in_(entity_ids)).all())
    if "npc" in layers:
        rows.extend(("npc", row) for row in db.query(TibiaWikiNpc).filter(TibiaWikiNpc.knowledge_entity_id.in_(entity_ids)).all())
    if "quest" in layers:
        rows.extend(("quest", row) for row in db.query(TibiaWikiQuest).filter(
            TibiaWikiQuest.knowledge_entity_id.in_(entity_ids), TibiaWikiQuest.is_group.is_(False),
        ).all())
    if "hunt_zone" in layers:
        rows.extend(("hunt_zone", row) for row in db.query(HuntZone).filter(HuntZone.knowledge_entity_id.in_(entity_ids)).all())
    creature_layers = set(layers) & {"creature", "boss"}
    if creature_layers:
        creatures = db.query(Creature).filter(
            Creature.knowledge_entity_id.in_(entity_ids), Creature.is_hidden.is_(False),
        ).all()
        rows.extend(("boss" if row.is_boss else "creature", row) for row in creatures if ("boss" if row.is_boss else "creature") in creature_layers)
    return rows


def _payload(layer: str, row: Any, values: list[dict[str, Any]], image_url: str | None) -> dict[str, Any]:
    values = sorted(values, key=lambda value: (
        value["z"], value["x"], value["y"], value.get("relationship") or "",
        value.get("label") or "",
    ))
    first = values[0]
    if layer in {"creature", "boss"}:
        subtitle, navigation = row.classification, f"/creatures/{row.slug or row.id}"
        preview = {"classification": row.classification, "difficulty": row.difficulty, "is_boss": bool(row.is_boss)}
    elif layer == "npc":
        subtitle, navigation = row.location_name or row.occupation, f"/npcs/{row.knowledge_entity_id}"
        preview = {"location": row.location_name, "occupation": row.occupation}
    elif layer == "quest":
        subtitle, navigation = row.location, f"/quests/{row.slug or row.id}"
        preview = {"location": row.location, "minimum_level": row.min_level, "difficulty": row.difficulty}
    elif layer == "location":
        subtitle, navigation = row.region, f"/locations/{row.slug or row.id}"
        preview = {"location_kind": row.location_kind, "region": row.region, "parent_location": row.parent_location}
    else:
        subtitle, navigation = row.region or row.city, f"/hunt-zones/{row.slug or row.id}"
        preview = {"city": row.city, "region": row.region, "requires_quest": row.requires_quest}
    return {
        "id": f"{layer}:{row.knowledge_entity_id}", "canonical_entity_id": row.knowledge_entity_id,
        "entity_type": layer, "entity_id": row.id, "name": row.name, "slug": row.slug,
        "to": navigation, "navigation_url": navigation, "subtitle": subtitle,
        "image_url": image_url, "preview": preview,
        "x": first["x"], "y": first["y"], "z": first["z"], "bounds": first.get("bounds"),
        "geometry_status": "mapped", "spatial_state": first["spatial_state"],
        "geometry_source": first["geometry_source"], "spatial_evidence": values,
        "location_labels": list(dict.fromkeys(value["label"] for value in values if value.get("label"))),
    }


def _decode_cursor(cursor: str | None) -> str | None:
    if cursor is None:
        return None
    try:
        decoded = base64.urlsafe_b64decode(cursor.encode("ascii") + b"=" * (-len(cursor) % 4)).decode("utf-8")
    except (ValueError, UnicodeError) as exc:
        raise ValueError("invalid_map_cursor") from exc
    match = CURSOR_PATTERN.fullmatch(decoded)
    if match is None:
        raise ValueError("invalid_map_cursor")
    try:
        UUID(match.group(1))
    except ValueError as exc:
        raise ValueError("invalid_map_cursor") from exc
    return decoded


def _encode_cursor(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii").rstrip("=")


def viewport_payload(
    db: Session, *, min_x: int, min_y: int, max_x: int, max_y: int, floor: int,
    layers: tuple[str, ...], zoom: float, cursor: str | None, limit: int,
) -> dict[str, Any]:
    after = _decode_cursor(cursor)
    found = _bounded_direct_evidence(
        db, min_x=min_x, min_y=min_y, max_x=max_x, max_y=max_y, floor=floor,
    )
    _expand_relationships(db, found)
    _expand_zone_spawns(db, found)
    rows = _domain_rows(db, set(found), layers)
    by_layer: dict[str, list[tuple[str, Any]]] = defaultdict(list)
    for layer, row in rows:
        by_layer[layer].append((layer, row))
    for group in by_layer.values():
        group.sort(key=lambda value: str(value[1].knowledge_entity_id))
    # Neutral, deterministic rounds give each populated layer a turn before
    # density truncation. Empty/exhausted layers do not consume page slots.
    rows = [
        value
        for round_rows in zip_longest(*(by_layer[layer] for layer in sorted(by_layer)))
        for value in round_rows if value is not None
    ]
    if after is not None:
        for index, (layer, row) in enumerate(rows):
            if f"{layer}:{row.knowledge_entity_id}" == after:
                rows = rows[index + 1:]
                break
        else:
            raise ValueError("invalid_map_cursor")
    page_limit = density_limit(zoom, limit)
    page_rows = rows[:page_limit]
    has_more = len(rows) > page_limit
    media = _media_urls(db, [row for _layer, row in page_rows])
    page = [
        _payload(layer, row, found[row.knowledge_entity_id], media.get((type(row), row.id)))
        for layer, row in page_rows
    ]
    return {
        "floor": floor,
        "bbox": {"min_x": min_x, "min_y": min_y, "max_x": max_x, "max_y": max_y},
        "layers": list(layers), "zoom": zoom, "items": page,
        "page": {"limit": page_limit, "has_more": has_more, "next_cursor": _encode_cursor(page[-1]["id"]) if has_more and page else None},
    }
