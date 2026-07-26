"""Durable PostgreSQL-backed knowledge import orchestration models."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base
from app.db.types import JSONBType


KNOWLEDGE_JOB_STATES = (
    "pending",
    "claimed",
    "running",
    "retrying",
    "succeeded",
    "partially_succeeded",
    "failed",
    "cancelled",
)
ACTIVE_KNOWLEDGE_JOB_STATES = ("pending", "claimed", "running", "retrying")
KNOWLEDGE_JOB_TRIGGERS = ("bootstrap", "scheduled", "manual", "retry", "renormalize", "system")


class KnowledgeJob(Base):
    __tablename__ = "knowledge_jobs"
    __table_args__ = (
        CheckConstraint(
            "state IN ('pending','claimed','running','retrying','succeeded','partially_succeeded','failed','cancelled')",
            name="ck_knowledge_job_state",
        ),
        CheckConstraint(
            "trigger IN ('bootstrap','scheduled','manual','retry','renormalize','system')",
            name="ck_knowledge_job_trigger",
        ),
        CheckConstraint("attempt_count >= 0", name="ck_knowledge_job_attempt_count_nonnegative"),
        CheckConstraint("max_attempts > 0", name="ck_knowledge_job_max_attempts_positive"),
        CheckConstraint("priority >= 0", name="ck_knowledge_job_priority_nonnegative"),
        CheckConstraint("parent_job_id IS NULL OR parent_job_id <> id", name="ck_knowledge_job_parent_not_self"),
        Index("ix_knowledge_jobs_due", "state", "priority", "scheduled_at"),
        Index("ix_knowledge_jobs_provider_state", "provider_id", "state"),
        Index("ix_knowledge_jobs_entity_state", "entity_type_id", "state"),
        Index("ix_knowledge_jobs_worker_lease", "worker_id", "lease_expires_at"),
        Index("ix_knowledge_jobs_correlation", "correlation_id"),
        Index(
            "uq_knowledge_jobs_active_idempotency",
            "idempotency_key",
            unique=True,
            postgresql_where=text("state IN ('pending','claimed','running','retrying')"),
            sqlite_where=text("state IN ('pending','claimed','running','retrying')"),
        ),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    provider_id = Column(
        String(64),
        ForeignKey("knowledge_providers.provider_id", ondelete="RESTRICT"),
        nullable=False,
    )
    job_type = Column(String(64), nullable=False)
    entity_type_id = Column(
        String(64),
        ForeignKey("knowledge_entity_types.entity_type", ondelete="RESTRICT"),
        nullable=True,
    )
    scope = Column(JSONBType, nullable=False, default=dict)
    payload = Column(JSONBType, nullable=False, default=dict)
    priority = Column(Integer, nullable=False, default=100)
    state = Column(String(32), nullable=False, default="pending")
    scheduled_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    claimed_at = Column(DateTime(timezone=True), nullable=True)
    lease_expires_at = Column(DateTime(timezone=True), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    worker_id = Column(String(128), nullable=True)
    attempt_count = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=5)
    idempotency_key = Column(String(64), nullable=False)
    parent_job_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("knowledge_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    correlation_id = Column(Uuid(as_uuid=True), nullable=False, default=uuid4)
    last_error_code = Column(String(64), nullable=True)
    safe_last_error = Column(String(512), nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    trigger = Column(String(24), nullable=False, default="system")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    provider = relationship("KnowledgeProvider")
    entity_type_definition = relationship("KnowledgeEntityType")
    attempts = relationship(
        "KnowledgeJobAttempt",
        back_populates="job",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="KnowledgeJobAttempt.attempt_number",
    )
    parent = relationship("KnowledgeJob", remote_side=[id])


class KnowledgeJobAttempt(Base):
    __tablename__ = "knowledge_job_attempts"
    __table_args__ = (
        UniqueConstraint("job_id", "attempt_number", name="uq_knowledge_job_attempt_number"),
        CheckConstraint("attempt_number > 0", name="ck_knowledge_attempt_number_positive"),
        CheckConstraint(
            "outcome IN ('running','succeeded','partially_succeeded','retrying','failed','cancelled','lease_expired')",
            name="ck_knowledge_attempt_outcome",
        ),
        Index("ix_knowledge_attempts_job_created", "job_id", "created_at"),
        Index("ix_knowledge_attempts_worker_started", "worker_id", "started_at"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    job_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("knowledge_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    attempt_number = Column(Integer, nullable=False)
    worker_id = Column(String(128), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    outcome = Column(String(32), nullable=False, default="running")
    retryable = Column(Boolean, nullable=False, default=False)
    error_code = Column(String(64), nullable=True)
    safe_error = Column(String(512), nullable=True)
    metrics = Column(JSONBType, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    job = relationship("KnowledgeJob", back_populates="attempts")


class KnowledgeWorkerHeartbeat(Base):
    __tablename__ = "knowledge_worker_heartbeats"
    __table_args__ = (
        CheckConstraint(
            "state IN ('idle','running','stopping','offline','error')",
            name="ck_knowledge_worker_state",
        ),
        Index("ix_knowledge_workers_state_seen", "state", "last_seen_at"),
    )

    worker_id = Column(String(128), primary_key=True)
    worker_type = Column(String(64), nullable=False, default="knowledge")
    node_id = Column(String(128), nullable=False)
    process_id = Column(Integer, nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_seen_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    current_job_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("knowledge_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    state = Column(String(24), nullable=False, default="idle")
    version = Column(String(64), nullable=False)
    safe_metadata = Column(JSONBType, nullable=False, default=dict)


class KnowledgeProviderCursor(Base):
    __tablename__ = "knowledge_provider_cursors"
    __table_args__ = (
        UniqueConstraint(
            "provider_id",
            "entity_type_id",
            "scope_hash",
            name="uq_knowledge_provider_cursor_scope",
        ),
        Index("ix_knowledge_cursors_provider_updated", "provider_id", "updated_at"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    provider_id = Column(
        String(64),
        ForeignKey("knowledge_providers.provider_id", ondelete="CASCADE"),
        nullable=False,
    )
    entity_type_id = Column(
        String(64),
        ForeignKey("knowledge_entity_types.entity_type", ondelete="CASCADE"),
        nullable=False,
    )
    scope_hash = Column(String(64), nullable=False)
    cursor = Column(JSONBType, nullable=False, default=dict)
    last_success_at = Column(DateTime(timezone=True), nullable=True)
    last_job_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("knowledge_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    version = Column(String(128), nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
