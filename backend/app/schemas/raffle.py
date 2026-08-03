from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class RafflePrizeCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    reward: str = Field(..., min_length=1, max_length=500)
    order_index: Optional[int] = None
    position: Optional[Literal["second", "first"]] = None
    amount: Optional[Decimal] = Field(None, gt=0)
    currency: Optional[str] = Field(None, min_length=1, max_length=20)


class RaffleCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    description: Optional[str] = None
    guild_name: str = Field(..., min_length=1)
    scope_type: Literal["guild", "server", "global"] = "guild"
    world_name: Optional[str] = None
    access_mode: Literal["guild_only", "world_only", "public"] = "guild_only"
    show_participants: bool = True
    visibility: Literal["public", "private"] = "public"
    registration_enabled: bool = True
    run_mode: Literal["manual", "automatic"] = "manual"
    scheduled_run_at: Optional[datetime] = None
    archive_after_days: int = 7
    prizes: List[RafflePrizeCreate] = Field(default_factory=list, max_length=50)
    purpose: Literal["test", "real", "legacy"] = "legacy"
    timezone_name: str = "America/Chicago"
    eligibility_days: int = Field(5, ge=1, le=30)
    eligibility_cutoff_at: Optional[datetime] = None
    unique_account_participation: bool = True
    weighting_mode: Literal["equal", "weighted"] = "equal"

    @field_validator("scheduled_run_at", "eligibility_cutoff_at")
    @classmethod
    def require_aware_timestamp(cls, value: Optional[datetime]) -> Optional[datetime]:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("Timestamp must include a UTC offset")
        return value


class RaffleUpdate(BaseModel):
    expected_version: Optional[int] = Field(None, ge=1)
    title: Optional[str] = Field(None, min_length=3, max_length=200)
    description: Optional[str] = None
    guild_name: Optional[str] = None
    access_mode: Optional[str] = None
    show_participants: Optional[bool] = None
    visibility: Optional[str] = None
    registration_enabled: Optional[bool] = None
    run_mode: Optional[str] = None
    scheduled_run_at: Optional[datetime] = None
    archive_after_days: Optional[int] = None
    status: Optional[str] = None
    timezone_name: Optional[str] = None
    eligibility_days: Optional[int] = Field(None, ge=1, le=30)
    publication_status: Optional[Literal["private", "published"]] = None
    unique_account_participation: Optional[bool] = None
    weighting_mode: Optional[Literal["equal", "weighted"]] = None
    prizes: Optional[List[RafflePrizeCreate]] = Field(None, max_length=50)

    @field_validator("scheduled_run_at")
    @classmethod
    def require_aware_timestamp(cls, value: Optional[datetime]) -> Optional[datetime]:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("Timestamp must include a UTC offset")
        return value


class RaffleParticipantResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    guild_roster_character_id: Optional[int] = None
    username: Optional[str] = None
    character_name: str
    normalized_character_name: str
    account_identity_known: bool = False
    guild_rank: Optional[str] = None
    weight: Decimal
    weight_multiplier: Decimal = Decimal("1")
    effective_probability: Optional[Decimal] = None
    is_eligible: bool
    created_at: datetime
    source: Optional[str] = None
    eligibility_override: Optional[bool] = None
    eligibility_override_reason: Optional[str] = None

    class Config:
        from_attributes = True


class RafflePrizeResponse(BaseModel):
    id: int
    name: str
    reward: str
    order_index: int
    position: Optional[str] = None
    amount: Optional[Decimal] = None
    currency: Optional[str] = None

    class Config:
        from_attributes = True


class RaffleWinnerResponse(BaseModel):
    id: Optional[int] = None
    prize_id: int
    prize_name: str
    reward: str
    participant_id: int
    user_id: Optional[int] = None
    username: Optional[str] = None
    character_name: str
    run_number: int
    is_rerun: bool
    rerun_reason: Optional[str] = None
    created_at: Optional[datetime] = None


