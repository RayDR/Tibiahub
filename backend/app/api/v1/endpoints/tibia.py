"""
Tibia.com API integration endpoints
"""
from fastapi import APIRouter, HTTPException
from app.services.tibia_api import get_character_info, get_worlds, get_guild_info, TibiaAPIError

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
