"""Read-only canonical projections for the public NPC directory.

The provider bridge remains the source of NPC facts.  This projector only
adds exact Knowledge identities and trusted Phase 3D spatial evidence; it
never creates entities, aliases, relationships, or coordinates.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable
from uuid import UUID

from sqlalchemy.orm import Session

from app.knowledge.indexing import normalize_name
from app.knowledge.models import (
    KnowledgeEntity, KnowledgeEntityAlias, KnowledgeRelationship, KnowledgeSearchMetadata,
)
from app.models.external_data import Item, TibiaWikiLocation, TibiaWikiNpc, TibiaWikiQuest
from app.models.media_asset import MediaAsset
from app.services.media_asset_service import build_npc_asset_key


REFERENCE_TYPES = {
    "item": ("item",),
    "quest": ("quest",),
    "place": ("location", "area", "town"),
}
REFERENCE_PLACEHOLDERS = {"-", "--", "n/a", "none", "unknown"}


def _valid_reference(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and bool(str(value.get("name") or "").strip())
        and str(value.get("name") or "").strip().casefold() not in REFERENCE_PLACEHOLDERS
    )


def _known_count(row: TibiaWikiNpc, field: str) -> int | None:
    if field not in set(row.supplied_fields or []):
        return None
    value = getattr(row, field, None)
    if isinstance(value, list) and value and not any(_valid_reference(item) for item in value):
        return None
    return sum(_valid_reference(item) for item in value) if isinstance(value, list) else 0


def _coverage(row: TibiaWikiNpc, field: str) -> str:
    count = _known_count(row, field)
    if count is None:
        return "unknown"
    return "available" if count else "known_empty"


def _media(row: TibiaWikiNpc, assets: dict[str, MediaAsset]) -> dict[str, Any]:
    key = build_npc_asset_key(row)
    asset = assets.get(key)
    cached = bool(asset and asset.status == "cached" and asset.file_exists())
    return {
        "status": "cached" if cached else "reference_only" if row.image_url else "missing",
        "url": f"/api/v1/npcs/{row.id}/image" if cached else None,
        "source_provider": row.source_name if row.image_url else None,
        "source_url": row.image_url,
    }


def _media_assets(db: Session, rows: Iterable[TibiaWikiNpc]) -> dict[str, MediaAsset]:
    keys = {build_npc_asset_key(row) for row in rows}
    if not keys:
        return {}
    return {
        asset.asset_key: asset
        for asset in db.query(MediaAsset).filter(MediaAsset.asset_key.in_(keys)).all()
    }


def _trade_by_npc(
    db: Session,
    entity_ids: set[UUID],
) -> dict[UUID, dict[str, list[dict[str, Any]]]]:
    result: dict[UUID, dict[str, list[dict[str, Any]]]] = defaultdict(
        lambda: {"buys": [], "sells": []}
    )
    if not entity_ids:
        return result
    relationships = db.query(KnowledgeRelationship).filter(
        KnowledgeRelationship.target_entity_id.in_(entity_ids),
        KnowledgeRelationship.relationship_type_code.in_(("sold_by_npc", "bought_by_npc")),
        KnowledgeRelationship.resolution_state == "resolved",
        KnowledgeRelationship.is_current.is_(True),
    ).all()
    item_ids = {relationship.source_entity_id for relationship in relationships}
    bridges = {
        item.knowledge_entity_id: item
        for item in db.query(Item).filter(Item.knowledge_entity_id.in_(item_ids)).all()
    } if item_ids else {}
    for relationship in relationships:
        item = bridges.get(relationship.source_entity_id)
        if item is None or relationship.target_entity_id is None:
            continue
        context = relationship.source_context or {}
        field = "sells" if relationship.relationship_type_code == "sold_by_npc" else "buys"
        semantic = "npc_sells_to_player" if field == "sells" else "npc_buys_from_player"
        result[relationship.target_entity_id][field].append({
            "name": item.name,
            "price": context.get("price"),
            "currency": context.get("currency"),
            "offers": list(context.get("offers") or []),
            "semantic": semantic,
            "canonical_id": item.knowledge_entity_id,
            "entity_type": "item",
            "slug": item.slug,
            "resolution_state": "resolved",
            "navigation_url": f"/items/{item.slug or item.id}",
        })
    for groups in result.values():
        for values in groups.values():
            values.sort(key=lambda value: (value["name"].casefold(), value.get("price") or -1))
    return result


def spatial_by_npc(db: Session, entity_ids: set[UUID]) -> dict[UUID, dict[str, Any]]:
    """Reuse the map's exact, provenance-aware spatial projection in one batch."""
    if not entity_ids:
        return {}
    # Imported lazily to keep the shared projection service independent from
    # API router import order.
    from app.api.v1.tibia_map import (
        _geometry,
        _spatial_evidence_by_entity,
        _unresolved_spatial_entity_ids,
    )

    evidence = _spatial_evidence_by_entity(db, entity_ids)
    unresolved = _unresolved_spatial_entity_ids(db, entity_ids)
    return {
        entity_id: _geometry(entity_id, evidence, unresolved)
        for entity_id in entity_ids
    }


