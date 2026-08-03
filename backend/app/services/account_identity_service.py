"""Canonical account characters, primary display cache, guild discovery, and unlinking."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.character_ownership import CharacterOwnershipClaim, CharacterOwnershipHistory
from app.models.guild_management import GuildDirectory, GuildManagementGrant, GuildRosterCharacter
from app.models.user import User
from app.models.user_character import UserCharacter
from app.models.workspace_audit import WorkspaceAudit
from app.services.character_ownership_service import ACTIVE_CLAIM_STATUSES, normalize_character_name
from app.services.guild_roster_service import normalize_guild_identity


class AccountIdentityError(ValueError):
    pass


def _world_key(value: str) -> str:
    return " ".join((value or "").split()).casefold()


def _copy_character_to_legacy(user: User, character: UserCharacter | None) -> None:
    if character is None:
        user.primary_character_id = None
        user.tibia_character_name = None
        user.level = None
        user.vocation = None
        user.world_name = None
        user.guild_name = None
        user.guild_rank = "Unranked"
        user.residence = None
        user.achievement_points = None
        user.tibia_status = "no_primary_character"
        user.tibia_last_error = None
        return
    if character.user_id != user.id or character.ownership_status != "verified":
        raise AccountIdentityError("The primary character must be a verified character owned by this account")
    user.primary_character_id = character.id
    user.tibia_character_name = character.character_name
    user.level = character.level
    user.vocation = character.vocation
    user.world_name = character.world_name
    user.guild_name = character.guild_name
    user.guild_rank = character.guild_rank or "Unranked"
    user.residence = character.residence
    user.achievement_points = character.achievement_points
    user.tibia_status = "ownership_verified"
    user.tibia_last_error = None


class AccountIdentityService:
    @staticmethod
    def sync_primary_cache(user: User) -> None:
        character = user.primary_character
        if not character or character.user_id != user.id or character.ownership_status != "verified":
            _copy_character_to_legacy(user, None)
        else:
            _copy_character_to_legacy(user, character)

    @staticmethod
    def set_primary(db: Session, user: User, character: UserCharacter, actor: User) -> None:
        _copy_character_to_legacy(user, character)
        db.add(WorkspaceAudit(
            actor_id=actor.id, workspace_type="personal", guild_name=character.guild_name,
            action="primary_character_changed", target_type="user_character", target_id=str(character.id),
            assisted=actor.id != user.id,
            safe_metadata={"account_id": user.id, "character": character.character_name, "world": character.world_name},
        ))

    @staticmethod
    def discover_guild(db: Session, character: UserCharacter) -> GuildDirectory | None:
        guild_name = (character.guild_name or "").strip()
        world_name = (character.world_name or "").strip()
        if character.ownership_status != "verified" or not guild_name or not world_name:
            return None
        guild_key = normalize_guild_identity(guild_name)
        world_key = _world_key(world_name)
        directory = db.query(GuildDirectory).filter_by(
            normalized_guild_name=guild_key, normalized_world_name=world_key,
        ).first()
        if directory is None:
            directory = GuildDirectory(
                guild_name=guild_name, normalized_guild_name=guild_key,
                world_name=world_name, normalized_world_name=world_key,
                source="verified_character", sync_status="pending",
            )
            db.add(directory)
        else:
            directory.guild_name = guild_name
            directory.world_name = world_name
            directory.is_active = True
            if not directory.last_successful_sync_at or datetime.now(UTC) - directory.last_successful_sync_at > timedelta(hours=6):
                directory.sync_status = "pending"
        roster = db.query(GuildRosterCharacter).filter(
            GuildRosterCharacter.normalized_guild_name == guild_key,
            GuildRosterCharacter.normalized_world_name == world_key,
            GuildRosterCharacter.normalized_character_name == character.normalized_name,
            GuildRosterCharacter.is_current.is_(True),
        ).first()
        if roster:
            roster.linked_user_character_id = character.id
            roster.linked_user_id = character.user_id
        return directory

    @staticmethod
    def serialize_character(db: Session, character: UserCharacter, *, primary_character_id: int | None) -> dict:
        from app.services.guild_authorization_service import GuildAuthorizationService, SUPPORTED_GUILD_CAPABILITIES

        roster = db.query(GuildRosterCharacter).filter(
            GuildRosterCharacter.linked_user_character_id == character.id,
            GuildRosterCharacter.is_current.is_(True),
        ).first()
        capabilities = {
            capability: bool(
                character.ownership_status == "verified"
                and character.guild_name
                and GuildAuthorizationService.can_manage(db, character.user, character.guild_name, capability)
            )
            for capability in SUPPORTED_GUILD_CAPABILITIES
        }
        return {
            "id": character.id, "character_name": character.character_name,
            "world_name": character.world_name, "guild_name": character.guild_name,
            "guild_rank": character.guild_rank, "level": character.level,
            "vocation": character.vocation, "residence": character.residence,
            "achievement_points": character.achievement_points,
            "ownership_status": character.ownership_status,
            "verification_method": character.verification_method,
            "ownership_verified_at": character.ownership_verified_at,
            "is_primary": character.id == primary_character_id,
            "is_current_roster_member": roster is not None,
            "guild_capabilities": capabilities,
        }

    @staticmethod
    def unlink(db: Session, user: User, character: UserCharacter, actor: User, reason: str) -> None:
        if character.user_id != user.id or character.ownership_status != "verified":
            raise AccountIdentityError("Only a verified character owned by this account can be unlinked")
        pending = db.query(CharacterOwnershipClaim.id).filter(
            CharacterOwnershipClaim.normalized_name == character.normalized_name,
            CharacterOwnershipClaim.status.in_(ACTIVE_CLAIM_STATUSES - {"pending", "queued", "processing"}),
        ).first()
        if pending:
            raise AccountIdentityError("Resolve the pending ownership transfer before unlinking this character")
        now = datetime.now(UTC)
        guild_key = normalize_guild_identity(character.guild_name or "")
        remaining_membership = bool(character.guild_name and db.query(UserCharacter.id).filter(
            UserCharacter.user_id == user.id,
            UserCharacter.id != character.id,
            UserCharacter.ownership_status == "verified",
            func.lower(UserCharacter.guild_name) == (character.guild_name or "").casefold(),
        ).first())
        if guild_key and not remaining_membership:
            grants = db.query(GuildManagementGrant).filter(
                GuildManagementGrant.user_id == user.id,
                GuildManagementGrant.normalized_guild_name == guild_key,
                GuildManagementGrant.revoked_at.is_(None),
            ).all()
            for grant in grants:
                grant.revoked_at = now
                grant.revoked_by_id = actor.id
                grant.audit_metadata = {**(grant.audit_metadata or {}), "automatic_reason": "verified_membership_removed"}
        db.query(GuildRosterCharacter).filter(
            GuildRosterCharacter.linked_user_character_id == character.id,
        ).update({
            GuildRosterCharacter.linked_user_character_id: None,
            GuildRosterCharacter.linked_user_id: None,
        }, synchronize_session=False)
        character.ownership_status = "unlinked"
        character.unlinked_at = now
        character.unlinked_by_user_id = actor.id
        if user.primary_character_id == character.id:
            _copy_character_to_legacy(user, None)
        db.add(CharacterOwnershipHistory(
            normalized_name=character.normalized_name,
            character_name=character.character_name,
            claim_id=character.ownership_claim_id,
            action="ownership_unlinked", from_user_id=user.id,
            actor_user_id=actor.id,
            safe_metadata={"guild": character.guild_name, "world": character.world_name, "reason": reason.strip()},
        ))
        db.add(WorkspaceAudit(
            actor_id=actor.id, workspace_type="personal", guild_name=character.guild_name,
            action="character_unlinked", target_type="user_character", target_id=str(character.id),
            assisted=actor.id != user.id,
            safe_metadata={"account_id": user.id, "character": character.character_name, "world": character.world_name, "reason": reason.strip()},
        ))

    @staticmethod
    def admin_link(
        db: Session, *, admin: User, target: User, character_name: str,
        snapshot: dict, reason: str, set_primary: bool, allow_transfer: bool,
    ) -> UserCharacter:
        normalized = normalize_character_name(character_name)
        character = db.query(UserCharacter).filter(
            (UserCharacter.normalized_name == normalized)
            | (func.lower(UserCharacter.character_name) == normalized)
        ).with_for_update().first()
        previous_user_id = character.user_id if character else None
        previous_user = db.get(User, previous_user_id) if previous_user_id and previous_user_id != target.id else None
        if character and character.ownership_status in {"verified", "disputed"} and character.user_id != target.id and not allow_transfer:
            raise AccountIdentityError("The character already has an owner; use the explicit administrative transfer confirmation")
        if character is None:
            character = UserCharacter(user_id=target.id, character_name=character_name, normalized_name=normalized)
            db.add(character)
        character.user_id = target.id
        character.character_name = snapshot.get("name") or character_name
        character.normalized_name = normalize_character_name(character.character_name)
        guild = snapshot.get("guild") or {}
        character.world_name = snapshot.get("world") or character.world_name
        character.guild_name = guild.get("name") or character.guild_name
        character.guild_rank = guild.get("rank") or character.guild_rank
        character.level = snapshot.get("level")
        character.vocation = snapshot.get("vocation")
        character.residence = snapshot.get("residence")
        character.achievement_points = snapshot.get("achievement_points")
        character.ownership_status = "verified"
        character.ownership_verified_at = datetime.now(UTC)
        character.verification_method = "admin_override"
        character.verified_by_user_id = admin.id
        character.verification_reason = reason.strip()
        character.unlinked_at = None
        character.unlinked_by_user_id = None
        db.flush()
        if previous_user and previous_user.primary_character_id == character.id:
            _copy_character_to_legacy(previous_user, None)
        if set_primary or target.primary_character_id is None:
            _copy_character_to_legacy(target, character)
        AccountIdentityService.discover_guild(db, character)
        db.add(CharacterOwnershipHistory(
            normalized_name=character.normalized_name, character_name=character.character_name,
            action="admin_ownership_linked" if previous_user_id in {None, target.id} else "admin_ownership_transferred",
            from_user_id=previous_user_id if previous_user_id != target.id else None,
            to_user_id=target.id, actor_user_id=admin.id,
            safe_metadata={"reason": reason.strip(), "set_primary": bool(set_primary), "admin_assistance": True},
        ))
        db.add(WorkspaceAudit(
            actor_id=admin.id, workspace_type="admin", guild_name=character.guild_name,
            action="admin_character_linked", target_type="user_character", target_id=str(character.id),
            assisted=True,
            safe_metadata={"account_id": target.id, "character": character.character_name, "world": character.world_name, "reason": reason.strip(), "transfer": previous_user_id not in {None, target.id}},
        ))
        return character
