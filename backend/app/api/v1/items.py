"""Items/Loot API endpoints."""
from difflib import SequenceMatcher
from typing import List

from fastapi import APIRouter, Depends, Query
from fastapi import HTTPException, Request, Response
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.db.database import SessionLocal, get_db
from app.models.creature import Creature
from app.models import Loot as LootModel
from app.models.external_data import (
    Item as ExternalItemModel,
    TibiaWikiLocation,
    TibiaWikiNpc,
    TibiaWikiQuest,
)
from app.models.spawn_location import SpawnLocation
from app.schemas import ItemDetail, ItemDropCreature, ItemRelatedEntity, ItemSearchResult
from app.api.v1.local_media import (
    LocalMediaDescriptor,
    build_local_media_file_response,
    resolve_local_media_descriptor,
)
from app.services.entity_metadata_service import EntityMetadataService
from app.services import media_asset_service as media_svc
from app.services.text_utils import normalize_search_text
from app.knowledge.services import KnowledgeGraphService

router = APIRouter(prefix="/items", tags=["items"])


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
def get_item_image(
    item_id: int,
    request: Request,
    include_placeholder: bool = Query(True, alias="placeholder"),
):
    """Serve loot/item image from local MediaAsset cache (local-first)."""
    descriptor = _resolve_item_media_descriptor(item_id)

    if descriptor.status != "cached":
        return _unavailable_item_image(
            label=descriptor.fallback_label,
            asset_key=descriptor.asset_key,
            include_placeholder=include_placeholder,
            status=descriptor.status,
        )

    response = build_local_media_file_response(
        request,
        descriptor,
        default_media_type="image/gif",
        cache_max_age_seconds=settings.IMAGE_CACHE_MAX_AGE_SECONDS,
        extra_headers={
            "X-Image-Source": "local-media-asset",
            "X-Image-Status": "cached",
            "X-Asset-Key": descriptor.asset_key,
        },
    )

    if response is None:
        return _unavailable_item_image(
            label=descriptor.fallback_label,
            asset_key=descriptor.asset_key,
            include_placeholder=include_placeholder,
            status="missing",
        )

    return response


def _resolve_item_media_descriptor(item_id: int) -> LocalMediaDescriptor:
    """Resolve item media metadata in a short-lived DB session."""

    def _resolver(db: Session) -> LocalMediaDescriptor:
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

        label = item.name if item else (loot.item_name or "Unknown Item")
        asset_key = (
            f"item:knowledge:{item.knowledge_entity_id}"
            if item
            else media_svc.build_loot_asset_key(loot)
        )

        # Public requests must never perform provider downloads.
        # Missing assets are populated exclusively by sync/admin workers.
        asset = media_svc.get_asset(db, asset_key)

        return LocalMediaDescriptor(
            local_path=(str(asset.local_path) if asset and asset.local_path else None),
            content_type=(asset.content_type if asset else None),
            size_bytes=(asset.size_bytes if asset else None),
            asset_hash=(asset.sha256_hash if asset else None),
            asset_key=asset_key,
            status=(getattr(asset, "status", "missing") if asset else "missing"),
            fallback_label=label,
        )

    return resolve_local_media_descriptor(
        _resolver,
        session_factory=SessionLocal,
    )


