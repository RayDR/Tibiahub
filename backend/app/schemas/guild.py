from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from app.models.guild import AnnouncementType, EventType, AttendanceStatus, RecruitmentStatus
from app.schemas.auth import UserResponse

# Announcement Schemas
class AnnouncementBase(BaseModel):
    title: str
    content: str
    type: AnnouncementType = AnnouncementType.GENERAL

class AnnouncementCreate(AnnouncementBase):
    pass

class AnnouncementResponse(AnnouncementBase):
    id: int
    author_id: int
    created_at: datetime
    author: Optional[UserResponse] = None

    class Config:
        from_attributes = True

# Event Schemas
class EventBase(BaseModel):
    title: str
    description: Optional[str] = None
    start_time: datetime
    end_time: Optional[datetime] = None
    type: EventType = EventType.OTHER

class EventCreate(EventBase):
    pass

class EventResponse(EventBase):
    id: int
    author_id: int
    created_at: datetime
    author: Optional[UserResponse] = None

    class Config:
        from_attributes = True

# Attendance Schemas
class AttendanceBase(BaseModel):
    status: AttendanceStatus

class AttendanceCreate(AttendanceBase):
    pass

class AttendanceResponse(AttendanceBase):
    event_id: int
    user_id: int
    created_at: datetime
    user: Optional[UserResponse] = None

    class Config:
        from_attributes = True

# Recruitment Schemas
class RecruitmentBase(BaseModel):
    recruit_name: str
    notes: Optional[str] = None

class RecruitmentCreate(RecruitmentBase):
    pass

class RecruitmentUpdate(BaseModel):
    status: RecruitmentStatus
    notes: Optional[str] = None

class RecruitmentResponse(RecruitmentBase):
    id: int
    recruiter_id: int
    status: RecruitmentStatus
    created_at: datetime
    recruiter: Optional[UserResponse] = None

    class Config:
        from_attributes = True


class GuildMemberSnapshotResponse(BaseModel):
    character_name: str
    level: Optional[int] = None
    vocation: Optional[str] = None
    rank: Optional[str] = None
    role: Optional[str] = None
    last_login: Optional[str] = None
    world: Optional[str] = None
    snapshot_at: datetime


class GuildMemberSnapshotPayload(BaseModel):
    guild_name: str
    source: str
    members: List[GuildMemberSnapshotResponse]
