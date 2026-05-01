"""
Creatures API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.database import get_db
from app.models import Creature as CreatureModel
from app.schemas import Creature, CreatureSimple, CreatureCreate

router = APIRouter(prefix="/creatures", tags=["creatures"])


@router.get("/", response_model=List[CreatureSimple])
async def get_creatures(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    search: Optional[str] = None,
    difficulty: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get list of creatures with optional filters"""
    query = db.query(CreatureModel)
    
    if search:
        query = query.filter(CreatureModel.name.ilike(f"%{search}%"))
    
    if difficulty:
        query = query.filter(CreatureModel.difficulty == difficulty)
    
    creatures = query.offset(skip).limit(limit).all()
    return creatures


@router.get("/{creature_id}", response_model=Creature)
async def get_creature(creature_id: int, db: Session = Depends(get_db)):
    """Get detailed information about a specific creature"""
    creature = db.query(CreatureModel).filter(CreatureModel.id == creature_id).first()
    
    if not creature:
        raise HTTPException(status_code=404, detail="Creature not found")
    
    return creature


@router.get("/name/{creature_name}", response_model=Creature)
async def get_creature_by_name(creature_name: str, db: Session = Depends(get_db)):
    """Get detailed information about a creature by name"""
    creature = db.query(CreatureModel).filter(
        CreatureModel.name.ilike(creature_name)
    ).first()
    
    if not creature:
        raise HTTPException(status_code=404, detail="Creature not found")
    
    return creature


@router.post("/", response_model=Creature, status_code=201)
async def create_creature(
    creature: CreatureCreate,
    db: Session = Depends(get_db)
):
    """Create a new creature"""
    # Check if creature already exists
    existing = db.query(CreatureModel).filter(
        CreatureModel.name == creature.name
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Creature already exists")
    
    db_creature = CreatureModel(**creature.dict())
    db.add(db_creature)
    db.commit()
    db.refresh(db_creature)
    
    return db_creature


from fastapi.responses import StreamingResponse
import urllib.request

@router.get("/{creature_id}/image")
async def get_creature_image(creature_id: int, db: Session = Depends(get_db)):
    """Proxy creature image to bypass hotlink protection"""
    creature = db.query(CreatureModel).filter(CreatureModel.id == creature_id).first()
    
    if not creature or not creature.image_url:
        raise HTTPException(status_code=404, detail="Image not found")
        
    try:
        # Create request with browser-like headers
        req = urllib.request.Request(
            creature.image_url, 
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Referer': 'https://tibia.fandom.com/'
            }
        )
        
        def iterfile():
            with urllib.request.urlopen(req) as response:
                while chunk := response.read(8192):
                    yield chunk
                    
        return StreamingResponse(iterfile(), media_type="image/gif")
    except Exception as e:
        print(f"Error fetching image: {e}")
        # Return a fallback image or 404
        raise HTTPException(status_code=404, detail=f"Image source unavailable: {str(e)}")
