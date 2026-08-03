from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.permissions import can_view_guild_workspace, is_global_admin, is_guild_leader, is_guild_viceleader
from app.models.leadership import (
    GuildLeadershipApplication, GuildLeadershipApplicationHistory,
    GuildLeadershipApplicationMessage, GuildLeadershipAssignment,
    GuildLeadershipOpening, GuildLeadershipRole, GuildLeadershipVote,
)
from app.models.user import User
from app.models.workspace_audit import WorkspaceAudit
from app.services.notification_service import NotificationService

CONDUCT_VERSION = "2026-07-v1"
ACTIVE_APPLICATION_STATUSES = {"applied", "under_review", "more_information_requested", "interview", "voting"}
TERMINAL_STATUSES = {"accepted", "rejected", "withdrawn", "cancelled"}
TRANSITIONS = {
    "applied": {"under_review", "more_information_requested", "rejected", "withdrawn", "cancelled"},
    "under_review": {"more_information_requested", "interview", "voting", "accepted", "rejected", "withdrawn", "cancelled"},
    "more_information_requested": {"under_review", "interview", "rejected", "withdrawn", "cancelled"},
    "interview": {"voting", "accepted", "rejected", "withdrawn", "cancelled"},
    "voting": {"accepted", "rejected", "withdrawn", "cancelled"},
}


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class LeadershipService:
    @staticmethod
    def valid_actions(application: GuildLeadershipApplication, viewer: User) -> list[str]:
        applicant = application.applicant_user_id == viewer.id
        reviewer = LeadershipService.reviewer(viewer, application.opening)
        manager = LeadershipService.manager(viewer, application.opening.guild_name)
        actions: list[str] = []
        if applicant and application.status in ACTIVE_APPLICATION_STATUSES:
            actions.append("withdraw")
            if application.status == "more_information_requested":
                actions.append("reply")
        if reviewer:
            actions.append("comment")
            if application.opening.voting_enabled and application.status == "voting" and not applicant:
                actions.append("vote")
        if manager and application.status not in TERMINAL_STATUSES:
            if application.status == "applied": actions.append("start_review")
            if application.status in {"applied", "under_review", "more_information_requested"}: actions.append("request_information")
            if application.status in {"under_review", "more_information_requested", "interview"}: actions.append("schedule_interview")
            if application.opening.voting_enabled and application.status in {"under_review", "interview"}: actions.append("start_voting")
            if "accepted" in TRANSITIONS.get(application.status, set()): actions.append("accept")
            if "rejected" in TRANSITIONS.get(application.status, set()): actions.append("reject")
            if "cancelled" in TRANSITIONS.get(application.status, set()): actions.append("cancel")
            if application.status == "more_information_requested": actions.append("return_to_review")
        return actions

    @staticmethod
    def ensure_role(db: Session, guild_name: str, actor: User) -> GuildLeadershipRole:
        role = db.query(GuildLeadershipRole).filter(GuildLeadershipRole.guild_name.ilike(guild_name), GuildLeadershipRole.role_code == "viceleader").first()
        if role:
            return role
        role = GuildLeadershipRole(guild_name=guild_name, role_code="viceleader", display_name_key="leadership.roles.viceleader", description_key="leadership.roles.viceleaderDescription", target_count=4, created_by_id=actor.id)
        db.add(role); db.flush()
        return role

    @staticmethod
    def leaders(db: Session, guild_name: str) -> list[User]:
        return [user for user in db.query(User).filter(User.is_active.is_(True)).all() if is_guild_leader(user, guild_name)]

    @staticmethod
    def reviewers(db: Session, opening: GuildLeadershipOpening) -> list[User]:
        return [
            user for user in db.query(User).filter(User.is_active.is_(True)).all()
            if LeadershipService.reviewer(user, opening)
        ]

    @staticmethod
    def reviewer(user: User, opening: GuildLeadershipOpening) -> bool:
        return bool(is_global_admin(user) or is_guild_leader(user, opening.guild_name) or (opening.allow_viceleader_review and is_guild_viceleader(user, opening.guild_name)))

    @staticmethod
    def manager(user: User, guild_name: str) -> bool:
        return bool(is_global_admin(user) or is_guild_leader(user, guild_name))

    @staticmethod
    def eligible_opening(opening: GuildLeadershipOpening, user: User) -> bool:
        now = datetime.now(UTC)
        accepted = sum(1 for application in opening.applications if application.status == "accepted")
        active_for_user = any(
            application.applicant_user_id == user.id and application.status in ACTIVE_APPLICATION_STATUSES
            for application in opening.applications
        )
        assigned_to_user = any(
            application.applicant_user_id == user.id
            and application.accepted_assignment is not None
            and application.accepted_assignment.is_active
            for application in opening.applications
        )
        return bool(
            user.is_active
            and can_view_guild_workspace(user, opening.guild_name)
            and not is_guild_leader(user, opening.guild_name)
            and not is_guild_viceleader(user, opening.guild_name)
            and opening.status == "open"
            and opening.role.is_active
            and opening.role.recruitment_enabled
            and (opening.application_deadline is None or _as_utc(opening.application_deadline) >= now)
            and accepted < opening.openings_count
            and not active_for_user
            and not assigned_to_user
        )

    @staticmethod
    def can_view_opening(opening: GuildLeadershipOpening, user: User) -> bool:
        if LeadershipService.manager(user, opening.guild_name):
            return True
        if opening.status != "draft" and LeadershipService.reviewer(user, opening):
            return True
        return LeadershipService.eligible_opening(opening, user)

    @staticmethod
    def actor_context(user: User, guild_name: str) -> str:
        owns_guild_character = any(
            row.ownership_status == "verified"
            and (row.guild_name or "").casefold() == guild_name.casefold()
            for row in getattr(user, "characters", [])
        )
        return "admin_assistance" if is_global_admin(user) and not owns_guild_character else "guild"

    @staticmethod
    def audit(db: Session, user: User, guild_name: str, action: str, target_type: str, target_id: int, metadata: dict | None = None) -> None:
        context = LeadershipService.actor_context(user, guild_name)
        db.add(WorkspaceAudit(actor_id=user.id, workspace_type="admin_guild_assist" if context == "admin_assistance" else "guild", guild_name=guild_name, action=action, target_type=target_type, target_id=str(target_id), assisted=context == "admin_assistance", safe_metadata=metadata or {}))

    @staticmethod
    def profile_snapshot(user: User, character) -> dict:
        return {"character_name": character.character_name, "level": character.level, "vocation": character.vocation, "guild_name": character.guild_name, "guild_rank": character.guild_rank, "join_date": user.join_date.isoformat() if user.join_date else None, "last_activity": (character.last_seen or character.last_login_at or user.last_login_at).isoformat() if (character.last_seen or character.last_login_at or user.last_login_at) else None, "discord_username": user.discord_username, "world": character.world_name}

    @staticmethod
    def apply(db: Session, opening: GuildLeadershipOpening, user: User, payload) -> GuildLeadershipApplication:
        if not LeadershipService.eligible_opening(opening, user):
            raise HTTPException(409, "Opening is not accepting applications")
        if not can_view_guild_workspace(user, opening.guild_name) or is_guild_leader(user, opening.guild_name) or is_guild_viceleader(user, opening.guild_name):
            raise HTTPException(403, "Applicant is not an eligible guild member")
        character = next((
            entry for entry in user.characters
            if entry.ownership_status == "verified"
            and entry.character_name.casefold() == payload.character_name.casefold()
        ), None)
        if not character or not character.guild_name or character.guild_name.casefold() != opening.guild_name.casefold():
            raise HTTPException(400, "Selected character is not linked to this guild")
        duplicate = db.query(GuildLeadershipApplication).filter(GuildLeadershipApplication.opening_id == opening.id, GuildLeadershipApplication.applicant_user_id == user.id, GuildLeadershipApplication.status.in_(ACTIVE_APPLICATION_STATUSES)).first()
        assignment = db.query(GuildLeadershipAssignment).filter(GuildLeadershipAssignment.guild_name.ilike(opening.guild_name), GuildLeadershipAssignment.role_id == opening.role_id, GuildLeadershipAssignment.user_id == user.id, GuildLeadershipAssignment.is_active.is_(True)).first()
        if duplicate or assignment:
            raise HTTPException(409, "An active application or assignment already exists")
        now = datetime.now(UTC)
        application = GuildLeadershipApplication(opening_id=opening.id, applicant_user_id=user.id, character_name=character.character_name, status="applied", why_apply=payload.why_apply, contribution=payload.contribution, availability=payload.availability, leadership_experience=payload.leadership_experience, applicant_message=payload.applicant_message, profile_snapshot=LeadershipService.profile_snapshot(user, character), conduct_agreed_at=now, conduct_version=CONDUCT_VERSION, submitted_at=now)
        db.add(application); db.flush()
        db.add(GuildLeadershipApplicationHistory(application_id=application.id, from_status=None, to_status="applied", actor_id=user.id, actor_context="applicant", safe_metadata={"conduct_version": CONDUCT_VERSION}))
        LeadershipService.audit(db, user, opening.guild_name, "leadership_application_submitted", "leadership_application", application.id)
        NotificationService.emit_users(db, LeadershipService.reviewers(db, opening), "leadership_application_received", f"leadership:application:{application.id}:received", guild_name=opening.guild_name, deep_link=f"/guild/leadership/recruitment/applications/{application.id}", payload={"character": application.character_name})
        return application

    @staticmethod
    def transition(db: Session, application: GuildLeadershipApplication, actor: User, target: str, reason: str | None = None, *, override: bool = False) -> None:
        opening = application.opening
        if not LeadershipService.manager(actor, opening.guild_name):
            raise HTTPException(403, "Only the guild leader may make final workflow decisions")
        if application.status in TERMINAL_STATUSES and not (override and is_global_admin(actor) and reason):
            raise HTTPException(409, "Final applications cannot be changed")
        if target not in TRANSITIONS.get(application.status, set()) and not (override and is_global_admin(actor) and reason):
            raise HTTPException(409, "Invalid application status transition")
        if target == "rejected" and not (reason or "").strip():
            raise HTTPException(422, "A rejection reason is required")
        previous = application.status; application.status = target; application.version += 1
        now = datetime.now(UTC)
        if target == "withdrawn": application.withdrawn_at = now
        if target in {"accepted", "rejected"}: application.final_decision_at = now; application.final_decision_by_id = actor.id
        if target == "rejected": application.rejection_reason = reason
        db.add(GuildLeadershipApplicationHistory(application_id=application.id, from_status=previous, to_status=target, actor_id=actor.id, actor_context=LeadershipService.actor_context(actor, opening.guild_name), reason=reason, safe_metadata={"admin_override": override}))
        LeadershipService.audit(db, actor, opening.guild_name, "leadership_application_status_changed", "leadership_application", application.id, {"from": previous, "to": target, "admin_override": override})
        NotificationService.emit_users(db, [application.applicant], "leadership_application_status_changed", f"leadership:application:{application.id}:status:{target}:{application.version}", guild_name=opening.guild_name, deep_link=f"/guild/leadership/recruitment/applications/{application.id}", payload={"status": target})

    @staticmethod
    def accept(db: Session, application: GuildLeadershipApplication, actor: User, reason: str | None) -> GuildLeadershipAssignment:
        if application.opening.voting_enabled:
            if application.status != "voting":
                raise HTTPException(409, "The application must enter voting before a decision")
            participation = db.query(GuildLeadershipVote).filter_by(application_id=application.id).count()
            if participation < application.opening.votes_required:
                raise HTTPException(409, "The required reviewer participation has not been reached")
        existing = db.query(GuildLeadershipAssignment).filter(GuildLeadershipAssignment.guild_name.ilike(application.opening.guild_name), GuildLeadershipAssignment.role_id == application.opening.role_id, GuildLeadershipAssignment.user_id == application.applicant_user_id, GuildLeadershipAssignment.is_active.is_(True)).first()
        if existing: raise HTTPException(409, "An active assignment already exists")
        LeadershipService.transition(db, application, actor, "accepted", reason)
        assignment = GuildLeadershipAssignment(guild_name=application.opening.guild_name, role_id=application.opening.role_id, user_id=application.applicant_user_id, character_name=application.character_name, assigned_by_id=actor.id, started_at=datetime.now(UTC), in_game_promotion_status="pending")
        db.add(assignment); db.flush(); application.accepted_assignment_id = assignment.id
        LeadershipService.audit(db, actor, application.opening.guild_name, "leadership_assignment_created", "leadership_assignment", assignment.id)
        NotificationService.emit_users(db, [application.applicant], "leadership_application_accepted", f"leadership:application:{application.id}:accepted", guild_name=application.opening.guild_name, deep_link=f"/guild/leadership/recruitment/applications/{application.id}", payload={"character": application.character_name})
        return assignment
