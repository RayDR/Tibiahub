"""
Admin endpoints for user management and system monitoring
"""
from typing import List, Any, Optional
import requests
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime

from app.db.database import get_db
from app.models.user import User
from app.models.user_character import UserCharacter
from app.models.creature import Creature
from app.api.v1.endpoints.auth import get_current_admin_user, get_current_user
from app.services.tibia_validation_service import TibiaValidationService
from app.core import config, security
from app.schemas.admin import (
    TibiaAPIStatus, 
    UserWithCharacters, 
    SystemSettings,
    UpdateSystemSettings,
    UserUpdate,
    GuildSyncResult
)

router = APIRouter()


def get_admin_or_guild_leader(current_user: User = Depends(get_current_user)):
    """Allow superusers or guild leaders to manage shared settings."""
    allowed_ranks = {"alpha warbringer", "bloodhowl marshal", "guild leader"}
    if current_user.is_superuser or (current_user.guild_rank and current_user.guild_rank.lower() in allowed_ranks):
        return current_user
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")


@router.get("/tibia-api-status", response_model=TibiaAPIStatus)
def get_tibia_api_status(
    current_user: User = Depends(get_current_admin_user)
):
    """
    Check the status of Tibia API
    Requires admin privileges
    """
    status_info = TibiaValidationService.check_api_status()
    
    return TibiaAPIStatus(
        status=status_info["status"],
        latency_ms=status_info.get("latency_ms"),
        cached=status_info["cached"],
        last_check=status_info["last_check"],
        message=status_info["message"]
    )


@router.get("/users", response_model=List[UserWithCharacters])
def get_all_users(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100
):
    """
    Get list of all users with their linked characters
    Requires admin privileges
    """
    users = db.query(User).offset(skip).limit(limit).all()
    
    result = []
    for user in users:
        characters = db.query(UserCharacter).filter(
            UserCharacter.user_id == user.id
        ).all()
        
        result.append(
            UserWithCharacters(
                id=user.id,
                username=user.username,
                email=user.email,
                guild_rank=user.guild_rank,
                is_active=user.is_active,
                is_superuser=user.is_superuser,
                join_date=user.join_date,
                created_at=user.created_at,
                characters=[
                    {
                        "character_name": char.character_name,
                        "level": char.level,
                        "vocation": char.vocation,
                        "last_seen": char.last_seen
                    }
                    for char in characters
                ]
            )
        )
    
    return result


@router.get("/users/{user_id}", response_model=UserWithCharacters)
def get_user_detail(
    user_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Get detailed information about a specific user
    Requires admin privileges
    """
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    characters = db.query(UserCharacter).filter(
        UserCharacter.user_id == user.id
    ).all()
    
    return UserWithCharacters(
        id=user.id,
        username=user.username,
        email=user.email,
        guild_rank=user.guild_rank,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        join_date=user.join_date,
        created_at=user.created_at,
        characters=[
            {
                "character_name": char.character_name,
                "level": char.level,
                "vocation": char.vocation,
                "last_seen": char.last_seen
            }
            for char in characters
        ]
    )


@router.get("/stats")
def get_stats(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Get system statistics
    Requires admin privileges
    """
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active == True).count()
    total_characters = db.query(UserCharacter).count()
    admin_users = db.query(User).filter(User.is_superuser == True).count()
    
    # Get guild rank distribution
    guild_ranks = {}
    for user in db.query(User).all():
        rank = user.guild_rank or "No Rank"
        guild_ranks[rank] = guild_ranks.get(rank, 0) + 1
    
    return {
        "total_users": total_users,
        "active_users": active_users,
        "inactive_users": total_users - active_users,
        "admin_users": admin_users,
        "total_characters_linked": total_characters,
        "guild_ranks": [{"rank": rank, "count": count} for rank, count in guild_ranks.items()]
    }


