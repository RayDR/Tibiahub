from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.api.v1.endpoints.auth import get_current_active_user, get_current_admin_user
from app.api.v1.endpoints.workspaces import _resolve_registered_guild
from app.core.permissions import is_guild_viceleader
from app.db.database import get_db
from app.models.leadership import (
    GuildLeadershipApplication, GuildLeadershipApplicationMessage, GuildLeadershipAssignment,
    GuildLeadershipInterview, GuildLeadershipOpening, GuildLeadershipRole, GuildLeadershipVote,
)
from app.models.user import User
from app.schemas.leadership import (
    ApplicationCreate, AssignmentEnd, DecisionCreate, InterviewCreate, MessageCreate, OpeningCreate,
    OpeningUpdate, PromotionUpdate, StatusUpdate, VoteCreate,
)
from app.services.leadership_service import ACTIVE_APPLICATION_STATUSES, LeadershipService
from app.services.notification_service import NotificationService

router = APIRouter()
admin_router = APIRouter()


def own_guild(user: User) -> str:
    guild = (user.guild_name or "").strip()
    if not guild: raise HTTPException(409, "No guild membership is linked")
    return guild


def opening_or_404(db: Session, opening_id: int, guild_name: str) -> GuildLeadershipOpening:
    row = db.query(GuildLeadershipOpening).filter(GuildLeadershipOpening.id == opening_id, GuildLeadershipOpening.guild_name.ilike(guild_name)).first()
    if not row: raise HTTPException(404, "Leadership opening not found")
    return row


def application_or_404(db: Session, application_id: int, guild_name: str) -> GuildLeadershipApplication:
    row = db.query(GuildLeadershipApplication).options(selectinload(GuildLeadershipApplication.opening), selectinload(GuildLeadershipApplication.histories), selectinload(GuildLeadershipApplication.messages), selectinload(GuildLeadershipApplication.votes), selectinload(GuildLeadershipApplication.interview)).join(GuildLeadershipOpening).filter(GuildLeadershipApplication.id == application_id, GuildLeadershipOpening.guild_name.ilike(guild_name)).first()
    if not row: raise HTTPException(404, "Leadership application not found")
    return row


def opening_data(row: GuildLeadershipOpening) -> dict:
    accepted = sum(1 for item in row.applications if item.status == "accepted")
    return {"id": row.id, "role_code": row.role.role_code, "title": row.title, "description": row.description, "responsibilities": row.responsibilities, "requirements": row.requirements, "openings_count": row.openings_count, "filled_count": accepted, "application_deadline": row.application_deadline, "status": row.status, "allow_viceleader_review": row.allow_viceleader_review, "voting_enabled": row.voting_enabled, "votes_required": row.votes_required, "created_at": row.created_at, "updated_at": row.updated_at}


def _name(user: User | None) -> str | None:
    return None if not user else user.display_name or user.username


def assignment_data(row: GuildLeadershipAssignment) -> dict:
    return {"id": row.id, "role_code": row.role.role_code, "character_name": row.character_name, "assignment_source": row.assignment_source, "started_at": row.started_at, "ended_at": row.ended_at, "is_active": row.is_active, "notes": row.notes, "assigned_by": _name(row.assigned_by), "in_game_promotion_status": row.in_game_promotion_status, "in_game_promoted_at": row.in_game_promoted_at, "in_game_promoted_by": _name(row.promoted_by)}


