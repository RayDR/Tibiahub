"""Items/Loot API endpoints."""
import hashlib
from difflib import SequenceMatcher
from typing import List

from fastapi import APIRouter, Depends, Query
from fastapi import HTTPException, Request, Response
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.db.database import get_db
from app.models.creature import Creature
from app.models import Loot as LootModel
from app.models.external_data import Item as ExternalItemModel
from app.models.spawn_location import SpawnLocation
from app.schemas import ItemDetail, ItemDropCreature, ItemSearchResult
from app.services.entity_metadata_service import EntityMetadataService
from app.services import media_asset_service as media_svc
from app.services.text_utils import normalize_search_text
from app.knowledge.services import KnowledgeGraphService

router = APIRouter(prefix="/items", tags=["items"])


def _is_image_autofetch_enabled(db: Session) -> bool:
    from app.models.settings import SystemSettings as SettingsModel

    def _get_setting(key: str, default: str = "") -> str:
        value = db.query(SettingsModel).filter(SettingsModel.key == key).first()
        return value.value if value and value.value is not None else default

    return _get_setting("auto_fetch_missing_images_enabled", "0") == "1"


def _placeholder_svg(label: str) -> bytes:
    safe = media_svc.escape_svg_text(label or "Unknown Item", limit=42)
    return (
        "<svg xmlns='http://www.w3.org/2000/svg' width='320' height='320' viewBox='0 0 320 320'>"
        "<defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'>"
        "<stop offset='0%' stop-color='#111827'/><stop offset='100%' stop-color='#1f2937'/></linearGradient></defs>"
        "<rect width='320' height='320' fill='url(#g)'/>"
        "<rect x='108' y='86' width='104' height='104' rx='12' fill='#374151'/><rect x='84' y='208' width='152' height='16' rx='8' fill='#4b5563'/>"
        f"<text x='160' y='278' text-anchor='middle' fill='#d1d5db' font-size='14' font-family='Arial, sans-serif'>{safe}</text>"
        "</svg>"
    ).encode("utf-8")


@router.get("/{item_id}/image")
async def get_item_image(item_id: int, request: Request, db: Session = Depends(get_db)):
    """Serve loot/item image from local MediaAsset cache (local-first)."""
    item = (
        db.query(ExternalItemModel)
        .filter(
            ExternalItemModel.id == item_id,
            ExternalItemModel.knowledge_entity_id.isnot(None),
        )
        .first()
    )
    loot = None if item else db.query(LootModel).filter(LootModel.id == item_id).first()
    if not item and not loot:
        loot = db.query(LootModel).filter(LootModel.external_id == str(item_id)).first()
    if not item and not loot:
        raise HTTPException(status_code=404, detail="Item not found")

    label = item.name if item else loot.item_name
    asset_key = (
        f"item:knowledge:{item.knowledge_entity_id}"
        if item
        else media_svc.build_loot_asset_key(loot)
    )
    source_url = item.image_url if item else media_svc.build_loot_source_url(loot)
    if not source_url:
        placeholder = _placeholder_svg(label)
        return Response(
            content=placeholder,
            media_type="image/svg+xml",
            headers={
                "Cache-Control": "public, max-age=3600",
                "X-Image-Source": "placeholder",
                "X-Asset-Key": asset_key,
            },
        )

    autofetch = _is_image_autofetch_enabled(db)
    asset = await media_svc.get_or_fetch_asset(
        db,
        asset_key=asset_key,
        source_url=source_url,
        autofetch_enabled=autofetch,
    )

    if not asset or asset.status != "cached":
        placeholder = _placeholder_svg(label)
        return Response(
            content=placeholder,
            media_type="image/svg+xml",
            headers={
                "Cache-Control": "public, max-age=3600",
                "X-Image-Source": "placeholder",
                "X-Image-Status": getattr(asset, "status", "missing") if asset else "missing",
                "X-Asset-Key": asset_key,
            },
        )

    content = asset.read_bytes()
    if not content:
        placeholder = _placeholder_svg(label)
        return Response(
            content=placeholder,
            media_type="image/svg+xml",
            headers={
                "Cache-Control": "public, max-age=3600",
                "X-Image-Source": "placeholder",
                "X-Image-Status": "missing",
                "X-Asset-Key": asset_key,
            },
        )

    etag = asset.sha256_hash[:20] if asset.sha256_hash else hashlib.sha1(content).hexdigest()
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={
            "ETag": etag,
            "Cache-Control": f"public, max-age={settings.IMAGE_CACHE_MAX_AGE_SECONDS}",
        })

    media_type = asset.content_type or "image/gif"
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Type": media_type,
            "Content-Length": str(len(content)),
            "Cache-Control": f"public, max-age={settings.IMAGE_CACHE_MAX_AGE_SECONDS}",
            "ETag": etag,
            "X-Image-Source": "local-media-asset",
            "X-Asset-Key": asset_key,
        },
    )


