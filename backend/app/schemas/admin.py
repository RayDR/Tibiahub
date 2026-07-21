"""
Schemas for admin endpoints
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class TibiaAPIStatus(BaseModel):
    """Status of Tibia Data API"""
    status: str = Field(..., description="online, offline, or degraded")
    latency_ms: Optional[float] = Field(None, description="API response time in milliseconds")
    cached: bool = Field(..., description="Whether this is a cached result")
    last_check: str = Field(..., description="ISO timestamp of last check")
    message: str = Field(..., description="Status message")


class CharacterInfo(BaseModel):
    """Information about a linked Tibia character"""
    character_name: str
    level: Optional[int] = None
    vocation: Optional[str] = None
    last_seen: Optional[datetime] = None


class UserWithCharacters(BaseModel):
    """User information with linked characters"""
    id: int
    username: str
    email: Optional[str] = None
    guild_name: Optional[str] = None
    guild_rank: Optional[str] = None
    discord_id: Optional[str] = None
    discord_username: Optional[str] = None
    is_active: bool
    is_superuser: bool
    join_date: Optional[datetime] = None
    created_at: datetime
    characters: List[dict] = []
    
    class Config:
        from_attributes = True


class SystemSettings(BaseModel):
    """System configuration settings"""
    tibia_validation_enabled: bool = Field(
        ..., 
        description="Whether Tibia character validation is enabled"
    )
    tibia_validation_strict: bool = Field(
        ..., 
        description="If true, fail registration when API is down. If false, allow without validation"
    )
    discord_webhook_url: Optional[str] = Field(
        None,
        description="Discord webhook URL for posting announcements"
    )
    discord_auto_post: bool = Field(
        False,
        description="Automatically post new announcements to Discord"
    )
    guild_raffles_enabled: bool = Field(
        True,
        description="Enable guild raffle features"
    )
    guild_contests_enabled: bool = Field(
        True,
        description="Enable guild contest/event features"
    )
    cyclopedia_category_images: dict[str, str] = Field(
        default_factory=dict,
        description="Mapping: category_key -> image URL used by Cyclopedia category cards",
    )
    access_token_expire_minutes: int = Field(
        ..., 
        description="JWT token expiration time in minutes"
    )


class UpdateSystemSettings(BaseModel):
    """Settings that can be updated"""
    tibia_validation_enabled: Optional[bool] = Field(
        None, 
        description="Enable/disable Tibia character validation"
    )
    tibia_validation_strict: Optional[bool] = Field(
        None, 
        description="Enable/disable strict validation (fail if API is down)"
    )
    discord_webhook_url: Optional[str] = Field(
        None,
        description="Discord webhook URL for posting announcements"
    )
    discord_auto_post: Optional[bool] = Field(
        None,
        description="Automatically post new announcements to Discord"
    )
    guild_raffles_enabled: Optional[bool] = Field(
        None,
        description="Enable/disable guild raffle features"
    )
    guild_contests_enabled: Optional[bool] = Field(
        None,
        description="Enable/disable guild contest/event features"
    )
    cyclopedia_category_images: Optional[dict[str, str]] = Field(
        None,
        description="Optional full mapping to save for Cyclopedia category images",
    )


class UserUpdate(BaseModel):
    """Fields that can be updated for a user"""
    username: Optional[str] = None
    email: Optional[str] = None
    guild_rank: Optional[str] = None
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None
    password: Optional[str] = Field(None, min_length=6)


class InvalidUser(BaseModel):
    """User with invalid character"""
    user_id: int
    username: str
    character_name: str
    reason: str


class GuildSyncResult(BaseModel):
    """Result of guild synchronization"""
    success: bool
    guild_name: str
    total_members: int
    synced_users: int
    updated_characters: int
    new_characters: int
    invalid_users: List[dict]
    message: str
