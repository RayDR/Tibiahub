"""
Admin API endpoints - CRUD operations for creatures and hunt zones
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.db.database import get_db
from app.models import Creature, HuntZone, Loot, Element, SpawnLocation
from app.schemas import (
    CreatureCreate, Creature as CreatureSchema,
    HuntZoneCreate, HuntZone as HuntZoneSchema,
    LootCreate, Loot as LootSchema,
    ElementCreate, Element as ElementSchema
)

router = APIRouter()


# ============================================================================
# CREATURES ADMIN
# ============================================================================

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
    
    db_zone = HuntZone(**zone.model_dump())
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
    
    for key, value in zone.model_dump().items():
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
