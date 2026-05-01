from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import List, Optional
from datetime import datetime

class ProfileResponse(BaseModel):
    username: str
    email: Optional[str] = None
    tibia_character_name: str
    guild_rank: Optional[str] = None
    guild_name: Optional[str] = None
    world_name: Optional[str] = None
    residence: Optional[str] = None
    achievement_points: Optional[int] = None
    last_login_at: Optional[datetime] = None
    tibia_status: Optional[str] = None
    tibia_last_error: Optional[str] = None
    vocation: Optional[str] = None
    level: Optional[int] = None
    is_active: bool
    join_date: Optional[datetime] = None
    created_at: datetime
    characters: List[str] = []  # list of character names linked to the user
    model_config = ConfigDict(from_attributes=True)

class ProfileUpdate(BaseModel):
    email: Optional[EmailStr] = Field(None, description="New email address")
    password: Optional[str] = Field(None, min_length=6, description="New password")
    model_config = ConfigDict(from_attributes=True)

