from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.v1.endpoints.auth import get_current_admin_user
from app.services.guild_authorization_service import LEADER_RANKS
from app.services.guild_roster_service import normalize_guild_identity
from app.db.database import get_db
from app.models.guild_management import GuildDirectory, GuildRosterCharacter
from app.models.guild_member_snapshot import GuildMemberSnapshot
from app.models.raffle import Raffle
from app.models.user import User
from app.models.user_character import UserCharacter
from app.models.workspace_audit import WorkspaceAudit

router = APIRouter()


def guild_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (name or "").strip().casefold()).strip("-")


def _registered_guild_names(db: Session) -> list[str]:
    names = {
        str(value).strip()
        for (value,) in db.query(GuildDirectory.guild_name).filter(GuildDirectory.is_active.is_(True)).distinct().all()
        if value and str(value).strip()
    }
    names.update({
        str(value).strip()
        for (value,) in db.query(UserCharacter.guild_name).filter(
            UserCharacter.ownership_status == "verified",
            UserCharacter.guild_name.isnot(None),
        ).distinct().all()
        if value and str(value).strip()
    })
    names.update({
        str(value).strip()
        for (value,) in db.query(GuildRosterCharacter.guild_name).filter(GuildRosterCharacter.is_current.is_(True)).distinct().all()
        if value and str(value).strip()
    })
    names.update({
        str(value).strip()
        for (value,) in db.query(GuildMemberSnapshot.guild_name).filter(GuildMemberSnapshot.guild_name.isnot(None)).distinct().all()
        if value and str(value).strip()
    })
    return sorted(names, key=str.casefold)


def _resolve_registered_guild(db: Session, key: str) -> str:
    for name in _registered_guild_names(db):
        if guild_key(name) == key.casefold():
            return name
    raise HTTPException(status_code=404, detail="Registered guild not found")


def _guild_summary(db: Session, name: str) -> dict:
    normalized = normalize_guild_identity(name)
    directory = db.query(GuildDirectory).filter(
        GuildDirectory.normalized_guild_name == normalized,
        GuildDirectory.is_active.is_(True),
    ).order_by(GuildDirectory.last_successful_sync_at.desc().nullslast()).first()
    roster = db.query(GuildRosterCharacter).filter(
        GuildRosterCharacter.normalized_guild_name == normalized,
        GuildRosterCharacter.is_current.is_(True),
    ).all()
    verified_characters = db.query(UserCharacter).filter(
        UserCharacter.ownership_status == "verified",
        UserCharacter.guild_name.isnot(None),
    ).all()
    verified_characters = [
        row for row in verified_characters
        if normalize_guild_identity(row.guild_name or "") == normalized and row.user and row.user.is_active
    ]
    leader_row = next((
        row for row in roster if (row.guild_rank or "").strip().casefold() in LEADER_RANKS
    ), None)
    leader_character = next((
        row for row in verified_characters if (row.guild_rank or "").strip().casefold() in LEADER_RANKS
    ), None)
    world = directory.world_name if directory else next(
        (row.world_name for row in [*roster, *verified_characters] if row.world_name), None
    )
    recent_sync = db.query(func.max(GuildMemberSnapshot.snapshot_at)).filter(
        GuildMemberSnapshot.guild_name.ilike(name)
    ).scalar()
    raffle_issues = db.query(Raffle.id).filter(
        Raffle.guild_name.ilike(name), Raffle.execution_state == "failed", Raffle.is_deleted.is_(False)
    ).count()
    active_members = directory.member_count if directory else (
        len(roster) if roster else len({row.user_id for row in verified_characters})
    )
    leader_name = None
    if leader_row and leader_row.linked_user:
        leader_name = leader_row.linked_user.display_name or leader_row.linked_user.username
    elif directory and directory.leader_character_name:
        leader_name = directory.leader_character_name
    elif leader_row:
        leader_name = leader_row.character_name
    elif leader_character:
        leader_name = leader_character.user.display_name or leader_character.user.username
    return {
        "key": guild_key(name),
        "name": name,
        "world_name": world,
        "leader": leader_name,
        "member_count": active_members,
        "is_active": bool(directory.is_active if directory else active_members > 0),
        "setup_status": "ready" if leader_name and world else "needs_attention",
        "recent_sync_at": recent_sync,
        "open_alerts": raffle_issues,
        "raffle_issues": raffle_issues,
    }


@router.get("/guilds")
def list_registered_guilds(
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin_user),
):
    return [_guild_summary(db, name) for name in _registered_guild_names(db)]


@router.get("/guilds/{key}")
def open_guild_assistance_workspace(
    key: str,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    name = _resolve_registered_guild(db, key)
    db.add(WorkspaceAudit(
        actor_id=admin.id,
        workspace_type="admin_guild_assist",
        guild_name=name,
        action="workspace_opened",
        target_type="guild",
        target_id=key,
        assisted=True,
        safe_metadata={"source": "admin_guild_directory"},
    ))
    db.commit()
    return {
        "workspace": {
            "type": "admin_guild_assist",
            "admin_user_id": admin.id,
            "guild_name": name,
        },
        "guild": _guild_summary(db, name),
        "audit_notice": True,
    }


@router.get("/guilds/{key}/audits")
def list_guild_assistance_audits(
    key: str,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin_user),
):
    name = _resolve_registered_guild(db, key)
    return db.query(WorkspaceAudit).filter(
        WorkspaceAudit.guild_name.ilike(name), WorkspaceAudit.assisted.is_(True)
    ).order_by(WorkspaceAudit.created_at.desc()).limit(100).all()
