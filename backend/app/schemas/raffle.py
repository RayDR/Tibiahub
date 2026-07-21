from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class RafflePrizeCreate(BaseModel):
    name: str
    reward: str
    order_index: Optional[int] = None
    position: Optional[Literal["second", "first"]] = None
    amount: Optional[Decimal] = None
    currency: Optional[str] = None


class RaffleCreate(BaseModel):
    title: str
    description: Optional[str] = None
    guild_name: str = Field(..., min_length=1)
    access_mode: str = "guild_only"
    show_participants: bool = True
    visibility: str = "public"
    registration_enabled: bool = True
    run_mode: str = "manual"
    scheduled_run_at: Optional[datetime] = None
    archive_after_days: int = 7
    prizes: List[RafflePrizeCreate] = []
    purpose: Literal["test", "real", "legacy"] = "legacy"
    timezone_name: str = "America/Chicago"
    eligibility_days: int = Field(5, ge=1, le=30)
    eligibility_cutoff_at: Optional[datetime] = None

    @field_validator("scheduled_run_at", "eligibility_cutoff_at")
    @classmethod
    def require_aware_timestamp(cls, value: Optional[datetime]) -> Optional[datetime]:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("Timestamp must include a UTC offset")
        return value


class RaffleUpdate(BaseModel):
    title: Optional[str] = None
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

    @field_validator("scheduled_run_at")
    @classmethod
    def require_aware_timestamp(cls, value: Optional[datetime]) -> Optional[datetime]:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("Timestamp must include a UTC offset")
        return value


class RaffleParticipantResponse(BaseModel):
    id: int
    user_id: int
    username: str
    character_name: str
    guild_rank: Optional[str] = None
    weight: float
    weight_multiplier: float = 1.0
    is_eligible: bool
    created_at: datetime

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
    user_id: int
    username: str
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
    participants: List[RaffleParticipantResponse] = []
    prizes: List[RafflePrizeResponse] = []
    current_winners: List[RaffleWinnerResponse] = []
    history: List[RaffleWinnerResponse] = []
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
    weight_multiplier: float = Field(..., ge=1.0, le=5.0)


class RaffleDrawRequest(BaseModel):
    dry_run: bool = False


class EligibilityEntryResponse(BaseModel):
    user_id: int
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
    results: List[AutomaticResultResponse] = []


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
    participants: List[PublicRaffleParticipantResponse] = []
    prizes: List[RafflePrizeResponse] = []
    winners: List[PublicRaffleWinnerResponse] = []
