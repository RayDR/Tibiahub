"""Centralized permission helpers for guild-scoped management."""
from __future__ import annotations

from enum import Enum
from fastapi import HTTPException, status

from app.models.user import User

class GuildRole(str, Enum):
    GLOBAL_ADMIN = "global_admin"
    GUILD_LEADER = "guild_leader"
    GUILD_VICELEADER = "guild_viceleader"
    GUILD_MEMBER = "guild_member"
    DELEGATED_MANAGER = "delegated_manager"


LEADER_RANKS = {
    "leader",
    "guild leader",
    "alpha warbringer",
}
VICELEADER_RANKS = {
    "vice leader",
    "viceleader",
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


def is_guild_viceleader(user: User, guild_id: str | int | None = None) -> bool:
    if not user or (user.guild_rank or "").strip().lower() not in VICELEADER_RANKS:
        return False
    if guild_id is None:
        return True
    return (user.guild_name or "").strip().casefold() == str(guild_id).strip().casefold()


def resolve_guild_role(user: User) -> GuildRole:
    if is_global_admin(user):
        return GuildRole.GLOBAL_ADMIN
    if is_guild_leader(user):
        return GuildRole.GUILD_LEADER
    if is_guild_viceleader(user):
        return GuildRole.GUILD_VICELEADER
    return GuildRole.GUILD_MEMBER


def can_view_guild_workspace(user: User, guild_name: str) -> bool:
    return bool(is_global_admin(user) or (
        (user.guild_name or "").strip().casefold() == (guild_name or "").strip().casefold()
    ))


def can_assist_guild(user: User, _guild_name: str) -> bool:
    return is_global_admin(user)


def can_manage_guild_members(user: User, guild_name: str) -> bool:
    return is_global_admin(user) or is_guild_leader(user, guild_name)


def can_manage_announcements(user: User, guild_name: str) -> bool:
    return can_manage_guild_members(user, guild_name) or is_guild_viceleader(user, guild_name)


def can_manage_events(user: User, guild_name: str) -> bool:
    return can_manage_announcements(user, guild_name)


def can_create_server_content(user: User, _world_name: str) -> bool:
    # Server-wide creation remains opt-in and admin-only until a policy grant is stored.
    return is_global_admin(user)


def can_create_global_content(user: User) -> bool:
    return is_global_admin(user)


def can_grant_delegated_permissions(user: User, guild_name: str) -> bool:
    return is_global_admin(user) or is_guild_leader(user, guild_name)


def can_manage_guild(user: User, guild_id: str | int | None = None) -> bool:
    if is_global_admin(user):
        return True
    return is_guild_leader(user, guild_id)


def require_guild_management(user: User, guild_id: str | int | None = None) -> None:
    if can_manage_guild(user, guild_id):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")


def is_matching_raffle_leader(user: User, guild_name: str) -> bool:
    """Use the canonical guild-leader policy for raffle ownership checks.

    Raffles used to maintain a second, narrower rank allowlist. That made a
    valid guild leader fail only on modern raffle operations when a guild used
    its configured leader title (for example ``Alpha Warbringer``).
    """
    return is_guild_leader(user, guild_name)


def has_active_raffle_grant(db, user: User, raffle_id: int) -> bool:
    from app.models.raffle import RaffleManagerGrant
    return bool(db.query(RaffleManagerGrant.id).filter(
        RaffleManagerGrant.raffle_id == raffle_id,
        RaffleManagerGrant.user_id == user.id,
        RaffleManagerGrant.revoked_at.is_(None),
    ).first())


def can_administer_raffle(db, user: User, raffle) -> bool:
    return bool(
        is_global_admin(user)
        or is_matching_raffle_leader(user, raffle.guild_name)
        or has_active_raffle_grant(db, user, raffle.id)
    )


def can_execute_raffle(db, user: User, raffle) -> bool:
    return can_administer_raffle(db, user, raffle)


def can_update_raffle_delivery(db, user: User, raffle) -> bool:
    return can_administer_raffle(db, user, raffle)


def can_view_private_raffle_results(db, user: User, raffle) -> bool:
    return can_administer_raffle(db, user, raffle)


def can_publish_raffle(user: User, raffle) -> bool:
    return is_global_admin(user) or is_matching_raffle_leader(user, raffle.guild_name)