def _rank_item(query: str, item_name: str) -> tuple[int, float, str]:
    normalized_query = normalize_search_text(query)
    normalized_name = normalize_search_text(item_name)
    if normalized_name == normalized_query:
        return (0, -1.0, normalized_name)
    if normalized_name.startswith(normalized_query):
        return (1, -1.0, normalized_name)
    if normalized_query in normalized_name:
        return (2, -1.0, normalized_name)
    return (3, -SequenceMatcher(a=normalized_query, b=normalized_name).ratio(), normalized_name)


def _hunt_zones(creature: Creature | None) -> list[dict]:
    if creature is None:
        return []
    return [
        {
            "id": spawn.hunt_zone.id,
            "name": spawn.hunt_zone.name,
            "city": spawn.hunt_zone.city,
            "min_level": None if spawn.hunt_zone.min_level == 0 else spawn.hunt_zone.min_level,
            "max_level": spawn.hunt_zone.max_level,
            "difficulty": spawn.hunt_zone.difficulty,
            "source_url": getattr(spawn.hunt_zone, "source_url", None),
        }
        for spawn in creature.spawn_locations or []
        if spawn.hunt_zone
    ]


def _canonical_item_drops(db: Session, item: ExternalItemModel) -> list[ItemDropCreature]:
    if item.knowledge_entity_id is None:
        return []
    relationships = [
        *KnowledgeGraphService.incoming(db, item.knowledge_entity_id, relationship_type="dropped_by"),
        *KnowledgeGraphService.outgoing(db, item.knowledge_entity_id, relationship_type="dropped_by"),
    ]
    drops: list[ItemDropCreature] = []
    for relationship in relationships:
        creature = None
        if relationship.target_entity_id is not None:
            creature = (
                db.query(Creature)
                .options(joinedload(Creature.spawn_locations).joinedload(SpawnLocation.hunt_zone))
                .filter(Creature.knowledge_entity_id == relationship.target_entity_id)
                .first()
            )
        legacy = None
        if creature is not None:
            legacy = (
                db.query(LootModel)
                .filter(
                    LootModel.creature_id == creature.id,
                    LootModel.normalized_name == item.normalized_name,
                )
                .first()
            )
        drops.append(
            ItemDropCreature(
                creature_id=creature.id if creature else None,
                creature_name=creature.name if creature else relationship.target_name,
                creature_slug=creature.slug if creature else None,
                chance=legacy.percentage if legacy else None,
                rarity=legacy.rarity if legacy else None,
                hunt_zones=_hunt_zones(creature),
                relationship_id=relationship.relationship_id,
                knowledge_entity_id=relationship.target_entity_id,
                resolution_status=relationship.resolution_state,
                source_provider=relationship.contributing_providers[0] if relationship.contributing_providers else None,
            )
        )
    return drops


def _build_canonical_item_result(db: Session, item: ExternalItemModel) -> ItemSearchResult:
    return ItemSearchResult(
        id=item.id,
        image_item_id=item.id,
        item_name=item.name,
        normalized_name=item.normalized_name or normalize_search_text(item.name),
        item_image_url=item.image_url,
        source_url=item.source_url,
        knowledge_entity_id=item.knowledge_entity_id,
        item_type=item.type,
        category=item.category,
        data_version=item.data_version or 1,
        last_synced_at=item.last_synced_at,
        drops=_canonical_item_drops(db, item),
    )


@router.get("/highlights", response_model=List[ItemSearchResult])
async def get_item_highlights(
    limit: int = Query(12, ge=1, le=50),
    db: Session = Depends(get_db),
):
    try:
        metadata = EntityMetadataService.get_highlights(db, entity_type="item", limit=limit)
        if not metadata:
            return []

        response: list[ItemSearchResult] = []
        for record in metadata:
            canonical = (
                db.query(ExternalItemModel)
                .filter(
                    ExternalItemModel.id == record.entity_id,
                    ExternalItemModel.knowledge_entity_id.isnot(None),
                )
                .first()
                if record.entity_id is not None
                else None
            )
            if canonical is not None:
                response.append(_build_canonical_item_result(db, canonical))
                continue
            drops = (
                db.query(LootModel)
                .options(joinedload(LootModel.creature))
                .filter(LootModel.normalized_name == record.entity_key)
                .limit(40)
                .all()
            )
            if not drops:
                continue
            response.append(_build_item_result(drops[0].item_name, drops, include_hunt_zones=False, max_drops=8))
        return response
    except Exception:
        return []


