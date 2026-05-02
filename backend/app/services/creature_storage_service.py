"""Persist and query locally cached creature details without losing local metadata."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable, Optional

from sqlalchemy.orm import Session, selectinload
from sqlalchemy import or_

from app.models import Creature, HuntZone, Loot, SpawnLocation
from app.services.entity_metadata_service import EntityMetadataService
from app.services.text_utils import normalize_search_text, slugify


def _merge_list(existing: Optional[list[Any]], incoming: Optional[Iterable[Any]]) -> list[Any]:
    values: list[Any] = []
    seen: set[str] = set()
    for source in [existing or [], list(incoming or [])]:
        for item in source:
            key = normalize_search_text(str(item))
            if not key or key in seen:
                continue
            seen.add(key)
            values.append(item)
    return values


def _copy_if_present(target: Creature, payload: dict[str, Any], field: str) -> None:
    value = payload.get(field)
    if value not in (None, "", []):
        setattr(target, field, value)


def _ensure_hunt_zone(db: Session, location_name: str) -> HuntZone:
    normalized_name = normalize_search_text(location_name)
    zone = db.query(HuntZone).filter(HuntZone.normalized_name == normalized_name).first()
    if not zone:
        zone = HuntZone(
            name=location_name,
            normalized_name=normalized_name,
            min_level=0,
            source_name="tibiawiki",
            source_url=None,
            description=None,
            last_synced_at=datetime.utcnow(),
        )
        db.add(zone)
        db.flush()
    elif not zone.name:
        zone.name = location_name
    return zone


def upsert_creature_payload(db: Session, payload: dict[str, Any]) -> Creature:
    normalized_name = normalize_search_text(payload.get("name"))
    creature = db.query(Creature).filter(Creature.normalized_name == normalized_name).first()
    if not creature and payload.get("id") is not None:
        creature = db.query(Creature).filter(Creature.id == payload["id"]).first()

    if not creature:
        creature = Creature(
            id=payload.get("id"),
            name=payload.get("name"),
            hitpoints=payload.get("hitpoints") or 0,
            experience=payload.get("experience") or 0,
        )
        db.add(creature)
        db.flush()

    creature.name = payload.get("name") or creature.name
    creature.normalized_name = normalized_name
    creature.slug = payload.get("slug") or slugify(creature.name)
    creature.external_id = str(payload.get("id")) if payload.get("id") is not None else creature.external_id
    creature.source_name = payload.get("source_name") or creature.source_name or "tibiawiki"
    creature.source_url = payload.get("source_url") or creature.source_url

    for field in [
        "article",
        "plural",
        "hitpoints",
        "experience",
        "armor",
        "speed",
        "max_damage",
        "summon_cost",
        "convince_cost",
        "difficulty",
        "occurrence",
        "is_boss",
        "loot_value",
        "description",
        "behavior",
        "image_url",
        "bestiary_class",
        "bestiary_level",
        "charm_points",
        "classification",
        "creature_class",
        "primary_type",
    ]:
        _copy_if_present(creature, payload, field)

    creature.data_sources = _merge_list(creature.data_sources, payload.get("data_sources"))
    creature.missing_fields = list(payload.get("missing_fields") or [])
    creature.related_tasks = _merge_list(creature.related_tasks, payload.get("related_tasks"))
    creature.locations = _merge_list(creature.locations, payload.get("locations"))
    creature.raw_data = payload
    creature.last_synced_at = datetime.utcnow()

    existing_loot = {loot.normalized_name: loot for loot in creature.loot_items}
    for loot_payload in payload.get("loot_items") or []:
        normalized_loot_name = normalize_search_text(loot_payload.get("item_name"))
        if not normalized_loot_name:
            continue
        loot = existing_loot.get(normalized_loot_name)
        if not loot:
            loot = Loot(creature_id=creature.id, item_name=loot_payload.get("item_name"))
            db.add(loot)
            creature.loot_items.append(loot)
        loot.item_name = loot_payload.get("item_name") or loot.item_name
        loot.normalized_name = normalized_loot_name
        loot.external_id = str(loot_payload.get("id")) if loot_payload.get("id") is not None else loot.external_id
        loot.rarity = loot_payload.get("rarity") or loot.rarity
        loot.percentage = loot_payload.get("percentage") if loot_payload.get("percentage") is not None else loot.percentage
        loot.min_amount = loot_payload.get("min_amount") or loot.min_amount or 1
        loot.max_amount = loot_payload.get("max_amount") or loot.max_amount or 1
        loot.item_value = loot_payload.get("item_value") if loot_payload.get("item_value") is not None else loot.item_value
        loot.item_type = loot_payload.get("item_type") or loot.item_type
        loot.item_image_url = loot_payload.get("item_image_url") or loot.item_image_url
        loot.source_url = loot_payload.get("source_url") or loot.source_url
        loot.raw_data = loot_payload

    existing_spawn_links = {spawn.hunt_zone.normalized_name: spawn for spawn in creature.spawn_locations if spawn.hunt_zone}
    for location in creature.locations or []:
        zone = _ensure_hunt_zone(db, location)
        if zone.normalized_name in existing_spawn_links:
            continue
        db.add(SpawnLocation(creature_id=creature.id, hunt_zone_id=zone.id, quantity="Unknown"))

    EntityMetadataService.update_sync_timestamp(
        db,
        entity_type="creature",
        entity_key=creature.normalized_name,
        display_name=creature.name,
        entity_id=creature.id,
    )
    db.flush()
    return creature


def get_cached_creature_by_id(db: Session, creature_id: int) -> Optional[Creature]:
    return (
        db.query(Creature)
        .options(
            selectinload(Creature.loot_items),
            selectinload(Creature.spawn_locations).selectinload(SpawnLocation.hunt_zone),
        )
        .filter(Creature.id == creature_id)
        .first()
    )


def get_cached_creature_by_name(db: Session, creature_name: str) -> Optional[Creature]:
    normalized_name = normalize_search_text(creature_name)
    return (
        db.query(Creature)
        .options(
            selectinload(Creature.loot_items),
            selectinload(Creature.spawn_locations).selectinload(SpawnLocation.hunt_zone),
        )
        .filter(Creature.normalized_name == normalized_name)
        .first()
    )


def get_cached_creature_by_slug(db: Session, creature_slug: str) -> Optional[Creature]:
    normalized_slug = (creature_slug or "").strip().lower()
    return (
        db.query(Creature)
        .options(
            selectinload(Creature.loot_items),
            selectinload(Creature.spawn_locations).selectinload(SpawnLocation.hunt_zone),
        )
        .filter(Creature.slug == normalized_slug)
        .first()
    )


def resolve_cached_creature(db: Session, identifier: str) -> Optional[Creature]:
    raw = (identifier or "").strip()
    if not raw:
        return None

    if raw.isdigit():
        creature = get_cached_creature_by_id(db, int(raw))
        if creature:
            return creature

    slug_candidate = raw.replace(" ", "-").replace("_", "-").strip().lower()
    slug_variants = {
        slug_candidate,
        slug_candidate.replace("-", "_"),
        raw.strip().lower(),
    }

    creature = (
        db.query(Creature)
        .options(
            selectinload(Creature.loot_items),
            selectinload(Creature.spawn_locations).selectinload(SpawnLocation.hunt_zone),
        )
        .filter(or_(*[Creature.slug == variant for variant in slug_variants if variant]))
        .first()
    )
    if creature:
        return creature

    normalized_name = normalize_search_text(raw.replace("-", " ").replace("_", " "))
    creature = (
        db.query(Creature)
        .options(
            selectinload(Creature.loot_items),
            selectinload(Creature.spawn_locations).selectinload(SpawnLocation.hunt_zone),
        )
        .filter(Creature.normalized_name == normalized_name)
        .first()
    )
    if creature:
        return creature

    return (
        db.query(Creature)
        .options(
            selectinload(Creature.loot_items),
            selectinload(Creature.spawn_locations).selectinload(SpawnLocation.hunt_zone),
        )
        .filter(Creature.name.ilike(raw))
        .first()
    )


def list_cached_creatures(
    db: Session,
    *,
    search: Optional[str],
    category: Optional[str],
    skip: int,
    limit: int,
    sort_by: str,
    sort_order: str,
) -> list[Creature]:
    query = db.query(Creature)
    if search:
        normalized = normalize_search_text(search)
        query = query.filter(Creature.normalized_name.contains(normalized))
    if category:
        query = query.filter(Creature.classification.ilike(category))

    sort_column = {
        "experience": Creature.experience,
        "hitpoints": Creature.hitpoints,
        "difficulty": Creature.difficulty,
    }.get(sort_by, Creature.name)
    query = query.order_by(sort_column.desc() if sort_order == "desc" else sort_column.asc(), Creature.name.asc())
    return query.offset(skip).limit(limit).all()