def directory_rows(db: Session, rows: Iterable[TibiaWikiNpc]) -> dict[UUID, dict[str, Any]]:
    values = list(rows)
    spatial = spatial_by_npc(db, {row.knowledge_entity_id for row in values})
    assets = _media_assets(db, values)
    trade = _trade_by_npc(db, {row.knowledge_entity_id for row in values})
    result: dict[UUID, dict[str, Any]] = {}
    for row in values:
        geometry = spatial.get(row.knowledge_entity_id, {})
        result[row.knowledge_entity_id] = {
            "id": row.id,
            "canonical_id": row.knowledge_entity_id,
            "knowledge_entity_id": row.knowledge_entity_id,
            "name": row.name,
            "slug": row.slug,
            "title": row.title,
            "occupation": row.occupation,
            "location_name": row.location_name or (row.provider_metadata or {}).get("location_text"),
            "buys_count": len(trade[row.knowledge_entity_id]["buys"]) or _known_count(row, "buys"),
            "sells_count": len(trade[row.knowledge_entity_id]["sells"]) or _known_count(row, "sells"),
            "quest_count": _known_count(row, "related_quests"),
            "destination_count": _known_count(row, "destinations"),
            "media": _media(row, assets),
            "geometry_status": geometry.get("geometry_status", "knowledge_only"),
            "spatial_state": geometry.get("spatial_state", "knowledge_only"),
            "map_available": geometry.get("geometry_status") == "mapped",
            "last_synced_at": row.last_synced_at,
        }
    return result


def aliases_for(db: Session, entity_id: UUID) -> list[str]:
    return [
        row.alias
        for row in db.query(KnowledgeEntityAlias)
        .filter(KnowledgeEntityAlias.entity_uuid == entity_id)
        .order_by(KnowledgeEntityAlias.normalized_alias, KnowledgeEntityAlias.uuid)
        .all()
    ]


def _candidate_entities(
    db: Session,
    names: Iterable[str],
    entity_types: tuple[str, ...],
) -> dict[str, dict[UUID, KnowledgeEntity]]:
    normalized_names = {normalize_name(name) for name in names if normalize_name(name)}
    candidates: dict[str, dict[UUID, KnowledgeEntity]] = defaultdict(dict)
    if not normalized_names:
        return candidates

    canonical = (
        db.query(KnowledgeEntity, KnowledgeSearchMetadata.normalized_name)
        .join(KnowledgeSearchMetadata, KnowledgeSearchMetadata.entity_uuid == KnowledgeEntity.uuid)
        .filter(
            KnowledgeEntity.entity_type.in_(entity_types),
            KnowledgeEntity.status == "active",
            KnowledgeEntity.visibility == "public",
            KnowledgeSearchMetadata.normalized_name.in_(normalized_names),
        )
        .all()
    )
    for entity, normalized in canonical:
        candidates[normalized][entity.uuid] = entity

    aliases = (
        db.query(KnowledgeEntity, KnowledgeEntityAlias.normalized_alias)
        .join(KnowledgeEntityAlias, KnowledgeEntityAlias.entity_uuid == KnowledgeEntity.uuid)
        .filter(
            KnowledgeEntity.entity_type.in_(entity_types),
            KnowledgeEntity.status == "active",
            KnowledgeEntity.visibility == "public",
            KnowledgeEntityAlias.entity_type.in_(entity_types),
            KnowledgeEntityAlias.normalized_alias.in_(normalized_names),
        )
        .all()
    )
    for entity, normalized in aliases:
        candidates[normalized][entity.uuid] = entity
    return candidates