@router.get("/settings", response_model=SystemSettings)
def get_system_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_or_guild_leader)
):
    """
    Get current system settings
    Requires admin privileges
    """
    from app.models.settings import SystemSettings as SettingsModel
    
    # Get Discord settings from database
    discord_webhook = db.query(SettingsModel).filter(SettingsModel.key == "discord_webhook_url").first()
    discord_auto_post = db.query(SettingsModel).filter(SettingsModel.key == "discord_auto_post").first()
    
    return SystemSettings(
        tibia_validation_enabled=config.settings.TIBIA_VALIDATION_ENABLED,
        tibia_validation_strict=config.settings.TIBIA_VALIDATION_STRICT,
        discord_webhook_url=discord_webhook.value if discord_webhook else "",
        discord_auto_post=discord_auto_post.value == "1" if discord_auto_post else False,
        access_token_expire_minutes=config.settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )


@router.put("/settings", response_model=SystemSettings)
def update_system_settings(
    settings_update: UpdateSystemSettings,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_or_guild_leader)
):
    """
    Update system settings
    Requires admin privileges
    """
    from app.models.settings import SystemSettings as SettingsModel
    from app.services.discord import set_discord_webhook
    
    if settings_update.tibia_validation_enabled is not None:
        config.settings.TIBIA_VALIDATION_ENABLED = settings_update.tibia_validation_enabled
    
    if settings_update.tibia_validation_strict is not None:
        config.settings.TIBIA_VALIDATION_STRICT = settings_update.tibia_validation_strict
    
    # Update Discord settings in database
    if settings_update.discord_webhook_url is not None:
        webhook_setting = db.query(SettingsModel).filter(SettingsModel.key == "discord_webhook_url").first()
        if webhook_setting:
            webhook_setting.value = settings_update.discord_webhook_url
            set_discord_webhook(settings_update.discord_webhook_url)
        db.commit()
    
    if settings_update.discord_auto_post is not None:
        auto_post_setting = db.query(SettingsModel).filter(SettingsModel.key == "discord_auto_post").first()
        if auto_post_setting:
            auto_post_setting.value = "1" if settings_update.discord_auto_post else "0"
        db.commit()
    
    # Get updated values
    discord_webhook = db.query(SettingsModel).filter(SettingsModel.key == "discord_webhook_url").first()
    discord_auto_post = db.query(SettingsModel).filter(SettingsModel.key == "discord_auto_post").first()
    
    return SystemSettings(
        tibia_validation_enabled=config.settings.TIBIA_VALIDATION_ENABLED,
        tibia_validation_strict=config.settings.TIBIA_VALIDATION_STRICT,
        discord_webhook_url=discord_webhook.value if discord_webhook else "",
        discord_auto_post=discord_auto_post.value == "1" if discord_auto_post else False
    )


