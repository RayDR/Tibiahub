from typing import List, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime, timedelta
from collections import OrderedDict

from app.db.database import get_db
from app.models.guild import Announcement, GuildEvent, EventAttendance, Recruitment, AnnouncementType, EventType
from app.models.guild_member_snapshot import GuildMemberSnapshot
from app.models.settings import SystemSettings
from app.models.user import User
from app.schemas.guild import (
    AnnouncementCreate, AnnouncementResponse,
    EventCreate, EventResponse,
    RecruitmentCreate, RecruitmentResponse, RecruitmentUpdate,
    AttendanceCreate, AttendanceResponse,
    GuildMemberSnapshotPayload,
    GuildMemberSnapshotResponse,
)
from app.api.v1.endpoints.auth import get_current_user, get_current_active_user, get_current_admin_user, get_current_manager_user
from app.core.permissions import require_guild_management
from app.services.tibia_api import get_active_guild_members, get_guild_info

router = APIRouter()


class SoftDeletePayload(BaseModel):
    reason: Optional[str] = None


def _latest_snapshot_rows(db: Session, guild_name: str, limit: int = 400) -> list[GuildMemberSnapshot]:
    rows = (
        db.query(GuildMemberSnapshot)
        .filter(GuildMemberSnapshot.guild_name.ilike(guild_name))
        .order_by(GuildMemberSnapshot.snapshot_at.desc(), GuildMemberSnapshot.level.desc())
        .limit(limit)
        .all()
    )

    deduped: OrderedDict[str, GuildMemberSnapshot] = OrderedDict()
    for row in rows:
        key = row.character_name.strip().lower()
        if key in deduped:
            continue
        deduped[key] = row
    return list(deduped.values())


async def _sync_guild_snapshot(db: Session, guild_name: str) -> list[GuildMemberSnapshot]:
    guild_info = await get_guild_info(guild_name)
    if not guild_info:
        raise ValueError("Guild data unavailable")

    members = guild_info.get("members") or []
    snapshot_time = datetime.utcnow()
    created_rows: list[GuildMemberSnapshot] = []
    for member in members:
        row = GuildMemberSnapshot(
            guild_name=guild_name,
            character_name=member.get("name") or "Unknown",
            level=member.get("level"),
            vocation=member.get("vocation"),
            rank=member.get("rank") or member.get("title") or member.get("position"),
            role=member.get("role"),
            last_login=member.get("last_login") or member.get("lastlogin"),
            world=guild_info.get("world"),
            snapshot_at=snapshot_time,
        )
        db.add(row)
        created_rows.append(row)

    db.commit()
    return created_rows

# --- Announcements ---

@router.post("/announcements", response_model=AnnouncementResponse)
def create_announcement(
    *,
    db: Session = Depends(get_db),
    announcement_in: AnnouncementCreate,
    current_user: User = Depends(get_current_manager_user),
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
    include_deleted: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    query = db.query(Announcement)
    if not include_deleted:
        query = query.filter(Announcement.is_deleted == False)
    announcements = query.order_by(Announcement.created_at.desc()).offset(skip).limit(limit).all()
    return announcements


@router.delete("/announcements/{announcement_id}", response_model=AnnouncementResponse)
def soft_delete_announcement(
    announcement_id: int,
    payload: Optional[SoftDeletePayload] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager_user),
) -> Any:
    announcement = db.query(Announcement).filter(Announcement.id == announcement_id).first()
    if not announcement:
        raise HTTPException(status_code=404, detail="Announcement not found")
    announcement.is_deleted = True
    announcement.deleted_at = datetime.utcnow()
    announcement.deleted_by_user_id = current_user.id
    announcement.delete_reason = payload.reason if payload else None
    db.commit()
    db.refresh(announcement)
    return announcement


@router.post("/announcements/{announcement_id}/restore", response_model=AnnouncementResponse)
def restore_announcement(
    announcement_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager_user),
) -> Any:
    announcement = db.query(Announcement).filter(Announcement.id == announcement_id).first()
    if not announcement:
        raise HTTPException(status_code=404, detail="Announcement not found")
    announcement.is_deleted = False
    announcement.deleted_at = None
    announcement.deleted_by_user_id = None
    announcement.delete_reason = None
    db.commit()
    db.refresh(announcement)
    return announcement

# --- Events ---

