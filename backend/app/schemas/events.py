"""
Schemas for Events and Raffles
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
from datetime import datetime


class EventParticipantBase(BaseModel):
    user_id: Optional[int] = None
    assigned_number: Optional[int] = None


class EventParticipant(EventParticipantBase):
    id: int
    event_id: int
    joined_at: datetime
    username: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


class EventBase(BaseModel):
    type: str = Field(..., description="raffle, contest, hunt_event, custom")
    title: str
    description: str
    rules: Optional[str] = None
    reward: Optional[str] = None
    start_date: datetime
    end_date: Optional[datetime] = None
    draw_date: Optional[datetime] = None
    total_slots: Optional[int] = None
    entry_cost: Optional[str] = "Free"
    is_public: bool = False
    registration_enabled: bool = True
    archive_after_days: int = 7
    participant_mode: str = "manual"  # 'manual' or 'guild_auto'
    active_days_limit: int = 10  # For guild_auto mode
    guild_name: Optional[str] = None  # For guild_auto mode
    guild_world: Optional[str] = None  # World restriction


class EventCreate(EventBase):
    pass


class EventUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    rules: Optional[str] = None
    reward: Optional[str] = None
    end_date: Optional[datetime] = None
    draw_date: Optional[datetime] = None
    status: Optional[str] = None
    is_public: Optional[bool] = None
    registration_enabled: Optional[bool] = None
    archive_after_days: Optional[int] = None
    participant_mode: Optional[str] = None
    active_days_limit: Optional[int] = None
    guild_name: Optional[str] = None
    guild_world: Optional[str] = None


class Event(EventBase):
    id: int
    uuid: Optional[str] = None
    public_code: Optional[str] = None
    status: str
    is_active: bool
    archived_at: Optional[datetime] = None
    creator_id: int
    creator_name: Optional[str] = None
    winner_id: Optional[int] = None
    winner_name: Optional[str] = None
    winner_number: Optional[int] = None
    is_drawn: bool
    announcement_id: Optional[int] = None
    participant_count: int = 0
    participants: List[EventParticipant] = []
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class DrawWinnerResponse(BaseModel):
    success: bool
    winner_id: int
    winner_name: str
    winner_number: int
    total_participants: int


class PublicParticipantBase(BaseModel):
    character_name: str
    character_level: Optional[int] = None
    character_vocation: Optional[str] = None
    character_world: Optional[str] = None
    last_login: Optional[str] = None


class PublicParticipantCreate(PublicParticipantBase):
    pass


class PublicParticipant(PublicParticipantBase):
    id: int
    event_id: int
    assigned_number: Optional[int] = None
    is_auto_loaded: bool
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
