"""Guild roster and module-grant HTTP entry points."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, selectinload

from app.api.v1.endpoints.auth import get_current_active_user
from app.db.database import get_db
from app.models.guild_management import GuildDirectory, GuildManagementGrant, GuildRosterCharacter
from app.models.user import User
from app.models.user_character import UserCharacter
from app.services.guild_authorization_service import (
    GuildAuthorizationError, GuildAuthorizationService, GuildManagementGrantService,
    SUPPORTED_GUILD_CAPABILITIES,
)
from app.services.guild_roster_service import GuildRosterService, GuildRosterSyncError, normalize_guild_identity


router = APIRouter()
Capability = Literal["raffles.manage", "events.manage", "hunts.manage", "announcements.manage"]


class GrantRequest(BaseModel):
    user_id: int
    capabilities: list[Capability] = Field(default_factory=list)
    grant_all: bool = False
    reason: str | None = Field(None, max_length=500)


class RevokeRequest(BaseModel):
    capabilities: list[Capability] | None = None


def _grant_payload(row: GuildManagementGrant) -> dict:
    return {
        "id": row.id, "user_id": row.user_id, "guild_name": row.guild_name,
        "capability": row.capability, "granted_by_id": row.granted_by_id,
        "granted_at": row.granted_at, "revoked_at": row.revoked_at,
    }


@router.get("/context")
def guild_management_context(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    return {"guilds": GuildAuthorizationService.guild_contexts(db, current_user)}


@router.get("/directory")
def guild_directory(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Global administrator access required")
    rows = db.query(GuildDirectory).order_by(GuildDirectory.guild_name, GuildDirectory.world_name).all()
    return [{
        "id": row.id, "guild_name": row.guild_name, "world_name": row.world_name,
        "source": row.source, "is_active": row.is_active,
        "first_discovered_at": row.first_discovered_at,
        "last_synchronized_at": row.last_synchronized_at,
        "last_successful_sync_at": row.last_successful_sync_at,
        "sync_status": row.sync_status, "sync_failure_code": row.sync_failure_code,
        "member_count": row.member_count, "leader_character_name": row.leader_character_name,
    } for row in rows]


@router.get("/manageable-guilds")
def manageable_guilds(
    capability: Capability = "raffles.manage",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    names = GuildAuthorizationService.manageable_guilds(db, current_user, capability)
    keys = {normalize_guild_identity(name) for name in names}
    worlds: dict[str, str] = {}
    for row in db.query(GuildRosterCharacter).filter(
        GuildRosterCharacter.normalized_guild_name.in_(keys),
        GuildRosterCharacter.is_current.is_(True),
    ).order_by(GuildRosterCharacter.id).all() if keys else []:
        worlds.setdefault(row.normalized_guild_name, row.world_name)
    if len(worlds) < len(keys):
        for row in db.query(UserCharacter).filter(
            UserCharacter.guild_name.isnot(None), UserCharacter.world_name.isnot(None),
            UserCharacter.ownership_status == "verified",
        ).order_by(UserCharacter.id).all():
            key = normalize_guild_identity(row.guild_name or "")
            if key in keys:
                worlds.setdefault(key, row.world_name)
    return {
        "capability": capability,
        "guilds": names,
        "guild_worlds": {name: worlds.get(normalize_guild_identity(name)) for name in names},
    }


@router.get("/guilds/{guild_name}/roster")
def guild_roster(
    guild_name: str,
    current_only: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if not any(GuildAuthorizationService.can_manage(db, current_user, guild_name, capability) for capability in SUPPORTED_GUILD_CAPABILITIES):
        raise HTTPException(status_code=403, detail="Insufficient guild permissions")
    query = db.query(GuildRosterCharacter).filter(GuildRosterCharacter.normalized_guild_name == normalize_guild_identity(guild_name))
    if current_only:
        query = query.filter(GuildRosterCharacter.is_current.is_(True))
    rows = query.options(selectinload(GuildRosterCharacter.linked_user)).order_by(GuildRosterCharacter.character_name).all()
    return [{
        "id": row.id, "guild_name": row.guild_name, "world_name": row.world_name,
        "character_name": row.character_name, "rank": row.guild_rank, "level": row.level,
        "vocation": row.vocation, "last_activity_at": row.last_activity_at,
        "last_online_seen_at": row.last_online_seen_at, "is_current": row.is_current,
        "linked_user_id": row.linked_user_id,
        "linked_username": row.linked_user.username if row.linked_user and row.linked_user.is_active else None,
        "public_profile_url": f"/members/{row.linked_user.username}" if row.linked_user and row.linked_user.is_active else None,
        "account_identity_known": row.linked_user_id is not None,
        "last_synchronized_at": row.last_synchronized_at,
    } for row in rows]


@router.post("/guilds/{guild_name}/roster/sync")
async def sync_guild_roster(
    guild_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if not GuildAuthorizationService.can_manage(db, current_user, guild_name, "raffles.manage"):
        raise HTTPException(status_code=403, detail="Insufficient guild permissions")
    try:
        result = await GuildRosterService.synchronize(db, guild_name)
        db.commit()
        return result.to_dict()
    except GuildRosterSyncError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/guilds/{guild_name}/grants")
def grant_guild_permissions(
    guild_name: str,
    payload: GrantRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    target = db.get(User, payload.user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    try:
        grants = (
            GuildManagementGrantService.grant_all(db, actor=current_user, target=target, guild_name=guild_name, reason=payload.reason)
            if payload.grant_all else
            GuildManagementGrantService.grant(db, actor=current_user, target=target, guild_name=guild_name, capabilities=list(payload.capabilities), reason=payload.reason)
        )
        db.commit()
        return [_grant_payload(row) for row in grants]
    except GuildAuthorizationError as exc:
        db.rollback()
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get("/guilds/{guild_name}/grants")
def active_guild_permissions(
    guild_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if not (
        current_user.is_superuser
        or GuildAuthorizationService.is_verified_leader(db, current_user, guild_name)
    ):
        raise HTTPException(
            status_code=403,
            detail="Only a global administrator or verified guild leader can view permissions",
        )
    rows = db.query(GuildManagementGrant).filter(
        GuildManagementGrant.normalized_guild_name == normalize_guild_identity(guild_name),
        GuildManagementGrant.revoked_at.is_(None),
    ).order_by(GuildManagementGrant.user_id, GuildManagementGrant.capability).all()
    return [_grant_payload(row) for row in rows]


@router.post("/guilds/{guild_name}/grants/{user_id}/revoke")
def revoke_guild_permissions(
    guild_name: str,
    user_id: int,
    payload: RevokeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    try:
        count = GuildManagementGrantService.revoke(
            db, actor=current_user, target=target, guild_name=guild_name,
            capabilities=list(payload.capabilities) if payload.capabilities is not None else None,
        )
        db.commit()
        return {"revoked": count}
    except GuildAuthorizationError as exc:
        db.rollback()
        raise HTTPException(status_code=403, detail=str(exc)) from exc