def application_data(row: GuildLeadershipApplication, viewer: User) -> dict:
    reviewer = LeadershipService.reviewer(viewer, row.opening)
    applicant = row.applicant_user_id == viewer.id
    if not (reviewer or applicant): raise HTTPException(403, "Application is private")
    messages = [item for item in row.messages if not item.deleted_at and (reviewer or item.audience in {"applicant", "both"})]
    data = {"id": row.id, "opening_id": row.opening_id, "opening_title": row.opening.title, "role_code": row.opening.role.role_code, "character_name": row.character_name, "status": row.status, "profile": row.profile_snapshot, "submitted_at": row.submitted_at, "conduct_agreed_at": row.conduct_agreed_at, "conduct_version": row.conduct_version, "final_decision_at": row.final_decision_at, "rejection_reason": row.rejection_reason if reviewer or applicant else None, "valid_actions": LeadershipService.valid_actions(row, viewer), "history": [{"from_status": item.from_status, "to_status": item.to_status, "reason": item.reason if reviewer or item.to_status in {"more_information_requested", "accepted", "rejected"} else None, "actor_name": _name(item.actor) if reviewer or item.actor_context == "applicant" else None, "actor_context": item.actor_context if reviewer else None, "admin_assistance": item.actor_context == "admin_assistance" if reviewer else False, "created_at": item.created_at} for item in row.histories], "messages": [{"id": item.id, "audience": item.audience, "message_type": item.message_type, "body": item.body, "author_name": item.author.display_name or item.author.username, "created_at": item.created_at} for item in messages], "interview": None if not row.interview else {"scheduled_at": row.interview.scheduled_at, "timezone": row.interview.timezone, "meeting_location": row.interview.meeting_location, "completed_at": row.interview.completed_at, "organizer": _name(row.interview.created_by), "completed_by": _name(row.interview.completed_by), "internal_notes": row.interview.interview_notes if reviewer else None}, "assignment": assignment_data(row.accepted_assignment) if row.accepted_assignment else None}
    if reviewer:
        current_vote = next((vote for vote in row.votes if vote.voter_user_id == viewer.id), None)
        data.update({"answers": {"why_apply": row.why_apply, "contribution": row.contribution, "availability": row.availability, "leadership_experience": row.leadership_experience, "applicant_message": row.applicant_message}, "vote_summary": {value: sum(1 for vote in row.votes if vote.vote == value) for value in ("support", "neutral", "oppose")}, "vote_participation": len(row.votes), "current_vote": current_vote.vote if current_vote else None, "current_vote_comment": current_vote.comment if current_vote else None})
    return data


def summary(db: Session, guild: str, user: User) -> dict:
    role = db.query(GuildLeadershipRole).filter(GuildLeadershipRole.guild_name.ilike(guild), GuildLeadershipRole.role_code == "viceleader").first()
    assigned_ids = {row.user_id for row in db.query(GuildLeadershipAssignment).join(GuildLeadershipRole).filter(GuildLeadershipAssignment.guild_name.ilike(guild), GuildLeadershipRole.role_code == "viceleader", GuildLeadershipAssignment.is_active.is_(True)).all()}
    ranked_ids = {member.id for member in db.query(User).filter(User.guild_name.ilike(guild), User.is_active.is_(True)).all() if is_guild_viceleader(member, guild)}
    active_assignments = len(assigned_ids | ranked_ids)
    openings = db.query(GuildLeadershipOpening).filter(GuildLeadershipOpening.guild_name.ilike(guild)).all()
    applications = db.query(GuildLeadershipApplication).join(GuildLeadershipOpening).filter(GuildLeadershipOpening.guild_name.ilike(guild), GuildLeadershipApplication.status.in_(ACTIVE_APPLICATION_STATUSES)).all()
    own = next((item for item in applications if item.applicant_user_id == user.id), None)
    can_review = LeadershipService.manager(user, guild) or any(LeadershipService.reviewer(user, opening) for opening in openings)
    pending_promotions = db.query(GuildLeadershipAssignment).filter(GuildLeadershipAssignment.guild_name.ilike(guild), GuildLeadershipAssignment.is_active.is_(True), GuildLeadershipAssignment.in_game_promotion_status == "pending").count()
    return {"guild_name": guild, "role": "viceleader", "active_viceleaders": active_assignments, "recommended_minimum": 4, "target_count": role.target_count if role else 4, "below_recommended": active_assignments < 4, "open_positions": sum(max(0, item.openings_count - sum(1 for app in item.applications if app.status == "accepted")) for item in openings if item.status == "open"), "active_applicants": len(applications) if can_review else None, "applications_requiring_attention": sum(1 for item in applications if item.status in {"applied", "more_information_requested"}) if can_review else None, "interviews_pending": sum(1 for item in applications if item.status == "interview") if can_review else 0, "applications_voting": sum(1 for item in applications if item.status == "voting") if can_review else 0, "recently_accepted": db.query(GuildLeadershipApplication).join(GuildLeadershipOpening).filter(GuildLeadershipOpening.guild_name.ilike(guild), GuildLeadershipApplication.status == "accepted").count(), "pending_promotions": pending_promotions if LeadershipService.manager(user, guild) else None, "own_status": own.status if own else None, "own_application_id": own.id if own else None, "capabilities": {"manage": LeadershipService.manager(user, guild), "review": can_review}}


