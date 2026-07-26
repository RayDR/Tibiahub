from pydantic import BaseModel, ConfigDict, EmailStr, Field
from typing import Literal, Optional
from datetime import datetime

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: Optional[EmailStr] = None
    model_config = ConfigDict(str_strip_whitespace=True)

class UserCreate(UserBase):
    password: str = Field(..., min_length=12, max_length=128)
    tibia_character_name: Optional[str] = Field(None, min_length=2, max_length=100)
    locale: Literal["en", "es"] = "en"

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(UserBase):
    id: int
    avatar_url: Optional[str] = None
    is_active: bool
    is_superuser: bool
    email_verified_at: Optional[datetime] = None
    guild_rank: Optional[str] = None
    join_date: Optional[datetime] = None
    created_at: datetime
    vocation: Optional[str] = None
    level: Optional[int] = None
    tibia_character_name: Optional[str] = None
    guild_name: Optional[str] = None
    world_name: Optional[str] = None
    residence: Optional[str] = None
    achievement_points: Optional[int] = None
    tibia_status: Optional[str] = None

    class Config:
        from_attributes = True