class RaffleResponse(BaseModel):
    id: int
    public_code: str
    title: str
    description: Optional[str] = None
    guild_name: str
    scope_type: str = "guild"
    world_name: Optional[str] = None
    access_mode: str
    show_participants: bool
    participant_count: int
    visibility: str
    registration_enabled: bool
    run_mode: str
    scheduled_run_at: Optional[datetime] = None
    archive_after_days: int
    archived_at: Optional[datetime] = None
    status: str
    current_run_number: int
    rerun_count: int
    created_at: datetime
    updated_at: datetime
    participants: List[RaffleParticipantResponse] = Field(default_factory=list)
    prizes: List[RafflePrizeResponse] = Field(default_factory=list)
    current_winners: List[RaffleWinnerResponse] = Field(default_factory=list)
    history: List[RaffleWinnerResponse] = Field(default_factory=list)
    purpose: str = "legacy"
    timezone_name: str = "America/Chicago"
    eligibility_days: int = 5
    eligibility_cutoff_at: Optional[datetime] = None
    publication_status: str = "private"
    execution_state: str = "pending"
    executed_at: Optional[datetime] = None
    scheduler_job_id: Optional[str] = None
    claimed_at: Optional[datetime] = None
    lease_expires_at: Optional[datetime] = None
    last_error_code: Optional[str] = None
    last_error_summary: Optional[str] = None
    retry_count: int = 0
    next_retry_at: Optional[datetime] = None
    unique_account_participation: bool = True
    weighting_mode: Literal["equal", "weighted"] = "equal"
    version: int = 1


class RaffleExecutionResponse(BaseModel):
    raffle_id: int
    run_number: int
    winner_count: int
    winners: List[RaffleWinnerResponse]
    simulation: bool = False
    status: Optional[str] = None
    access_mode: Optional[str] = None
    eligible_count: Optional[int] = None
    ineligible_count: Optional[int] = None
    participant_count: Optional[int] = None
    prizes: Optional[List[dict]] = None
    eligible_participants: Optional[List[dict]] = None
    ineligible_participants: Optional[List[dict]] = None
    warnings: Optional[List[str]] = None


class RaffleRerunRequest(BaseModel):
    reason: str = Field(..., min_length=3)


class RaffleWeightUpdateRequest(BaseModel):
    weight: Decimal = Field(..., gt=0, le=1_000_000)


class RaffleParticipationSettingsRequest(BaseModel):
    unique_account_participation: Optional[bool] = None
    weighting_mode: Optional[Literal["equal", "weighted"]] = None


class RaffleParticipantsMutationRequest(BaseModel):
    roster_character_ids: List[int] = Field(default_factory=list, max_length=500)
    add_all_eligible: bool = False
    activity_days: Literal[7, 15, 30] = 30
    replace_existing: bool = False


class RaffleParticipantsRemoveRequest(BaseModel):
    participant_ids: List[int] = Field(..., min_length=1, max_length=500)
    reason: Optional[str] = Field(None, max_length=500)


class RaffleParticipantMutationResponse(BaseModel):
    raffle_id: int
    added: int = 0
    restored: int = 0
    removed: int = 0
    unchanged: int = 0


class RaffleCandidateResponse(BaseModel):
    roster_character_id: int
    character_name: str
    rank: Optional[str] = None
    level: Optional[int] = None
    vocation: Optional[str] = None
    last_activity_at: datetime
    linked_user_id: Optional[int] = None
    linked_username: Optional[str] = None
    account_identity_key: Optional[str] = None
    account_identity_known: bool
    already_participating: bool
    selectable: bool
    reason: Optional[str] = None


class RaffleDrawRequest(BaseModel):
    dry_run: bool = False


class EligibilityEntryResponse(BaseModel):
    character_name: Optional[str] = None
    guild_name: Optional[str] = None
    guild_rank: Optional[str] = None
    last_activity_at: Optional[datetime] = None
    is_eligible: bool
    exclusion_code: Optional[str] = None
    exclusion_summary: Optional[str] = None


