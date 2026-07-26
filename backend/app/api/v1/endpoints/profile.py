from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session
from pydantic import EmailStr
from typing import Optional
from datetime import UTC, datetime

from app.db.database import get_db
from app.models.user import User
from app.models.user_character import UserCharacter
from app.models.auth_security import AuthOneTimeToken
from app.schemas.profile import ProfileResponse, ProfileUpdate
from app.core.security import get_password_hash, verify_password
from app.api.v1.endpoints.auth import get_current_active_user

router = APIRouter()


@router.get("/me", response_model=ProfileResponse)
def get_my_profile(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get current user's profile with character info
    """
    verified_characters = [char for char in getattr(current_user, "characters", []) if char.ownership_status == "verified"]
    character_names = [char.character_name for char in verified_characters]
    primary_name = current_user.tibia_character_name if any(char.character_name.casefold() == (current_user.tibia_character_name or "").casefold() for char in verified_characters) else None
    
    return ProfileResponse(
        username=current_user.username,
        display_name=current_user.display_name,
        title=current_user.title,
        email=current_user.email,
        email_verified_at=current_user.email_verified_at,
        avatar_url=current_user.avatar_url,
        tibia_character_name=primary_name,
        guild_rank=current_user.guild_rank,
        guild_name=current_user.guild_name,
        world_name=current_user.world_name,
        residence=current_user.residence,
        achievement_points=current_user.achievement_points,
        last_login_at=current_user.last_login_at,
        tibia_status=current_user.tibia_status,
        tibia_last_error=current_user.tibia_last_error,
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
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Update current user's profile
    Only email and password can be updated by the user
    """
    if profile_in.email is not None:
        # Check if email is already taken
        normalized_email = str(profile_in.email).strip().casefold()
        existing = db.query(User).filter(
            func.lower(User.email) == normalized_email,
            User.id != current_user.id
        ).first()
        
        if existing:
            raise HTTPException(status_code=400, detail="Email already in use")
        
        if normalized_email != (current_user.email or "").strip().casefold():
            current_user.email = normalized_email
            current_user.email_verified_at = None
            db.query(AuthOneTimeToken).filter(
                AuthOneTimeToken.user_id == current_user.id,
                AuthOneTimeToken.consumed_at.is_(None),
                AuthOneTimeToken.invalidated_at.is_(None),
            ).update({AuthOneTimeToken.invalidated_at: datetime.now(UTC)}, synchronize_session=False)

    if profile_in.display_name is not None:
        current_user.display_name = profile_in.display_name.strip() or None

    if profile_in.title is not None:
        current_user.title = profile_in.title.strip() or None

    if profile_in.avatar_url is not None:
        current_user.avatar_url = profile_in.avatar_url or None

    new_password = profile_in.new_password
    if new_password is not None:
        if profile_in.new_password is not None:
            if not profile_in.current_password:
                raise HTTPException(status_code=400, detail="Current password is required")
            if not verify_password(profile_in.current_password, current_user.hashed_password):
                raise HTTPException(status_code=400, detail="Current password is invalid")
        current_user.hashed_password = get_password_hash(new_password)
        db.query(AuthOneTimeToken).filter(
            AuthOneTimeToken.user_id == current_user.id,
            AuthOneTimeToken.consumed_at.is_(None),
            AuthOneTimeToken.invalidated_at.is_(None),
        ).update({AuthOneTimeToken.invalidated_at: datetime.now(UTC)}, synchronize_session=False)
    
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    
    verified_characters = [char for char in getattr(current_user, "characters", []) if char.ownership_status == "verified"]
    character_names = [char.character_name for char in verified_characters]
    primary_name = current_user.tibia_character_name if any(char.character_name.casefold() == (current_user.tibia_character_name or "").casefold() for char in verified_characters) else None
    
    return ProfileResponse(
        username=current_user.username,
        display_name=current_user.display_name,
        title=current_user.title,
        email=current_user.email,
        email_verified_at=current_user.email_verified_at,
        avatar_url=current_user.avatar_url,
        tibia_character_name=primary_name,
        guild_rank=current_user.guild_rank,
        guild_name=current_user.guild_name,
        world_name=current_user.world_name,
        residence=current_user.residence,
        achievement_points=current_user.achievement_points,
        last_login_at=current_user.last_login_at,
        tibia_status=current_user.tibia_status,
        tibia_last_error=current_user.tibia_last_error,
        vocation=current_user.vocation,
        level=current_user.level,
        is_active=current_user.is_active,
        join_date=current_user.join_date,
        created_at=current_user.created_at,
        characters=character_names
    )


# Keep old endpoint for backwards compatibility
@router.get("/profile", response_model=ProfileResponse)
def get_profile(current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    """Return the authenticated user's email and linked Tibia characters."""
    return get_my_profile(current_user, db)


@router.put("/profile", response_model=ProfileResponse)
def update_profile(
    profile_in: ProfileUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Update email and/or password for the authenticated user."""
    return update_my_profile(profile_in, current_user, db)