@router.put("/users/{user_id}", response_model=UserWithCharacters)
def update_user(
    user_id: int,
    user_update: UserUpdate,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Update user information
    Requires admin privileges
    """
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Update fields if provided
    if user_update.username is not None:
        # Check if username is already taken
        existing = db.query(User).filter(User.username == user_update.username, User.id != user_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="Username already taken")
        user.username = user_update.username
    
    if user_update.email is not None:
        user.email = user_update.email
    
    if user_update.guild_rank is not None:
        user.guild_rank = user_update.guild_rank
    
    if user_update.is_active is not None:
        user.is_active = user_update.is_active
    
    if user_update.is_superuser is not None:
        user.is_superuser = user_update.is_superuser
    
    if user_update.password is not None:
        user.hashed_password = security.get_password_hash(user_update.password)
    
    db.commit()
    db.refresh(user)
    
    # Get characters
    characters = db.query(UserCharacter).filter(UserCharacter.user_id == user.id).all()
    
    return UserWithCharacters(
        id=user.id,
        username=user.username,
        email=user.email,
        guild_rank=user.guild_rank,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        join_date=user.join_date,
        created_at=user.created_at,
        characters=[
            {
                "character_name": char.character_name,
                "level": char.level,
                "vocation": char.vocation,
                "last_seen": char.last_seen
            }
            for char in characters
        ]
    )


@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Delete a user and their characters
    Requires admin privileges
    """
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Prevent deleting yourself
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    
    # Delete user characters
    db.query(UserCharacter).filter(UserCharacter.user_id == user_id).delete()
    
    # Delete user
    db.delete(user)
    db.commit()
    
    return {"message": f"User {user.username} deleted successfully"}


@router.put("/users/{user_id}/character")
def update_user_character(
    user_id: int,
    character_name: str,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Update the character linked to a user account
    Validates the character exists in Tibia (but allows saving even if validation fails)
    Prevents linking if character is already linked to another account
    Requires admin privileges
    """
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if character is already linked to another user
    existing_link = db.query(UserCharacter).filter(
        UserCharacter.character_name.ilike(character_name),
        UserCharacter.user_id != user_id
    ).first()
    
    if existing_link:
        linked_user = db.query(User).filter(User.id == existing_link.user_id).first()
        raise HTTPException(
            status_code=400, 
            detail=f"Character '{character_name}' is already linked to user '{linked_user.username}' (ID: {linked_user.id})"
        )
    
    # Try to validate character (but don't block if it fails)
    validation_passed = False
    validation_message = ""
    char_data = None
    
    try:
        is_valid, char_data, error_msg = TibiaValidationService.validate_character(character_name, strict=False)
        validation_passed = is_valid
        if not is_valid:
            validation_message = error_msg or "Character validation failed"
    except Exception as e:
        validation_message = f"Validation error: {str(e)}"
    
    # Update or create character link
    char_link = db.query(UserCharacter).filter(UserCharacter.user_id == user_id).first()
    
    if char_link:
        # Update existing character
        char_link.character_name = character_name
        if char_data:
            char_link.level = char_data.get("level")
            char_link.vocation = char_data.get("vocation")
    else:
        # Create new character link
        char_link = UserCharacter(
            user_id=user_id,
            character_name=character_name,
            level=char_data.get("level") if char_data else None,
            vocation=char_data.get("vocation") if char_data else None
        )
        db.add(char_link)
    
    db.commit()
    db.refresh(char_link)
    
    return {
        "success": True,
        "message": "Character updated successfully",
        "character_name": character_name,
        "validation_passed": validation_passed,
        "validation_message": validation_message if not validation_passed else None,
        "character_data": {
            "level": char_link.level,
            "vocation": char_link.vocation,
        }
    }


@router.post("/sync-guild", response_model=GuildSyncResult)
def sync_guild_members(
    guild_name: str = "Bloodborne Warhowl",
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Synchronize guild members from Tibia API
    Fetches guild data and updates character information
    Requires admin privileges
    """
    try:
        # Fetch guild data from Tibia API
        response = requests.get(
            f"https://api.tibiadata.com/v4/guild/{guild_name}",
            timeout=15
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to fetch guild data. Status: {response.status_code}"
            )
        
        data = response.json()
        
        if "guild" not in data or "members" not in data["guild"]:
            raise HTTPException(
                status_code=404,
                detail="Guild not found or invalid response from Tibia API"
            )
        
        guild_data = data["guild"]
        members = guild_data.get("members", [])
        
        synced_count = 0
        new_characters = 0
        updated_characters = 0
        invalid_users = []
        
        # Process each guild member
        for member in members:
            character_name = member.get("name")
            rank = member.get("rank")
            level = member.get("level")
            vocation = member.get("vocation")
            
            if not character_name:
                continue
            
            # Find or create character
            char = db.query(UserCharacter).filter(
                UserCharacter.character_name == character_name
            ).first()
            
            if char:
                # Update existing character
                char.level = level
                char.vocation = vocation
                char.last_seen = datetime.utcnow()
                updated_characters += 1
                
                # Update user's guild rank if they have a linked account
                if char.user:
                    char.user.guild_rank = rank
                    synced_count += 1
            else:
                # Check if this character should be linked to a user
                # For now, just track it as a potential new character
                new_characters += 1
        
        # Find users with characters not in the guild
        all_user_chars = db.query(UserCharacter).all()
        guild_char_names = [m.get("name") for m in members]
        
        for char in all_user_chars:
            if char.character_name not in guild_char_names and char.user:
                invalid_users.append({
                    "user_id": char.user.id,
                    "username": char.user.username,
                    "character_name": char.character_name,
                    "reason": "Character not found in guild"
                })
        
        db.commit()
        
        return GuildSyncResult(
            success=True,
            guild_name=guild_name,
            total_members=len(members),
            synced_users=synced_count,
            updated_characters=updated_characters,
            new_characters=new_characters,
            invalid_users=invalid_users,
            message=f"Successfully synced {synced_count} users with guild {guild_name}"
        )
        
    except requests.exceptions.RequestException as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error connecting to Tibia API: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error syncing guild: {str(e)}"
        )


@router.get("/api-monitor")
def get_external_apis_status(
    current_user: User = Depends(get_current_admin_user)
):
    """
    Monitor external API statuses and retrieve sample data
    Tests: TibiaWiki, Tibia.com API, TibiaData
    Requires admin privileges
    """
    import time
    apis_status = []
    
    # 1. Tibia.com Official API
    try:
        start = time.time()
        response = requests.get(
            "https://api.tibia.com/v1/worlds",
            timeout=10,
            headers={'User-Agent': 'TibiaWeeklyTasks/1.0'}
        )
        latency = int((time.time() - start) * 1000)
        
        if response.status_code == 200:
            data = response.json()
            apis_status.append({
                "name": "Tibia.com Official API",
                "url": "https://api.tibia.com/v1/worlds",
                "status": "online",
                "status_code": 200,
                "latency_ms": latency,
                "sample_data": {
                    "worlds_count": len(data.get("worlds", {}).get("regular_worlds", [])),
                    "first_3_worlds": [w.get("name") for w in data.get("worlds", {}).get("regular_worlds", [])[:3]]
                },
                "full_response": data
            })
        else:
            apis_status.append({
                "name": "Tibia.com Official API",
                "url": "https://api.tibia.com/v1/worlds",
                "status": "error",
                "status_code": response.status_code,
                "latency_ms": latency,
                "error": f"HTTP {response.status_code} - Server returned error"
            })
    except requests.exceptions.Timeout:
        apis_status.append({
            "name": "Tibia.com Official API",
            "url": "https://api.tibia.com/v1/worlds",
            "status": "offline",
            "error": "Request timeout (>10s) - API may be down or slow"
        })
    except requests.exceptions.ConnectionError as e:
        apis_status.append({
            "name": "Tibia.com Official API",
            "url": "https://api.tibia.com/v1/worlds",
            "status": "offline",
            "error": f"Connection failed - DNS or network issue: {str(e)[:100]}"
        })
    except Exception as e:
        apis_status.append({
            "name": "Tibia.com Official API",
            "url": "https://api.tibia.com/v1/worlds",
            "status": "offline",
            "error": f"Unexpected error: {str(e)[:100]}"
        })
    
    # 2. TibiaData API
    try:
        start = time.time()
        response = requests.get(
            "https://api.tibiadata.com/v4/worlds",
            timeout=10,
            headers={'User-Agent': 'TibiaWeeklyTasks/1.0'}
        )
        latency = int((time.time() - start) * 1000)
        
        if response.status_code == 200:
            data = response.json()
            worlds = data.get("worlds", {}).get("regular_worlds", [])
            apis_status.append({
                "name": "TibiaData API",
                "url": "https://api.tibiadata.com/v4/worlds",
                "status": "online",
                "status_code": 200,
                "latency_ms": latency,
                "sample_data": {
                    "worlds_count": len(worlds),
                    "first_3_worlds": [w.get("name") for w in worlds[:3]]
                },
                "full_response": data
            })
        else:
            apis_status.append({
                "name": "TibiaData API",
                "url": "https://api.tibiadata.com/v4/worlds",
                "status": "error",
                "status_code": response.status_code,
                "latency_ms": latency,
                "error": f"HTTP {response.status_code} - Proxy/server error (check api.tibiadata.com status)"
            })
    except requests.exceptions.Timeout:
        apis_status.append({
            "name": "TibiaData API",
            "url": "https://api.tibiadata.com/v4/worlds",
            "status": "offline",
            "error": "Request timeout (>10s) - API overloaded or down"
        })
    except requests.exceptions.ConnectionError as e:
        apis_status.append({
            "name": "TibiaData API",
            "url": "https://api.tibiadata.com/v4/worlds",
            "status": "offline",
            "error": f"Connection failed - Network/DNS issue: {str(e)[:100]}"
        })
    except Exception as e:
        apis_status.append({
            "name": "TibiaData API",
            "url": "https://api.tibiadata.com/v4/worlds",
            "status": "offline",
            "error": f"Unexpected error: {str(e)[:100]}"
        })
    
    # 3. TibiaWiki API (MediaWiki)
    try:
        start = time.time()
        response = requests.get(
            "https://tibia.fandom.com/api.php",
            params={
                "action": "query",
                "format": "json",
                "list": "allpages",
                "aplimit": 3,
                "apnamespace": 0
            },
            timeout=10,
            headers={'User-Agent': 'TibiaWeeklyTasks/1.0'}
        )
        latency = int((time.time() - start) * 1000)
        
        if response.status_code == 200:
            data = response.json()
            pages = data.get("query", {}).get("allpages", [])
            apis_status.append({
                "name": "TibiaWiki (Fandom)",
                "url": "https://tibia.fandom.com/api.php",
                "status": "online",
                "status_code": 200,
                "latency_ms": latency,
                "sample_data": {
                    "pages_count": len(pages),
                    "sample_pages": [p.get("title") for p in pages]
                },
                "full_response": data
            })
        else:
            apis_status.append({
                "name": "TibiaWiki (Fandom)",
                "url": "https://tibia.fandom.com/api.php",
                "status": "error",
                "status_code": response.status_code,
                "latency_ms": latency,
                "error": f"HTTP {response.status_code} - Fandom API error"
            })
    except requests.exceptions.Timeout:
        apis_status.append({
            "name": "TibiaWiki (Fandom)",
            "url": "https://tibia.fandom.com/api.php",
            "status": "offline",
            "error": "Request timeout (>10s) - Fandom may be slow"
        })
    except requests.exceptions.ConnectionError as e:
        apis_status.append({
            "name": "TibiaWiki (Fandom)",
            "url": "https://tibia.fandom.com/api.php",
            "status": "offline",
            "error": f"Connection failed: {str(e)[:100]}"
        })
    except Exception as e:
        apis_status.append({
            "name": "TibiaWiki (Fandom)",
            "url": "https://tibia.fandom.com/api.php",
            "status": "offline",
            "error": f"Unexpected error: {str(e)[:100]}"
        })
    
    # 4. Our own backend health check
    try:
        from app.db.database import SessionLocal
        db = SessionLocal()
        creature_count = db.query(func.count(Creature.id)).scalar()
        db.close()
        
        apis_status.append({
            "name": "TibiaHub Database",
            "url": "internal",
            "status": "online",
            "status_code": 200,
            "latency_ms": 0,
            "sample_data": {
                "creature_count": creature_count,
                "database": "SQLite",
                "status": "healthy"
            }
        })
    except Exception as e:
        apis_status.append({
            "name": "TibiaHub Database",
            "url": "internal",
            "status": "error",
            "error": str(e)
        })
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "total_apis": len(apis_status),
        "online_count": len([a for a in apis_status if a["status"] == "online"]),
        "apis": apis_status
    }

