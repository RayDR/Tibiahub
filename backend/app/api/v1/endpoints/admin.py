"""
Admin endpoints for user management and system monitoring
"""
from typing import List, Any, Optional
import requests
from pathlib import Path
import hashlib
import re

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import UTC, datetime

from app.db.database import get_db
from app.models.user import User
from app.models.user_character import UserCharacter
from app.models.creature import Creature
from app.models.events import Event
from app.models.raffle import Raffle
from app.models.workspace_audit import WorkspaceAudit
from app.api.v1.endpoints.auth import get_current_admin_user, get_current_user
from app.core.permissions import can_manage_guild, is_global_admin
from app.services.media_asset_service import UnsafeMediaError, validate_raster_image
from app.services.tibia_validation_service import TibiaValidationService
from app.services.tibia_api import TibiaAPIError, get_guild_info
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

_CATEGORY_IMAGE_KEY_PREFIX = "cyclopedia_category_image_"
_CATEGORY_IMAGE_DIR = Path("backend/storage/category-images")


def _normalize_category_key(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", (value or "").strip().lower()).strip("_")
    return normalized or "uncategorized"


def _looks_like_test_account(user: User) -> bool:
    username = (user.username or "").strip().lower()
    email = (user.email or "").strip().lower()
    test_markers = (
        "test",
        "demo",
        "guest",
        "temp",
        "dummy",
        "sample",
        "qa",
        "bot",
    )
    if any(marker in username for marker in test_markers):
        return True
    if email and any(marker in email for marker in test_markers):
        return True
    return False


def _get_setting(db: Session, key: str, default: str = "") -> str:
    from app.models.settings import SystemSettings as SettingsModel
    value = db.query(SettingsModel).filter(SettingsModel.key == key).first()
    return value.value if value and value.value is not None else default


def _set_setting(db: Session, key: str, value: str, description: str = "") -> None:
    from app.models.settings import SystemSettings as SettingsModel
    setting = db.query(SettingsModel).filter(SettingsModel.key == key).first()
    if setting:
        setting.value = value
        if description:
            setting.description = description
    else:
        db.add(SettingsModel(key=key, value=value, description=description, is_active=True))


def _load_category_images(db: Session) -> dict[str, str]:
    from app.models.settings import SystemSettings as SettingsModel
    rows = (
        db.query(SettingsModel)
        .filter(SettingsModel.key.like(f"{_CATEGORY_IMAGE_KEY_PREFIX}%"), SettingsModel.is_active == True)
        .all()
    )
    mapping: dict[str, str] = {}
    for row in rows:
        key = row.key[len(_CATEGORY_IMAGE_KEY_PREFIX):]
        if key and row.value:
            mapping[key] = row.value
    return mapping


def _save_category_images(db: Session, payload: dict[str, str]) -> None:
    from app.models.settings import SystemSettings as SettingsModel
    existing = (
        db.query(SettingsModel)
        .filter(SettingsModel.key.like(f"{_CATEGORY_IMAGE_KEY_PREFIX}%"))
        .all()
    )
    by_key = {row.key: row for row in existing}

    normalized_payload: dict[str, str] = {}
    for category, url in (payload or {}).items():
        category_key = _normalize_category_key(category)
        image_url = (url or "").strip()
        if not image_url:
            continue
        normalized_payload[category_key] = image_url

    # Upsert provided values
    for category_key, image_url in normalized_payload.items():
        setting_key = f"{_CATEGORY_IMAGE_KEY_PREFIX}{category_key}"
        row = by_key.get(setting_key)
        if row:
            row.value = image_url
            row.is_active = True
            row.description = "Cyclopedia category image URL"
        else:
            db.add(
                SettingsModel(
                    key=setting_key,
                    value=image_url,
                    description="Cyclopedia category image URL",
                    is_active=True,
                )
            )

    # Remove keys no longer present in payload
    keep = {f"{_CATEGORY_IMAGE_KEY_PREFIX}{k}" for k in normalized_payload.keys()}
    for row in existing:
        if row.key not in keep:
            db.delete(row)


def _category_file_from_url(value: str) -> Path | None:
    prefix = "/api/v1/creatures/category-images/file/"
    if not value.startswith(prefix):
        return None
    filename = Path(value[len(prefix):]).name
    candidate = (_CATEGORY_IMAGE_DIR / filename).resolve()
    root = _CATEGORY_IMAGE_DIR.resolve()
    return candidate if candidate.parent == root else None


def _remove_unreferenced_category_files(old_values: set[str], current_values: set[str]) -> None:
    for stale_url in old_values - current_values:
        path = _category_file_from_url(stale_url)
        if path and path.is_file():
            path.unlink(missing_ok=True)


def get_admin_or_guild_leader(current_user: User = Depends(get_current_user)):
    if is_global_admin(current_user) or can_manage_guild(current_user):
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
    limit: int = 100,
    include_inactive: bool = False,
    exclude_test_accounts: bool = True,
    guild_name: Optional[str] = None,
):
    """
    Get list of all users with their linked characters
    Requires admin privileges
    """
    query = db.query(User)
    if not include_inactive:
        query = query.filter(User.is_active == True)

    requested_guild = (guild_name or "").strip()
    if requested_guild:
        if not is_global_admin(current_user):
            own_guild = (current_user.guild_name or "").strip().lower()
            if own_guild != requested_guild.lower():
                raise HTTPException(status_code=403, detail="You can only access users from your guild")
        query = query.filter(func.lower(User.guild_name) == requested_guild.lower())

    users = query.order_by(User.created_at.desc()).offset(skip).limit(limit).all()

    if exclude_test_accounts:
        users = [user for user in users if not _looks_like_test_account(user)]
    
    result = []
    for user in users:
        characters = db.query(UserCharacter).filter(
            UserCharacter.user_id == user.id
        ).all()
        
        result.append(
            UserWithCharacters(
                id=user.id,
                username=user.username,
                display_name=user.display_name,
                email=user.email,
                guild_name=user.guild_name,
                guild_rank=user.guild_rank,
                is_active=user.is_active,
                is_superuser=user.is_superuser,
                is_moderator=user.is_moderator,
                is_writer=user.is_writer,
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
        display_name=user.display_name,
        email=user.email,
        guild_name=user.guild_name,
        guild_rank=user.guild_rank,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        is_moderator=user.is_moderator,
        is_writer=user.is_writer,
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


@router.get("/guilds")
def get_registered_guilds(
    current_user: User = Depends(get_admin_or_guild_leader),
    db: Session = Depends(get_db),
):
    guilds: set[str] = set()
    for (guild_name,) in db.query(User.guild_name).filter(User.guild_name.isnot(None), User.is_active == True).all():
        name = (guild_name or "").strip()
        if name:
            guilds.add(name)
    for (guild_name,) in db.query(Event.guild_name).filter(Event.guild_name.isnot(None), Event.is_deleted == False).all():
        name = (guild_name or "").strip()
        if name:
            guilds.add(name)
    for (guild_name,) in db.query(Raffle.guild_name).filter(Raffle.guild_name.isnot(None), Raffle.is_deleted == False).all():
        name = (guild_name or "").strip()
        if name:
            guilds.add(name)

    if not is_global_admin(current_user):
        own = (current_user.guild_name or "").strip()
        return [own] if own else []

    return sorted(guilds)


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
    guild_raffles_enabled = _get_setting(db, "guild_raffles_enabled", "1") == "1"
    guild_contests_enabled = _get_setting(db, "guild_contests_enabled", "1") == "1"
    cyclopedia_category_images = _load_category_images(db)
    
    return SystemSettings(
        tibia_validation_enabled=config.settings.TIBIA_VALIDATION_ENABLED,
        tibia_validation_strict=config.settings.TIBIA_VALIDATION_STRICT,
        discord_webhook_url=discord_webhook.value if discord_webhook else "",
        discord_auto_post=discord_auto_post.value == "1" if discord_auto_post else False,
        guild_raffles_enabled=guild_raffles_enabled,
        guild_contests_enabled=guild_contests_enabled,
        cyclopedia_category_images=cyclopedia_category_images,
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
        else:
            db.add(SettingsModel(key="discord_auto_post", value="1" if settings_update.discord_auto_post else "0", description="Auto post announcements to Discord", is_active=True))

    if settings_update.guild_raffles_enabled is not None:
        _set_setting(
            db,
            "guild_raffles_enabled",
            "1" if settings_update.guild_raffles_enabled else "0",
            "Enable guild raffle features",
        )

    if settings_update.guild_contests_enabled is not None:
        _set_setting(
            db,
            "guild_contests_enabled",
            "1" if settings_update.guild_contests_enabled else "0",
            "Enable guild contest/event features",
        )

    old_category_images = set(_load_category_images(db).values())
    if settings_update.cyclopedia_category_images is not None:
        _save_category_images(db, settings_update.cyclopedia_category_images)

    db.commit()
    if settings_update.cyclopedia_category_images is not None:
        _remove_unreferenced_category_files(
            old_category_images,
            set(_load_category_images(db).values()),
        )
    
    # Get updated values
    discord_webhook = db.query(SettingsModel).filter(SettingsModel.key == "discord_webhook_url").first()
    discord_auto_post = db.query(SettingsModel).filter(SettingsModel.key == "discord_auto_post").first()
    guild_raffles_enabled = _get_setting(db, "guild_raffles_enabled", "1") == "1"
    guild_contests_enabled = _get_setting(db, "guild_contests_enabled", "1") == "1"
    cyclopedia_category_images = _load_category_images(db)
    
    return SystemSettings(
        tibia_validation_enabled=config.settings.TIBIA_VALIDATION_ENABLED,
        tibia_validation_strict=config.settings.TIBIA_VALIDATION_STRICT,
        discord_webhook_url=discord_webhook.value if discord_webhook else "",
        discord_auto_post=discord_auto_post.value == "1" if discord_auto_post else False,
        guild_raffles_enabled=guild_raffles_enabled,
        guild_contests_enabled=guild_contests_enabled,
        cyclopedia_category_images=cyclopedia_category_images,
        access_token_expire_minutes=config.settings.ACCESS_TOKEN_EXPIRE_MINUTES,
    )


@router.post("/settings/category-images/upload")
async def upload_category_image(
    category: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """Upload an image file for a Cyclopedia category and persist URL in settings."""
    _ = current_user
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty upload")
    if len(raw) > 3 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image too large (max 3MB)")

    try:
        content_type, ext = validate_raster_image(raw, file.content_type)
    except UnsafeMediaError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    category_key = _normalize_category_key(category)
    _CATEGORY_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(raw).hexdigest()[:12]
    filename = f"{category_key}_{digest}{ext}"
    target = _CATEGORY_IMAGE_DIR / filename
    target.write_bytes(raw)

    public_url = f"/api/v1/creatures/category-images/file/{filename}"
    old_values = set(_load_category_images(db).values())
    _save_category_images(db, {**_load_category_images(db), category_key: public_url})
    try:
        db.commit()
    except Exception:
        db.rollback()
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="Unable to save category image")
    _remove_unreferenced_category_files(old_values, set(_load_category_images(db).values()))

    return {
        "category": category_key,
        "image_url": public_url,
        "content_type": content_type,
    }


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

    previous_capabilities = {
        "admin": bool(user.is_superuser),
        "moderator": bool(user.is_moderator),
        "writer": bool(user.is_writer),
    }
    
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
        if user.is_superuser and not user_update.is_superuser and db.query(User.id).filter(User.is_superuser.is_(True), User.is_active.is_(True)).count() <= 1:
            raise HTTPException(status_code=409, detail="At least one active global administrator is required")
        user.is_superuser = user_update.is_superuser
    if user_update.is_moderator is not None:
        user.is_moderator = user_update.is_moderator
    if user_update.is_writer is not None:
        user.is_writer = user_update.is_writer
    
    if user_update.password is not None:
        user.hashed_password = security.get_password_hash(user_update.password)

    current_capabilities = {
        "admin": bool(user.is_superuser),
        "moderator": bool(user.is_moderator),
        "writer": bool(user.is_writer),
    }
    if current_capabilities != previous_capabilities:
        db.add(WorkspaceAudit(actor_id=current_user.id, workspace_type="admin", action="user_capabilities_updated",
                              target_type="user", target_id=str(user.id), assisted=False,
                              safe_metadata={"actor_context": "system", "before": previous_capabilities,
                                             "after": current_capabilities}))
    
    db.commit()
    db.refresh(user)
    
    # Get characters
    characters = db.query(UserCharacter).filter(UserCharacter.user_id == user.id).all()
    
    return UserWithCharacters(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        email=user.email,
        guild_name=user.guild_name,
        guild_rank=user.guild_rank,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        is_moderator=user.is_moderator,
        is_writer=user.is_writer,
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
async def sync_guild_members(
    guild_name: str = "Bloodborne Warhowl",
    current_user: User = Depends(get_admin_or_guild_leader),
    db: Session = Depends(get_db)
):
    """
    Synchronize guild members from Tibia API
    Fetches guild data and updates character information
    Requires admin privileges
    """
    if not can_manage_guild(current_user, guild_name):
        raise HTTPException(status_code=403, detail="You can only manage your own guild")

    try:
        guild_data = await get_guild_info(guild_name)
        if not guild_data:
            raise HTTPException(status_code=404, detail="Guild not found in TibiaData")
        members = guild_data.get("members") or []
        member_by_name = {
            str(member.get("name") or "").strip().casefold(): member
            for member in members if str(member.get("name") or "").strip()
        }
        synced_count = 0
        new_characters = 0
        updated_characters = 0
        invalid_users = []
        linked_user_ids: set[int] = set()

        for char in db.query(UserCharacter).all():
            member = member_by_name.get((char.character_name or "").strip().casefold())
            if not member:
                continue
            char.level = member.get("level")
            char.vocation = member.get("vocation")
            char.guild_name = guild_name
            char.guild_rank = member.get("rank")
            char.world_name = guild_data.get("world") or char.world_name
            char.last_seen = datetime.now(UTC)
            updated_characters += 1
            if char.user:
                linked_user_ids.add(char.user.id)
                char.user.guild_name = guild_name
                char.user.world_name = char.world_name
                if not char.user.tibia_character_name or (char.user.tibia_character_name or "").casefold() == char.character_name.casefold():
                    char.user.guild_rank = char.guild_rank or "Member"

        existing_names = {
            (name or "").strip().casefold()
            for (name,) in db.query(UserCharacter.character_name).all()
        }
        new_characters = sum(1 for name in member_by_name if name not in existing_names)
        synced_count = len(linked_user_ids)
        unlinked_users = 0

        scoped_users = db.query(User).filter(func.lower(User.guild_name) == guild_name.strip().lower()).all()
        for user in scoped_users:
            matching = [char for char in user.characters if (char.character_name or "").strip().casefold() in member_by_name]
            if matching:
                continue
            for char in user.characters:
                if (char.guild_name or "").strip().casefold() == guild_name.strip().casefold():
                    char.guild_name = None
                    char.guild_rank = None
            invalid_users.append({"user_id": user.id, "username": user.username,
                                  "character_name": user.tibia_character_name or "",
                                  "reason": "No linked character remains in the TibiaData guild roster"})
            user.guild_name = None
            user.guild_rank = "Unranked"
            unlinked_users += 1

        if is_global_admin(current_user):
            db.add(WorkspaceAudit(actor_id=current_user.id, workspace_type="admin_guild_assist",
                                  guild_name=guild_name, action="guild_membership_synchronized",
                                  target_type="guild", target_id=guild_name, assisted=True,
                                  safe_metadata={"actor_context": "system", "source": "tibiadata",
                                                 "synced_users": synced_count, "unlinked_users": unlinked_users}))
        db.commit()
        return GuildSyncResult(
            success=True,
            guild_name=guild_name,
            total_members=len(members),
            synced_users=synced_count,
            updated_characters=updated_characters,
            new_characters=new_characters,
            invalid_users=invalid_users,
            unlinked_users=unlinked_users,
            message=f"Successfully synchronized {synced_count} linked users with {guild_name}"
        )
    except HTTPException:
        raise
    except TibiaAPIError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="TibiaData is temporarily unavailable") from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Unable to synchronize guild membership") from exc


@router.get("/api-monitor")
def get_external_apis_status(
    current_user: User = Depends(get_current_admin_user)
):
    """
    Monitor external API statuses and retrieve sample data
    Tests: TibiaData and TibiaWiki
    Requires admin privileges
    """
    import time
    apis_status = []
    
    # TibiaData is the authoritative live game-data source.
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
                "database": "PostgreSQL",
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
        "timestamp": datetime.now(UTC).isoformat(),
        "total_apis": len(apis_status),
        "online_count": len([a for a in apis_status if a["status"] == "online"]),
        "apis": apis_status
    }
