from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class UserBase(BaseModel):
    username: str
    email: Optional[str] = None

class UserCreate(UserBase):
    password: str
    tibia_character_name: Optional[str] = None  # For linking character during registration

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(UserBase):
    id: int
    is_active: bool
    is_superuser: bool
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
