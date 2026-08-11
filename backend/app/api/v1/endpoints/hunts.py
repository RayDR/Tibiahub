from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.api.v1.endpoints.auth import get_current_active_user, get_current_admin_user
from app.core.permissions import can_manage_guild, is_global_admin
from app.db.database import get_db
from app.models.hunt import GuildHunt, GuildHuntParticipant, HuntCatalog
from app.schemas.hunt import (
    GuildHuntAttendanceUpdate, GuildHuntCancel, GuildHuntCreate, GuildHuntResponse,
    GuildHuntUpdate, Hunt, HuntCreate, HuntUpdate,
)
from app.models.user import User
from app.services.guild_hunt_service import GuildHuntError, GuildHuntPlannerService
from app.services.guild_authorization_service import GuildAuthorizationService

router = APIRouter()


def _guild_for(db: Session, user: User, requested: str | None = None) -> str:
    contexts = GuildAuthorizationService.guild_contexts(db, user)
    selected = (requested or (contexts[0]["guild_name"] if contexts else "")).strip()
    if not selected:
        raise HTTPException(409, "No guild membership is linked")
    if not is_global_admin(user) and not (
        GuildAuthorizationService.is_verified_member(db, user, selected)
        or GuildAuthorizationService.has_grant(db, user, selected, "hunts.manage")
    ):
        raise HTTPException(403, "Guild workspace access denied")
    return selected


def _hunt_or_404(db: Session, hunt_id: int, user: User, *, lock: bool = False) -> GuildHunt:
    hunt = GuildHuntPlannerService.get(db, hunt_id, lock=lock)
    if hunt is None:
        raise HTTPException(404, "Guild hunt not found")
    if not is_global_admin(user) and not GuildAuthorizationService.is_verified_member(db, user, hunt.guild_name) and not GuildAuthorizationService.has_grant(db, user, hunt.guild_name, "hunts.manage"):
        raise HTTPException(403, "Guild workspace access denied")
    return hunt


def _planner_response(db: Session, hunt: GuildHunt, user: User) -> dict:
    participants = list(hunt.participants)
    return {
        **{column.name: getattr(hunt, column.name) for column in GuildHunt.__table__.columns},
        "participants": participants,
        "registered_count": sum(1 for item in participants if item.attendance_status in GuildHuntPlannerService.ACTIVE_ATTENDANCE),
        "current_user_joined": any(item.user_id == user.id and item.attendance_status == "registered" for item in participants),
        "capabilities": {
            "manage": can_manage_guild(user, hunt.guild_name, db=db, capability="hunts.manage"),
            "join": hunt.status == "scheduled" and GuildAuthorizationService.is_verified_member(db, user, hunt.guild_name),
            "attendance": hunt.status in {"in_progress", "finished"} and can_manage_guild(user, hunt.guild_name, db=db, capability="hunts.manage"),
        },
    }


def _domain_error(exc: Exception) -> HTTPException:
    return HTTPException(403 if isinstance(exc, PermissionError) else 409, str(exc))