@router.get("/me/leadership")
def get_summary(db: Session = Depends(get_db), user: User = Depends(get_current_active_user)): return summary(db, own_guild(user), user)


@router.get("/me/leadership/roles")
def get_roles(db: Session = Depends(get_db), user: User = Depends(get_current_active_user)):
    role = db.query(GuildLeadershipRole).filter(GuildLeadershipRole.guild_name.ilike(own_guild(user)), GuildLeadershipRole.role_code == "viceleader").first()
    return [{"role_code": "viceleader", "display_name_key": "leadership.roles.viceleader", "description_key": "leadership.roles.viceleaderDescription", "target_count": role.target_count if role else 4, "recruitment_enabled": role.recruitment_enabled if role else True}]


@router.get("/me/leadership/openings")
def list_openings(db: Session = Depends(get_db), user: User = Depends(get_current_active_user)):
    guild = own_guild(user); query = db.query(GuildLeadershipOpening).filter(GuildLeadershipOpening.guild_name.ilike(guild))
    if not LeadershipService.reviewer(user, type("Opening", (), {"guild_name": guild, "allow_viceleader_review": True})()): query = query.filter(GuildLeadershipOpening.status.in_(["open", "closed", "archived"]))
    return [opening_data(row) for row in query.order_by(GuildLeadershipOpening.created_at.desc()).all()]


def create_opening_for(db: Session, guild: str, user: User, payload: OpeningCreate):
    if not LeadershipService.manager(user, guild): raise HTTPException(403, "Only guild leaders manage openings")
    if payload.application_deadline and payload.application_deadline < datetime.now(UTC): raise HTTPException(400, "Deadline cannot be in the past")
    role = LeadershipService.ensure_role(db, guild, user); role.target_count = payload.target_count
    row = GuildLeadershipOpening(guild_name=guild, role_id=role.id, created_by_id=user.id, **payload.model_dump(exclude={"target_count"}))
    db.add(row); db.flush(); LeadershipService.audit(db, user, guild, "leadership_opening_created", "leadership_opening", row.id); db.commit(); db.refresh(row)
    return opening_data(row)


@router.post("/me/leadership/openings", status_code=201)
def create_opening(payload: OpeningCreate, db: Session = Depends(get_db), user: User = Depends(get_current_active_user)): return create_opening_for(db, own_guild(user), user, payload)


@router.get("/me/leadership/openings/{opening_id}")
def get_opening(opening_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_active_user)): return opening_data(opening_or_404(db, opening_id, own_guild(user)))


@router.patch("/me/leadership/openings/{opening_id}")
def update_opening(opening_id: int, payload: OpeningUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_active_user)):
    row = opening_or_404(db, opening_id, own_guild(user))
    if not LeadershipService.manager(user, row.guild_name) or row.status == "archived": raise HTTPException(403, "Opening is read-only")
    for key, value in payload.model_dump(exclude_unset=True).items(): setattr(row, key, value)
    row.version += 1; LeadershipService.audit(db, user, row.guild_name, "leadership_opening_updated", "leadership_opening", row.id); db.commit(); return opening_data(row)


