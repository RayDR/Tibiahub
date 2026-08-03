"""Durable maintenance holds and full-sync execution phases."""

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base
from app.db.types import JSONBType


class MaintenanceHold(Base):
    __tablename__ = "maintenance_holds"
    __table_args__ = (
        CheckConstraint("hold_type IN ('manual','sync')", name="ck_maintenance_hold_type"),
        CheckConstraint("hold_type <> 'sync' OR owner_job_id IS NOT NULL", name="ck_sync_hold_has_owner"),
        UniqueConstraint("owner_job_id", name="uq_maintenance_sync_owner_job"),
        Index("ix_maintenance_holds_active", "released_at", "hold_type"),
    )

    id = Column(Integer, primary_key=True)
    hold_type = Column(String(20), nullable=False, index=True)
    owner_job_id = Column(String(64), ForeignKey("sync_jobs.id", ondelete="CASCADE"), nullable=True, index=True)
    reason = Column(Text, nullable=False)
    public_message = Column(String(500), nullable=False)
    enabled_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    enabled_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    planned_end_at = Column(DateTime(timezone=True), nullable=True)
    auto_release = Column(Boolean, nullable=False, default=False)
    released_at = Column(DateTime(timezone=True), nullable=True)
    released_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    release_reason = Column(Text, nullable=True)
    last_heartbeat_at = Column(DateTime(timezone=True), nullable=True)
    safe_metadata = Column(JSONBType, nullable=False, default=dict)

    owner_job = relationship("SyncJob")
    enabled_by = relationship("User", foreign_keys=[enabled_by_user_id])
    released_by = relationship("User", foreign_keys=[released_by_user_id])


class SyncJobPhase(Base):
    __tablename__ = "sync_job_phases"
    __table_args__ = (
        UniqueConstraint("job_id", "phase_key", name="uq_sync_job_phase"),
        CheckConstraint(
            "status IN ('pending','running','retrying','completed','failed','skipped','cancelled')",
            name="ck_sync_job_phase_status",
        ),
        Index("ix_sync_job_phases_order", "job_id", "order_index"),
    )

    id = Column(Integer, primary_key=True)
    job_id = Column(String(64), ForeignKey("sync_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    phase_key = Column(String(64), nullable=False)
    order_index = Column(Integer, nullable=False)
    provider = Column(String(80), nullable=True)
    required = Column(Boolean, nullable=False, default=False)
    status = Column(String(20), nullable=False, default="pending", index=True)
    attempt_count = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=3)
    processed_count = Column(Integer, nullable=False, default=0)
    failed_count = Column(Integer, nullable=False, default=0)
    current_entity = Column(String(255), nullable=True)
    current_offset = Column(Integer, nullable=False, default=0)
    checkpoint = Column(JSONBType, nullable=False, default=dict)
    next_retry_at = Column(DateTime(timezone=True), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    error_category = Column(String(80), nullable=True)
    safe_error = Column(String(500), nullable=True)
    safe_metadata = Column(JSONBType, nullable=False, default=dict)

    job = relationship("SyncJob")


class SyncWorkerHeartbeat(Base):
    __tablename__ = "sync_worker_heartbeats"

    worker_id = Column(String(128), primary_key=True)
    state = Column(String(30), nullable=False)
    last_seen_at = Column(DateTime(timezone=True), nullable=False)
    current_job_id = Column(String(64), ForeignKey("sync_jobs.id", ondelete="SET NULL"), nullable=True)
    version = Column(String(40), nullable=False)
    enabled = Column(Boolean, nullable=False, default=True)
    last_success_at = Column(DateTime(timezone=True), nullable=True)
    last_failure_category = Column(String(80), nullable=True)

    current_job = relationship("SyncJob")
