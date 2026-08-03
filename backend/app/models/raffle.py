"""
Guild raffle models.

Participants are character identities. A verified local account may be linked
when known, while synchronized external guild characters remain first-class.
"""
from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base
from app.db.types import JSONBType


def _normalized_character_default(context) -> str:
    return " ".join(str(context.get_current_parameters().get("character_name") or context.get_current_parameters().get("participant_character_name") or "").split()).casefold()


def _raffle_id_snapshot_default(context) -> int:
    return int(context.get_current_parameters().get("raffle_id") or 0)


class Raffle(Base):
    __tablename__ = "raffles"
    __table_args__ = (
        Index(
            "ix_raffles_scheduler_due",
            "scheduled_run_at",
            "next_retry_at",
            postgresql_where=text(
                "run_mode = 'automatic' AND is_deleted IS FALSE "
                "AND execution_state IN ('pending','failed','claimed','running')"
            ),
        ),
        CheckConstraint("weighting_mode IN ('equal','weighted')", name="ck_raffles_weighting_mode"),
    )

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    public_code = Column(String(6), nullable=False, unique=True, index=True)
    guild_name = Column(String(200), nullable=False)
    scope_type = Column(String(20), nullable=False, default="guild")  # guild|server|global
    world_name = Column(String(100), nullable=True)
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
    unique_account_participation = Column(Boolean, nullable=False, default=True)
    weighting_mode = Column(String(20), nullable=False, default="equal")
    publication_status = Column(String(20), nullable=False, default="private")
    published_at = Column(DateTime(timezone=True), nullable=True)
    published_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    published_by_character_name = Column(String(100), nullable=True)
    execution_state = Column(String(20), nullable=False, default="pending")
    executed_at = Column(DateTime(timezone=True), nullable=True)
    execution_trigger = Column(String(20), nullable=True)
    scheduler_job_id = Column(String(255), nullable=True)
    claim_token = Column(String(64), nullable=True)
    claimed_at = Column(DateTime(timezone=True), nullable=True)
    lease_expires_at = Column(DateTime(timezone=True), nullable=True)
    last_error_code = Column(String(100), nullable=True)
    last_error_summary = Column(Text, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    next_retry_at = Column(DateTime(timezone=True), nullable=True)
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
    scheduler_attempts = relationship("RaffleSchedulerAttempt", back_populates="raffle", cascade="all, delete-orphan")


class RaffleParticipant(Base):
    __tablename__ = "raffle_participants"
    __table_args__ = (
        Index("uq_raffle_active_participant_character", "raffle_id", "normalized_character_name", unique=True, postgresql_where=text("is_deleted IS FALSE"), sqlite_where=text("is_deleted = 0")),
        Index("uq_raffle_active_known_account", "raffle_id", "enforced_account_identity_key", unique=True, postgresql_where=text("is_deleted IS FALSE AND enforced_account_identity_key IS NOT NULL"), sqlite_where=text("is_deleted = 0 AND enforced_account_identity_key IS NOT NULL")),
        CheckConstraint("weight > 0", name="ck_raffle_participant_positive_weight"),
    )

    id = Column(Integer, primary_key=True, index=True)
    raffle_id = Column(Integer, ForeignKey("raffles.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    guild_roster_character_id = Column(Integer, ForeignKey("guild_roster_characters.id", ondelete="SET NULL"), nullable=True, index=True)
    character_name = Column(String(100), nullable=False, index=True)
    normalized_character_name = Column(String(100), nullable=False, index=True, default=_normalized_character_default)
    known_account_identity_key = Column(String(100), nullable=True, index=True)
    enforced_account_identity_key = Column(String(100), nullable=True)
    guild_name_snapshot = Column(String(200), nullable=False, default="")
    world_name_snapshot = Column(String(100), nullable=True)
    guild_rank = Column(String(100), nullable=True)
    weight = Column(Numeric(12, 4), nullable=False, default=1)
    weight_multiplier = Column(Numeric(12, 4), nullable=False, default=1)
    is_eligible = Column(Boolean, nullable=False, default=True)
    eligibility_override = Column(Boolean, nullable=True)
    eligibility_override_reason = Column(Text, nullable=True)
    source = Column(String(50), nullable=False, default="guild_sync")
    source_data = Column(JSONBType, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    deleted_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    delete_reason = Column(Text, nullable=True)
    is_deleted = Column(Boolean, nullable=False, default=False)

    raffle = relationship("Raffle", back_populates="participants")
    user = relationship("User", foreign_keys=[user_id], backref="raffle_participations")
    guild_roster_character = relationship("GuildRosterCharacter")
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
    participant_snapshot = Column(JSONBType, nullable=True)
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

    id = Column(Integer, primary_key=True)
    snapshot_id = Column(Integer, ForeignKey("raffle_eligibility_snapshots.id"), nullable=False, index=True)
    participant_id = Column(Integer, ForeignKey("raffle_participants.id", ondelete="SET NULL"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    guild_roster_character_id = Column(Integer, ForeignKey("guild_roster_characters.id", ondelete="SET NULL"), nullable=True)
    character_name = Column(String(100), nullable=True)
    normalized_character_name = Column(String(100), nullable=False, default=_normalized_character_default)
    known_account_identity_key = Column(String(100), nullable=True)
    guild_name = Column(String(200), nullable=True)
    guild_rank = Column(String(100), nullable=True)
    world_name = Column(String(100), nullable=True)
    weight_snapshot = Column(Numeric(12, 4), nullable=False, default=1)
    last_activity_at = Column(DateTime(timezone=True), nullable=True)
    is_eligible = Column(Boolean, nullable=False)
    exclusion_code = Column(String(50), nullable=True)
    exclusion_summary = Column(String(255), nullable=True)
    source_data = Column(JSONBType, nullable=True)
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
    participant_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    participant_roster_character_id = Column(Integer, ForeignKey("guild_roster_characters.id", ondelete="SET NULL"), nullable=True)
    participant_character_name = Column(String(100), nullable=False)
    participant_normalized_character_name = Column(String(100), nullable=False, default=_normalized_character_default)
    participant_account_identity_key = Column(String(100), nullable=True)
    participant_guild_name = Column(String(200), nullable=False, default="")
    participant_world_name = Column(String(100), nullable=True)
    participant_weight = Column(Numeric(12, 4), nullable=False, default=1)
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
    history = relationship("RaffleDeliveryAudit", back_populates="delivery", cascade="all, delete-orphan", order_by="RaffleDeliveryAudit.created_at")


class RaffleDeliveryAudit(Base):
    __tablename__ = "raffle_delivery_audits"

    id = Column(Integer, primary_key=True)
    delivery_id = Column(Integer, ForeignKey("raffle_prize_deliveries.id"), nullable=False, index=True)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    previous_status = Column(String(20), nullable=False)
    new_status = Column(String(20), nullable=False)
    note = Column(Text, nullable=True)
    admin_override = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    delivery = relationship("RafflePrizeDelivery", back_populates="history")
    actor = relationship("User")


class RaffleRerunAudit(Base):
    __tablename__ = "raffle_rerun_audits"

    id = Column(Integer, primary_key=True)
    raffle_id = Column(Integer, ForeignKey("raffles.id"), nullable=False, index=True)
    source_run_id = Column(Integer, ForeignKey("raffle_runs.id"), nullable=False)
    new_run_id = Column(Integer, ForeignKey("raffle_runs.id"), nullable=False)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    positions = Column(JSONBType, nullable=False)
    reason = Column(Text, nullable=False)
    override_delivered = Column(Boolean, nullable=False, default=False)
    override_reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    raffle = relationship("Raffle")
    source_run = relationship("RaffleRun", foreign_keys=[source_run_id])
    new_run = relationship("RaffleRun", foreign_keys=[new_run_id])
    actor = relationship("User")


class RaffleTestAudit(Base):
    __tablename__ = "raffle_test_audits"

    id = Column(Integer, primary_key=True)
    raffle_id = Column(Integer, ForeignKey("raffles.id", ondelete="SET NULL"), nullable=True, index=True)
    raffle_id_snapshot = Column(Integer, nullable=False, index=True, default=_raffle_id_snapshot_default)
    raffle_title_snapshot = Column(String(200), nullable=False, default="")
    guild_name_snapshot = Column(String(200), nullable=False, default="")
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(String(80), nullable=False, index=True)
    reason = Column(Text, nullable=True)
    details = Column(JSONBType, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    raffle = relationship("Raffle")
    actor = relationship("User")


class RaffleSchedulerAttempt(Base):
    __tablename__ = "raffle_scheduler_attempts"
    __table_args__ = (UniqueConstraint("job_id", name="uq_raffle_scheduler_job_id"),)

    id = Column(Integer, primary_key=True)
    raffle_id = Column(Integer, ForeignKey("raffles.id"), nullable=False, index=True)
    job_id = Column(String(255), nullable=False)
    worker_id = Column(String(255), nullable=False)
    trigger = Column(String(30), nullable=False, default="scheduler")
    attempt_number = Column(Integer, nullable=False)
    state = Column(String(30), nullable=False)
    retryable = Column(Boolean, nullable=False, default=False)
    failure_code = Column(String(100), nullable=True)
    failure_summary = Column(Text, nullable=True)
    claimed_at = Column(DateTime(timezone=True), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    raffle = relationship("Raffle", back_populates="scheduler_attempts")


class RaffleSchedulerState(Base):
    __tablename__ = "raffle_scheduler_state"

    worker_id = Column(String(255), primary_key=True)
    enabled = Column(Boolean, nullable=False, default=True)
    heartbeat_at = Column(DateTime(timezone=True), nullable=False)
    last_poll_at = Column(DateTime(timezone=True), nullable=True)
    last_success_at = Column(DateTime(timezone=True), nullable=True)
    last_failure_at = Column(DateTime(timezone=True), nullable=True)
    last_failure_code = Column(String(100), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class InternalNotification(Base):
    __tablename__ = "internal_notifications"
    __table_args__ = (UniqueConstraint("recipient_user_id", "deduplication_key", name="uq_notification_recipient_dedupe"),)

    id = Column(Integer, primary_key=True)
    recipient_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    guild_name = Column(String(200), nullable=True, index=True)
    raffle_id = Column(Integer, ForeignKey("raffles.id"), nullable=True, index=True)
    notification_type = Column(String(80), nullable=False, index=True)
    title_key = Column(String(255), nullable=False)
    message_key = Column(String(255), nullable=False)
    interpolation = Column(JSONBType, nullable=False, default=dict)
    deep_link = Column(String(500), nullable=True)
    deduplication_key = Column(String(255), nullable=False)
    is_read = Column(Boolean, nullable=False, default=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    read_at = Column(DateTime(timezone=True), nullable=True)

    recipient = relationship("User")
    raffle = relationship("Raffle")