def lifecycle(db: Session, row: GuildLeadershipOpening, user: User, target: str):
    if not LeadershipService.manager(user, row.guild_name) or row.status == "archived": raise HTTPException(403, "Opening is read-only")
    allowed = {"draft": {"open", "archived"}, "open": {"paused", "closed"}, "paused": {"open", "closed"}, "closed": {"archived", "open"}}
    if target not in allowed.get(row.status, set()): raise HTTPException(409, "Invalid opening lifecycle transition")
    if target == "open" and row.application_deadline and row.application_deadline < datetime.now(UTC): raise HTTPException(400, "Deadline cannot be in the past")
    row.status = target; row.version += 1
    if target == "open": row.opened_at = datetime.now(UTC)
    if target == "closed": row.closed_at = datetime.now(UTC)
    LeadershipService.audit(db, user, row.guild_name, f"leadership_opening_{target}", "leadership_opening", row.id)
    if target == "open": NotificationService.emit_users(db, db.query(User).filter(User.guild_name.ilike(row.guild_name), User.is_active.is_(True)).all(), "leadership_opening_published", f"leadership:opening:{row.id}:published:{row.version}", guild_name=row.guild_name, deep_link="/guild/leadership/recruitment", payload={"title": row.title})
    db.commit(); return opening_data(row)


for action in ("open", "pause", "close", "archive"):
    def endpoint(opening_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_active_user), _action=action): return lifecycle(db, opening_or_404(db, opening_id, own_guild(user)), user, "paused" if _action == "pause" else _action)
    router.add_api_route(f"/me/leadership/openings/{{opening_id}}/{action}", endpoint, methods=["POST"])


@router.post("/me/leadership/openings/{opening_id}/applications", status_code=201)
def apply(opening_id: int, payload: ApplicationCreate, db: Session = Depends(get_db), user: User = Depends(get_current_active_user)):
    row = LeadershipService.apply(db, opening_or_404(db, opening_id, own_guild(user)), user, payload); db.commit(); return application_data(row, user)


@router.get("/me/leadership/applications/mine")
def mine(db: Session = Depends(get_db), user: User = Depends(get_current_active_user)):
    rows = db.query(GuildLeadershipApplication).join(GuildLeadershipOpening).filter(GuildLeadershipOpening.guild_name.ilike(own_guild(user)), GuildLeadershipApplication.applicant_user_id == user.id).all(); return [application_data(row, user) for row in rows]


@router.get("/me/leadership/applications")
def applications(db: Session = Depends(get_db), user: User = Depends(get_current_active_user)):
    guild = own_guild(user); rows = db.query(GuildLeadershipApplication).join(GuildLeadershipOpening).filter(GuildLeadershipOpening.guild_name.ilike(guild)).all()
    return [application_data(row, user) for row in rows if LeadershipService.reviewer(user, row.opening)]


@router.get("/me/leadership/applications/{application_id}")
def application_detail(application_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_active_user)): return application_data(application_or_404(db, application_id, own_guild(user)), user)


@router.patch("/me/leadership/applications/{application_id}/status")
def status(application_id: int, payload: StatusUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_active_user)):
    row = application_or_404(db, application_id, own_guild(user))
    if payload.status == "accepted": LeadershipService.accept(db, row, user, payload.reason)
    else: LeadershipService.transition(db, row, user, payload.status, payload.reason, override=payload.admin_override)
    db.commit(); return application_data(row, user)


@router.post("/me/leadership/applications/{application_id}/withdraw")
def withdraw(application_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_active_user)):
    row = application_or_404(db, application_id, own_guild(user))
    if row.applicant_user_id != user.id or row.status not in ACTIVE_APPLICATION_STATUSES: raise HTTPException(403, "Application cannot be withdrawn")
    previous = row.status; row.status = "withdrawn"; row.withdrawn_at = datetime.now(UTC); row.version += 1
    from app.models.leadership import GuildLeadershipApplicationHistory
    db.add(GuildLeadershipApplicationHistory(application_id=row.id, from_status=previous, to_status="withdrawn", actor_id=user.id, actor_context="applicant", safe_metadata={}))
    LeadershipService.audit(db, user, row.opening.guild_name, "leadership_application_withdrawn", "leadership_application", row.id); db.commit(); return application_data(row, user)


@router.get("/me/leadership/applications/{application_id}/messages")
def messages(application_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_active_user)): return application_data(application_or_404(db, application_id, own_guild(user)), user)["messages"]


