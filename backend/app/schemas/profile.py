from pydantic import BaseModel, Field, ConfigDict, EmailStr, field_validator
from typing import List, Optional
from datetime import datetime
from app.core.password_policy import validate_password

class ProfileResponse(BaseModel):
    username: str
    display_name: Optional[str] = None
    title: Optional[str] = None
    email: Optional[str] = None
    email_verified_at: Optional[datetime] = None
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
    characters: List[str] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)

class ProfileUpdate(BaseModel):
    display_name: Optional[str] = Field(None, max_length=100, description="Public display name")
    title: Optional[str] = Field(None, max_length=100, description="Custom title or bio line")
    email: Optional[EmailStr] = Field(None, description="New email address")
    avatar_url: Optional[str] = Field(None, description="Avatar image URL")
    current_password: Optional[str] = Field(None, min_length=6, description="Current password")
    new_password: Optional[str] = Field(None, description="New password")
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    @field_validator("new_password")
    @classmethod
    def password_policy(cls, value: Optional[str]) -> Optional[str]:
        return validate_password(value) if value is not None else None
