"""Read models used by the Cyclopedia Creature browser and side preview."""
from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.db.database import get_db
from app.models import Creature as CreatureModel, Loot as LootModel, SpawnLocation
from app.models.creature import creature_resistances, creature_weaknesses
from app.models.element import Element as ElementModel
from app.schemas import ItemMedia
from app.services.creature_category_service import canonicalize_creature_category, creature_category_expression
from app.services.creature_storage_service import list_cached_creatures, resolve_cached_creature
from app.services.text_utils import normalize_search_text

router = APIRouter(prefix="/creatures", tags=["creature-browser"])


class CreatureBrowseLoot(BaseModel):
    id: int
    item_name: str
    percentage: Optional[float] = None
    rarity: Optional[str] = None
    item_value: Optional[int] = None
    media: ItemMedia = Field(default_factory=ItemMedia)


class CreatureBrowseLocation(BaseModel):
    id: Optional[int] = None
    name: str
    slug: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None
    map_image_url: Optional[str] = None


class CreatureBrowseItem(BaseModel):
    id: int
    slug: Optional[str] = None
    name: str
    hitpoints: Optional[int] = None
    experience: Optional[int] = None
    is_boss: bool = False
    difficulty: Optional[str] = None
    classification: Optional[str] = None
    bestiary_level: Optional[str] = None
    bestiary_class: Optional[str] = None
    creature_class: Optional[str] = None
    primary_type: Optional[str] = None
    location_preview: Optional[CreatureBrowseLocation] = None
    loot_preview: list[CreatureBrowseLoot] = Field(default_factory=list)


class CreatureBrowsePage(BaseModel):
    items: list[CreatureBrowseItem]
    total: int
    skip: int
    limit: int


class CreatureCombatModifier(BaseModel):
    name: str
    kind: Literal["weakness", "resistance"]
    damage_percent: Optional[int] = None
    delta_percent: Optional[int] = None


class CreaturePreview(BaseModel):
    id: int
    slug: Optional[str] = None
    name: str
    difficulty: Optional[str] = None
    classification: Optional[str] = None
    bestiary_level: Optional[str] = None
    bestiary_class: Optional[str] = None
    creature_class: Optional[str] = None
    primary_type: Optional[str] = None
    description: Optional[str] = None
    behavior: Optional[str] = None
    hitpoints: Optional[int] = None
    experience: Optional[int] = None
    charm_points: Optional[int] = None
    image_url: str
    loot: list[CreatureBrowseLoot] = Field(default_factory=list)
    locations: list[CreatureBrowseLocation] = Field(default_factory=list)
    combat_modifiers: list[CreatureCombatModifier] = Field(default_factory=list)


def _location(spawn: SpawnLocation) -> CreatureBrowseLocation | None:
    zone = spawn.hunt_zone
    if not zone:
        return None
    return CreatureBrowseLocation(
        id=zone.id,
        name=zone.name,
        slug=zone.slug,
        city=zone.city,
        region=zone.region,
        map_image_url=f"/api/v1/hunt-zones/{zone.id}/map-image?placeholder=false",
    )


def _loot(row: LootModel) -> CreatureBrowseLoot:
    return CreatureBrowseLoot(
        id=row.id,
        item_name=row.item_name,
        percentage=row.percentage,
        rarity=row.rarity,
        item_value=row.item_value,
        media=row.media,
    )


def _rank_loot(rows: list[LootModel], limit: int | None = None) -> list[CreatureBrowseLoot]:
    ranked = sorted(
        rows,
        key=lambda row: (
            -(row.item_value or 0),
            -(row.percentage or 0),
            (row.item_name or "").lower(),
        ),
    )
    if limit is not None:
        ranked = ranked[:limit]
    return [_loot(row) for row in ranked]


def _total(
    db: Session,
    *,
    search: str | None,
    category: str | None,
    is_boss: bool,
) -> int:
    query = db.query(func.count(CreatureModel.id)).filter(
        CreatureModel.is_hidden.is_(False),
        CreatureModel.is_boss.is_(is_boss),
    )
    if search:
        normalized = normalize_search_text(search)
        query = query.filter(CreatureModel.normalized_name.contains(normalized, autoescape=True))
    if category:
        canonical = canonicalize_creature_category(category)
        if canonical is None:
            return 0
        query = query.filter(creature_category_expression() == canonical)
    return int(query.scalar() or 0)


def _load_enriched(db: Session, ids: list[int]) -> dict[int, CreatureModel]:
    if not ids:
        return {}
    rows = (
        db.query(CreatureModel)
        .options(
            selectinload(CreatureModel.loot_items).selectinload(LootModel.image_asset),
            selectinload(CreatureModel.spawn_locations).selectinload(SpawnLocation.hunt_zone),
        )
        .filter(CreatureModel.id.in_(ids), CreatureModel.is_hidden.is_(False))
        .all()
    )
    return {row.id: row for row in rows}


