from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class RafflePrizeCreate(BaseModel):
    name: str
    reward: str
    order_index: Optional[int] = None


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
