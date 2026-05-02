"""Centralized permission helpers for guild-scoped management."""
from __future__ import annotations

from fastapi import HTTPException, status

from app.models.user import User

LEADER_RANKS = {
    "leader",
    "vice leader",
    "guild leader",
    "alpha warbringer",
    "bloodhowl marshal",
}


def is_global_admin(user: User) -> bool:
    return bool(user and user.is_superuser)


def is_guild_leader(user: User, guild_id: str | int | None = None) -> bool:
    if not user:
        return False
    rank = (user.guild_rank or "").strip().lower()
    if rank not in LEADER_RANKS:
        return False

    if guild_id is None:
        return True

    guild_name = str(guild_id).strip().lower()
    return bool(guild_name) and (user.guild_name or "").strip().lower() == guild_name


def can_manage_guild(user: User, guild_id: str | int | None = None) -> bool:
    if is_global_admin(user):
        return True
    return is_guild_leader(user, guild_id)


def require_guild_management(user: User, guild_id: str | int | None = None) -> None:
    if can_manage_guild(user, guild_id):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