@router.get("/planner", response_model=list[GuildHuntResponse])
def list_guild_hunts(
    guild_name: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    status_filter: list[str] | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    guild = _guild_for(db, current_user, guild_name)
    rows = GuildHuntPlannerService.list_for_guild(db, guild, start=start, end=end, statuses=set(status_filter or []))
    return [_planner_response(db, row, current_user) for row in rows]


@router.post("/planner", response_model=GuildHuntResponse, status_code=201)
def create_guild_hunt(payload: GuildHuntCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    guild = _guild_for(db, current_user, payload.guild_name)
    try:
        hunt = GuildHuntPlannerService.create(db, current_user, guild, payload.model_dump())
        db.commit()
    except (GuildHuntError, PermissionError) as exc:
        db.rollback()
        raise _domain_error(exc) from exc
    return _planner_response(db, GuildHuntPlannerService.get(db, hunt.id), current_user)


@router.get("/planner/{hunt_id}", response_model=GuildHuntResponse)
def get_guild_hunt(hunt_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    return _planner_response(db, _hunt_or_404(db, hunt_id, current_user), current_user)


@router.patch("/planner/{hunt_id}", response_model=GuildHuntResponse)
def update_guild_hunt(hunt_id: int, payload: GuildHuntUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    hunt = _hunt_or_404(db, hunt_id, current_user, lock=True)
    try:
        GuildHuntPlannerService.update(db, current_user, hunt, payload.model_dump(exclude_unset=True))
        db.commit()
    except (GuildHuntError, PermissionError) as exc:
        db.rollback()
        raise _domain_error(exc) from exc
    return _planner_response(db, GuildHuntPlannerService.get(db, hunt_id), current_user)


@router.post("/planner/{hunt_id}/join", response_model=GuildHuntResponse)
def join_guild_hunt(hunt_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    hunt = _hunt_or_404(db, hunt_id, current_user, lock=True)
    try:
        GuildHuntPlannerService.join(db, current_user, hunt)
        db.commit()
    except (GuildHuntError, PermissionError) as exc:
        db.rollback()
        raise _domain_error(exc) from exc
    return _planner_response(db, GuildHuntPlannerService.get(db, hunt_id), current_user)


@router.post("/planner/{hunt_id}/leave", response_model=GuildHuntResponse)
def leave_guild_hunt(hunt_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    hunt = _hunt_or_404(db, hunt_id, current_user, lock=True)
    try:
        GuildHuntPlannerService.leave(db, current_user, hunt)
        db.commit()
    except (GuildHuntError, PermissionError) as exc:
        db.rollback()
        raise _domain_error(exc) from exc
    return _planner_response(db, GuildHuntPlannerService.get(db, hunt_id), current_user)


@router.post("/planner/{hunt_id}/cancel", response_model=GuildHuntResponse)
def cancel_guild_hunt(hunt_id: int, payload: GuildHuntCancel, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    hunt = _hunt_or_404(db, hunt_id, current_user, lock=True)
    try:
        GuildHuntPlannerService.transition(db, current_user, hunt, "cancel", reason=payload.reason)
        db.commit()
    except (GuildHuntError, PermissionError) as exc:
        db.rollback()
        raise _domain_error(exc) from exc
    return _planner_response(db, GuildHuntPlannerService.get(db, hunt_id), current_user)


@router.post("/planner/{hunt_id}/{action}", response_model=GuildHuntResponse)
def transition_guild_hunt(hunt_id: int, action: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    if action not in {"start", "finish"}:
        raise HTTPException(404, "Guild hunt action not found")
    hunt = _hunt_or_404(db, hunt_id, current_user, lock=True)
    try:
        GuildHuntPlannerService.transition(db, current_user, hunt, action)
        db.commit()
    except (GuildHuntError, PermissionError) as exc:
        db.rollback()
        raise _domain_error(exc) from exc
    return _planner_response(db, GuildHuntPlannerService.get(db, hunt_id), current_user)


@router.patch("/planner/{hunt_id}/participants/{participant_id}", response_model=GuildHuntResponse)
def mark_guild_hunt_attendance(hunt_id: int, participant_id: int, payload: GuildHuntAttendanceUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    hunt = _hunt_or_404(db, hunt_id, current_user, lock=True)
    participant = db.query(GuildHuntParticipant).filter_by(id=participant_id, hunt_id=hunt_id).first()
    if participant is None:
        raise HTTPException(404, "Hunt participant not found")
    try:
        GuildHuntPlannerService.mark_attendance(db, current_user, hunt, participant, payload.attendance_status)
        db.commit()
    except (GuildHuntError, PermissionError) as exc:
        db.rollback()
        raise _domain_error(exc) from exc
    return _planner_response(db, GuildHuntPlannerService.get(db, hunt_id), current_user)

@router.get("/", response_model=List[Hunt])
async def get_hunts(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    level_min: Optional[int] = None,
    level_max: Optional[int] = None,
    vocation: Optional[str] = None,
    location: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get list of hunts with optional filters"""
    query = db.query(HuntCatalog)
    
    # Apply filters
    if level_min is not None:
        query = query.filter(HuntCatalog.level_max >= level_min)
    if level_max is not None:
        query = query.filter(HuntCatalog.level_min <= level_max)
    if vocation:
        query = query.filter(HuntCatalog.vocation.contains(vocation))
    if location:
        query = query.filter(HuntCatalog.location.contains(location))
    
    hunts = query.order_by(HuntCatalog.level_min).offset(skip).limit(limit).all()
    return hunts

@router.get("/{hunt_id}", response_model=Hunt)
async def get_hunt(
    hunt_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get a specific hunt by ID"""
    hunt = db.query(HuntCatalog).filter(HuntCatalog.id == hunt_id).first()
    if not hunt:
        raise HTTPException(status_code=404, detail="Hunt not found")
    return hunt

@router.post("/", response_model=Hunt)
async def create_hunt(
    hunt: HuntCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Create a new hunt (admin only)"""
    db_hunt = HuntCatalog(**hunt.model_dump())
    db.add(db_hunt)
    db.commit()
    db.refresh(db_hunt)
    return db_hunt

@router.put("/{hunt_id}", response_model=Hunt)
async def update_hunt(
    hunt_id: int,
    hunt: HuntUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Update a hunt (admin only)"""
    db_hunt = db.query(HuntCatalog).filter(HuntCatalog.id == hunt_id).first()
    if not db_hunt:
        raise HTTPException(status_code=404, detail="Hunt not found")
    
    for key, value in hunt.model_dump(exclude_unset=True).items():
        setattr(db_hunt, key, value)
    
    db.commit()
    db.refresh(db_hunt)
    return db_hunt

@router.delete("/{hunt_id}")
async def delete_hunt(
    hunt_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Delete a hunt (admin only)"""
    db_hunt = db.query(HuntCatalog).filter(HuntCatalog.id == hunt_id).first()
    if not db_hunt:
        raise HTTPException(status_code=404, detail="Hunt not found")
    
    db.delete(db_hunt)
    db.commit()
    return {"message": "Hunt deleted successfully"}