@router.post("/me/leadership/applications/{application_id}/messages", status_code=201)
def add_message(application_id: int, payload: MessageCreate, db: Session = Depends(get_db), user: User = Depends(get_current_active_user)):
    row = application_or_404(db, application_id, own_guild(user)); reviewer = LeadershipService.reviewer(user, row.opening); applicant = row.applicant_user_id == user.id
    if applicant:
        if row.status != "more_information_requested" or payload.audience not in {"reviewers", "both"}: raise HTTPException(403, "Applicant replies are not currently allowed")
    elif not reviewer: raise HTTPException(403, "Application messages are private")
    if payload.audience == "reviewers" and not reviewer and not applicant: raise HTTPException(403, "Internal comments are private")
    item = GuildLeadershipApplicationMessage(application_id=row.id, author_id=user.id, **payload.model_dump()); db.add(item); db.flush()
    LeadershipService.audit(db, user, row.opening.guild_name, "leadership_message_added", "leadership_application", row.id, {"audience": payload.audience, "message_type": payload.message_type})
    recipients = [row.applicant] if reviewer and payload.audience in {"applicant", "both"} else LeadershipService.leaders(db, row.opening.guild_name)
    NotificationService.emit_users(db, recipients, "leadership_applicant_replied" if applicant else "leadership_more_information_requested", f"leadership:message:{item.id}", guild_name=row.opening.guild_name, deep_link=f"/guild/leadership/recruitment/applications/{row.id}", payload={"character": row.character_name}); db.commit()
    return {"id": item.id, "audience": item.audience, "message_type": item.message_type, "body": item.body, "created_at": item.created_at}


@router.post("/me/leadership/applications/{application_id}/comments", status_code=201)
def comment(application_id: int, payload: MessageCreate, db: Session = Depends(get_db), user: User = Depends(get_current_active_user)):
    return add_message(application_id, MessageCreate(audience="reviewers", message_type="internal_comment", body=payload.body), db, user)


@router.post("/me/leadership/applications/{application_id}/interview")
def interview(application_id: int, payload: InterviewCreate, db: Session = Depends(get_db), user: User = Depends(get_current_active_user)):
    row = application_or_404(db, application_id, own_guild(user))
    if not LeadershipService.manager(user, row.opening.guild_name): raise HTTPException(403, "Only guild leaders schedule interviews")
    item = row.interview or GuildLeadershipInterview(application_id=row.id, created_by_id=user.id, scheduled_at=payload.scheduled_at, timezone=payload.timezone, meeting_location=payload.meeting_location)
    item.scheduled_at=payload.scheduled_at; item.timezone=payload.timezone; item.meeting_location=payload.meeting_location; item.interview_notes=payload.interview_notes
    if payload.completed: item.completed_at=datetime.now(UTC); item.completed_by_id=user.id
    db.add(item); LeadershipService.audit(db, user, row.opening.guild_name, "leadership_interview_completed" if payload.completed else "leadership_interview_scheduled", "leadership_application", row.id)
    NotificationService.emit_users(db, [row.applicant], "leadership_interview_scheduled", f"leadership:interview:{row.id}:{payload.scheduled_at.isoformat()}", guild_name=row.opening.guild_name, deep_link=f"/guild/leadership/recruitment/applications/{row.id}", payload={"character": row.character_name}); db.commit(); return application_data(row, user)


@router.post("/me/leadership/applications/{application_id}/votes")
def vote(application_id: int, payload: VoteCreate, db: Session = Depends(get_db), user: User = Depends(get_current_active_user)):
    row = application_or_404(db, application_id, own_guild(user))
    if not row.opening.voting_enabled or not LeadershipService.reviewer(user, row.opening) or row.applicant_user_id == user.id: raise HTTPException(403, "Voting is not permitted")
    item = db.query(GuildLeadershipVote).filter_by(application_id=row.id, voter_user_id=user.id).first()
    if item: item.vote=payload.vote; item.comment=payload.comment
    else: item=GuildLeadershipVote(application_id=row.id, voter_user_id=user.id, **payload.model_dump()); db.add(item)
    LeadershipService.audit(db, user, row.opening.guild_name, "leadership_vote_submitted", "leadership_application", row.id, {"changed": bool(item.id)}); db.commit(); return application_data(row, user)["vote_summary"]


