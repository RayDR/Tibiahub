"""One policy layer for verified leadership and guild module grants."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.guild_management import GuildManagementGrant, GuildRosterCharacter
from app.models.user import User
from app.models.user_character import UserCharacter
from app.models.workspace_audit import WorkspaceAudit
from app.services.guild_roster_service import normalize_guild_identity


SUPPORTED_GUILD_CAPABILITIES = (
    "raffles.manage",
    "events.manage",
    "hunts.manage",
    "announcements.manage",
)
LEADER_RANKS = frozenset({"leader", "guild leader", "alpha warbringer"})


class GuildAuthorizationError(ValueError):
    pass


class GuildAuthorizationService:
    @classmethod
    def guild_contexts(cls, db: Session, user: User) -> list[dict]:
        """Return every verified/authorized guild with explicit capabilities.

        This is the canonical frontend navigation context; it deliberately
        does not infer membership or authority from ``User.guild_name``.
        """
        verified_rows = db.query(UserCharacter).filter(
            UserCharacter.user_id == user.id,
            UserCharacter.ownership_status == "verified",
            UserCharacter.guild_name.isnot(None),
        ).order_by(UserCharacter.id).all()
        grant_rows = db.query(GuildManagementGrant).filter(
            GuildManagementGrant.user_id == user.id,
            GuildManagementGrant.revoked_at.is_(None),
        ).all()
        names: dict[str, str] = {}
        characters: dict[str, list[UserCharacter]] = {}
        worlds: dict[str, str] = {}
        granted: dict[str, set[str]] = {}
        for row in verified_rows:
            key = normalize_guild_identity(row.guild_name or "")
            if not key:
                continue
            names.setdefault(key, (row.guild_name or "").strip())
            characters.setdefault(key, []).append(row)
            if row.world_name:
                worlds.setdefault(key, row.world_name)
        for row in grant_rows:
            names.setdefault(row.normalized_guild_name, row.guild_name)
            granted.setdefault(row.normalized_guild_name, set()).add(row.capability)
        if user.is_superuser:
            for row in db.query(GuildRosterCharacter).filter(
                GuildRosterCharacter.is_current.is_(True),
            ).order_by(GuildRosterCharacter.id).all():
                names.setdefault(row.normalized_guild_name, row.guild_name)
                worlds.setdefault(row.normalized_guild_name, row.world_name)
            for row in db.query(UserCharacter).filter(
                UserCharacter.guild_name.isnot(None),
            ).order_by(UserCharacter.id).all():
                key = normalize_guild_identity(row.guild_name or "")
                if key:
                    names.setdefault(key, (row.guild_name or "").strip())
                    if row.world_name:
                        worlds.setdefault(key, row.world_name)

        result = []
        for key, name in sorted(names.items(), key=lambda item: item[1].casefold()):
            rows = characters.get(key, [])
            leader = any((row.guild_rank or "").strip().casefold() in LEADER_RANKS for row in rows)
            if user.is_superuser:
                role = "global_admin"
                capabilities = {capability: True for capability in SUPPORTED_GUILD_CAPABILITIES}
            elif leader:
                role = "guild_leader"
                capabilities = {capability: True for capability in SUPPORTED_GUILD_CAPABILITIES}
            else:
                active = granted.get(key, set())
                role = "delegated_manager" if active else "guild_member"
                capabilities = {capability: capability in active for capability in SUPPORTED_GUILD_CAPABILITIES}
            result.append({
                "guild_name": name,
                "world_name": worlds.get(key),
                "role": role,
                "capabilities": capabilities,
                "can_grant_permissions": bool(user.is_superuser or leader),
                "representative_character_name": rows[0].character_name if rows else None,
            })
        return result

    @staticmethod
    def verified_characters(db: Session, user: User, guild_name: str) -> list[UserCharacter]:
        key = normalize_guild_identity(guild_name)
        if not key:
            return []
        rows = db.query(UserCharacter).filter(
            UserCharacter.user_id == user.id,
            UserCharacter.ownership_status == "verified",
            UserCharacter.guild_name.isnot(None),
        ).all()
        return [row for row in rows if normalize_guild_identity(row.guild_name or "") == key]

    @classmethod
    def is_verified_member(cls, db: Session, user: User, guild_name: str) -> bool:
        key = normalize_guild_identity(guild_name)
        return bool(key and cls.verified_characters(db, user, guild_name))

    @classmethod
    def is_verified_leader(cls, db: Session, user: User, guild_name: str) -> bool:
        return any(
            (row.guild_rank or "").strip().casefold() in LEADER_RANKS
            for row in cls.verified_characters(db, user, guild_name)
        )

    @staticmethod
    def has_grant(db: Session, user: User, guild_name: str, capability: str) -> bool:
        return bool(db.query(GuildManagementGrant.id).filter(
            GuildManagementGrant.user_id == user.id,
            GuildManagementGrant.normalized_guild_name == normalize_guild_identity(guild_name),
            GuildManagementGrant.capability == capability,
            GuildManagementGrant.revoked_at.is_(None),
        ).first())

    @classmethod
    def representative_character(cls, db: Session, user: User, guild_name: str) -> UserCharacter | None:
        return next((
            row for row in cls.verified_characters(db, user, guild_name)
        ), None)

    @classmethod
    def can_manage(cls, db: Session, user: User, guild_name: str, capability: str) -> bool:
        if capability not in SUPPORTED_GUILD_CAPABILITIES:
            return False
        return bool(user and user.is_active and (
            user.is_superuser
            or cls.is_verified_leader(db, user, guild_name)
            or cls.has_grant(db, user, guild_name, capability)
        ))

    @classmethod
    def manageable_guilds(cls, db: Session, user: User, capability: str) -> list[str]:
        names: dict[str, str] = {}
        for row in db.query(UserCharacter).filter(
            UserCharacter.user_id == user.id,
            UserCharacter.ownership_status == "verified",
            UserCharacter.guild_name.isnot(None),
        ).all():
            if row.guild_name and (row.guild_rank or "").strip().casefold() in LEADER_RANKS:
                names[normalize_guild_identity(row.guild_name)] = row.guild_name
        for row in db.query(GuildManagementGrant).filter(
            GuildManagementGrant.user_id == user.id,
            GuildManagementGrant.capability == capability,
            GuildManagementGrant.revoked_at.is_(None),
        ).all():
            names[row.normalized_guild_name] = row.guild_name
        if user.is_superuser:
            for (name,) in db.query(GuildRosterCharacter.guild_name).distinct().all():
                names[normalize_guild_identity(name)] = name
            for (name,) in db.query(UserCharacter.guild_name).filter(UserCharacter.guild_name.isnot(None)).distinct().all():
                names[normalize_guild_identity(name)] = name
        return sorted(names.values(), key=str.casefold)


class GuildManagementGrantService:
    @staticmethod
    def _require_eligible(db: Session, target: User, guild_name: str) -> None:
        if not target or not target.is_active:
            raise GuildAuthorizationError("The target account does not exist or is inactive")
        if not GuildAuthorizationService.is_verified_member(db, target, guild_name):
            raise GuildAuthorizationError("The target must own a verified character currently in this guild")

    @classmethod
    def grant(
        cls, db: Session, *, actor: User, target: User, guild_name: str,
        capabilities: list[str], reason: str | None = None,
    ) -> list[GuildManagementGrant]:
        if not capabilities:
            raise GuildAuthorizationError("At least one guild capability is required")
        if not (actor.is_superuser or GuildAuthorizationService.is_verified_leader(db, actor, guild_name)):
            raise GuildAuthorizationError("Only a global administrator or verified guild leader can grant permissions")
        cls._require_eligible(db, target, guild_name)
        invalid = set(capabilities) - set(SUPPORTED_GUILD_CAPABILITIES)
        if invalid:
            raise GuildAuthorizationError(f"Unsupported guild capability: {sorted(invalid)[0]}")
        key = normalize_guild_identity(guild_name)
        now = datetime.now(UTC)
        grants = []
        for capability in dict.fromkeys(capabilities):
            row = db.query(GuildManagementGrant).filter_by(
                user_id=target.id, normalized_guild_name=key, capability=capability,
            ).one_or_none()
            if row is None:
                row = GuildManagementGrant(
                    user_id=target.id, guild_name=guild_name.strip(), normalized_guild_name=key,
                    capability=capability, granted_by_id=actor.id,
                )
                db.add(row)
            else:
                row.guild_name = guild_name.strip()
                row.granted_by_id = actor.id
                row.granted_at = now
                row.revoked_at = None
                row.revoked_by_id = None
            row.reason = (reason or "").strip() or None
            row.audit_metadata = {"source": "guild_management"}
            grants.append(row)
        db.add(WorkspaceAudit(
            actor_id=actor.id,
            workspace_type="admin_guild_assist" if actor.is_superuser else "guild",
            guild_name=guild_name.strip(),
            action="guild_management_permissions_granted",
            target_type="user",
            target_id=str(target.id),
            assisted=bool(actor.is_superuser),
            safe_metadata={
                "capabilities": [row.capability for row in grants],
                "grant_all": set(capabilities) == set(SUPPORTED_GUILD_CAPABILITIES),
                "reason_supplied": bool((reason or "").strip()),
            },
        ))
        db.flush()
        return grants

    @classmethod
    def grant_all(cls, db: Session, *, actor: User, target: User, guild_name: str, reason: str | None = None):
        return cls.grant(db, actor=actor, target=target, guild_name=guild_name, capabilities=list(SUPPORTED_GUILD_CAPABILITIES), reason=reason)

    @staticmethod
    def revoke(db: Session, *, actor: User, target: User, guild_name: str, capabilities: list[str] | None = None) -> int:
        if not (actor.is_superuser or GuildAuthorizationService.is_verified_leader(db, actor, guild_name)):
            raise GuildAuthorizationError("Only a global administrator or verified guild leader can revoke permissions")
        query = db.query(GuildManagementGrant).filter(
            GuildManagementGrant.user_id == target.id,
            GuildManagementGrant.normalized_guild_name == normalize_guild_identity(guild_name),
            GuildManagementGrant.revoked_at.is_(None),
        )
        if capabilities is not None:
            query = query.filter(GuildManagementGrant.capability.in_(capabilities))
        rows = query.all()
        now = datetime.now(UTC)
        for row in rows:
            row.revoked_at = now
            row.revoked_by_id = actor.id
        db.add(WorkspaceAudit(
            actor_id=actor.id,
            workspace_type="admin_guild_assist" if actor.is_superuser else "guild",
            guild_name=guild_name.strip(),
            action="guild_management_permissions_revoked",
            target_type="user",
            target_id=str(target.id),
            assisted=bool(actor.is_superuser),
            safe_metadata={"capabilities": [row.capability for row in rows], "revoked": len(rows)},
        ))
        db.flush()
        return len(rows)
