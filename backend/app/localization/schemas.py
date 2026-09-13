"""API schemas for localization review and operations."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LocalizationReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str | None = Field(default=None, min_length=1, max_length=50000)
    lock: bool | None = None


class LocalizationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    entity_uuid: UUID | None
    resource_type: str
    resource_key: str
    field_path: str
    language: str
    text: str
    source_language: str
    source_text_hash: str
    origin: str
    status: str
    provider: str | None
    provider_model: str | None
    locked: bool
    reviewed_by_id: int | None
    reviewed_at: datetime | None
    approved_by_id: int | None
    approved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class LocalizationPage(BaseModel):
    items: list[LocalizationResponse]
    total: int
    skip: int
    limit: int


class LocalizationJobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_uuid: UUID | None = None
    resource_type: str = Field(min_length=1, max_length=64)
    resource_key: str = Field(min_length=1, max_length=255)
    field_path: str = Field(min_length=1, max_length=255)
    source_text: str = Field(min_length=1, max_length=50000)
    source_language: str = Field(min_length=2, max_length=32)
    target_language: str = Field(min_length=2, max_length=32)
    protected_terms: list[str] = Field(default_factory=list, max_length=100)
    context: str | None = Field(default=None, max_length=512)


class LocalizationJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    entity_uuid: UUID | None
    resource_type: str
    resource_key: str
    field_path: str
    source_language: str
    target_language: str
    source_text_hash: str
    status: str
    attempt_count: int
    next_attempt_at: datetime | None
    safe_failure_category: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class LocalizationJobPage(BaseModel):
    items: list[LocalizationJobResponse]
    total: int
    skip: int
    limit: int