@router.post("/me/leadership/applications/{application_id}/decision")
def decision(application_id: int, payload: DecisionCreate, db: Session = Depends(get_db), user: User = Depends(get_current_active_user)):
    row = application_or_404(db, application_id, own_guild(user))
    if payload.decision == "accepted": LeadershipService.accept(db, row, user, payload.reason)
    else: LeadershipService.transition(db, row, user, "rejected", payload.reason)
    db.commit(); return application_data(row, user)


@router.get("/me/leadership/assignments")
def assignments(db: Session = Depends(get_db), user: User = Depends(get_current_active_user)):
    guild=own_guild(user); return [assignment_data(row) for row in db.query(GuildLeadershipAssignment).filter(GuildLeadershipAssignment.guild_name.ilike(guild)).order_by(GuildLeadershipAssignment.is_active.desc(), GuildLeadershipAssignment.started_at.desc()).all()]


@router.patch("/me/leadership/assignments/{assignment_id}/promotion")
def promotion(assignment_id: int, payload: PromotionUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_active_user)):
    row=db.query(GuildLeadershipAssignment).filter(GuildLeadershipAssignment.id==assignment_id, GuildLeadershipAssignment.guild_name.ilike(own_guild(user))).first()
    if not row or not LeadershipService.manager(user, row.guild_name): raise HTTPException(403, "Promotion tracking is restricted")
    if payload.completed and row.in_game_promotion_status == "completed": raise HTTPException(409, "In-game promotion is already complete")
    row.in_game_promotion_status="completed" if payload.completed else "pending"; row.in_game_promoted_at=datetime.now(UTC) if payload.completed else None; row.in_game_promoted_by_id=user.id if payload.completed else None
    if payload.note: row.notes = payload.note
    LeadershipService.audit(db, user, row.guild_name, "leadership_promotion_completed" if payload.completed else "leadership_promotion_pending", "leadership_assignment", row.id); db.commit(); return {"id": row.id, "in_game_promotion_status": row.in_game_promotion_status, "in_game_promoted_at": row.in_game_promoted_at}


@router.post("/me/leadership/assignments/{assignment_id}/end")
def end_assignment(assignment_id: int, payload: AssignmentEnd, db: Session = Depends(get_db), user: User = Depends(get_current_active_user)):
    row = db.query(GuildLeadershipAssignment).filter(GuildLeadershipAssignment.id == assignment_id, GuildLeadershipAssignment.guild_name.ilike(own_guild(user))).first()
    if not row or not LeadershipService.manager(user, row.guild_name): raise HTTPException(403, "Assignment management is restricted")
    if not row.is_active: raise HTTPException(409, "Assignment is already ended")
    row.is_active = False; row.ended_at = datetime.now(UTC); row.notes = payload.reason
    LeadershipService.audit(db, user, row.guild_name, "leadership_assignment_ended", "leadership_assignment", row.id, {"reason_recorded": True}); db.commit()
    return assignment_data(row)


# Explicit admin-assistance contracts use the same domain rules with a fixed registered guild.
@admin_router.get("/guilds/{guild_key}/leadership")
def admin_summary(guild_key: str, db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)): return summary(db, _resolve_registered_guild(db, guild_key), admin)


@admin_router.get("/guilds/{guild_key}/leadership/openings")
def admin_openings(guild_key: str, db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)): return [opening_data(row) for row in db.query(GuildLeadershipOpening).filter(GuildLeadershipOpening.guild_name.ilike(_resolve_registered_guild(db, guild_key))).all()]


@admin_router.post("/guilds/{guild_key}/leadership/openings", status_code=201)
def admin_create_opening(guild_key: str, payload: OpeningCreate, db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)): return create_opening_for(db, _resolve_registered_guild(db, guild_key), admin, payload)


