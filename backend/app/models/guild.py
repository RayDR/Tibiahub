"""
Guild Management Models
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.db.database import Base

class AnnouncementType(str, enum.Enum):
    GENERAL = "general"
    CONTEST = "contest"
    HUNT = "hunt"

class Announcement(Base):
    __tablename__ = "announcements"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    type = Column(Enum(AnnouncementType), default=AnnouncementType.GENERAL)

    author = relationship("User", backref="announcements")

class EventType(str, enum.Enum):
    QUEST = "quest"
    HUNT = "hunt"
    PVP = "pvp"
    MEETING = "meeting"
    OTHER = "other"

class GuildEvent(Base):
    __tablename__ = "guild_events"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=True)
    type = Column(Enum(EventType), default=EventType.OTHER)
    author_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    author = relationship("User", backref="guild_events_created")
    attendees = relationship("EventAttendance", back_populates="event")

class AttendanceStatus(str, enum.Enum):
    CONFIRMED = "confirmed"
    MAYBE = "maybe"
    DECLINED = "declined"
    BENCH = "bench"

class EventAttendance(Base):
    __tablename__ = "event_attendance"

    event_id = Column(Integer, ForeignKey("guild_events.id"), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    status = Column(Enum(AttendanceStatus), default=AttendanceStatus.CONFIRMED)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    event = relationship("GuildEvent", back_populates="attendees")
    user = relationship("User", backref="guild_event_attendance")

class RecruitmentStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"

class Recruitment(Base):
    __tablename__ = "recruitments"

    id = Column(Integer, primary_key=True, index=True)
    recruiter_id = Column(Integer, ForeignKey("users.id"))
    recruit_name = Column(String(100), nullable=False)
    status = Column(Enum(RecruitmentStatus), default=RecruitmentStatus.PENDING)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    notes = Column(Text, nullable=True)

    recruiter = relationship("User", backref="recruits")