@router.post("/events", response_model=EventResponse)
def create_event(
    *,
    db: Session = Depends(get_db),
    event_in: EventCreate,
    current_user: User = Depends(get_current_manager_user)
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
    include_deleted: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    query = db.query(GuildEvent)
    if not include_deleted:
        query = query.filter(GuildEvent.is_deleted == False)
    events = query.order_by(GuildEvent.start_time.asc()).offset(skip).limit(limit).all()
    return events


@router.delete("/events/{event_id}", response_model=EventResponse)
def soft_delete_guild_event(
    event_id: int,
    payload: Optional[SoftDeletePayload] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager_user),
) -> Any:
    event = db.query(GuildEvent).filter(GuildEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    event.is_deleted = True
    event.deleted_at = datetime.utcnow()
    event.deleted_by_user_id = current_user.id
    event.delete_reason = payload.reason if payload else None
    db.commit()
    db.refresh(event)
    return event


@router.post("/events/{event_id}/restore", response_model=EventResponse)
def restore_guild_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager_user),
) -> Any:
    event = db.query(GuildEvent).filter(GuildEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    event.is_deleted = False
    event.deleted_at = None
    event.deleted_by_user_id = None
    event.delete_reason = None
    db.commit()
    db.refresh(event)
    return event

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


@router.get("/features")
async def get_guild_feature_flags(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    _ = current_user

    def _flag(key: str, default: bool = True) -> bool:
        try:
            record = db.query(SystemSettings).filter(SystemSettings.key == key).first()
            if not record or record.value is None:
                return default
            return str(record.value).strip().lower() in {"1", "true", "yes", "on"}
        except SQLAlchemyError:
            db.rollback()
            return default

    try:
        return {
            "guild_raffles_enabled": _flag("guild_raffles_enabled", True),
            "guild_contests_enabled": _flag("guild_contests_enabled", True),
        }
    except Exception:
        return {
            "guild_raffles_enabled": True,
            "guild_contests_enabled": True,
        }


@router.get("/{guild_name}/members", response_model=GuildMemberSnapshotPayload)
async def get_guild_members_snapshot(
    guild_name: str,
    refresh: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    source = "snapshot"
    if refresh:
        if not current_user.is_superuser and (current_user.guild_rank or "").lower() not in {"leader", "vice leader"}:
            raise HTTPException(status_code=403, detail="Only guild leaders can force sync")

        latest = (
            db.query(GuildMemberSnapshot)
            .filter(GuildMemberSnapshot.guild_name.ilike(guild_name))
            .order_by(GuildMemberSnapshot.snapshot_at.desc())
            .first()
        )
        if latest and latest.snapshot_at and datetime.utcnow() - latest.snapshot_at < timedelta(hours=1):
            retry_at = latest.snapshot_at + timedelta(hours=1)
            raise HTTPException(status_code=429, detail=f"Manual sync allowed once per hour. Retry after {retry_at.isoformat()} UTC")

        try:
            await _sync_guild_snapshot(db, guild_name)
            source = "live"
        except Exception:
            source = "snapshot"

    rows = _latest_snapshot_rows(db, guild_name)
    if not rows:
        try:
            await _sync_guild_snapshot(db, guild_name)
            source = "live"
            rows = _latest_snapshot_rows(db, guild_name)
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"Guild members unavailable: {str(exc)}") from exc

    members = [
        GuildMemberSnapshotResponse(
            character_name=row.character_name,
            level=row.level,
            vocation=row.vocation,
            rank=row.rank,
            role=row.role,
            last_login=row.last_login,
            world=row.world,
            snapshot_at=row.snapshot_at,
        )
        for row in rows
    ]
    return GuildMemberSnapshotPayload(guild_name=guild_name, source=source, members=members)


@router.post("/{guild_name}/members/sync", response_model=GuildMemberSnapshotPayload)
async def sync_guild_members_snapshot(
    guild_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager_user),
) -> Any:
    require_guild_management(current_user, guild_name)
    latest = (
        db.query(GuildMemberSnapshot)
        .filter(GuildMemberSnapshot.guild_name.ilike(guild_name))
        .order_by(GuildMemberSnapshot.snapshot_at.desc())
        .first()
    )
    if latest and latest.snapshot_at and datetime.utcnow() - latest.snapshot_at < timedelta(hours=1):
        retry_at = latest.snapshot_at + timedelta(hours=1)
        raise HTTPException(status_code=429, detail=f"Manual sync allowed once per hour. Retry after {retry_at.isoformat()} UTC")

    try:
        await _sync_guild_snapshot(db, guild_name)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Guild sync failed: {str(exc)}") from exc

    rows = _latest_snapshot_rows(db, guild_name)
    members = [
        GuildMemberSnapshotResponse(
            character_name=row.character_name,
            level=row.level,
            vocation=row.vocation,
            rank=row.rank,
            role=row.role,
            last_login=row.last_login,
            world=row.world,
            snapshot_at=row.snapshot_at,
        )
        for row in rows
    ]
    return GuildMemberSnapshotPayload(guild_name=guild_name, source="live", members=members)