@admin_router.patch("/guilds/{guild_key}/leadership/openings/{opening_id}")
def admin_update_opening(guild_key: str, opening_id: int, payload: OpeningUpdate, db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    guild = _resolve_registered_guild(db, guild_key); row = opening_or_404(db, opening_id, guild)
    if row.status == "archived": raise HTTPException(409, "Archived openings are read-only")
    for key, value in payload.model_dump(exclude_unset=True).items(): setattr(row, key, value)
    row.version += 1; LeadershipService.audit(db, admin, guild, "leadership_opening_updated", "leadership_opening", row.id); db.commit()
    return opening_data(row)


for admin_action in ("open", "pause", "close", "archive"):
    def admin_lifecycle(guild_key: str, opening_id: int, db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user), _action=admin_action):
        guild = _resolve_registered_guild(db, guild_key)
        return lifecycle(db, opening_or_404(db, opening_id, guild), admin, "paused" if _action == "pause" else _action)
    admin_router.add_api_route(f"/guilds/{{guild_key}}/leadership/openings/{{opening_id}}/{admin_action}", admin_lifecycle, methods=["POST"])


@admin_router.get("/guilds/{guild_key}/leadership/applications")
def admin_applications(guild_key: str, db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    guild=_resolve_registered_guild(db, guild_key); return [application_data(row, admin) for row in db.query(GuildLeadershipApplication).join(GuildLeadershipOpening).filter(GuildLeadershipOpening.guild_name.ilike(guild)).all()]


@admin_router.get("/guilds/{guild_key}/leadership/applications/{application_id}")
def admin_application(guild_key: str, application_id: int, db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)): return application_data(application_or_404(db, application_id, _resolve_registered_guild(db, guild_key)), admin)


