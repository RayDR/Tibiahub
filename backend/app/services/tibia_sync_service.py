"""Helpers to synchronize Tibia character snapshots into local user records."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models.user import User
from app.models.user_character import UserCharacter
from app.services.account_identity_service import AccountIdentityService
from app.services.character_ownership_service import normalize_character_name
from app.services.tibia_api import TibiaAPIError, get_character_info


async def sync_user_character_snapshot(db: Session, user: User, *, character_name: Optional[str] = None) -> Optional[dict]:
    if character_name:
        record = db.query(UserCharacter).filter(
            UserCharacter.user_id == user.id,
            UserCharacter.normalized_name == normalize_character_name(character_name),
            UserCharacter.ownership_status == "verified",
        ).first()
    else:
        record = user.primary_character
    if not record or record.user_id != user.id or record.ownership_status != "verified":
        return None
    target_name = record.character_name

    payload = await get_character_info(target_name)
    if not payload:
        user.tibia_status = "not_found"
        user.tibia_last_error = f"Character '{target_name}' not found"
        user.last_updated = datetime.now(UTC)
        db.add(user)
        db.commit()
        return None

    guild_info = payload.get("guild")
    account_info = payload.get("account_information") or {}
    record.character_name = payload.get("name") or target_name
    record.normalized_name = normalize_character_name(record.character_name)
    record.level = payload.get("level")
    record.vocation = payload.get("vocation")
    record.world_name = payload.get("world")
    record.guild_name = guild_info.get("name") if isinstance(guild_info, dict) else guild_info
    record.guild_rank = (guild_info or {}).get("rank") if isinstance(guild_info, dict) else record.guild_rank
    record.residence = payload.get("residence")
    record.achievement_points = payload.get("achievement_points") or account_info.get("achievement_points")
    record.sex = payload.get("sex")
    record.last_login_at = payload.get("last_login_at")
    record.last_seen = datetime.now(UTC)

    if user.primary_character_id == record.id:
        AccountIdentityService.sync_primary_cache(user)
    user.last_updated = datetime.now(UTC)
    db.add(user)
    db.commit()
    db.refresh(user)
    db.refresh(record)
    return payload


async def try_sync_user_character_snapshot(db: Session, user: User, *, character_name: Optional[str] = None) -> tuple[Optional[dict], Optional[str]]:
    try:
        payload = await sync_user_character_snapshot(db, user, character_name=character_name)
        return payload, None
    except TibiaAPIError as exc:
        user.tibia_status = "error"
        user.tibia_last_error = str(exc)
        user.last_updated = datetime.now(UTC)
        db.add(user)
        db.commit()
        return None, str(exc)
