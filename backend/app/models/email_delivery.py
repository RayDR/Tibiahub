"""Durable email delivery queue and isolated worker heartbeat."""

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.sql import func

from app.db.database import Base
from app.db.types import JSONBType


class EmailOutbox(Base):
    __tablename__ = "email_outbox"
    __table_args__ = (
        Index("ix_email_outbox_due", "status", "next_attempt_at", "id"),
        CheckConstraint(
            "status IN ('pending','processing','sent','retry','failed','cancelled')",
            name="ck_email_outbox_status",
        ),
    )

    id = Column(Integer, primary_key=True)
    message_type = Column(String(60), nullable=False, index=True)
    recipient_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    recipient_email = Column(String(320), nullable=False)
    locale = Column(String(8), nullable=False, default="en")
    template_payload = Column(JSONBType, nullable=False, default=dict)
    secret_payload_ciphertext = Column(Text, nullable=True)
    idempotency_key = Column(String(160), nullable=False, unique=True)
    status = Column(String(20), nullable=False, default="pending", index=True)
    attempt_count = Column(Integer, nullable=False, default=0)
    next_attempt_at = Column(DateTime(timezone=True), nullable=True, index=True)
    lease_expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    safe_failure_category = Column(String(80), nullable=True)


class EmailWorkerHeartbeat(Base):
    __tablename__ = "email_worker_heartbeats"

    worker_id = Column(String(100), primary_key=True)
    state = Column(String(30), nullable=False)
    last_seen_at = Column(DateTime(timezone=True), nullable=False)
    current_job_id = Column(Integer, ForeignKey("email_outbox.id", ondelete="SET NULL"), nullable=True)
    version = Column(String(40), nullable=False)
    last_success_at = Column(DateTime(timezone=True), nullable=True)
    last_failure_category = Column(String(80), nullable=True)
    enabled = Column(Boolean, nullable=False, default=True)
