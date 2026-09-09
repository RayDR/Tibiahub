from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256

from sqlalchemy import case, or_
from sqlalchemy.orm import Session

from app.models.creature import Creature
from app.models.entity_metadata import EntityMetadata
from app.models.external_data import Item as ExternalItem, TibiaWikiNpc
from app.models.hunt_zone import HuntZone
from app.models.media_asset import MediaAsset
from app.services import media_asset_service

POOL_SIZE = 15
_QUERY_LIMIT = 240
_QUEST_VISUAL_TERMS = (
    "book",
    "scroll",
    "tome",
    "parchment",
    "letter",
    "document",
    "journal",
    "diary",
    "map",
    "note",
    "tablet",
    "rune",
)


def _day_key(now: datetime | None = None) -> str:
    current = now or datetime.now(UTC)
    return current.astimezone(UTC).date().isoformat()


def _daily_pick(values: list, category: str, day_key: str):
    if not values:
        return None
    digest = sha256(f"tibiahub:{day_key}:{category}".encode("utf-8")).digest()
    index = int.from_bytes(digest[:8], "big") % len(values)
    return values[index]


def _existing(asset: MediaAsset | None) -> bool:
    return bool(asset and asset.status == "cached" and asset.file_exists())


def _gif_first(asset: MediaAsset) -> int:
    return 0 if "gif" in (asset.content_type or "").lower() else 1


def _creature_pool(db: Session, *, bosses: bool) -> list[str]:
    gif_first = case((MediaAsset.content_type.ilike("%gif%"), 0), else_=1)
    rows = (
        db.query(Creature, MediaAsset)
        .join(MediaAsset, Creature.image_asset_id == MediaAsset.id)
        .filter(
            Creature.is_hidden.is_(False),
            Creature.is_boss.is_(bosses),
            MediaAsset.status == "cached",
        )
        .order_by(gif_first, Creature.id.asc())
        .limit(_QUERY_LIMIT)
        .all()
    )
    available = [(row, asset) for row, asset in rows if _existing(asset)]
    available.sort(key=lambda pair: (_gif_first(pair[1]), pair[0].id))
    return [
        f"/api/v1/creatures/{row.id}/image?placeholder=false"
        for row, _asset in available[:POOL_SIZE]
    ]


def _popular_item_ids(db: Session) -> list[int]:
    return [
        row.entity_id
        for row in (
            db.query(EntityMetadata)
            .filter(
                EntityMetadata.entity_type == "item",
                EntityMetadata.entity_id.isnot(None),
            )
            .order_by(
                EntityMetadata.search_count.desc(),
                EntityMetadata.last_viewed_at.desc(),
            )
            .limit(80)
            .all()
        )
        if row.entity_id is not None
    ]


def _item_rows(db: Session, *, quest_like: bool) -> list[ExternalItem]:
    base = db.query(ExternalItem).filter(ExternalItem.knowledge_entity_id.isnot(None))
    if quest_like:
        terms = [ExternalItem.normalized_name.contains(term) for term in _QUEST_VISUAL_TERMS]
        return base.filter(or_(*terms)).order_by(ExternalItem.id.asc()).limit(_QUERY_LIMIT).all()

    popular_ids = _popular_item_ids(db)
    popular = db.query(ExternalItem).filter(ExternalItem.id.in_(popular_ids)).all() if popular_ids else []
    popular_by_id = {row.id: row for row in popular}
    ordered_popular = [popular_by_id[row_id] for row_id in popular_ids if row_id in popular_by_id]
    fallback = base.order_by(ExternalItem.id.asc()).limit(_QUERY_LIMIT).all()
    seen: set[int] = set()
    result: list[ExternalItem] = []
    for row in [*ordered_popular, *fallback]:
        if row.id in seen:
            continue
        seen.add(row.id)
        result.append(row)
    return result