@admin_router.patch("/guilds/{guild_key}/leadership/applications/{application_id}/status")
def admin_status(guild_key: str, application_id: int, payload: StatusUpdate, db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    guild = _resolve_registered_guild(db, guild_key); row = application_or_404(db, application_id, guild)
    if payload.status == "accepted": LeadershipService.accept(db, row, admin, payload.reason)
    else: LeadershipService.transition(db, row, admin, payload.status, payload.reason, override=payload.admin_override)
    db.commit(); return application_data(row, admin)


@admin_router.post("/guilds/{guild_key}/leadership/applications/{application_id}/messages", status_code=201)
def admin_message(guild_key: str, application_id: int, payload: MessageCreate, db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    guild = _resolve_registered_guild(db, guild_key); row = application_or_404(db, application_id, guild)
    item = GuildLeadershipApplicationMessage(application_id=row.id, author_id=admin.id, **payload.model_dump()); db.add(item); db.flush()
    LeadershipService.audit(db, admin, guild, "leadership_message_added", "leadership_application", row.id, {"audience": payload.audience, "message_type": payload.message_type})
    if payload.audience in {"applicant", "both"}:
        NotificationService.emit_users(db, [row.applicant], "leadership_more_information_requested", f"leadership:message:{item.id}", guild_name=guild, deep_link=f"/guild/leadership/recruitment/applications/{row.id}", payload={"character": row.character_name})
    db.commit()
    return {"id": item.id, "audience": item.audience, "message_type": item.message_type, "body": item.body, "created_at": item.created_at}


@admin_router.post("/guilds/{guild_key}/leadership/applications/{application_id}/decision")
def admin_decision(guild_key: str, application_id: int, payload: DecisionCreate, db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    guild = _resolve_registered_guild(db, guild_key); row = application_or_404(db, application_id, guild)
    if payload.decision == "accepted": LeadershipService.accept(db, row, admin, payload.reason)
    else: LeadershipService.transition(db, row, admin, "rejected", payload.reason)
    db.commit(); return application_data(row, admin)


@admin_router.post("/guilds/{guild_key}/leadership/applications/{application_id}/interview")
def admin_interview(guild_key: str, application_id: int, payload: InterviewCreate, db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    guild = _resolve_registered_guild(db, guild_key); row = application_or_404(db, application_id, guild)
    item = row.interview or GuildLeadershipInterview(application_id=row.id, created_by_id=admin.id, scheduled_at=payload.scheduled_at, timezone=payload.timezone, meeting_location=payload.meeting_location)
    item.scheduled_at = payload.scheduled_at; item.timezone = payload.timezone; item.meeting_location = payload.meeting_location; item.interview_notes = payload.interview_notes
    if payload.completed: item.completed_at = datetime.now(UTC); item.completed_by_id = admin.id
    db.add(item); LeadershipService.audit(db, admin, guild, "leadership_interview_completed" if payload.completed else "leadership_interview_scheduled", "leadership_application", row.id)
    NotificationService.emit_users(db, [row.applicant], "leadership_interview_scheduled", f"leadership:interview:{row.id}:{payload.scheduled_at.isoformat()}", guild_name=guild, deep_link=f"/guild/leadership/recruitment/applications/{row.id}", payload={"character": row.character_name}); db.commit()
    return application_data(row, admin)


@admin_router.post("/guilds/{guild_key}/leadership/applications/{application_id}/votes")
def admin_vote(guild_key: str, application_id: int, payload: VoteCreate, db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    guild = _resolve_registered_guild(db, guild_key); row = application_or_404(db, application_id, guild)
    if not row.opening.voting_enabled: raise HTTPException(409, "Voting is disabled")
    item = db.query(GuildLeadershipVote).filter_by(application_id=row.id, voter_user_id=admin.id).first()
    changed = item is not None
    if item: item.vote = payload.vote; item.comment = payload.comment
    else: db.add(GuildLeadershipVote(application_id=row.id, voter_user_id=admin.id, **payload.model_dump()))
    LeadershipService.audit(db, admin, guild, "leadership_vote_changed" if changed else "leadership_vote_submitted", "leadership_application", row.id); db.commit()
    return application_data(row, admin)["vote_summary"]


@admin_router.get("/guilds/{guild_key}/leadership/assignments")
def admin_assignments(guild_key: str, db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    guild = _resolve_registered_guild(db, guild_key)
    return [assignment_data(row) for row in db.query(GuildLeadershipAssignment).filter(GuildLeadershipAssignment.guild_name.ilike(guild)).order_by(GuildLeadershipAssignment.is_active.desc(), GuildLeadershipAssignment.started_at.desc()).all()]


@admin_router.patch("/guilds/{guild_key}/leadership/assignments/{assignment_id}/promotion")
def admin_promotion(guild_key: str, assignment_id: int, payload: PromotionUpdate, db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    guild = _resolve_registered_guild(db, guild_key); row = db.query(GuildLeadershipAssignment).filter(GuildLeadershipAssignment.id == assignment_id, GuildLeadershipAssignment.guild_name.ilike(guild)).first()
    if not row: raise HTTPException(404, "Leadership assignment not found")
    if payload.completed and row.in_game_promotion_status == "completed": raise HTTPException(409, "In-game promotion is already complete")
    row.in_game_promotion_status = "completed" if payload.completed else "pending"; row.in_game_promoted_at = datetime.now(UTC) if payload.completed else None; row.in_game_promoted_by_id = admin.id if payload.completed else None
    if payload.note: row.notes = payload.note
    LeadershipService.audit(db, admin, guild, "leadership_promotion_completed" if payload.completed else "leadership_promotion_pending", "leadership_assignment", row.id); db.commit()
    return {"id": row.id, "in_game_promotion_status": row.in_game_promotion_status, "in_game_promoted_at": row.in_game_promoted_at}


@admin_router.post("/guilds/{guild_key}/leadership/assignments/{assignment_id}/end")
def admin_end_assignment(guild_key: str, assignment_id: int, payload: AssignmentEnd, db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    guild = _resolve_registered_guild(db, guild_key); row = db.query(GuildLeadershipAssignment).filter(GuildLeadershipAssignment.id == assignment_id, GuildLeadershipAssignment.guild_name.ilike(guild)).first()
    if not row: raise HTTPException(404, "Leadership assignment not found")
    if not row.is_active: raise HTTPException(409, "Assignment is already ended")
    row.is_active = False; row.ended_at = datetime.now(UTC); row.notes = payload.reason
    LeadershipService.audit(db, admin, guild, "leadership_assignment_ended", "leadership_assignment", row.id, {"reason_recorded": True}); db.commit()
    return assignment_data(row)
