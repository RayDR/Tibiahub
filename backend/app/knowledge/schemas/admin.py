"""Credential-safe global-admin Knowledge Operations API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


JobState = Literal[
    "pending",
    "claimed",
    "running",
    "retrying",
    "succeeded",
    "partially_succeeded",
    "failed",
    "cancelled",
]
JobTrigger = Literal["bootstrap", "scheduled", "manual", "retry", "renormalize", "system"]


def _reject_sensitive_keys(value: Any) -> Any:
    forbidden = {"url", "endpoint", "password", "secret", "token", "credential", "authorization"}
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).strip().lower() in forbidden:
                raise ValueError("Provider URLs and credential-like fields are not accepted")
            _reject_sensitive_keys(item)
    elif isinstance(value, list):
        for item in value:
            _reject_sensitive_keys(item)
    return value


class KnowledgeJobCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")
    job_type: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    entity_type: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_]{0,63}$")
    scope: dict[str, Any] = Field(default_factory=dict)
    payload: dict[str, Any] = Field(default_factory=dict)
    priority: int = Field(default=100, ge=0, le=1000)
    scheduled_at: datetime | None = None
    max_attempts: int = Field(default=5, ge=1, le=20)
    allow_completed_recreate: bool = False

    @field_validator("scope", "payload")
    @classmethod
    def no_arbitrary_urls_or_credentials(cls, value: dict[str, Any]) -> dict[str, Any]:
        return _reject_sensitive_keys(value)


class KnowledgeJobAttemptResponse(BaseModel):
    id: UUID
    attempt_number: int
    worker_id: str
    started_at: datetime
    completed_at: datetime | None
    outcome: str
    retryable: bool
    error_code: str | None
    safe_error: str | None
    metrics: dict[str, Any]


class KnowledgeJobResponse(BaseModel):
    id: UUID
    provider_id: str
    job_type: str
    entity_type: str | None
    scope: dict[str, Any]
    priority: int
    state: JobState
    scheduled_at: datetime
    claimed_at: datetime | None
    lease_expires_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    worker_id: str | None
    attempt_count: int
    max_attempts: int
    parent_job_id: UUID | None
    correlation_id: UUID
    last_error_code: str | None
    safe_last_error: str | None
    trigger: JobTrigger
    created_at: datetime
    updated_at: datetime
    can_retry: bool
    can_cancel: bool


class KnowledgeJobDetailResponse(KnowledgeJobResponse):
    attempts: list[KnowledgeJobAttemptResponse]


class KnowledgeJobPage(BaseModel):
    items: list[KnowledgeJobResponse]
    total: int
    skip: int
    limit: int


class KnowledgeJobCreatedResponse(BaseModel):
    item: KnowledgeJobResponse
    created: bool


class KnowledgeWorkerResponse(BaseModel):
    worker_id: str
    worker_type: str
    node_id: str
    process_id: int
    started_at: datetime
    last_seen_at: datetime
    current_job_id: UUID | None
    state: str
    version: str
    safe_metadata: dict[str, Any]


class KnowledgeProviderResponse(BaseModel):
    provider_id: str
    provider_name: str
    priority: int
    enabled: bool
    version: str | None
    health: str
    last_attempted_at: datetime | None
    last_success_at: datetime | None
    last_failure_at: datetime | None
    consecutive_failures: int
    cooldown_until: datetime | None
    supports_entities: list[str]
    supports_media: bool
    supports_search: bool
    supported_job_types: list[str]
