from typing import List, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime

from app.db.database import get_db
from app.models.guild import Announcement, GuildEvent, EventAttendance, Recruitment, AnnouncementType, EventType
from app.models.user import User
from app.schemas.guild import (
    AnnouncementCreate, AnnouncementResponse,
    EventCreate, EventResponse,
    RecruitmentCreate, RecruitmentResponse, RecruitmentUpdate,
    AttendanceCreate, AttendanceResponse
)
from app.api.v1.endpoints.auth import get_current_user, get_current_active_user, get_current_admin_user
from app.services.tibia_api import get_active_guild_members

router = APIRouter()

# --- Announcements ---

@router.post("/announcements", response_model=AnnouncementResponse)
def create_announcement(
    *,
    db: Session = Depends(get_db),
    announcement_in: AnnouncementCreate,
    current_user: User = Depends(get_current_admin_user),
) -> Any:
    announcement = Announcement(
        title=announcement_in.title,
        content=announcement_in.content,
        type=announcement_in.type,
        author_id=current_user.id
    )
    db.add(announcement)
    db.commit()
    db.refresh(announcement)
    return announcement

@router.get("/announcements", response_model=List[AnnouncementResponse])
def read_announcements(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    announcements = db.query(Announcement).order_by(Announcement.created_at.desc()).offset(skip).limit(limit).all()
    return announcements

# --- Events ---

@router.post("/events", response_model=EventResponse)
def create_event(
    *,
    db: Session = Depends(get_db),
    event_in: EventCreate,
    current_user: User = Depends(get_current_active_user)
) -> Any:
    event = GuildEvent(
        title=event_in.title,
        description=event_in.description,
        start_time=event_in.start_time,
        end_time=event_in.end_time,
        type=event_in.type,
        author_id=current_user.id
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event

@router.get("/events", response_model=List[EventResponse])
def read_events(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    events = db.query(GuildEvent).order_by(GuildEvent.start_time.asc()).offset(skip).limit(limit).all()
    return events

@router.post("/events/{event_id}/attend", response_model=AttendanceResponse)
def attend_event(
    event_id: int,
    status_in: AttendanceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    event = db.query(GuildEvent).filter(GuildEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    attendance = db.query(EventAttendance).filter(
        EventAttendance.event_id == event_id,
        EventAttendance.user_id == current_user.id
    ).first()

    if attendance:
        attendance.status = status_in.status
    else:
        attendance = EventAttendance(
            event_id=event_id,
            user_id=current_user.id,
            status=status_in.status
        )
        db.add(attendance)
    
    db.commit()
    db.refresh(attendance)
    return attendance

# --- Recruitment ---

@router.post("/recruitments", response_model=RecruitmentResponse)
def report_recruitment(
    *,
    db: Session = Depends(get_db),
    recruitment_in: RecruitmentCreate,
    current_user: User = Depends(get_current_active_user)
) -> Any:
    recruitment = Recruitment(
        recruiter_id=current_user.id,
        recruit_name=recruitment_in.recruit_name,
        notes=recruitment_in.notes
    )
    db.add(recruitment)
    db.commit()
    db.refresh(recruitment)
    return recruitment

@router.get("/recruitments", response_model=List[RecruitmentResponse])
def read_recruitments(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
) -> Any:
    recruitments = db.query(Recruitment).order_by(Recruitment.created_at.desc()).offset(skip).limit(limit).all()
    return recruitments

@router.get("/raffle/participants")
async def get_raffle_participants(
    guild_name: str,
    days: int = 10,
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    Get active guild members for raffle
    """
    members = await get_active_guild_members(guild_name, days)
    return members
