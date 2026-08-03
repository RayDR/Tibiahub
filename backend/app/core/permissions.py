"""Centralized permission helpers for guild-scoped management."""
from __future__ import annotations

from enum import Enum
from fastapi import HTTPException, status

from app.models.user import User
from app.services.guild_authorization_service import (
    GuildAuthorizationService,
    LEADER_RANKS,
)

class GuildRole(str, Enum):
    GLOBAL_ADMIN = "global_admin"
    GUILD_LEADER = "guild_leader"
    GUILD_VICELEADER = "guild_viceleader"
    GUILD_MEMBER = "guild_member"
    DELEGATED_MANAGER = "delegated_manager"


VICELEADER_RANKS = {
    "vice leader",
    "viceleader",
    "bloodhowl marshal",
}


def is_global_admin(user: User) -> bool:
    return bool(user and user.is_superuser)


def _verified_guild_characters(user: User, guild_id: str | int | None = None):
    requested = str(guild_id or "").strip().casefold()
    return [
        row for row in getattr(user, "characters", [])
        if row.ownership_status == "verified"
        and row.guild_name
        and (not requested or row.guild_name.strip().casefold() == requested)
    ]


def is_guild_leader(user: User, guild_id: str | int | None = None, db=None) -> bool:
    if not user:
        return False
    if db is not None and guild_id is not None:
        return GuildAuthorizationService.is_verified_leader(db, user, str(guild_id))
    return any((row.guild_rank or "").strip().casefold() in LEADER_RANKS for row in _verified_guild_characters(user, guild_id))


def is_guild_viceleader(user: User, guild_id: str | int | None = None) -> bool:
    return bool(user and any(
        (row.guild_rank or "").strip().casefold() in VICELEADER_RANKS
        for row in _verified_guild_characters(user, guild_id)
    ))


def resolve_guild_role(user: User) -> GuildRole:
    if is_global_admin(user):
        return GuildRole.GLOBAL_ADMIN
    if is_guild_leader(user):
        return GuildRole.GUILD_LEADER
    if is_guild_viceleader(user):
        return GuildRole.GUILD_VICELEADER
    return GuildRole.GUILD_MEMBER


def can_view_guild_workspace(user: User, guild_name: str) -> bool:
    return bool(is_global_admin(user) or _verified_guild_characters(user, guild_name))


def can_assist_guild(user: User, _guild_name: str) -> bool:
    return is_global_admin(user)


def can_manage_guild_members(user: User, guild_name: str, db=None) -> bool:
    if db is not None:
        return GuildAuthorizationService.can_manage(db, user, guild_name, "announcements.manage")
    return is_global_admin(user) or is_guild_leader(user, guild_name)


def can_manage_announcements(user: User, guild_name: str, db=None) -> bool:
    if db is not None:
        return GuildAuthorizationService.can_manage(db, user, guild_name, "announcements.manage")
    return can_manage_guild_members(user, guild_name) or is_guild_viceleader(user, guild_name)


def can_manage_events(user: User, guild_name: str, db=None) -> bool:
    if db is not None:
        return GuildAuthorizationService.can_manage(db, user, guild_name, "events.manage")
    return can_manage_announcements(user, guild_name)


def can_create_server_content(user: User, _world_name: str) -> bool:
    # Server-wide creation remains opt-in and admin-only until a policy grant is stored.
    return is_global_admin(user)


def can_create_global_content(user: User) -> bool:
    return is_global_admin(user)


def can_grant_delegated_permissions(user: User, guild_name: str, db=None) -> bool:
    return is_global_admin(user) or is_guild_leader(user, guild_name, db=db)


def can_manage_guild(user: User, guild_id: str | int | None = None, db=None, capability: str = "raffles.manage") -> bool:
    if db is not None and guild_id is not None:
        return GuildAuthorizationService.can_manage(db, user, str(guild_id), capability)
    if is_global_admin(user):
        return True
    return is_guild_leader(user, guild_id)


def require_guild_management(user: User, guild_id: str | int | None = None, db=None, capability: str = "raffles.manage") -> None:
    if can_manage_guild(user, guild_id, db=db, capability=capability):
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
        GuildAuthorizationService.can_manage(db, user, raffle.guild_name, "raffles.manage")
        or has_active_raffle_grant(db, user, raffle.id)
    )


def can_execute_raffle(db, user: User, raffle) -> bool:
    return can_administer_raffle(db, user, raffle)


def can_update_raffle_delivery(db, user: User, raffle) -> bool:
    return can_administer_raffle(db, user, raffle)


def can_view_private_raffle_results(db, user: User, raffle) -> bool:
    return can_administer_raffle(db, user, raffle)


def can_publish_raffle(user: User, raffle, db=None) -> bool:
    if db is not None:
        if is_global_admin(user) or GuildAuthorizationService.is_verified_leader(db, user, raffle.guild_name):
            return True
        # A guild-wide raffle manager may publish only while the grant is
        # active and their verified in-guild publication identity still
        # exists. A compatibility per-raffle grant does not confer publishing.
        return bool(
            GuildAuthorizationService.has_grant(db, user, raffle.guild_name, "raffles.manage")
            and GuildAuthorizationService.representative_character(db, user, raffle.guild_name)
        )
    return is_global_admin(user) or is_matching_raffle_leader(user, raffle.guild_name)
