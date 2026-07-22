"""Normalized activity scopes and compatibility with historical access modes."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from fastapi import HTTPException

from app.core.permissions import can_create_global_content, can_create_server_content
from app.models.user import User


class ScopeType(str, Enum):
    GUILD = "guild"
    SERVER = "server"
    GLOBAL = "global"
    COALITION = "coalition"


@dataclass(frozen=True)
class ContentScope:
    scope_type: ScopeType
    guild_name: str | None = None
    world_name: str | None = None


LEGACY_ACCESS_MODES = {
    "guild_only": ScopeType.GUILD,
    "world_only": ScopeType.SERVER,
    "public": ScopeType.GLOBAL,
}


def scope_from_legacy(access_mode: str, *, guild_name: str | None = None, world_name: str | None = None) -> ContentScope:
    """Keep historical records readable without rewriting their stored values."""
    scope_type = LEGACY_ACCESS_MODES.get((access_mode or "").strip().lower())
    if scope_type is None:
        raise ValueError("Unsupported legacy access mode")
    return ContentScope(scope_type, guild_name=guild_name, world_name=world_name)


def require_scope_creation(user: User, scope: ContentScope) -> None:
    if scope.scope_type is ScopeType.COALITION:
        raise HTTPException(status_code=422, detail="Coalition scope is not available")
    if scope.scope_type is ScopeType.GUILD:
        own = (user.guild_name or "").strip().casefold()
        target = (scope.guild_name or "").strip().casefold()
        if not target or (not user.is_superuser and own != target):
            raise HTTPException(status_code=403, detail="Guild scope is limited to your own guild")
        return
    if scope.scope_type is ScopeType.SERVER:
        if not scope.world_name or not can_create_server_content(user, scope.world_name):
            raise HTTPException(status_code=403, detail="Server-wide creation is not permitted")
        return
    if not can_create_global_content(user):
        raise HTTPException(status_code=403, detail="Global creation is restricted to administrators")
