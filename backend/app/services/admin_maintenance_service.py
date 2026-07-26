"""Preflighted, service-owned maintenance operations for global administrators."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.knowledge.models import KnowledgeEntity, KnowledgeRelationship
from app.models.events import Event
from app.models.hunt import GuildHunt
from app.models.leadership import GuildLeadershipApplication, GuildLeadershipOpening
from app.models.raffle import Raffle
from app.models.user import User
from app.models.user_character import UserCharacter
from app.models.workspace_audit import WorkspaceAudit
from app.services.guild_hunt_service import GuildHuntPlannerService


class MaintenanceError(ValueError):
    pass


class AdminMaintenanceService:
    CATEGORIES = {"guilds", "users", "characters", "raffles", "leadership", "events", "hunts", "knowledge"}
    ACTIVE_APPLICATIONS = {"applied", "under_review", "more_information_requested", "interview", "voting"}

    @classmethod
    def list_items(cls, db: Session, category: str, search: str = "", limit: int = 100) -> list[dict]:
        cls._category(category)
        needle = search.strip()
        if category == "guilds":
            names = set()
            for model in (User, Event, Raffle, GuildHunt, GuildLeadershipOpening):
                for (name,) in db.query(model.guild_name).filter(model.guild_name.isnot(None)).distinct().all():
                    if name and (not needle or needle.casefold() in name.casefold()):
                        names.add(name.strip())
            return [cls.preflight(db, category, name) for name in sorted(names)[:limit]]
        model, label_column = cls._model(category)
        query = db.query(model)
        if needle:
            query = query.filter(label_column.ilike(f"%{needle}%"))
        rows = query.order_by(label_column.asc()).limit(limit).all()
        return [cls.preflight(db, category, str(cls._identity(category, row)), row=row) for row in rows]

    @classmethod
    def preflight(cls, db: Session, category: str, identity: str, *, row=None) -> dict:
        cls._category(category)
        if category == "guilds":
            label = identity.strip()
            if not label:
                raise MaintenanceError("Guild not found")
            counts = {
                "active_users": db.query(User).filter(User.guild_name.ilike(label), User.is_active.is_(True)).count(),
                "active_events": db.query(Event).filter(Event.guild_name.ilike(label), Event.is_deleted.is_(False)).count(),
                "active_raffles": db.query(Raffle).filter(Raffle.guild_name.ilike(label), Raffle.is_deleted.is_(False)).count(),
                "hunts": db.query(GuildHunt).filter(GuildHunt.guild_name.ilike(label)).count(),
                "leadership_openings": db.query(GuildLeadershipOpening).filter(GuildLeadershipOpening.guild_name.ilike(label)).count(),
            }
            return cls._result(category, identity, label, "inspect_only", ["guild_aggregate"], counts)
        if row is None:
            row = cls._get(db, category, identity)
        if row is None:
            raise MaintenanceError("Maintenance record not found")
        blockers: list[str] = []
        counts: dict[str, int] = {}
        action = "retire"
        label = cls._label(category, row)
        if category == "users":
            action = "deactivate"
            if not row.is_active:
                blockers.append("user_inactive")
            if row.is_superuser and db.query(User).filter(User.is_superuser.is_(True), User.is_active.is_(True)).count() <= 1:
                blockers.append("final_global_admin")
            counts["owned_characters"] = db.query(UserCharacter).filter_by(user_id=row.id).count()
        elif category == "characters":
            action = "unlink"
            if row.ownership_status != "legacy_unverified" or row.ownership_claim_id is not None:
                blockers.append("character_ownership_workflow")
        elif category == "raffles":
            action = "soft_delete"
            if row.is_deleted:
                blockers.append("raffle_deleted")
            if row.execution_state in {"claimed", "running"}:
                blockers.append("raffle_running")
            counts.update({"participants": len(row.participants), "winners": len(row.winners)})
        elif category == "leadership":
            action = "archive"
            active = db.query(GuildLeadershipApplication).filter(
                GuildLeadershipApplication.opening_id == row.id,
                GuildLeadershipApplication.status.in_(cls.ACTIVE_APPLICATIONS),
            ).count()
            counts["active_applications"] = active
            if active:
                blockers.append("leadership_active_applications")
            if row.status == "archived":
                blockers.append("leadership_archived")
        elif category == "events":
            action = "soft_delete"
            if row.is_deleted:
                blockers.append("event_deleted")
            counts["participants"] = len(row.participants)
        elif category == "hunts":
            action = "cancel"
            if row.status != "scheduled":
                blockers.append("hunt_not_scheduled")
            counts["participants"] = len(row.participants)
        elif category == "knowledge":
            action = "retire"
            if row.status == "retired":
                blockers.append("knowledge_retired")
            counts["relationships"] = db.query(KnowledgeRelationship).filter(or_(
                KnowledgeRelationship.source_entity_id == row.uuid,
                KnowledgeRelationship.target_entity_id == row.uuid,
            )).count()
        return cls._result(category, identity, label, action, blockers, counts)

    @classmethod
    def execute(cls, db: Session, actor: User, category: str, identity: str, confirmation: str, reason: str) -> dict:
        if not actor.is_superuser or not actor.is_active:
            raise PermissionError("Active global administrator required")
        report = cls.preflight(db, category, identity)
        if report["blockers"]:
            raise MaintenanceError(report["blockers"][0])
        if confirmation.strip() != report["confirmation"]:
            raise MaintenanceError("Confirmation text does not match the selected record")
        if len(reason.strip()) < 5:
            raise MaintenanceError("A maintenance reason of at least five characters is required")
        row = cls._get(db, category, identity)
        now = datetime.now(UTC)
        if category == "users":
            row.is_active = False
        elif category == "characters":
            user = row.user
            if (user.tibia_character_name or "").casefold() == row.character_name.casefold():
                for field in ("tibia_character_name", "vocation", "level", "world_name", "guild_name", "guild_rank", "residence", "achievement_points", "tibia_status"):
                    setattr(user, field, None)
            db.delete(row)
        elif category == "raffles":
            row.is_deleted = True; row.deleted_at = now; row.deleted_by_user_id = actor.id
            row.delete_reason = reason.strip(); row.is_active = False; row.status = "deleted"
        elif category == "leadership":
            row.status = "archived"; row.version += 1
        elif category == "events":
            row.is_active = False; row.is_deleted = True; row.deleted_at = now
            row.deleted_by_user_id = actor.id; row.delete_reason = reason.strip(); row.status = "deleted"
        elif category == "hunts":
            GuildHuntPlannerService.transition(db, actor, row, "cancel", reason=reason)
        elif category == "knowledge":
            row.status = "retired"; row.visibility = "internal"; row.search_weight = 0
        else:
            raise MaintenanceError("Guild aggregates cannot be deleted directly")
        db.flush()
        db.add(WorkspaceAudit(
            actor_id=actor.id, workspace_type="admin", guild_name=getattr(row, "guild_name", None),
            action=f"maintenance_{report['action']}", target_type=category, target_id=identity,
            assisted=False, safe_metadata={"reason": reason.strip(), "preflight_counts": report["counts"]},
        ))
        return {**report, "executed": True}

    @staticmethod
    def _result(category: str, identity: str, label: str, action: str, blockers: list[str], counts: dict) -> dict:
        return {"category": category, "id": identity, "label": label, "action": action, "deletable": not blockers and action != "inspect_only", "blockers": blockers, "counts": counts, "confirmation": label}

    @classmethod
    def _category(cls, category: str) -> None:
        if category not in cls.CATEGORIES:
            raise MaintenanceError("Unknown maintenance category")

    @staticmethod
    def _model(category: str):
        return {
            "users": (User, User.username),
            "characters": (UserCharacter, UserCharacter.character_name),
            "raffles": (Raffle, Raffle.title),
            "leadership": (GuildLeadershipOpening, GuildLeadershipOpening.title),
            "events": (Event, Event.title),
            "hunts": (GuildHunt, GuildHunt.target),
            "knowledge": (KnowledgeEntity, KnowledgeEntity.canonical_name),
        }[category]

    @staticmethod
    def _identity(category: str, row):
        return row.uuid if category == "knowledge" else row.id

    @staticmethod
    def _label(category: str, row) -> str:
        if category == "users":
            return row.username
        if category == "characters":
            return row.character_name
        if category in {"raffles", "leadership", "events"}:
            return row.title
        if category == "hunts":
            return f"{row.target} — {row.scheduled_at.date().isoformat()}"
        return row.canonical_name

    @staticmethod
    def _get(db: Session, category: str, identity: str):
        model, _ = AdminMaintenanceService._model(category)
        try:
            key = UUID(identity) if category == "knowledge" else int(identity)
        except (TypeError, ValueError):
            return None
        return db.get(model, key)
