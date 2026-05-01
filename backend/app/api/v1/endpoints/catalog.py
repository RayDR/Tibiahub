"""
Unified Catalog Endpoints (Hunts, Quests, Custom)
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_
from typing import List, Optional
from datetime import datetime

from app.db.database import get_db
from app.models.catalog import Catalog
from app.models.user import User
from app.api.v1.endpoints.auth import get_current_user, get_current_admin_user

router = APIRouter()


@router.get("/", response_model=List[dict])
def get_catalog_items(
    type: Optional[str] = None,
    level_min: Optional[int] = None,
    level_max: Optional[int] = None,
    vocation: Optional[str] = None,
    location: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get catalog items with optional filtering"""
    query = db.query(Catalog).filter(Catalog.is_active == True)
    
    if type:
        query = query.filter(Catalog.type == type)
    
    if level_min is not None:
        query = query.filter(Catalog.level_min >= level_min)
    
    if level_max is not None:
        query = query.filter(Catalog.level_max <= level_max)
    
    if vocation:
        query = query.filter(or_(
            Catalog.vocation == vocation,
            Catalog.vocation == 'All',
            Catalog.vocation == None
        ))
    
    if location:
        query = query.filter(Catalog.location.ilike(f'%{location}%'))
    
    items = query.order_by(desc(Catalog.created_at)).offset(skip).limit(limit).all()
    
    return [
        {
            "id": item.id,
            "type": item.type,
            "name": item.name,
            "location": item.location,
            "level_min": item.level_min,
            "level_max": item.level_max,
            "vocation": item.vocation,
            "exp_per_hour": item.exp_per_hour,
            "profit_per_hour": item.profit_per_hour,
            "creatures": item.creatures,
            "quest_reward": item.quest_reward,
            "quest_requirements": item.quest_requirements,
            "strategy": item.strategy,
            "notes": item.notes,
            "difficulty": item.difficulty,
            "is_active": item.is_active,
            "created_at": item.created_at,
            "updated_at": item.updated_at
        }
        for item in items
    ]


@router.get("/{catalog_id}", response_model=dict)
def get_catalog_item(
    catalog_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific catalog item"""
    item = db.query(Catalog).filter(Catalog.id == catalog_id, Catalog.is_active == True).first()
    if not item:
        raise HTTPException(status_code=404, detail="Catalog item not found")
    
    return {
        "id": item.id,
        "type": item.type,
        "name": item.name,
        "location": item.location,
        "level_min": item.level_min,
        "level_max": item.level_max,
        "vocation": item.vocation,
        "exp_per_hour": item.exp_per_hour,
        "profit_per_hour": item.profit_per_hour,
        "creatures": item.creatures,
        "quest_reward": item.quest_reward,
        "quest_requirements": item.quest_requirements,
        "strategy": item.strategy,
        "notes": item.notes,
        "difficulty": item.difficulty,
        "is_active": item.is_active,
        "created_at": item.created_at,
        "updated_at": item.updated_at
    }


@router.post("/", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_catalog_item(
    item_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Create a new catalog item (admin only)"""
    new_item = Catalog(**item_data)
    
    db.add(new_item)
    db.commit()
    db.refresh(new_item)
    
    return {
        "id": new_item.id,
        "type": new_item.type,
        "name": new_item.name,
        "location": new_item.location,
        "level_min": new_item.level_min,
        "level_max": new_item.level_max,
        "vocation": new_item.vocation,
        "exp_per_hour": new_item.exp_per_hour,
        "profit_per_hour": new_item.profit_per_hour,
        "creatures": new_item.creatures,
        "quest_reward": new_item.quest_reward,
        "quest_requirements": new_item.quest_requirements,
        "strategy": new_item.strategy,
        "notes": new_item.notes,
        "difficulty": new_item.difficulty,
        "is_active": new_item.is_active,
        "created_at": new_item.created_at,
        "updated_at": new_item.updated_at
    }


@router.put("/{catalog_id}", response_model=dict)
def update_catalog_item(
    catalog_id: int,
    item_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Update a catalog item (admin only)"""
    item = db.query(Catalog).filter(Catalog.id == catalog_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Catalog item not found")
    
    for key, value in item_data.items():
        if hasattr(item, key):
            setattr(item, key, value)
    
    item.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(item)
    
    return get_catalog_item(catalog_id, db, current_user)


@router.delete("/{catalog_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_catalog_item(
    catalog_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Delete a catalog item (admin only)"""
    item = db.query(Catalog).filter(Catalog.id == catalog_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Catalog item not found")
    
    item.is_active = False
    db.commit()
    return
