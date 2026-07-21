"""
Guild raffle models.

This system is account-based through local users, while keeping the winning
character that represents each account inside the guild raffle.
"""
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class Raffle(Base):
    __tablename__ = "raffles"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    public_code = Column(String(6), nullable=False, unique=True, index=True)
    guild_name = Column(String(200), nullable=False)
    access_mode = Column(String(20), nullable=False, default="guild_only")  # guild_only|world_only|public
    show_participants = Column(Boolean, nullable=False, default=True)
    visibility = Column(String(20), nullable=False, default="public")  # public|private
    registration_enabled = Column(Boolean, nullable=False, default=True)
    run_mode = Column(String(20), nullable=False, default="manual")  # manual|automatic
    scheduled_run_at = Column(DateTime(timezone=True), nullable=True)
    purpose = Column(String(20), nullable=False, default="legacy")  # test|real|legacy
    timezone_name = Column(String(64), nullable=False, default="America/Chicago")
    eligibility_days = Column(Integer, nullable=False, default=5)
    eligibility_cutoff_at = Column(DateTime(timezone=True), nullable=True)
    publication_status = Column(String(20), nullable=False, default="private")
    published_at = Column(DateTime(timezone=True), nullable=True)
    published_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    execution_state = Column(String(20), nullable=False, default="pending")
    executed_at = Column(DateTime(timezone=True), nullable=True)
    execution_trigger = Column(String(20), nullable=True)
    scheduler_job_id = Column(String(255), nullable=True)
    claim_token = Column(String(64), nullable=True)
    claimed_at = Column(DateTime(timezone=True), nullable=True)
    lease_expires_at = Column(DateTime(timezone=True), nullable=True)
    last_error_code = Column(String(100), nullable=True)
    last_error_summary = Column(Text, nullable=True)
    version = Column(Integer, nullable=False, default=1)
    archive_after_days = Column(Integer, nullable=False, default=7)
    archived_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(50), nullable=False, default="draft")
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    last_executed_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    current_run_number = Column(Integer, nullable=False, default=0)
    rerun_count = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    deleted_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    delete_reason = Column(Text, nullable=True)
    is_deleted = Column(Boolean, nullable=False, default=False)

    created_by = relationship("User", foreign_keys=[created_by_id], backref="created_raffles")
    last_executed_by = relationship("User", foreign_keys=[last_executed_by_id], backref="executed_raffles")
    published_by = relationship("User", foreign_keys=[published_by_id])
    participants = relationship("RaffleParticipant", back_populates="raffle", cascade="all, delete-orphan")
    prizes = relationship("RafflePrize", back_populates="raffle", cascade="all, delete-orphan", order_by="RafflePrize.order_index")
    winners = relationship("RaffleWinner", back_populates="raffle", cascade="all, delete-orphan", order_by="RaffleWinner.created_at")
    manager_grants = relationship("RaffleManagerGrant", back_populates="raffle", cascade="all, delete-orphan")
    eligibility_snapshots = relationship("RaffleEligibilitySnapshot", back_populates="raffle", cascade="all, delete-orphan")
    runs = relationship("RaffleRun", back_populates="raffle", cascade="all, delete-orphan", foreign_keys="RaffleRun.raffle_id")
    deliveries = relationship("RafflePrizeDelivery", back_populates="raffle", cascade="all, delete-orphan")


