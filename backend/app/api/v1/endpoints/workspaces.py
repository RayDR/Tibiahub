from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.v1.endpoints.auth import get_current_admin_user
from app.core.permissions import is_guild_leader
from app.db.database import get_db
from app.models.guild_member_snapshot import GuildMemberSnapshot
from app.models.raffle import Raffle
from app.models.user import User
from app.models.workspace_audit import WorkspaceAudit

router = APIRouter()


def guild_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (name or "").strip().casefold()).strip("-")


def _registered_guild_names(db: Session) -> list[str]:
    names = {
        str(value).strip()
        for (value,) in db.query(User.guild_name).filter(User.guild_name.isnot(None)).distinct().all()
        if value and str(value).strip()
    }
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
    users = db.query(User).filter(User.guild_name.ilike(name)).all()
    leader = next((user for user in users if is_guild_leader(user, name)), None)
    world = next((user.world_name for user in users if user.world_name), None)
    recent_sync = db.query(func.max(GuildMemberSnapshot.snapshot_at)).filter(
        GuildMemberSnapshot.guild_name.ilike(name)
    ).scalar()
    raffle_issues = db.query(Raffle.id).filter(
        Raffle.guild_name.ilike(name), Raffle.execution_state == "failed", Raffle.is_deleted.is_(False)
    ).count()
    active_members = sum(1 for user in users if user.is_active)
    return {
        "key": guild_key(name),
        "name": name,
        "world_name": world,
        "leader": leader.display_name or leader.username if leader else None,
        "member_count": active_members,
        "is_active": active_members > 0,
        "setup_status": "ready" if leader and world else "needs_attention",
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
