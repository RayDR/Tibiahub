from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import List, Optional
from datetime import datetime

class ProfileResponse(BaseModel):
    username: str
    display_name: Optional[str] = None
    title: Optional[str] = None
    email: Optional[str] = None
    avatar_url: Optional[str] = None
    tibia_character_name: Optional[str] = None
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
    display_name: Optional[str] = Field(None, max_length=100, description="Public display name")
    title: Optional[str] = Field(None, max_length=100, description="Custom title or bio line")
    email: Optional[EmailStr] = Field(None, description="New email address")
    avatar_url: Optional[str] = Field(None, description="Avatar image URL")
    current_password: Optional[str] = Field(None, min_length=6, description="Current password")
    new_password: Optional[str] = Field(None, min_length=6, description="New password")
    password: Optional[str] = Field(None, min_length=6, description="Legacy password field")
    model_config = ConfigDict(from_attributes=True)
