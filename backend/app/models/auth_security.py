"""Durable authentication tokens and privacy-preserving request throttles."""

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class AuthOneTimeToken(Base):
    __tablename__ = "auth_one_time_tokens"
    __table_args__ = (
        Index("ix_auth_one_time_tokens_lookup", "purpose", "token_hash", unique=True),
        Index("ix_auth_one_time_tokens_user_recent", "user_id", "purpose", "created_at"),
        CheckConstraint("purpose IN ('password_reset','email_verification')", name="ck_auth_token_purpose"),
        CheckConstraint("length(token_hash) = 64", name="ck_auth_token_hash_length"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    purpose = Column(String(40), nullable=False)
    token_hash = Column(String(64), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    consumed_at = Column(DateTime(timezone=True), nullable=True)
    invalidated_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    user = relationship("User")


class AuthRequestEvent(Base):
    __tablename__ = "auth_request_events"
    __table_args__ = (
        Index("ix_auth_request_events_subject_recent", "purpose", "subject_hash", "created_at"),
        Index("ix_auth_request_events_requester_recent", "purpose", "requester_hash", "created_at"),
        CheckConstraint("purpose IN ('password_reset','email_verification')", name="ck_auth_request_purpose"),
    )

    id = Column(Integer, primary_key=True)
    purpose = Column(String(40), nullable=False)
    subject_hash = Column(String(64), nullable=False)
    requester_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