def _item_pool(db: Session, *, quest_like: bool) -> list[str]:
    rows = _item_rows(db, quest_like=quest_like)
    if not rows:
        return []

    keys_by_id: dict[int, tuple[str | None, str | None]] = {}
    for row in rows:
        keys_by_id[row.id] = (
            media_asset_service.build_canonical_item_asset_key(row.knowledge_entity_id),
            media_asset_service.build_legacy_item_asset_key(row.name),
        )

    asset_keys = {key for keys in keys_by_id.values() for key in keys if key}
    linked_ids = {row.image_asset_id for row in rows if row.image_asset_id is not None}
    assets = (
        db.query(MediaAsset)
        .filter(
            or_(
                MediaAsset.asset_key.in_(asset_keys),
                MediaAsset.id.in_(linked_ids),
            ),
            MediaAsset.status == "cached",
        )
        .all()
        if asset_keys or linked_ids
        else []
    )
    by_key = {asset.asset_key: asset for asset in assets}
    by_id = {asset.id: asset for asset in assets}

    resolved: list[tuple[ExternalItem, MediaAsset]] = []
    for row in rows:
        asset = by_id.get(row.image_asset_id) if row.image_asset_id is not None else None
        if not _existing(asset):
            canonical_key, legacy_key = keys_by_id[row.id]
            asset = by_key.get(canonical_key) or (by_key.get(legacy_key) if legacy_key else None)
        if _existing(asset):
            resolved.append((row, asset))

    if quest_like:
        term_priority = {term: index for index, term in enumerate(_QUEST_VISUAL_TERMS)}

        def quest_rank(pair: tuple[ExternalItem, MediaAsset]):
            row, asset = pair
            name = row.normalized_name or row.name.lower()
            semantic_rank = min(
                (priority for term, priority in term_priority.items() if term in name),
                default=len(term_priority),
            )
            return (_gif_first(asset), semantic_rank, row.id)

        resolved.sort(key=quest_rank)
    else:
        popularity = {row_id: index for index, row_id in enumerate(_popular_item_ids(db))}
        resolved.sort(
            key=lambda pair: (
                _gif_first(pair[1]),
                popularity.get(pair[0].id, len(popularity) + pair[0].id),
            )
        )

    return [
        f"/api/v1/items/{row.id}/image"
        for row, _asset in resolved[:POOL_SIZE]
    ]


def _npc_pool(db: Session) -> list[str]:
    rows = db.query(TibiaWikiNpc).order_by(TibiaWikiNpc.id.asc()).limit(_QUERY_LIMIT).all()
    if not rows:
        return []

    keys_by_id = {
        row.id: (
            media_asset_service.build_canonical_npc_asset_key(row.knowledge_entity_id),
            media_asset_service.build_legacy_npc_asset_key(row),
        )
        for row in rows
    }
    keys = {key for values in keys_by_id.values() for key in values if key}
    assets = db.query(MediaAsset).filter(
        MediaAsset.asset_key.in_(keys),
        MediaAsset.status == "cached",
    ).all() if keys else []
    by_key = {asset.asset_key: asset for asset in assets}

    resolved: list[tuple[TibiaWikiNpc, MediaAsset]] = []
    for row in rows:
        asset = next((by_key.get(key) for key in keys_by_id[row.id] if _existing(by_key.get(key))), None)
        if asset is not None:
            resolved.append((row, asset))
    resolved.sort(key=lambda pair: (_gif_first(pair[1]), pair[0].id))
    return [
        f"/api/v1/npcs/{row.knowledge_entity_id}/image"
        for row, _asset in resolved[:POOL_SIZE]
    ]


def _zone_pool(db: Session) -> list[str]:
    gif_first = case((MediaAsset.content_type.ilike("%gif%"), 0), else_=1)
    rows = (
        db.query(HuntZone, MediaAsset)
        .join(MediaAsset, HuntZone.map_asset_id == MediaAsset.id)
        .filter(MediaAsset.status == "cached")
        .order_by(gif_first, HuntZone.id.asc())
        .limit(_QUERY_LIMIT)
        .all()
    )
    available = [(row, asset) for row, asset in rows if _existing(asset)]
    return [
        f"/api/v1/hunt-zones/{row.id}/map-image"
        for row, _asset in available[:POOL_SIZE]
    ]


def daily_category_visuals(db: Session, *, now: datetime | None = None) -> dict[str, str | None]:
    day_key = _day_key(now)
    pools = {
        "creatures": _creature_pool(db, bosses=False),
        "bosses": _creature_pool(db, bosses=True),
        "items": _item_pool(db, quest_like=False),
        "quests": _item_pool(db, quest_like=True),
        "zones": _zone_pool(db),
        "npcs": _npc_pool(db),
    }
    return {
        "visual_day": day_key,
        **{
            category: _daily_pick(values, category, day_key)
            for category, values in pools.items()
        },
    }
