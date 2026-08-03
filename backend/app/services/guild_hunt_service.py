"""Guild Hunt Planner business rules.

All writes flow through this service so the API, dashboard, and maintenance UI
share the same authorization, lifecycle, capacity, and audit behavior.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session, selectinload

from app.core.permissions import can_manage_guild, can_view_guild_workspace
from app.models.hunt import GuildHunt, GuildHuntParticipant
from app.models.user import User
from app.models.user_character import UserCharacter
from app.models.workspace_audit import WorkspaceAudit


class GuildHuntError(ValueError):
    pass


class GuildHuntPlannerService:
    ACTIVE_ATTENDANCE = {"registered", "attended"}

    @staticmethod
    def can_manage(db: Session, user: User, hunt: GuildHunt) -> bool:
        return can_manage_guild(user, hunt.guild_name, db=db, capability="hunts.manage")

    @staticmethod
    def can_view(user: User, hunt: GuildHunt) -> bool:
        return can_view_guild_workspace(user, hunt.guild_name)

    @staticmethod
    def audit(db: Session, actor: User, hunt: GuildHunt, action: str, metadata: dict | None = None) -> None:
        db.add(WorkspaceAudit(
            actor_id=actor.id,
            workspace_type="admin_guild_assist" if actor.is_superuser and (actor.guild_name or "").casefold() != hunt.guild_name.casefold() else "guild",
            guild_name=hunt.guild_name,
            action=action,
            target_type="guild_hunt",
            target_id=str(hunt.id),
            assisted=bool(actor.is_superuser and (actor.guild_name or "").casefold() != hunt.guild_name.casefold()),
            safe_metadata=metadata or {},
        ))

    @staticmethod
    def get(db: Session, hunt_id: int, *, lock: bool = False) -> GuildHunt | None:
        query = db.query(GuildHunt).options(
            selectinload(GuildHunt.participants).selectinload(GuildHuntParticipant.user),
        ).filter(GuildHunt.id == hunt_id)
        if lock:
            query = query.with_for_update()
        return query.first()

    @staticmethod
    def list_for_guild(db: Session, guild_name: str, *, start: datetime | None = None, end: datetime | None = None, statuses: set[str] | None = None) -> list[GuildHunt]:
        query = db.query(GuildHunt).options(selectinload(GuildHunt.participants)).filter(GuildHunt.guild_name.ilike(guild_name))
        if start is not None:
            query = query.filter(GuildHunt.scheduled_at >= start)
        if end is not None:
            query = query.filter(GuildHunt.scheduled_at < end)
        if statuses:
            query = query.filter(GuildHunt.status.in_(statuses))
        return query.order_by(GuildHunt.scheduled_at.asc()).limit(500).all()

    @staticmethod
    def create(db: Session, actor: User, guild_name: str, values: dict) -> GuildHunt:
        if not can_manage_guild(actor, guild_name, db=db, capability="hunts.manage"):
            raise PermissionError("Guild leader permission required")
        values = dict(values)
        values.pop("guild_name", None)
        GuildHuntPlannerService._validate_capacity(values)
        GuildHuntPlannerService._validate_schedule(values["scheduled_at"])
        hunt = GuildHunt(guild_name=guild_name, created_by_id=actor.id, status="scheduled", **values)
        db.add(hunt)
        db.flush()
        GuildHuntPlannerService.audit(db, actor, hunt, "guild_hunt_created")
        return hunt

    @staticmethod
    def update(db: Session, actor: User, hunt: GuildHunt, values: dict) -> GuildHunt:
        if not GuildHuntPlannerService.can_manage(db, actor, hunt):
            raise PermissionError("Guild leader permission required")
        if hunt.status != "scheduled":
            raise GuildHuntError("Only scheduled hunts can be edited")
        merged = {field: getattr(hunt, field) for field in ("maximum_participants", "required_ek", "required_ed", "required_rp", "required_ms")}
        merged.update({key: value for key, value in values.items() if value is not None})
        GuildHuntPlannerService._validate_capacity(merged)
        if values.get("scheduled_at") is not None:
            GuildHuntPlannerService._validate_schedule(values["scheduled_at"])
        registered = sum(1 for item in hunt.participants if item.attendance_status in GuildHuntPlannerService.ACTIVE_ATTENDANCE)
        if merged["maximum_participants"] < registered:
            raise GuildHuntError("Capacity cannot be lower than current registrations")
        for key, value in values.items():
            if value is not None:
                setattr(hunt, key, value)
        GuildHuntPlannerService.audit(db, actor, hunt, "guild_hunt_updated")
        return hunt

    @staticmethod
    def transition(db: Session, actor: User, hunt: GuildHunt, action: str, *, reason: str | None = None) -> GuildHunt:
        if not GuildHuntPlannerService.can_manage(db, actor, hunt):
            raise PermissionError("Guild leader permission required")
        allowed = {("scheduled", "cancel"), ("scheduled", "start"), ("in_progress", "finish")}
        if (hunt.status, action) not in allowed:
            raise GuildHuntError("Invalid hunt lifecycle transition")
        now = datetime.now(UTC)
        if action == "cancel":
            if not reason or len(reason.strip()) < 3:
                raise GuildHuntError("Cancellation reason is required")
            hunt.status = "cancelled"
            hunt.cancelled_by_id = actor.id
            hunt.cancellation_reason = reason.strip()
        elif action == "start":
            hunt.status = "in_progress"
            hunt.started_at = now
        else:
            hunt.status = "finished"
            hunt.finished_at = now
        GuildHuntPlannerService.audit(db, actor, hunt, f"guild_hunt_{action}ed", {"reason_supplied": bool(reason)})
        return hunt

    @staticmethod
    def join(db: Session, actor: User, hunt: GuildHunt) -> GuildHuntParticipant:
        if not GuildHuntPlannerService.can_view(actor, hunt) or hunt.status != "scheduled":
            raise PermissionError("This hunt is not available to join")
        existing = next((item for item in hunt.participants if item.user_id == actor.id), None)
        active_count = sum(1 for item in hunt.participants if item.attendance_status in GuildHuntPlannerService.ACTIVE_ATTENDANCE)
        if (existing is None or existing.attendance_status not in GuildHuntPlannerService.ACTIVE_ATTENDANCE) and active_count >= hunt.maximum_participants:
            raise GuildHuntError("This hunt is full")
        character = db.query(UserCharacter).filter(
            UserCharacter.user_id == actor.id,
            UserCharacter.ownership_status == "verified",
            UserCharacter.guild_name.ilike(hunt.guild_name),
        ).order_by(UserCharacter.ownership_verified_at.desc()).first()
        if character is None:
            raise GuildHuntError("A verified character in this guild is required")
        if existing:
            existing.character_name = character.character_name
            existing.vocation = character.vocation or actor.vocation
            existing.attendance_status = "registered"
            existing.joined_at = datetime.now(UTC)
            existing.left_at = None
            participant = existing
        else:
            participant = GuildHuntParticipant(
                user_id=actor.id,
                character_name=character.character_name,
                vocation=character.vocation or actor.vocation,
                attendance_status="registered",
            )
            hunt.participants.append(participant)
        GuildHuntPlannerService.audit(db, actor, hunt, "guild_hunt_joined")
        return participant

    @staticmethod
    def leave(db: Session, actor: User, hunt: GuildHunt) -> GuildHuntParticipant:
        if hunt.status != "scheduled":
            raise GuildHuntError("Only scheduled hunts can be left")
        participant = next((item for item in hunt.participants if item.user_id == actor.id), None)
        if participant is None or participant.attendance_status != "registered":
            raise GuildHuntError("You are not registered for this hunt")
        participant.attendance_status = "left"
        participant.left_at = datetime.now(UTC)
        GuildHuntPlannerService.audit(db, actor, hunt, "guild_hunt_left")
        return participant

    @staticmethod
    def mark_attendance(db: Session, actor: User, hunt: GuildHunt, participant: GuildHuntParticipant, status: str) -> GuildHuntParticipant:
        if not GuildHuntPlannerService.can_manage(db, actor, hunt):
            raise PermissionError("Guild leader permission required")
        if hunt.status not in {"in_progress", "finished"} or status not in {"attended", "absent"}:
            raise GuildHuntError("Attendance can be recorded only after a hunt starts")
        if (participant.hunt_id != hunt.id and participant.hunt is not hunt) or participant.attendance_status == "left":
            raise GuildHuntError("Participant is not registered for this hunt")
        participant.attendance_status = status
        participant.attendance_marked_at = datetime.now(UTC)
        participant.attendance_marked_by_id = actor.id
        GuildHuntPlannerService.audit(db, actor, hunt, "guild_hunt_attendance_marked", {"attendance_status": status})
        return participant

    @staticmethod
    def _validate_capacity(values: dict) -> None:
        required = sum(int(values.get(field, 0) or 0) for field in ("required_ek", "required_ed", "required_rp", "required_ms"))
        if required > int(values["maximum_participants"]):
            raise GuildHuntError("Required vocation slots cannot exceed maximum participants")

    @staticmethod
    def _validate_schedule(value: datetime) -> None:
        scheduled = value if value.tzinfo else value.replace(tzinfo=UTC)
        if scheduled <= datetime.now(UTC):
            raise GuildHuntError("Guild hunts must be scheduled in the future")
