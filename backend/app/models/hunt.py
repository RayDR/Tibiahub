from sqlalchemy import CheckConstraint, Column, ForeignKey, Index, Integer, String, Text, DateTime, UniqueConstraint, func
from sqlalchemy.orm import relationship
from app.db.database import Base
from app.db.types import JSONBType

class HuntCatalog(Base):
    __tablename__ = "hunt_catalog"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    location = Column(String(200), nullable=False)
    level_min = Column(Integer, nullable=False)
    level_max = Column(Integer, nullable=False)
    vocation = Column(Text)
    exp_per_hour = Column(Integer)
    profit_per_hour = Column(Integer)
    creatures = Column(Text, nullable=False)
    strategy = Column(Text)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class GuildHunt(Base):
    """A scheduled guild activity; distinct from the global hunting-place catalog."""

    __tablename__ = "guild_hunts"
    __table_args__ = (
        CheckConstraint("status IN ('scheduled','in_progress','finished','cancelled')", name="ck_guild_hunt_status"),
        CheckConstraint("maximum_participants > 0", name="ck_guild_hunt_positive_capacity"),
        CheckConstraint("recommended_level > 0", name="ck_guild_hunt_positive_level"),
        CheckConstraint("required_ek >= 0 AND required_ed >= 0 AND required_rp >= 0 AND required_ms >= 0", name="ck_guild_hunt_nonnegative_roles"),
        Index("ix_guild_hunts_guild_schedule", "guild_name", "scheduled_at"),
        Index("ix_guild_hunts_guild_status", "guild_name", "status"),
    )

    id = Column(Integer, primary_key=True)
    guild_name = Column(String(200), nullable=False)
    scheduled_at = Column(DateTime(timezone=True), nullable=False)
    timezone_name = Column(String(64), nullable=False, default="UTC")
    server_name = Column(String(100), nullable=False)
    location = Column(String(200), nullable=False)
    target = Column(String(200), nullable=False)
    recommended_level = Column(Integer, nullable=False)
    recommended_vocations = Column(JSONBType, nullable=False, default=list)
    maximum_participants = Column(Integer, nullable=False)
    required_ek = Column(Integer, nullable=False, default=0)
    required_ed = Column(Integer, nullable=False, default=0)
    required_rp = Column(Integer, nullable=False, default=0)
    required_ms = Column(Integer, nullable=False, default=0)
    description = Column(Text, nullable=True)
    discord_channel = Column(String(200), nullable=True)
    voice_channel = Column(String(200), nullable=True)
    status = Column(String(24), nullable=False, default="scheduled")
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    cancelled_by_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    cancellation_reason = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    creator = relationship("User", foreign_keys=[created_by_id])
    participants = relationship("GuildHuntParticipant", back_populates="hunt", order_by="GuildHuntParticipant.joined_at")


class GuildHuntParticipant(Base):
    __tablename__ = "guild_hunt_participants"
    __table_args__ = (
        UniqueConstraint("hunt_id", "user_id", name="uq_guild_hunt_participant_user"),
        CheckConstraint("attendance_status IN ('registered','attended','absent','left')", name="ck_guild_hunt_attendance_status"),
        Index("ix_guild_hunt_participants_hunt_status", "hunt_id", "attendance_status"),
    )

    id = Column(Integer, primary_key=True)
    hunt_id = Column(Integer, ForeignKey("guild_hunts.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    character_name = Column(String(100), nullable=False)
    vocation = Column(String(30), nullable=True)
    attendance_status = Column(String(20), nullable=False, default="registered")
    joined_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    left_at = Column(DateTime(timezone=True), nullable=True)
    attendance_marked_at = Column(DateTime(timezone=True), nullable=True)
    attendance_marked_by_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)

    hunt = relationship("GuildHunt", back_populates="participants")
    user = relationship("User", foreign_keys=[user_id])