class EligibilityPreviewResponse(BaseModel):
    raffle_id: int
    cutoff_at: datetime
    timezone_name: str
    eligibility_days: int
    candidate_count: int
    eligible_count: int
    excluded_count: int
    snapshot_hash: str
    entries: List[EligibilityEntryResponse]
    persisted: bool = False
    snapshot_id: Optional[int] = None


class AutomaticExecutionRequest(BaseModel):
    # The public management API is always a manual trigger. The future
    # scheduler will call the same service directly with trigger="scheduler".
    trigger: Literal["manual"] = "manual"


class AutomaticResultResponse(BaseModel):
    id: int
    prize_id: int
    prize_position: str
    prize_name: str
    amount: Decimal
    currency: str
    character_name: str
    selection_index: int
    candidate_count: int
    delivery_status: str
    delivery_deadline_at: datetime
    delivered_at: Optional[datetime] = None
    delivered_by_name: Optional[str] = None
    delivery_note: Optional[str] = None
    delivery_history: List[dict] = Field(default_factory=list)


class AutomaticRunResponse(BaseModel):
    id: int
    raffle_id: int
    run_number: int
    snapshot_id: int
    parent_run_id: Optional[int] = None
    trigger: str
    state: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    failure_code: Optional[str] = None
    failure_summary: Optional[str] = None
    algorithm_version: str
    entropy_commitment: Optional[str] = None
    results: List[AutomaticResultResponse] = Field(default_factory=list)


class AutomaticRerunRequest(BaseModel):
    positions: List[Literal["second", "first"]] = Field(..., min_length=1, max_length=2)
    reason: str = Field(..., min_length=3, max_length=1000)
    override_delivered: bool = False
    override_reason: Optional[str] = Field(None, max_length=1000)


class DeliveryUpdateRequest(BaseModel):
    status: Literal["pending", "delivered", "disputed", "cancelled"]
    note: Optional[str] = Field(None, max_length=2000)
    admin_override: bool = False


class DeliveryResponse(BaseModel):
    result_id: int
    status: str
    delivery_deadline_at: datetime
    delivered_at: Optional[datetime] = None
    delivered_by_id: Optional[int] = None
    note: Optional[str] = None


class TestEligibilityOverrideRequest(BaseModel):
    eligible: bool
    reason: str = Field(..., min_length=3, max_length=1000)


class TestRetryRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=1000)


class TestCleanupRequest(BaseModel):
    confirmation: Literal["ARCHIVE TEST RAFFLE"]
    reason: str = Field(..., min_length=3, max_length=1000)


class TestCleanupResponse(BaseModel):
    raffle_id: int
    archived: bool
    participant_associations_removed: int
    users_modified: int = 0
    guilds_modified: int = 0
    real_raffles_modified: int = 0


class ManagerGrantRequest(BaseModel):
    user_id: int


class ManagerGrantResponse(BaseModel):
    raffle_id: int
    user_id: int
    granted_by_id: int
    created_at: datetime
    revoked_at: Optional[datetime] = None


class PublicationResponse(BaseModel):
    raffle_id: int
    publication_status: str
    published_at: Optional[datetime] = None
    published_by_id: Optional[int] = None


class PublicRaffleParticipantResponse(BaseModel):
    character_name: str
    guild_rank: Optional[str] = None


class PublicRaffleWinnerResponse(BaseModel):
    prize_position: str
    prize_name: str
    amount: Decimal
    currency: str
    character_name: str
    delivery_status: str
    delivery_deadline_at: datetime


class PublicRaffleResponse(BaseModel):
    public_code: str
    title: str
    description: Optional[str] = None
    guild_name: str
    access_mode: str
    purpose: str
    timezone_name: str
    scheduled_run_at: Optional[datetime] = None
    status: str
    publication_status: str
    show_participants: bool
    participant_count: int
    participants: List[PublicRaffleParticipantResponse] = Field(default_factory=list)
    prizes: List[RafflePrizeResponse] = Field(default_factory=list)
    winners: List[PublicRaffleWinnerResponse] = Field(default_factory=list)
