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


RAFFLE_LEADER_RANKS = {"leader", "guild leader"}


def is_matching_raffle_leader(user: User, guild_name: str) -> bool:
    """Raffle authority is intentionally narrower than broad guild management."""
    if not user or (user.guild_rank or "").strip().lower() not in RAFFLE_LEADER_RANKS:
        return False
    return (user.guild_name or "").strip().casefold() == (guild_name or "").strip().casefold()


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
