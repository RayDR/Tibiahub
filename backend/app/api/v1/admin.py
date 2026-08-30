"""
Admin API endpoints - CRUD operations for creatures and hunt zones
"""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.database import get_db
from app.models import Creature, HuntZone, Loot, Element, SpawnLocation
from app.models.user import User
from app.models.quest import Quest
from app.api.v1.endpoints.auth import get_current_admin_user
from app.services import media_asset_service as media_svc
from app.schemas import (
    CreatureCreate, Creature as CreatureSchema,
    HuntZoneCreate, HuntZone as HuntZoneSchema,
    LootCreate, Loot as LootSchema,
    ElementCreate, Element as ElementSchema
)


class CreatureImagePatch(BaseModel):
    name: Optional[str] = None
    classification: Optional[str] = None
    difficulty: Optional[str] = None
    is_hidden: Optional[bool] = None
    image_alias: Optional[str] = None
    image_url_override: Optional[str] = None
    image_source_name: Optional[str] = None
    image_locked: Optional[bool] = None
    clear_local_cache: Optional[bool] = False


class LootImagePatch(BaseModel):
    item_image_alias: Optional[str] = None
    item_image_url_override: Optional[str] = None
    item_image_locked: Optional[bool] = None
    clear_local_cache: Optional[bool] = False

router = APIRouter(dependencies=[Depends(get_current_admin_user)])


# ============================================================================
# CREATURES ADMIN
# ============================================================================

@router.get("/creatures")
def list_creatures_admin(
    skip: int = 0,
    limit: int = 50,
    search: Optional[str] = None,
    include_hidden: bool = True,
    db: Session = Depends(get_db),
):
    query = db.query(Creature)
    if search:
        search_term = f"%{search.strip()}%"
        query = query.filter(Creature.name.ilike(search_term))
    if not include_hidden:
        query = query.filter(Creature.is_hidden == False)
    total = query.count()
    items = query.order_by(Creature.name.asc()).offset(skip).limit(limit).all()
    return {"items": items, "total": total, "skip": skip, "limit": limit}

@router.post("/creatures/", response_model=CreatureSchema, status_code=status.HTTP_201_CREATED)
def create_creature(creature: CreatureCreate, db: Session = Depends(get_db)):
    """Create a new creature"""
    # Check if creature already exists
    db_creature = db.query(Creature).filter(Creature.name == creature.name).first()
    if db_creature:
        raise HTTPException(status_code=400, detail="Creature already exists")
    
    db_creature = Creature(**creature.model_dump())
    db.add(db_creature)
    db.commit()
    db.refresh(db_creature)
    return db_creature


@router.put("/creatures/{creature_id}", response_model=CreatureSchema)
def update_creature(creature_id: int, creature: CreatureCreate, db: Session = Depends(get_db)):
    """Update an existing creature"""
    db_creature = db.query(Creature).filter(Creature.id == creature_id).first()
    if not db_creature:
        raise HTTPException(status_code=404, detail="Creature not found")
    
    for key, value in creature.model_dump().items():
        setattr(db_creature, key, value)
    
    db.commit()
    db.refresh(db_creature)
    return db_creature


