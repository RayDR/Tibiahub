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
    prizes: List[RafflePrizeCreate] = []


class RaffleParticipantResponse(BaseModel):
    id: int
    user_id: int
    username: str
    character_name: str
    guild_rank: Optional[str] = None
    weight: float
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
    id: int
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
    created_at: datetime


class RaffleResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    guild_name: str
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


class RaffleRerunRequest(BaseModel):
    reason: str = Field(..., min_length=3)
