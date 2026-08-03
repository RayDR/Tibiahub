"""Proof-based Tibia character ownership claims and immutable history."""

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base
from app.db.types import JSONBType


class CharacterOwnershipClaim(Base):
    __tablename__ = "character_ownership_claims"
    __table_args__ = (
        Index("ix_character_claims_queue", "status", "next_attempt_at", "id"),
        Index(
            "uq_character_active_claim_user_name",
            "user_id",
            "normalized_name",
            unique=True,
            postgresql_where=text("status IN ('pending','queued','processing','transfer_pending','disputed')"),
            sqlite_where=text("status IN ('pending','queued','processing','transfer_pending','disputed')"),
        ),
        CheckConstraint(
            "status IN ('pending','queued','processing','verified','transfer_pending','disputed','rejected','expired','failed')",
            name="ck_character_claim_status",
        ),
        CheckConstraint("length(challenge_hash) = 64", name="ck_character_claim_hash_length"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    character_name = Column(String(100), nullable=False)
    normalized_name = Column(String(100), nullable=False, index=True)
    challenge_hash = Column(String(64), nullable=False, unique=True)
    challenge_ciphertext = Column(Text, nullable=True)
    status = Column(String(30), nullable=False, default="pending", index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    verification_requested_at = Column(DateTime(timezone=True), nullable=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    consumed_at = Column(DateTime(timezone=True), nullable=True)
    lease_expires_at = Column(DateTime(timezone=True), nullable=True)
    next_attempt_at = Column(DateTime(timezone=True), nullable=True)
    attempt_count = Column(Integer, nullable=False, default=0)
    safe_failure_code = Column(String(50), nullable=True)
    dispute_reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    user = relationship("User")


class CharacterOwnershipHistory(Base):
    __tablename__ = "character_ownership_history"
    __table_args__ = (Index("ix_character_ownership_history_name", "normalized_name", "created_at"),)

    id = Column(Integer, primary_key=True)
    normalized_name = Column(String(100), nullable=False)
    character_name = Column(String(100), nullable=False)
    claim_id = Column(Integer, ForeignKey("character_ownership_claims.id", ondelete="SET NULL"), nullable=True)
    action = Column(String(40), nullable=False)
    from_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    to_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    actor_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    safe_metadata = Column(JSONBType, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    claim = relationship("CharacterOwnershipClaim")
