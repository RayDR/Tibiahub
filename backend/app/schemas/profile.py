from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import List, Optional
from datetime import datetime

class ProfileResponse(BaseModel):
    username: str
    email: Optional[str] = None
    tibia_character_name: str
    guild_rank: Optional[str] = None
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

