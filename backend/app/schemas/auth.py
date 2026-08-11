from pydantic import BaseModel, EmailStr, Field, field_validator, ConfigDict
from typing import Literal, Optional
from datetime import datetime
from app.core.password_policy import validate_password

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: Optional[EmailStr] = None

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value):
        return value.strip() if isinstance(value, str) else value

class UserCreate(UserBase):
    password: str
    tibia_character_name: Optional[str] = Field(None, min_length=2, max_length=100)
    locale: Literal["en", "es"] = "en"

    @field_validator("password")
    @classmethod
    def password_policy(cls, value: str) -> str:
        return validate_password(value)

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(UserBase):
    # Legacy accounts may contain internally scoped addresses (for example,
    # ``admin@tibiahub.local``). Keep strict EmailStr validation on UserCreate,
    # but do not make authenticated reads fail while those records are remediated.
    email: Optional[str] = None
    id: int
    display_name: Optional[str] = None
    title: Optional[str] = None
    avatar_url: Optional[str] = None
    primary_character_id: Optional[int] = None
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

    model_config = ConfigDict(from_attributes=True)
