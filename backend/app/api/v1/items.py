"""
Items/Loot API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional

from app.db.database import get_db
from app.models import Loot as LootModel
from app.models import Creature as CreatureModel
from app.schemas import LootWithCreature

router = APIRouter(prefix="/items", tags=["items"])


@router.get("/", response_model=List[LootWithCreature])
async def search_items(
    search: str = Query(..., min_length=2, description="Search term for item name"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Search for items/loot by name.
    Returns list of drops with the creature that drops them.
    """
    # Join with Creature to get the creature details efficiently
    query = db.query(LootModel).join(CreatureModel).options(joinedload(LootModel.creature))
    
    if search:
        query = query.filter(LootModel.item_name.ilike(f"%{search}%"))
    
    # Order by rarity (common first? or rare first?) and percentage
    # Let's order by exact match first, then by percentage descending
    items = query.order_by(LootModel.percentage.desc()).offset(skip).limit(limit).all()
    
    return items
