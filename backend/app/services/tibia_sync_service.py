"""Helpers to synchronize Tibia character snapshots into local user records."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models.user import User
from app.models.user_character import UserCharacter
from app.services.tibia_api import TibiaAPIError, get_character_info


async def sync_user_character_snapshot(db: Session, user: User, *, character_name: Optional[str] = None) -> Optional[dict]:
    target_name = character_name or user.tibia_character_name
    if not target_name:
        return None

    payload = await get_character_info(target_name)
    if not payload:
        user.tibia_status = "not_found"
        user.tibia_last_error = f"Character '{target_name}' not found"
        user.last_updated = datetime.utcnow()
        db.add(user)
        db.commit()
        return None

    guild_info = payload.get("guild")
    account_info = payload.get("account_information") or {}
    user.tibia_character_name = payload.get("name") or target_name
    user.vocation = payload.get("vocation")
    user.level = payload.get("level")
    user.world_name = payload.get("world")
    user.guild_name = guild_info.get("name") if isinstance(guild_info, dict) else guild_info
    user.guild_rank = (guild_info or {}).get("rank") if isinstance(guild_info, dict) else user.guild_rank
    user.residence = payload.get("residence")
    user.achievement_points = payload.get("achievement_points") or account_info.get("achievement_points")
    user.last_login_at = payload.get("last_login_at")
    user.tibia_status = "ok"
    user.tibia_last_error = None
    user.last_updated = datetime.utcnow()

    record = db.query(UserCharacter).filter(UserCharacter.user_id == user.id, UserCharacter.character_name == user.tibia_character_name).first()
    if not record:
        record = UserCharacter(user_id=user.id, character_name=user.tibia_character_name)
        db.add(record)

    record.character_name = user.tibia_character_name
    record.level = user.level
    record.vocation = user.vocation
    record.world_name = user.world_name
    record.guild_name = user.guild_name
    record.guild_rank = user.guild_rank
    record.residence = user.residence
    record.achievement_points = user.achievement_points
    record.sex = payload.get("sex")
    record.last_login_at = user.last_login_at
    record.last_seen = datetime.utcnow()

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
        user.last_updated = datetime.utcnow()
        db.add(user)
        db.commit()
        return None, str(exc)