def _unavailable_item_image(
    *,
    label: str,
    asset_key: str,
    include_placeholder: bool,
    status: str = "missing",
) -> Response:
    headers = {
        "Cache-Control": "public, max-age=300",
        "X-Image-Source": (
            "placeholder"
            if include_placeholder
            else "unavailable"
        ),
        "X-Image-Status": status,
        "X-Asset-Key": asset_key,
    }

    if not include_placeholder:
        raise HTTPException(
            status_code=404,
            detail="Item image unavailable",
            headers=headers,
        )

    return Response(
        content=_placeholder_svg(label),
        media_type="image/svg+xml",
        headers=headers,
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
            "slug": spawn.hunt_zone.slug or normalize_search_text(spawn.hunt_zone.name).replace(" ", "-"),
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
    unique_relationships = {relationship.relationship_id: relationship for relationship in relationships}
    target_ids = {
        relationship.target_entity_id
        for relationship in unique_relationships.values()
        if relationship.target_entity_id is not None
    }
    creatures = (
        db.query(Creature)
        .options(joinedload(Creature.spawn_locations).joinedload(SpawnLocation.hunt_zone))
        .filter(Creature.knowledge_entity_id.in_(target_ids))
        .all()
        if target_ids else []
    )
    creatures_by_knowledge_id = {creature.knowledge_entity_id: creature for creature in creatures}
    creature_ids = [creature.id for creature in creatures]
    legacy_rows = (
        db.query(LootModel)
        .filter(
            LootModel.creature_id.in_(creature_ids),
            LootModel.normalized_name == item.normalized_name,
        )
        .all()
        if creature_ids else []
    )
    legacy_by_creature_id = {row.creature_id: row for row in legacy_rows}

    drops: list[ItemDropCreature] = []
    for relationship in unique_relationships.values():
        creature = creatures_by_knowledge_id.get(relationship.target_entity_id)
        legacy = legacy_by_creature_id.get(creature.id) if creature else None
        drops.append(
            ItemDropCreature(
                creature_id=creature.id if creature else None,
                creature_name=creature.name if creature else relationship.target_name,
                creature_slug=creature.slug if creature else None,
                chance=legacy.percentage if legacy else None,
                rarity=legacy.rarity if legacy else None,
                min_amount=legacy.min_amount if legacy else None,
                max_amount=legacy.max_amount if legacy else None,
                is_boss=bool(creature.is_boss) if creature else False,
                hunt_zones=_hunt_zones(creature),
                relationship_id=relationship.relationship_id,
                knowledge_entity_id=relationship.target_entity_id,
                resolution_status=relationship.resolution_state,
                source_provider=relationship.contributing_providers[0] if relationship.contributing_providers else None,
            )
        )
    return drops


def _record_name(value: object) -> str | None:
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, dict):
        for key in ("name", "npc", "quest", "location"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
    return None


def _item_related_entities(db: Session, item: ExternalItemModel) -> list[ItemRelatedEntity]:
    """Resolve only canonical local targets, using one query per entity type."""
    npc_names = {
        normalize_search_text(name)
        for name in (
            _record_name(value)
            for value in [*(item.buy_from or []), *(item.sell_to or [])]
        )
        if name
    }
    quest_names = {
        normalize_search_text(name)
        for name in [*(item.rewards_from or []), *(item.required_for or [])]
        if isinstance(name, str) and name.strip()
    }
    raw_data = item.raw_data if isinstance(item.raw_data, dict) else {}
    raw_locations = raw_data.get("locations") or []
    location_names = {
        normalize_search_text(name)
        for name in (_record_name(value) for value in raw_locations)
        if name
    }
    rows: list[tuple[str, object]] = []
    if npc_names:
        rows.extend(("npc", row) for row in db.query(TibiaWikiNpc).filter(TibiaWikiNpc.normalized_name.in_(npc_names)).all())
    if quest_names:
        rows.extend(("quest", row) for row in db.query(TibiaWikiQuest).filter(TibiaWikiQuest.normalized_name.in_(quest_names)).all())
    if location_names:
        rows.extend(("location", row) for row in db.query(TibiaWikiLocation).filter(TibiaWikiLocation.normalized_name.in_(location_names)).all())
    return [
        ItemRelatedEntity(kind=kind, name=row.name, slug=row.slug)
        for kind, row in rows
        if getattr(row, "slug", None)
    ]


def _build_canonical_item_result(db: Session, item: ExternalItemModel) -> ItemSearchResult:
    return ItemSearchResult(
        id=item.id,
        image_item_id=item.id,
        item_name=item.name,
        normalized_name=item.normalized_name or normalize_search_text(item.name),
        slug=item.slug or normalize_search_text(item.name).replace(" ", "-"),
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


@router.get("/popular", response_model=List[ItemSearchResult])
async def get_popular_items(
    limit: int = Query(12, ge=1, le=30),
    db: Session = Depends(get_db),
):
    """Return locally popular loot in stable activity order."""
    metadata = EntityMetadataService.get_popular(
        db,
        entity_type="item",
        limit=min(limit * 2, 60),
    )
    ids = [row.entity_id for row in metadata if row.entity_id is not None]
    canonical = (
        db.query(ExternalItemModel)
        .filter(
            ExternalItemModel.id.in_(ids),
            ExternalItemModel.knowledge_entity_id.isnot(None),
        )
        .all()
        if ids
        else []
    )
    by_id = {row.id: row for row in canonical}
    results = [
        _build_canonical_item_result(db, by_id[item_id])
        for item_id in ids
        if item_id in by_id
    ]
    if len(results) < limit:
        seen = {row.id for row in canonical}
        fallback = (
            db.query(ExternalItemModel)
            .filter(
                ExternalItemModel.knowledge_entity_id.isnot(None),
                ExternalItemModel.id.notin_(seen) if seen else True,
            )
            .order_by(ExternalItemModel.updated_at.desc().nullslast(), ExternalItemModel.id.asc())
            .limit(limit - len(results))
            .all()
        )
        results.extend(_build_canonical_item_result(db, row) for row in fallback)
    return results[:limit]


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
    ordered_canonical = canonical_query.order_by(ExternalItemModel.name.asc(), ExternalItemModel.id.asc())
    canonical_items = (
        ordered_canonical.limit(max(limit * 2, 40)).all()
        if search
        else ordered_canonical.offset(skip).limit(limit).all()
    )
    canonical_results = [_build_canonical_item_result(db, item) for item in canonical_items]
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
        else:
            return canonical_results
    if canonical_match_count and not search:
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
    selected_keys = ranked_keys[: max(limit * 2, 40)]
    EntityMetadataService.record_searches(
        db,
        entity_type="item",
        matches=[(key, grouped[key][0].item_name, None) for key in selected_keys],
    )
    db.commit()
    combined: dict[str, ItemSearchResult] = {
        result.normalized_name: result
        for result in canonical_results
    }
    for key in selected_keys:
        result = _build_item_result(grouped[key][0].item_name, grouped[key])
        combined.setdefault(normalize_search_text(result.item_name), result)
    ranked_results = sorted(
        combined.values(),
        key=lambda result: _rank_item(search, result.item_name),
    )
    return ranked_results[skip: skip + limit]


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
        canonical_slug = canonical.slug or normalize_search_text(canonical.name).replace(" ", "-")
        response.headers["X-Canonical-Slug"] = canonical_slug
        return ItemDetail(
            id=canonical.id,
            item_name=canonical.name,
            normalized_name=canonical.normalized_name or normalize_search_text(canonical.name),
            slug=canonical_slug,
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
            related_entities=_item_related_entities(db, canonical),
            drops=drops,
        )

    local_query = (
        db.query(LootModel)
        .options(
            joinedload(LootModel.creature)
            .joinedload(Creature.spawn_locations)
            .joinedload(SpawnLocation.hunt_zone)
        )
    )
    if item_identifier.isdigit():
        item_id = int(item_identifier)
        local_by_id = local_query.filter(or_(
            LootModel.id == item_id,
            LootModel.external_id == item_identifier,
        )).first()
    else:
        display_identifier = item_identifier.replace("-", " ").replace("_", " ").strip()
        local_by_id = local_query.filter(or_(
            LootModel.normalized_name == normalized_identifier,
            func.lower(LootModel.item_name) == display_identifier.lower(),
        )).first()
        if local_by_id is None:
            first_token = normalized_identifier.split(" ", 1)[0]
            candidates = local_query.filter(or_(
                LootModel.normalized_name.contains(first_token),
                LootModel.item_name.ilike(f"{first_token}%"),
            )).limit(500).all()
            local_by_id = next((
                row for row in candidates
                if normalize_search_text(row.item_name) == normalized_identifier
                or normalize_search_text(row.normalized_name) == normalized_identifier
            ), None)

    if local_by_id:
        legacy_slug = normalize_search_text(local_by_id.item_name).replace(" ", "-")
        response.headers["X-Canonical-Slug"] = legacy_slug
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
        EntityMetadataService.record_searches(
            db,
            entity_type="item",
            matches=[(mapped.normalized_name, mapped.item_name, None)],
        )
        db.commit()
        return ItemDetail(
            id=local_by_id.id,
            item_name=mapped.item_name,
            normalized_name=mapped.normalized_name,
            slug=legacy_slug,
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
                        "slug": spawn.hunt_zone.slug or normalize_search_text(spawn.hunt_zone.name).replace(" ", "-"),
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
            min_amount=drop.min_amount,
            max_amount=drop.max_amount,
            is_boss=bool(drop.creature.is_boss),
            hunt_zones=hunt_zones,
        ))
    sample = drops[0]
    return ItemSearchResult(
        id=sample.id,
        image_item_id=sample.id,
        item_name=item_name,
        normalized_name=sample.normalized_name or normalize_search_text(item_name),
        slug=normalize_search_text(item_name).replace(" ", "-"),
        item_image_url=sample.item_image_url,
        source_url=sample.source_url,
        item_type=sample.item_type,
        drops=related_drops,
    )