def _browse_item(row: CreatureModel) -> CreatureBrowseItem:
    locations = [candidate for spawn in row.spawn_locations if (candidate := _location(spawn))]
    locations.sort(key=lambda value: value.name.lower())
    return CreatureBrowseItem(
        id=row.id,
        slug=row.slug,
        name=row.name,
        hitpoints=row.hitpoints,
        experience=row.experience,
        is_boss=row.is_boss,
        difficulty=row.difficulty,
        classification=row.classification,
        bestiary_level=row.bestiary_level,
        bestiary_class=row.bestiary_class,
        creature_class=row.creature_class,
        primary_type=row.primary_type,
        location_preview=locations[0] if locations else None,
        loot_preview=_rank_loot(row.loot_items, 2),
    )


@router.get("/browser", response_model=CreatureBrowsePage)
def browse_creatures(
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    category: Optional[str] = None,
    is_boss: bool = False,
    sort_by: str = Query("name", pattern="^(name|experience|hitpoints|difficulty)$"),
    sort_order: str = Query("asc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
) -> CreatureBrowsePage:
    base_rows = list_cached_creatures(
        db,
        search=search,
        category=category,
        is_boss=is_boss,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
        include_hidden=False,
    )
    ids = [row.id for row in base_rows]
    enriched = _load_enriched(db, ids)
    response.headers["Cache-Control"] = "public, max-age=120, stale-while-revalidate=300"
    return CreatureBrowsePage(
        items=[_browse_item(enriched[row_id]) for row_id in ids if row_id in enriched],
        total=_total(db, search=search, category=category, is_boss=is_boss),
        skip=skip,
        limit=limit,
    )


@router.get("/browser-items", response_model=list[CreatureBrowseItem])
def browse_creature_items(
    ids: str = Query(..., min_length=1),
    response: Response = None,
    db: Session = Depends(get_db),
) -> list[CreatureBrowseItem]:
    parsed: list[int] = []
    for token in ids.split(","):
        token = token.strip()
        if not token.isdigit():
            continue
        value = int(token)
        if value not in parsed:
            parsed.append(value)
        if len(parsed) >= 60:
            break
    enriched = _load_enriched(db, parsed)
    if response is not None:
        response.headers["Cache-Control"] = "public, max-age=120, stale-while-revalidate=300"
    return [_browse_item(enriched[row_id]) for row_id in parsed if row_id in enriched]


def _modifier_rows(db: Session, creature_id: int) -> list[CreatureCombatModifier]:
    result: list[CreatureCombatModifier] = []
    for kind, table in (("weakness", creature_weaknesses), ("resistance", creature_resistances)):
        rows = (
            db.query(ElementModel, table.c.percentage)
            .join(table, ElementModel.id == table.c.element_id)
            .filter(table.c.creature_id == creature_id)
            .order_by(ElementModel.name.asc())
            .all()
        )
        for element, percentage in rows:
            damage_percent = int(percentage) if percentage is not None else None
            result.append(
                CreatureCombatModifier(
                    name=element.name,
                    kind=kind,
                    damage_percent=damage_percent,
                    delta_percent=(damage_percent - 100) if damage_percent is not None else None,
                )
            )
    return result


@router.get("/{creature_identifier}/preview", response_model=CreaturePreview)
def creature_preview(
    creature_identifier: str,
    response: Response,
    db: Session = Depends(get_db),
) -> CreaturePreview:
    row = resolve_cached_creature(db, creature_identifier)
    if row is None:
        raise HTTPException(status_code=404, detail="We couldn't find this creature.")

    enriched = _load_enriched(db, [row.id]).get(row.id) or row
    locations = [candidate for spawn in enriched.spawn_locations if (candidate := _location(spawn))]
    locations.sort(key=lambda value: value.name.lower())
    response.headers["Cache-Control"] = "public, max-age=120, stale-while-revalidate=300"
    return CreaturePreview(
        id=enriched.id,
        slug=enriched.slug,
        name=enriched.name,
        difficulty=enriched.difficulty,
        classification=enriched.classification,
        bestiary_level=enriched.bestiary_level,
        bestiary_class=enriched.bestiary_class,
        creature_class=enriched.creature_class,
        primary_type=enriched.primary_type,
        description=enriched.description,
        behavior=enriched.behavior,
        hitpoints=enriched.hitpoints,
        experience=enriched.experience,
        charm_points=enriched.charm_points,
        image_url=f"/api/v1/creatures/{enriched.id}/image?placeholder=false",
        loot=_rank_loot(enriched.loot_items),
        locations=locations,
        combat_modifiers=_modifier_rows(db, enriched.id),
    )