@router.get("/", response_model=List[ItemSearchResult])
async def search_items(
    search: str | None = Query(None, min_length=2, description="Search term for item name"),
    category: str | None = Query(None, min_length=1, max_length=100),
    item_type: str | None = Query(None, min_length=1, max_length=100),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Search for items/loot by name.
    Returns grouped results sorted by exactness and fuzzy similarity.
    """
    canonical_query = db.query(ExternalItemModel).filter(ExternalItemModel.knowledge_entity_id.isnot(None))
    if search:
        canonical_query = canonical_query.filter(
            ExternalItemModel.normalized_name.contains(normalize_search_text(search))
        )
    if category:
        canonical_query = canonical_query.filter(ExternalItemModel.category.ilike(category))
    if item_type:
        canonical_query = canonical_query.filter(ExternalItemModel.type.ilike(item_type))
    canonical_match_count = canonical_query.count()
    canonical_items = (
        canonical_query.order_by(ExternalItemModel.name.asc(), ExternalItemModel.id.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    if canonical_items:
        if search:
            EntityMetadataService.record_searches(
                db,
                entity_type="item",
                matches=[
                    (item.normalized_name, item.name, item.id)
                    for item in canonical_items
                ],
            )
            db.commit()
        return [_build_canonical_item_result(db, item) for item in canonical_items]
    if canonical_match_count:
        return []
    if category or item_type:
        return []

    if not search:
        rows = (
            db.query(LootModel)
            .options(
                joinedload(LootModel.creature)
                .joinedload(Creature.spawn_locations)
                .joinedload(SpawnLocation.hunt_zone)
            )
            .filter(LootModel.normalized_name.isnot(None))
            .limit(500)
            .all()
        )
        grouped: dict[str, list[LootModel]] = {}
        for row in rows:
            key = row.normalized_name or normalize_search_text(row.item_name)
            grouped.setdefault(key, []).append(row)
        ranked_keys = sorted(grouped.keys(), key=lambda key: _rank_item(grouped[key][0].item_name, grouped[key][0].item_name))
        selected_keys = ranked_keys[skip: skip + limit]
        return [_build_item_result(grouped[key][0].item_name, grouped[key]) for key in selected_keys]

    normalized_search = normalize_search_text(search)
    query = (
        db.query(LootModel)
        .options(
            joinedload(LootModel.creature)
            .joinedload(Creature.spawn_locations)
            .joinedload(SpawnLocation.hunt_zone)
        )
        .filter(LootModel.normalized_name.isnot(None))
        .filter(LootModel.normalized_name.contains(normalized_search))
    )
    candidate_rows = query.limit(max(limit * 8, 40)).all()
    if not candidate_rows:
        candidate_rows = (
            db.query(LootModel)
            .options(
                joinedload(LootModel.creature)
                .joinedload(Creature.spawn_locations)
                .joinedload(SpawnLocation.hunt_zone)
            )
            .limit(200)
            .all()
        )

    grouped: dict[str, list[LootModel]] = {}
    for row in candidate_rows:
        key = row.normalized_name or normalize_search_text(row.item_name)
        grouped.setdefault(key, []).append(row)

    ranked_keys = sorted(
        grouped.keys(),
        key=lambda key: _rank_item(search, grouped[key][0].item_name),
    )
    selected_keys = ranked_keys[skip: skip + limit]
    EntityMetadataService.record_searches(
        db,
        entity_type="item",
        matches=[(key, grouped[key][0].item_name, None) for key in selected_keys],
    )
    db.commit()
    return [_build_item_result(grouped[key][0].item_name, grouped[key]) for key in selected_keys]


@router.get("/{item_identifier}", response_model=ItemDetail)
async def get_item_detail(
    item_identifier: str,
    response: Response,
    db: Session = Depends(get_db),
):
    """Get item detail exclusively from local PostgreSQL records."""
    normalized_identifier = normalize_search_text(item_identifier.replace("-", " ").replace("_", " "))
    canonical_query = db.query(ExternalItemModel).filter(ExternalItemModel.knowledge_entity_id.isnot(None))
    if item_identifier.isdigit():
        numeric_identifier = int(item_identifier)
        canonical_query = canonical_query.filter(
            or_(
                ExternalItemModel.id == numeric_identifier,
                ExternalItemModel.item_id == numeric_identifier,
                ExternalItemModel.external_id == item_identifier,
            )
        )
    else:
        canonical_query = canonical_query.filter(
            or_(
                ExternalItemModel.slug == item_identifier,
                ExternalItemModel.normalized_name == normalized_identifier,
            )
        )
    canonical = canonical_query.order_by(ExternalItemModel.id.asc()).first()
    if canonical is not None:
        drops = _canonical_item_drops(db, canonical)
        top_drop = max((drop.chance for drop in drops if drop.chance is not None), default=None)
        rarity = next((drop.rarity for drop in drops if drop.rarity), None)
        if canonical.last_synced_at:
            response.headers["X-Last-Synced-At"] = canonical.last_synced_at.isoformat()
        return ItemDetail(
            id=canonical.id,
            item_name=canonical.name,
            normalized_name=canonical.normalized_name or normalize_search_text(canonical.name),
            item_image_url=canonical.image_url,
            source_url=canonical.source_url,
            rarity=rarity,
            drop_chance=top_drop,
            knowledge_entity_id=canonical.knowledge_entity_id,
            data_version=canonical.data_version or 1,
            last_synced_at=canonical.last_synced_at,
            game_item_id=canonical.item_id,
            item_class=canonical.item_class,
            item_type=canonical.type,
            category=canonical.category,
            weight=canonical.weight,
            value=canonical.value,
            level_requirement=canonical.level_required,
            vocation_requirements=list(canonical.vocation_requirements or []),
            attack=canonical.attack,
            defense=canonical.defense,
            armor=canonical.armor,
            range=canonical.range,
            slots=list(canonical.slots or []),
            imbuement_slots=canonical.imbuement_slots,
            attributes=dict(canonical.attributes or {}),
            resistances=dict(canonical.resistances or {}),
            bonuses=dict(canonical.bonuses or {}),
            description=canonical.description,
            notes=canonical.notes,
            buy_from=list(canonical.buy_from or []),
            sell_to=list(canonical.sell_to or []),
            rewards_from=list(canonical.rewards_from or []),
            required_for=list(canonical.required_for or []),
            drops=drops,
        )

    if not item_identifier.isdigit():
        raise HTTPException(status_code=404, detail="Item not found")

    item_id = int(item_identifier)
    local_by_id = (
        db.query(LootModel)
        .options(
            joinedload(LootModel.creature)
            .joinedload(Creature.spawn_locations)
            .joinedload(SpawnLocation.hunt_zone)
        )
        .filter(LootModel.id == item_id)
        .first()
    )

    if not local_by_id:
        local_by_id = (
            db.query(LootModel)
            .options(
                joinedload(LootModel.creature)
                .joinedload(Creature.spawn_locations)
                .joinedload(SpawnLocation.hunt_zone)
            )
            .filter(LootModel.external_id == str(item_id))
            .first()
        )

    if local_by_id:
        all_rows = (
            db.query(LootModel)
            .options(
                joinedload(LootModel.creature)
                .joinedload(Creature.spawn_locations)
                .joinedload(SpawnLocation.hunt_zone)
            )
            .filter(LootModel.normalized_name == local_by_id.normalized_name)
            .all()
        )
        mapped = _build_item_result(local_by_id.item_name, all_rows)
        top_drop = max((drop.chance for drop in mapped.drops if drop.chance is not None), default=None)
        rarity = next((drop.rarity for drop in mapped.drops if drop.rarity), None)
        return ItemDetail(
            id=local_by_id.id,
            item_name=mapped.item_name,
            normalized_name=mapped.normalized_name,
            item_image_url=mapped.item_image_url,
            source_url=mapped.source_url,
            rarity=rarity,
            drop_chance=top_drop,
            drops=mapped.drops,
        )

    raise HTTPException(status_code=404, detail="Item not found")


def _build_item_result(
    item_name: str,
    drops: list[LootModel],
    *,
    include_hunt_zones: bool = True,
    max_drops: int | None = None,
) -> ItemSearchResult:
    related_drops: list[ItemDropCreature] = []
    seen_creature_ids: set[int] = set()
    for drop in sorted(drops, key=lambda item: (item.percentage is None, -(item.percentage or 0))):
        if max_drops is not None and len(related_drops) >= max_drops:
            break
        if not drop.creature or drop.creature.id in seen_creature_ids:
            continue
        seen_creature_ids.add(drop.creature.id)
        hunt_zones = []
        if include_hunt_zones:
            for spawn in drop.creature.spawn_locations or []:
                if spawn.hunt_zone:
                    hunt_zones.append({
                        "id": spawn.hunt_zone.id,
                        "name": spawn.hunt_zone.name,
                        "city": spawn.hunt_zone.city,
                        "min_level": None if spawn.hunt_zone.min_level == 0 else spawn.hunt_zone.min_level,
                        "max_level": spawn.hunt_zone.max_level,
                        "difficulty": spawn.hunt_zone.difficulty,
                        "source_url": getattr(spawn.hunt_zone, "source_url", None),
                    })
        related_drops.append(ItemDropCreature(
            creature_id=drop.creature.id,
            creature_name=drop.creature.name,
            creature_slug=getattr(drop.creature, "slug", None),
            chance=drop.percentage,
            rarity=drop.rarity,
            hunt_zones=hunt_zones,
        ))
    sample = drops[0]
    return ItemSearchResult(
        image_item_id=sample.id,
        item_name=item_name,
        normalized_name=sample.normalized_name or normalize_search_text(item_name),
        item_image_url=sample.item_image_url,
        source_url=sample.source_url,
        drops=related_drops,
    )
