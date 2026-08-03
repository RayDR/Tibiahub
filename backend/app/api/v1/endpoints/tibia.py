"""Tibia.com API integration endpoints."""

from fastapi import APIRouter, Depends, HTTPException

from app.api.v1.endpoints.auth import get_current_active_user, get_current_admin_user
from app.db.database import get_db
from app.models.user import User
from app.services.tibia_api import get_character_info, get_worlds, get_guild_info, TibiaAPIError
from app.services.tibia_sync_service import try_sync_user_character_snapshot
from sqlalchemy.orm import Session

router = APIRouter(prefix="/tibia", tags=["tibia-api"])

@router.get("/character/{character_name}")
async def get_character(character_name: str):
    """
    Fetch character information from Tibia.com API
    Example: /api/v1/tibia/character/Ray%20On
    """
    try:
        char_info = await get_character_info(character_name)
        if not char_info:
            raise HTTPException(status_code=404, detail=f"Character '{character_name}' not found")
        return char_info
    except TibiaAPIError as e:
        raise HTTPException(status_code=503, detail=f"Tibia API error: {str(e)}")


@router.post("/sync/me")
async def sync_my_character(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    if not current_user.primary_character or current_user.primary_character.ownership_status != "verified":
        raise HTTPException(status_code=409, detail="Select a verified primary character before synchronizing")
    payload, error = await try_sync_user_character_snapshot(db, current_user)
    if error:
        raise HTTPException(status_code=503, detail=error)
    return {"status": "ok", "character": payload}


@router.post("/sync/user/{user_id}")
async def sync_user_character(
    user_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    _ = current_user
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.primary_character or user.primary_character.ownership_status != "verified":
        raise HTTPException(status_code=409, detail="The account has no verified primary character")
    payload, error = await try_sync_user_character_snapshot(db, user)
    if error:
        raise HTTPException(status_code=503, detail=error)
    return {"status": "ok", "user_id": user.id, "character": payload}

@router.get("/worlds")
async def get_worlds_list():
    """
    Fetch list of available worlds from Tibia.com API
    """
    try:
        worlds = await get_worlds()
        return {"worlds": worlds, "count": len(worlds)}
    except TibiaAPIError as e:
        raise HTTPException(status_code=503, detail=f"Tibia API error: {str(e)}")

@router.get("/guild/{guild_name}")
async def get_guild(guild_name: str):
    """
    Fetch guild information from Tibia.com API
    Example: /api/v1/tibia/guild/Bloodborne%20Warhowl
    """
    try:
        guild_info = await get_guild_info(guild_name)
        if not guild_info:
            raise HTTPException(status_code=404, detail=f"Guild '{guild_name}' not found")
        return guild_info
    except TibiaAPIError as e:
        raise HTTPException(status_code=503, detail=f"Tibia API error: {str(e)}")