def _bridges(db: Session, entity_ids: set[UUID]) -> dict[UUID, tuple[str, int, str | None]]:
    result: dict[UUID, tuple[str, int, str | None]] = {}
    if not entity_ids:
        return result
    for model, entity_type in ((Item, "item"), (TibiaWikiQuest, "quest"), (TibiaWikiLocation, "location")):
        for row in db.query(model).filter(model.knowledge_entity_id.in_(entity_ids)).all():
            result[row.knowledge_entity_id] = (entity_type, row.id, row.slug)
    return result


def resolve_named_references(
    db: Session,
    values: Iterable[dict[str, Any]],
    reference_kind: str,
    *,
    semantic: str,
) -> list[dict[str, Any]]:
    """Resolve a bounded reference list by exact canonical name or verified alias."""
    source_values = [value for value in values if _valid_reference(value)]
    entity_types = REFERENCE_TYPES[reference_kind]
    candidates = _candidate_entities(db, (str(value["name"]) for value in source_values), entity_types)
    all_ids = {entity_id for matches in candidates.values() for entity_id in matches}
    bridges = _bridges(db, all_ids)
    result: list[dict[str, Any]] = []
    for value in source_values:
        name = str(value["name"]).strip()
        matches = list(candidates.get(normalize_name(name), {}).values())
        entity = matches[0] if len(matches) == 1 else None
        bridge = bridges.get(entity.uuid) if entity else None
        navigation_url = None
        if entity and bridge:
            route_type, bridge_id, slug = bridge
            prefix = {"item": "items", "quest": "quests", "location": "locations"}[route_type]
            navigation_url = f"/{prefix}/{slug or bridge_id}"
        result.append({
            **value,
            "name": name,
            "semantic": semantic,
            "canonical_id": entity.uuid if entity else None,
            "entity_type": entity.entity_type if entity else entity_types[0],
            "slug": bridge[2] if bridge else (entity.slug if entity else None),
            "resolution_state": "resolved" if entity else "ambiguous" if len(matches) > 1 else "unresolved",
            "navigation_url": navigation_url,
        })
    return result


def detail_references(db: Session, row: TibiaWikiNpc) -> dict[str, Any]:
    assets = _media_assets(db, [row])
    trade = _trade_by_npc(db, {row.knowledge_entity_id})[row.knowledge_entity_id]
    bridge_buys = resolve_named_references(
        db, row.buys or [], "item", semantic="npc_buys_from_player",
    )
    bridge_sells = resolve_named_references(
        db, row.sells or [], "item", semantic="npc_sells_to_player",
    )

    def merge(canonical: list[dict[str, Any]], bridge: list[dict[str, Any]]) -> list[dict[str, Any]]:
        output = list(canonical)
        seen = {normalize_name(value["name"]) for value in output}
        output.extend(value for value in bridge if normalize_name(value["name"]) not in seen)
        return output

    field_coverage = {
        field: _coverage(row, field)
        for field in ("buys", "sells", "destinations", "related_quests")
    }
    if trade["buys"]:
        field_coverage["buys"] = "available"
    if trade["sells"]:
        field_coverage["sells"] = "available"
    return {
        "aliases": aliases_for(db, row.knowledge_entity_id),
        "field_coverage": field_coverage,
        "buys": merge(trade["buys"], bridge_buys),
        "sells": merge(trade["sells"], bridge_sells),
        "destinations": resolve_named_references(
            db, row.destinations or [], "place", semantic="travel_destination",
        ),
        "related_quests": resolve_named_references(
            db, row.related_quests or [], "quest", semantic="related",
        ),
        "media": _media(row, assets),
        "spatial": spatial_by_npc(db, {row.knowledge_entity_id}).get(row.knowledge_entity_id),
    }
