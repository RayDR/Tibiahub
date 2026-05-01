from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from typing import List, Optional
from jose import JWTError, jwt
from app.db.database import get_db
from app.models.hunt import HuntCatalog
from app.schemas.hunt import Hunt, HuntCreate, HuntUpdate
from app.models.user import User
from app.core.config import settings

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception
    return user

def get_current_active_user(current_user: User = Depends(get_current_user)):
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

def get_current_superuser(current_user: User = Depends(get_current_active_user)):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough privileges")
    return current_user

@router.get("/", response_model=List[Hunt])
async def get_hunts(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    level_min: Optional[int] = None,
    level_max: Optional[int] = None,
    vocation: Optional[str] = None,
    location: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get list of hunts with optional filters"""
    query = db.query(HuntCatalog)
    
    # Apply filters
    if level_min is not None:
        query = query.filter(HuntCatalog.level_max >= level_min)
    if level_max is not None:
        query = query.filter(HuntCatalog.level_min <= level_max)
    if vocation:
        query = query.filter(HuntCatalog.vocation.contains(vocation))
    if location:
        query = query.filter(HuntCatalog.location.contains(location))
    
    hunts = query.order_by(HuntCatalog.level_min).offset(skip).limit(limit).all()
    return hunts

@router.get("/{hunt_id}", response_model=Hunt)
async def get_hunt(
    hunt_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get a specific hunt by ID"""
    hunt = db.query(HuntCatalog).filter(HuntCatalog.id == hunt_id).first()
    if not hunt:
        raise HTTPException(status_code=404, detail="Hunt not found")
    return hunt

@router.post("/", response_model=Hunt)
async def create_hunt(
    hunt: HuntCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser)
):
    """Create a new hunt (admin only)"""
    db_hunt = HuntCatalog(**hunt.dict())
    db.add(db_hunt)
    db.commit()
    db.refresh(db_hunt)
    return db_hunt

@router.put("/{hunt_id}", response_model=Hunt)
async def update_hunt(
    hunt_id: int,
    hunt: HuntUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser)
):
    """Update a hunt (admin only)"""
    db_hunt = db.query(HuntCatalog).filter(HuntCatalog.id == hunt_id).first()
    if not db_hunt:
        raise HTTPException(status_code=404, detail="Hunt not found")
    
    for key, value in hunt.dict(exclude_unset=True).items():
        setattr(db_hunt, key, value)
    
    db.commit()
    db.refresh(db_hunt)
    return db_hunt

@router.delete("/{hunt_id}")
async def delete_hunt(
    hunt_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser)
):
    """Delete a hunt (admin only)"""
    db_hunt = db.query(HuntCatalog).filter(HuntCatalog.id == hunt_id).first()
    if not db_hunt:
        raise HTTPException(status_code=404, detail="Hunt not found")
    
    db.delete(db_hunt)
    db.commit()
    return {"message": "Hunt deleted successfully"}