class RaffleParticipant(Base):
    __tablename__ = "raffle_participants"
    __table_args__ = (
        UniqueConstraint("raffle_id", "user_id", name="uq_raffle_participant_user"),
        UniqueConstraint("raffle_id", "character_name", name="uq_raffle_participant_character"),
    )

    id = Column(Integer, primary_key=True, index=True)
    raffle_id = Column(Integer, ForeignKey("raffles.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    character_name = Column(String(100), nullable=False, index=True)
    guild_rank = Column(String(100), nullable=True)
    weight = Column(Float, nullable=False, default=1.0)
    weight_multiplier = Column(Float, nullable=False, default=1.0)
    is_eligible = Column(Boolean, nullable=False, default=True)
    source = Column(String(50), nullable=False, default="guild_sync")
    source_data = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    deleted_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    delete_reason = Column(Text, nullable=True)
    is_deleted = Column(Boolean, nullable=False, default=False)

    raffle = relationship("Raffle", back_populates="participants")
    user = relationship("User", foreign_keys=[user_id], backref="raffle_participations")
    winners = relationship("RaffleWinner", back_populates="participant")


class RafflePrize(Base):
    __tablename__ = "raffle_prizes"

    id = Column(Integer, primary_key=True, index=True)
    raffle_id = Column(Integer, ForeignKey("raffles.id"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    reward = Column(String(200), nullable=False)
    order_index = Column(Integer, nullable=False, default=1)
    position = Column(String(20), nullable=True)  # second|first for automatic raffles
    amount = Column(Numeric(12, 2), nullable=True)
    currency = Column(String(20), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    raffle = relationship("Raffle", back_populates="prizes")
    winners = relationship("RaffleWinner", back_populates="prize")


class RaffleWinner(Base):
    __tablename__ = "raffle_winners"

    id = Column(Integer, primary_key=True, index=True)
    raffle_id = Column(Integer, ForeignKey("raffles.id"), nullable=False, index=True)
    prize_id = Column(Integer, ForeignKey("raffle_prizes.id"), nullable=False, index=True)
    participant_id = Column(Integer, ForeignKey("raffle_participants.id"), nullable=False, index=True)
    executed_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    run_number = Column(Integer, nullable=False, default=1)
    is_rerun = Column(Boolean, nullable=False, default=False)
    rerun_reason = Column(Text, nullable=True)
    participant_snapshot = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    raffle = relationship("Raffle", back_populates="winners")
    prize = relationship("RafflePrize", back_populates="winners")
    participant = relationship("RaffleParticipant", back_populates="winners")
    executed_by = relationship("User", backref="raffle_winner_executions")


class RaffleManagerGrant(Base):
    __tablename__ = "raffle_manager_grants"
    __table_args__ = (UniqueConstraint("raffle_id", "user_id", name="uq_raffle_manager_grant"),)

    id = Column(Integer, primary_key=True)
    raffle_id = Column(Integer, ForeignKey("raffles.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    granted_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    raffle = relationship("Raffle", back_populates="manager_grants")
    user = relationship("User", foreign_keys=[user_id])
    granted_by = relationship("User", foreign_keys=[granted_by_id])


class RaffleEligibilitySnapshot(Base):
    __tablename__ = "raffle_eligibility_snapshots"
    __table_args__ = (UniqueConstraint("raffle_id", "snapshot_number", name="uq_raffle_snapshot_number"),)

    id = Column(Integer, primary_key=True)
    raffle_id = Column(Integer, ForeignKey("raffles.id"), nullable=False, index=True)
    snapshot_number = Column(Integer, nullable=False)
    cutoff_at = Column(DateTime(timezone=True), nullable=False)
    timezone_name = Column(String(64), nullable=False)
    eligibility_days = Column(Integer, nullable=False)
    source = Column(String(50), nullable=False)
    candidate_count = Column(Integer, nullable=False)
    eligible_count = Column(Integer, nullable=False)
    excluded_count = Column(Integer, nullable=False)
    snapshot_hash = Column(String(64), nullable=False)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    raffle = relationship("Raffle", back_populates="eligibility_snapshots")
    entries = relationship("RaffleEligibilityEntry", back_populates="snapshot", cascade="all, delete-orphan")
    created_by = relationship("User", foreign_keys=[created_by_id])


class RaffleEligibilityEntry(Base):
    __tablename__ = "raffle_eligibility_entries"
    __table_args__ = (UniqueConstraint("snapshot_id", "user_id", name="uq_raffle_snapshot_user"),)

    id = Column(Integer, primary_key=True)
    snapshot_id = Column(Integer, ForeignKey("raffle_eligibility_snapshots.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    character_name = Column(String(100), nullable=True)
    guild_name = Column(String(200), nullable=True)
    guild_rank = Column(String(100), nullable=True)
    last_activity_at = Column(DateTime(timezone=True), nullable=True)
    is_eligible = Column(Boolean, nullable=False)
    exclusion_code = Column(String(50), nullable=True)
    exclusion_summary = Column(String(255), nullable=True)
    source_data = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    snapshot = relationship("RaffleEligibilitySnapshot", back_populates="entries")
    user = relationship("User")


class RaffleRun(Base):
    __tablename__ = "raffle_runs"
    __table_args__ = (UniqueConstraint("raffle_id", "run_number", name="uq_raffle_run_number"),)

    id = Column(Integer, primary_key=True)
    raffle_id = Column(Integer, ForeignKey("raffles.id"), nullable=False, index=True)
    run_number = Column(Integer, nullable=False)
    snapshot_id = Column(Integer, ForeignKey("raffle_eligibility_snapshots.id"), nullable=False)
    parent_run_id = Column(Integer, ForeignKey("raffle_runs.id"), nullable=True)
    trigger = Column(String(20), nullable=False)
    state = Column(String(20), nullable=False)
    requested_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    failure_code = Column(String(100), nullable=True)
    failure_summary = Column(Text, nullable=True)
    algorithm_version = Column(String(50), nullable=False)
    entropy_commitment = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    raffle = relationship("Raffle", back_populates="runs", foreign_keys=[raffle_id])
    snapshot = relationship("RaffleEligibilitySnapshot")
    parent_run = relationship("RaffleRun", remote_side=[id])
    requested_by = relationship("User")
    results = relationship("RaffleRunResult", back_populates="run", cascade="all, delete-orphan")


class RaffleRunResult(Base):
    __tablename__ = "raffle_run_results"
    __table_args__ = (UniqueConstraint("run_id", "prize_position", name="uq_raffle_run_position"),)

    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("raffle_runs.id"), nullable=False, index=True)
    prize_id = Column(Integer, ForeignKey("raffle_prizes.id"), nullable=False)
    prize_position = Column(String(20), nullable=False)
    participant_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    participant_character_name = Column(String(100), nullable=False)
    selection_index = Column(Integer, nullable=False)
    candidate_count = Column(Integer, nullable=False)
    derived_entropy_hash = Column(String(64), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    superseded_by_result_id = Column(Integer, ForeignKey("raffle_run_results.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    run = relationship("RaffleRun", back_populates="results", foreign_keys=[run_id])
    prize = relationship("RafflePrize")
    participant_user = relationship("User")
    superseded_by = relationship("RaffleRunResult", remote_side=[id])
    delivery = relationship("RafflePrizeDelivery", back_populates="result", uselist=False)


class RafflePrizeDelivery(Base):
    __tablename__ = "raffle_prize_deliveries"
    __table_args__ = (UniqueConstraint("result_id", name="uq_raffle_delivery_result"),)

    id = Column(Integer, primary_key=True)
    raffle_id = Column(Integer, ForeignKey("raffles.id"), nullable=False, index=True)
    result_id = Column(Integer, ForeignKey("raffle_run_results.id"), nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    delivery_deadline_at = Column(DateTime(timezone=True), nullable=False)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    delivered_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    note = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    raffle = relationship("Raffle", back_populates="deliveries")
    result = relationship("RaffleRunResult", back_populates="delivery")
    delivered_by = relationship("User")


class RaffleRerunAudit(Base):
    __tablename__ = "raffle_rerun_audits"

    id = Column(Integer, primary_key=True)
    raffle_id = Column(Integer, ForeignKey("raffles.id"), nullable=False, index=True)
    source_run_id = Column(Integer, ForeignKey("raffle_runs.id"), nullable=False)
    new_run_id = Column(Integer, ForeignKey("raffle_runs.id"), nullable=False)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    positions = Column(JSON, nullable=False)
    reason = Column(Text, nullable=False)
    override_delivered = Column(Boolean, nullable=False, default=False)
    override_reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    raffle = relationship("Raffle")
    source_run = relationship("RaffleRun", foreign_keys=[source_run_id])
    new_run = relationship("RaffleRun", foreign_keys=[new_run_id])
    actor = relationship("User")
