"""Account profile, avatars, canonical characters, guilds, and public identity."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.v1.endpoints.auth import get_current_active_user
from app.core.security import get_password_hash, verify_password
from app.db.database import get_db
from app.models.auth_security import AuthOneTimeToken
from app.models.user import User
from app.models.user_character import UserCharacter
from app.schemas.profile import (
    CharacterUnlinkRequest, NotificationPreferencesUpdate, PrimaryCharacterUpdate,
    ProfileResponse, ProfileUpdate,
)
from app.services.account_identity_service import AccountIdentityError, AccountIdentityService
from app.services.avatar_service import AvatarService
from app.services.character_ownership_service import normalize_character_name
from app.services.guild_authorization_service import GuildAuthorizationService
from app.services.media_asset_service import UnsafeMediaError
from app.services.tibia_api import get_character_info


router = APIRouter()


def _avatar_url(user: User, size: int = 256) -> str | None:
    return AvatarService.url(user.avatar_managed_key, size) or user.avatar_url


def _profile_data(db: Session, user: User) -> dict:
    verified = [row for row in user.characters if row.ownership_status == "verified"]
    details = [
        AccountIdentityService.serialize_character(db, row, primary_character_id=user.primary_character_id)
        for row in sorted(verified, key=lambda item: item.character_name.casefold())
    ]
    return {
        "id": user.id, "username": user.username, "display_name": user.display_name,
        "title": user.title, "email": user.email, "email_verified_at": user.email_verified_at,
        "avatar_url": _avatar_url(user), "tibia_character_name": user.tibia_character_name,
        "guild_rank": user.guild_rank, "guild_name": user.guild_name,
        "world_name": user.world_name, "residence": user.residence,
        "achievement_points": user.achievement_points, "last_login_at": user.last_login_at,
        "tibia_status": user.tibia_status, "tibia_last_error": user.tibia_last_error,
        "vocation": user.vocation, "level": user.level, "is_active": user.is_active,
        "is_superuser": user.is_superuser, "join_date": user.join_date,
        "created_at": user.created_at, "characters": [row.character_name for row in verified],
        "character_details": details,
        "guild_contexts": GuildAuthorizationService.guild_contexts(db, user),
        "primary_character_id": user.primary_character_id,
        "in_app_notifications_enabled": user.in_app_notifications_enabled,
        "email_notifications_enabled": user.email_notifications_enabled,
    }


@router.get("/me", response_model=ProfileResponse)
def get_my_profile(user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    return _profile_data(db, user)


@router.put("/me", response_model=ProfileResponse)
def update_my_profile(
    payload: ProfileUpdate,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    if payload.email is not None:
        normalized = str(payload.email).strip().casefold()
        if db.query(User.id).filter(func.lower(User.email) == normalized, User.id != user.id).first():
            raise HTTPException(400, "Email already in use")
        if normalized != (user.email or "").strip().casefold():
            user.email = normalized
            user.email_verified_at = None
            db.query(AuthOneTimeToken).filter(
                AuthOneTimeToken.user_id == user.id,
                AuthOneTimeToken.consumed_at.is_(None),
                AuthOneTimeToken.invalidated_at.is_(None),
            ).update({AuthOneTimeToken.invalidated_at: datetime.now(UTC)}, synchronize_session=False)
    if payload.display_name is not None:
        user.display_name = payload.display_name.strip() or None
    if payload.title is not None:
        user.title = payload.title.strip() or None
    # Kept only for backwards-compatible external URLs. Managed uploads always
    # win in serializers and the new UI does not expose this field.
    if payload.avatar_url is not None and not user.avatar_managed_key:
        user.avatar_url = payload.avatar_url or None
    if payload.new_password is not None:
        if not payload.current_password:
            raise HTTPException(400, "Current password is required")
        if not verify_password(payload.current_password, user.hashed_password):
            raise HTTPException(400, "Current password is invalid")
        user.hashed_password = get_password_hash(payload.new_password)
        db.query(AuthOneTimeToken).filter(
            AuthOneTimeToken.user_id == user.id,
            AuthOneTimeToken.consumed_at.is_(None),
            AuthOneTimeToken.invalidated_at.is_(None),
        ).update({AuthOneTimeToken.invalidated_at: datetime.now(UTC)}, synchronize_session=False)
    db.commit()
    db.refresh(user)
    return _profile_data(db, user)


@router.post("/me/avatar", response_model=ProfileResponse)
async def upload_avatar(
    image: UploadFile = File(...),
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    raw = await image.read(5 * 1024 * 1024 + 1)
    try:
        key, outputs = AvatarService.process(raw, image.content_type)
        AvatarService.store(key, outputs)
    except UnsafeMediaError as exc:
        raise HTTPException(400, str(exc)) from exc
    old_key = user.avatar_managed_key
    user.avatar_managed_key = key
    user.avatar_updated_at = datetime.now(UTC)
    try:
        db.commit()
        db.refresh(user)
    except Exception:
        db.rollback()
        AvatarService.remove(key)
        raise
    AvatarService.remove(old_key)
    return _profile_data(db, user)


@router.delete("/me/avatar", response_model=ProfileResponse)
def remove_avatar(user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    old_key = user.avatar_managed_key
    user.avatar_managed_key = None
    user.avatar_updated_at = datetime.now(UTC)
    user.avatar_url = None
    db.commit()
    db.refresh(user)
    AvatarService.remove(old_key)
    return _profile_data(db, user)


@router.get("/avatars/{key}/{size}.webp")
def avatar_file(key: str, size: int):
    target = AvatarService.path(key, size)
    if target is None:
        raise HTTPException(404, "Avatar not found")
    return FileResponse(
        path=str(target), media_type="image/webp",
        headers={"Cache-Control": "public, max-age=31536000, immutable", "X-Content-Type-Options": "nosniff"},
    )


@router.get("/me/characters")
def my_characters(user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    return [
        AccountIdentityService.serialize_character(db, row, primary_character_id=user.primary_character_id)
        for row in sorted(user.characters, key=lambda item: item.character_name.casefold())
        if row.ownership_status in {"verified", "disputed"}
    ]


@router.post("/me/primary-character", response_model=ProfileResponse)
def set_primary_character(
    payload: PrimaryCharacterUpdate,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    character = db.query(UserCharacter).filter_by(id=payload.character_id, user_id=user.id).first()
    if character is None:
        raise HTTPException(404, "Character not found")
    try:
        AccountIdentityService.set_primary(db, user, character, user)
        db.commit()
        db.refresh(user)
        return _profile_data(db, user)
    except AccountIdentityError as exc:
        db.rollback()
        raise HTTPException(409, str(exc)) from exc


@router.post("/me/characters/{character_id}/refresh")
async def refresh_character(
    character_id: int,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    character = db.query(UserCharacter).filter_by(id=character_id, user_id=user.id, ownership_status="verified").first()
    if character is None:
        raise HTTPException(404, "Verified character not found")
    try:
        snapshot = await get_character_info(character.character_name)
    except Exception as exc:
        raise HTTPException(503, "Character data is temporarily unavailable") from exc
    if not snapshot or normalize_character_name(snapshot.get("name") or "") != character.normalized_name:
        raise HTTPException(503, "Character data is temporarily unavailable")
    guild = snapshot.get("guild") or {}
    character.level = snapshot.get("level")
    character.vocation = snapshot.get("vocation")
    character.world_name = snapshot.get("world")
    character.guild_name = guild.get("name")
    character.guild_rank = guild.get("rank")
    character.residence = snapshot.get("residence")
    character.achievement_points = snapshot.get("achievement_points")
    character.last_seen = datetime.now(UTC)
    AccountIdentityService.discover_guild(db, character)
    if user.primary_character_id == character.id:
        AccountIdentityService.sync_primary_cache(user)
    db.commit()
    return AccountIdentityService.serialize_character(db, character, primary_character_id=user.primary_character_id)


@router.delete("/me/characters/{character_id}", response_model=ProfileResponse)
def unlink_character(
    character_id: int,
    payload: CharacterUnlinkRequest,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    character = db.query(UserCharacter).filter_by(id=character_id, user_id=user.id).first()
    if character is None:
        raise HTTPException(404, "Character not found")
    if payload.confirmation.strip() != character.character_name:
        raise HTTPException(409, "Confirmation does not match the character name")
    try:
        AccountIdentityService.unlink(db, user, character, user, payload.reason)
        db.commit()
        db.refresh(user)
        return _profile_data(db, user)
    except AccountIdentityError as exc:
        db.rollback()
        raise HTTPException(409, str(exc)) from exc


@router.get("/me/guilds")
def my_guilds(user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    return {"guilds": GuildAuthorizationService.guild_contexts(db, user)}


@router.put("/me/notification-preferences", response_model=ProfileResponse)
def update_notification_preferences(
    payload: NotificationPreferencesUpdate,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    user.in_app_notifications_enabled = payload.in_app_notifications_enabled
    user.email_notifications_enabled = payload.email_notifications_enabled
    db.commit()
    db.refresh(user)
    return _profile_data(db, user)


@router.get("/public/{username}")
def public_profile(username: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(func.lower(User.username) == username.strip().casefold(), User.is_active.is_(True)).first()
    if user is None:
        raise HTTPException(404, "Member profile not found")
    characters = [
        AccountIdentityService.serialize_character(db, row, primary_character_id=user.primary_character_id)
        for row in user.characters if row.ownership_status == "verified"
    ]
    primary = next((row for row in characters if row["is_primary"]), None)
    return {
        "username": user.username, "display_name": user.display_name, "title": user.title,
        "avatar_url": _avatar_url(user), "primary_character": primary,
        "characters": characters,
        "guilds": [{
            "guild_name": row["guild_name"], "world_name": row["world_name"],
            "guild_rank": row["guild_rank"], "character_name": row["character_name"],
        } for row in characters if row["guild_name"]],
    }


# Compatibility aliases retained for older clients.
@router.get("/profile", response_model=ProfileResponse)
def get_profile(user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    return _profile_data(db, user)


@router.put("/profile", response_model=ProfileResponse)
def update_profile(
    payload: ProfileUpdate,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return update_my_profile(payload, user, db)
