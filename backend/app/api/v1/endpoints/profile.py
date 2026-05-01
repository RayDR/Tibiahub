from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import EmailStr
from typing import Optional
from datetime import datetime

from app.db.database import get_db
from app.models.user import User
from app.models.user_character import UserCharacter
from app.schemas.profile import ProfileResponse, ProfileUpdate
from app.core.security import get_password_hash
from app.api.v1.endpoints.auth import get_current_user

router = APIRouter()


@router.get("/me", response_model=ProfileResponse)
def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current user's profile with character info
    """
    # Get character info
    character = db.query(UserCharacter).filter(
        UserCharacter.user_id == current_user.id
    ).first()
    
    character_names = [char.character_name for char in getattr(current_user, "characters", [])]
    
    return ProfileResponse(
        username=current_user.username,
        email=current_user.email,
        tibia_character_name=current_user.tibia_character_name,
        guild_rank=current_user.guild_rank,
        vocation=current_user.vocation,
        level=current_user.level,
        is_active=current_user.is_active,
        join_date=current_user.join_date,
        created_at=current_user.created_at,
        characters=character_names
    )


@router.put("/me", response_model=ProfileResponse)
def update_my_profile(
    profile_in: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update current user's profile
    Only email and password can be updated by the user
    """
    if profile_in.email is not None:
        # Check if email is already taken
        existing = db.query(User).filter(
            User.email == profile_in.email,
            User.id != current_user.id
        ).first()
        
        if existing:
            raise HTTPException(status_code=400, detail="Email already in use")
        
        current_user.email = profile_in.email
    
    if profile_in.password is not None:
        current_user.hashed_password = get_password_hash(profile_in.password)
    
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    
    # Get character info
    character = db.query(UserCharacter).filter(
        UserCharacter.user_id == current_user.id
    ).first()
    
    character_names = [char.character_name for char in getattr(current_user, "characters", [])]
    
    return ProfileResponse(
        username=current_user.username,
        email=current_user.email,
        tibia_character_name=current_user.tibia_character_name,
        guild_rank=current_user.guild_rank,
        vocation=current_user.vocation,
        level=current_user.level,
        is_active=current_user.is_active,
        join_date=current_user.join_date,
        created_at=current_user.created_at,
        characters=character_names
    )


# Keep old endpoint for backwards compatibility
@router.get("/profile", response_model=ProfileResponse)
def get_profile(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Return the authenticated user's email and linked Tibia characters."""
    return get_my_profile(current_user, db)


@router.put("/profile", response_model=ProfileResponse)
def update_profile(
    profile_in: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update email and/or password for the authenticated user."""
    return update_my_profile(profile_in, current_user, db)