@router.delete("/creatures/{creature_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_creature(creature_id: int, db: Session = Depends(get_db)):
    """Delete a creature"""
    db_creature = db.query(Creature).filter(Creature.id == creature_id).first()
    if not db_creature:
        raise HTTPException(status_code=404, detail="Creature not found")
    
    db.delete(db_creature)
    db.commit()
    return None


# ============================================================================
# HUNT ZONES ADMIN
# ============================================================================

@router.post("/hunt-zones/", response_model=HuntZoneSchema, status_code=status.HTTP_201_CREATED)
def create_hunt_zone(zone: HuntZoneCreate, db: Session = Depends(get_db)):
    """Create a new hunt zone"""
    # Check if zone already exists
    db_zone = db.query(HuntZone).filter(HuntZone.name == zone.name).first()
    if db_zone:
        raise HTTPException(status_code=400, detail="Hunt zone already exists")
    
    db_zone = HuntZone(**zone.model_dump(exclude={
        "quest_name", "quest_slug", "vocation_recommendations", "canonical_id",
        "missing_fields", "data_sources", "spatial",
    }))
    db.add(db_zone)
    db.commit()
    db.refresh(db_zone)
    return db_zone


@router.put("/hunt-zones/{zone_id}", response_model=HuntZoneSchema)
def update_hunt_zone(zone_id: int, zone: HuntZoneCreate, db: Session = Depends(get_db)):
    """Update an existing hunt zone"""
    db_zone = db.query(HuntZone).filter(HuntZone.id == zone_id).first()
    if not db_zone:
        raise HTTPException(status_code=404, detail="Hunt zone not found")
    
    for key, value in zone.model_dump(exclude={
        "quest_name", "quest_slug", "vocation_recommendations", "canonical_id",
        "missing_fields", "data_sources", "spatial",
    }).items():
        setattr(db_zone, key, value)
    
    db.commit()
    db.refresh(db_zone)
    return db_zone


@router.delete("/hunt-zones/{zone_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_hunt_zone(zone_id: int, db: Session = Depends(get_db)):
    """Delete a hunt zone"""
    db_zone = db.query(HuntZone).filter(HuntZone.id == zone_id).first()
    if not db_zone:
        raise HTTPException(status_code=404, detail="Hunt zone not found")
    
    db.delete(db_zone)
    db.commit()
    return None


# ============================================================================
# LOOT ADMIN
# ============================================================================

@router.post("/creatures/{creature_id}/loot/", response_model=LootSchema, status_code=status.HTTP_201_CREATED)
def add_loot_to_creature(creature_id: int, loot: LootCreate, db: Session = Depends(get_db)):
    """Add loot item to a creature"""
    # Check if creature exists
    db_creature = db.query(Creature).filter(Creature.id == creature_id).first()
    if not db_creature:
        raise HTTPException(status_code=404, detail="Creature not found")
    
    db_loot = Loot(**loot.model_dump(), creature_id=creature_id)
    db.add(db_loot)
    db.commit()
    db.refresh(db_loot)
    return db_loot


@router.delete("/loot/{loot_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_loot(loot_id: int, db: Session = Depends(get_db)):
    """Delete a loot item"""
    db_loot = db.query(Loot).filter(Loot.id == loot_id).first()
    if not db_loot:
        raise HTTPException(status_code=404, detail="Loot not found")
    
    db.delete(db_loot)
    db.commit()
    return None


# ============================================================================
# ELEMENTS ADMIN
# ============================================================================

@router.post("/elements/", response_model=ElementSchema, status_code=status.HTTP_201_CREATED)
def create_element(element: ElementCreate, db: Session = Depends(get_db)):
    """Create a new element"""
    db_element = Element(**element.model_dump())
    db.add(db_element)
    db.commit()
    db.refresh(db_element)
    return db_element


@router.get("/elements/", response_model=List[ElementSchema])
def list_elements(db: Session = Depends(get_db)):
    """List all elements"""
    return db.query(Element).all()


@router.delete("/elements/{element_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_element(element_id: int, db: Session = Depends(get_db)):
    """Delete an element"""
    db_element = db.query(Element).filter(Element.id == element_id).first()
    if not db_element:
        raise HTTPException(status_code=404, detail="Element not found")
    
    db.delete(db_element)
    db.commit()
    return None


# ============================================================================
# IMAGE ALIAS / OVERRIDE ADMIN
# ============================================================================

@router.patch("/creatures/{creature_id}/image", status_code=status.HTTP_200_OK)
async def patch_creature_image(
    creature_id: int,
    payload: CreatureImagePatch,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Set image alias, override URL, or lock flag for a creature image."""
    creature = db.query(Creature).filter(Creature.id == creature_id).first()
    if not creature:
        raise HTTPException(status_code=404, detail="Creature not found")

    previous_asset_key = media_svc.build_creature_asset_key(creature)

    if payload.name is not None and payload.name.strip():
        creature.name = payload.name.strip()
    if payload.classification is not None:
        creature.classification = payload.classification.strip() or None
    if payload.difficulty is not None:
        creature.difficulty = payload.difficulty.strip() or None
    if payload.is_hidden is not None:
        creature.is_hidden = bool(payload.is_hidden)

    if payload.image_alias is not None:
        creature.image_alias = payload.image_alias or None
    if payload.image_url_override is not None:
        if payload.image_url_override.strip():
            try:
                media_svc.validate_remote_url(payload.image_url_override.strip())
            except media_svc.UnsafeMediaError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
        creature.image_url_override = payload.image_url_override or None
    if payload.image_source_name is not None:
        creature.image_source_name = payload.image_source_name or None
    if payload.image_locked is not None:
        creature.image_locked = payload.image_locked

    if payload.clear_local_cache:
        media_svc.clear_asset(db, asset_key=previous_asset_key)
        creature.image_asset_id = None

    db.commit()

    # Refresh MediaAsset in background so admin sees immediate feedback
    asset_key = media_svc.build_creature_asset_key(creature)
    source_url = media_svc.build_creature_source_url(creature)
    asset_status = "no_source"
    if source_url:
        asset = await media_svc.refresh_asset(db, asset_key=asset_key, source_url=source_url)
        asset_status = (asset.status if asset else "failed")
        # Link creature → asset
        if asset and asset.id and not creature.image_asset_id:
            creature.image_asset_id = asset.id
            db.commit()

    return {
        "id": creature.id,
        "name": creature.name,
        "classification": creature.classification,
        "difficulty": creature.difficulty,
        "is_hidden": creature.is_hidden,
        "image_alias": creature.image_alias,
        "image_url_override": creature.image_url_override,
        "image_source_name": creature.image_source_name,
        "image_locked": creature.image_locked,
        "clear_local_cache": bool(payload.clear_local_cache),
        "asset_key": asset_key,
        "asset_status": asset_status,
    }


@router.patch("/loot/{loot_id}/image", status_code=status.HTTP_200_OK)
async def patch_loot_image(
    loot_id: int,
    payload: LootImagePatch,
    db: Session = Depends(get_db),
):
    """Set image alias, override URL, or lock flag for a loot item image."""
    loot = db.query(Loot).filter(Loot.id == loot_id).first()
    if not loot:
        raise HTTPException(status_code=404, detail="Loot item not found")

    previous_asset_key = media_svc.build_loot_asset_key(loot)

    if payload.item_image_alias is not None:
        loot.item_image_alias = payload.item_image_alias or None
    if payload.item_image_url_override is not None:
        if payload.item_image_url_override.strip():
            try:
                media_svc.validate_remote_url(payload.item_image_url_override.strip())
            except media_svc.UnsafeMediaError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
        loot.item_image_url_override = payload.item_image_url_override or None
    if payload.item_image_locked is not None:
        loot.item_image_locked = payload.item_image_locked

    if payload.clear_local_cache:
        media_svc.clear_asset(db, asset_key=previous_asset_key)
        loot.image_asset_id = None

    db.commit()

    asset_key = media_svc.build_loot_asset_key(loot)
    source_url = media_svc.build_loot_source_url(loot)
    asset_status = "no_source"
    if source_url:
        asset = await media_svc.refresh_asset(db, asset_key=asset_key, source_url=source_url)
        asset_status = (asset.status if asset else "failed")
        if asset and asset.id and not loot.image_asset_id:
            loot.image_asset_id = asset.id
            db.commit()

    return {
        "id": loot.id,
        "item_name": loot.item_name,
        "item_image_alias": loot.item_image_alias,
        "item_image_url_override": loot.item_image_url_override,
        "item_image_locked": loot.item_image_locked,
        "clear_local_cache": bool(payload.clear_local_cache),
        "asset_key": asset_key,
        "asset_status": asset_status,
    }


# ============================================================================
# SYSTEM OVERVIEW
# ============================================================================

@router.get("/overview/stats")
def get_overview_stats(db: Session = Depends(get_db), _admin: User = Depends(get_current_admin_user)):
    """Return aggregate system stats for the admin overview page."""
    total_creatures = db.query(Creature).count()
    visible_creatures = db.query(Creature).filter(Creature.is_hidden != True).count()
    hidden_creatures = total_creatures - visible_creatures
    total_hunt_zones = db.query(HuntZone).count()
    total_quests = db.query(Quest).count()
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active == True).count()
    admin_users = db.query(User).filter(User.is_superuser == True).count()

    return {
        "creatures": {
            "total": total_creatures,
            "visible": visible_creatures,
            "hidden": hidden_creatures,
        },
        "hunt_zones": {"total": total_hunt_zones},
        "quests": {"total": total_quests},
        "users": {
            "total": total_users,
            "active": active_users,
            "inactive": total_users - active_users,
            "admin": admin_users,
        },
    }
