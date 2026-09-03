from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from typing import Literal, Optional
from datetime import datetime
from uuid import UUID

class HuntBase(BaseModel):
    name: str
    location: str
    level_min: int
    level_max: int
    vocation: Optional[str] = None
    exp_per_hour: Optional[int] = None
    profit_per_hour: Optional[int] = None
    creatures: str
    strategy: Optional[str] = None
    notes: Optional[str] = None

class HuntCreate(HuntBase):
    pass

class HuntUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    level_min: Optional[int] = None
    level_max: Optional[int] = None
    vocation: Optional[str] = None
    exp_per_hour: Optional[int] = None
    profit_per_hour: Optional[int] = None
    creatures: Optional[str] = None
    strategy: Optional[str] = None
    notes: Optional[str] = None

class Hunt(HuntBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


VocationCode = Literal["EK", "ED", "RP", "MS"]
HuntStatus = Literal["scheduled", "in_progress", "finished", "cancelled"]
AttendanceStatus = Literal["registered", "attended", "absent", "left"]


class GuildHuntCreate(BaseModel):
    guild_name: str | None = Field(default=None, max_length=200)
    scheduled_at: datetime
    timezone_name: str = Field(default="UTC", min_length=1, max_length=64)
    server_name: str = Field(min_length=1, max_length=100)
    location: str = Field(min_length=2, max_length=200)
    target: str = Field(min_length=2, max_length=200)
    hunting_zone_id: UUID | None = None
    recommended_level: int = Field(ge=1, le=9999)
    recommended_vocations: list[VocationCode] = Field(default_factory=list, max_length=4)
    maximum_participants: int = Field(ge=1, le=100)
    required_ek: int = Field(default=0, ge=0, le=100)
    required_ed: int = Field(default=0, ge=0, le=100)
    required_rp: int = Field(default=0, ge=0, le=100)
    required_ms: int = Field(default=0, ge=0, le=100)
    description: str | None = Field(default=None, max_length=4000)
    discord_channel: str | None = Field(default=None, max_length=200)
    voice_channel: str | None = Field(default=None, max_length=200)

    @field_validator("recommended_vocations")
    @classmethod
    def unique_vocations(cls, value: list[VocationCode]) -> list[VocationCode]:
        return list(dict.fromkeys(value))

    @model_validator(mode="after")
    def capacity_covers_required_roles(self):
        required = self.required_ek + self.required_ed + self.required_rp + self.required_ms
        if required > self.maximum_participants:
            raise ValueError("Required vocation slots cannot exceed maximum participants")
        return self


class GuildHuntUpdate(BaseModel):
    scheduled_at: datetime | None = None
    timezone_name: str | None = Field(default=None, min_length=1, max_length=64)
    server_name: str | None = Field(default=None, min_length=1, max_length=100)
    location: str | None = Field(default=None, min_length=2, max_length=200)
    target: str | None = Field(default=None, min_length=2, max_length=200)
    hunting_zone_id: UUID | None = None
    recommended_level: int | None = Field(default=None, ge=1, le=9999)
    recommended_vocations: list[VocationCode] | None = Field(default=None, max_length=4)
    maximum_participants: int | None = Field(default=None, ge=1, le=100)
    required_ek: int | None = Field(default=None, ge=0, le=100)
    required_ed: int | None = Field(default=None, ge=0, le=100)
    required_rp: int | None = Field(default=None, ge=0, le=100)
    required_ms: int | None = Field(default=None, ge=0, le=100)
    description: str | None = Field(default=None, max_length=4000)
    discord_channel: str | None = Field(default=None, max_length=200)
    voice_channel: str | None = Field(default=None, max_length=200)


class GuildHuntCancel(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)


class GuildHuntAttendanceUpdate(BaseModel):
    attendance_status: Literal["attended", "absent"]


class GuildHuntParticipantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    character_name: str
    vocation: str | None
    attendance_status: AttendanceStatus
    joined_at: datetime
    left_at: datetime | None


class GuildHuntZoneCreatureSummary(BaseModel):
    id: int | None = None
    canonical_id: UUID | None = None
    name: str
    slug: str | None = None
    is_boss: bool | None = None
    image_url: str | None = None


class GuildHuntZoneQuestSummary(BaseModel):
    id: int | None = None
    canonical_id: UUID | None = None
    name: str
    slug: str | None = None


class GuildHuntZoneSummary(BaseModel):
    canonical_id: UUID
    domain_id: int | None = None
    name: str
    slug: str | None = None
    city: str | None = None
    region: str | None = None
    min_level: int | None = None
    max_level: int | None = None
    recommended_level: int | None = None
    recommended_vocations: list[str] | None = None
    difficulty: str | None = None
    creature_count: int = 0
    boss_count: int = 0
    creature_preview: list[GuildHuntZoneCreatureSummary] = Field(default_factory=list)
    access_required: bool | None = None
    access_quest_count: int = 0
    access_quests: list[GuildHuntZoneQuestSummary] = Field(default_factory=list)
    spatial_state: str = "knowledge_only"
    map_available: bool = False
    map_floor: int | None = None
    media_url: str | None = None
    is_current: bool = True


class GuildHuntResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    guild_name: str
    scheduled_at: datetime
    timezone_name: str
    server_name: str
    location: str
    target: str
    hunting_zone_id: UUID | None
    hunting_zone_summary: GuildHuntZoneSummary | None = None
    recommended_level: int
    recommended_vocations: list[VocationCode]
    maximum_participants: int
    required_ek: int
    required_ed: int
    required_rp: int
    required_ms: int
    description: str | None
    discord_channel: str | None
    voice_channel: str | None
    status: HuntStatus
    created_by_id: int
    cancellation_reason: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime
    participants: list[GuildHuntParticipantResponse]
    registered_count: int
    current_user_joined: bool
    capabilities: dict[str, bool]
