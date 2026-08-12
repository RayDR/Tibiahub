"""Moderated Hunt Analyzer samples; submissions are never authoritative by default."""
from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.sql import func
from app.db.database import Base
from app.db.types import JSONBType


class HuntAnalyzerSubmission(Base):
    __tablename__ = "hunt_analyzer_submissions"
    __table_args__ = (Index("ix_hunt_analyzer_zone_status", "normalized_zone", "moderation_status"),)
    id = Column(Integer, primary_key=True)
    submitted_by_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    zone_name = Column(String(255), nullable=False)
    normalized_zone = Column(String(255), nullable=False, index=True)
    duration_seconds = Column(Integer, nullable=False)
    raw_exp = Column(Integer, nullable=False)
    profit = Column(Integer, nullable=False)
    source_kind = Column(String(32), nullable=False, default="paste")
    source_payload = Column(JSONBType, nullable=False)
    moderation_status = Column(String(32), nullable=False, default="pending", index=True)
    moderation_reason = Column(Text, nullable=True)
    moderated_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    submitted_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    moderated_at = Column(DateTime(timezone=True), nullable=True)
