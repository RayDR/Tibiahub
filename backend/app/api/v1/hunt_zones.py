"""
Hunt Zones API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.database import get_db
from app.models import HuntZone as HuntZoneModel
from app.schemas import HuntZone, HuntZoneCreate, HuntRecommendation
from app.services.hunt_service import HuntRecommendationService

router = APIRouter(prefix="/hunt-zones", tags=["hunt-zones"])


@router.get("/", response_model=List[HuntZone])
async def get_hunt_zones(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    min_level: Optional[int] = None,
    max_level: Optional[int] = None,
    city: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get list of hunt zones with optional filters"""
    query = db.query(HuntZoneModel)
    
    if min_level is not None:
        query = query.filter(HuntZoneModel.min_level >= min_level)
    
    if max_level is not None:
        query = query.filter(
            (HuntZoneModel.max_level.is_(None)) | (HuntZoneModel.max_level <= max_level)
        )
    
    if city:
        query = query.filter(HuntZoneModel.city.ilike(f"%{city}%"))

    if search:
        query = query.filter(
            (HuntZoneModel.name.ilike(f"%{search}%")) |
            (HuntZoneModel.city.ilike(f"%{search}%"))
        )
    
    zones = query.offset(skip).limit(limit).all()
    return zones


@router.get("/{zone_id}", response_model=HuntZone)
async def get_hunt_zone(zone_id: int, db: Session = Depends(get_db)):
    """Get detailed information about a specific hunt zone"""
    zone = db.query(HuntZoneModel).filter(HuntZoneModel.id == zone_id).first()
    
    if not zone:
        raise HTTPException(status_code=404, detail="Hunt zone not found")
    
    return zone


@router.get("/recommendations/{vocation}", response_model=List[HuntRecommendation])
async def get_hunt_recommendations(
    vocation: str,
    level: int = Query(..., ge=1, le=2000),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """
    Get hunt zone recommendations for a specific vocation and level
    
    - **vocation**: knight, paladin, sorcerer, druid, or monk
    - **level**: Player level (1-2000)
    - **limit**: Maximum number of recommendations (default: 10)
    """
    try:
        recommendations = HuntRecommendationService.get_recommendations(
            db, vocation, level, limit
        )
        return recommendations
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/", response_model=HuntZone, status_code=201)
async def create_hunt_zone(
    zone: HuntZoneCreate,
    db: Session = Depends(get_db)
):
    """Create a new hunt zone"""
    existing = db.query(HuntZoneModel).filter(
        HuntZoneModel.name == zone.name
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Hunt zone already exists")
    
    db_zone = HuntZoneModel(**zone.dict())
    db.add(db_zone)
    db.commit()
    db.refresh(db_zone)
    
    return db_zone
