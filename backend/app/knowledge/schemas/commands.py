"""Provider-neutral service inputs; these are not public API contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeEntityCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_type: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    canonical_name: str = Field(min_length=1, max_length=255)
    language_neutral_id: str = Field(min_length=1, max_length=255)
    aliases: list[str] = Field(default_factory=list)
    status: str = Field(default="active", min_length=1, max_length=32)
    source_priority: int = Field(default=100, ge=0)
    visibility: str = Field(default="public", pattern=r"^(public|internal|private)$")
    search_weight: float = Field(default=1.0, ge=0)
    allow_name_collision: bool = False
    slug_suffix: str | None = Field(default=None, pattern=r"^[a-z0-9-]{1,80}$")


class KnowledgeDocumentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_id: str = Field(min_length=1, max_length=64)
    provider_document_id: str = Field(min_length=1, max_length=512)
    entity_uuid: UUID | None = None
    raw_json: dict[str, Any] | list[Any]
    retrieved_at: datetime | None = None
    version: str | None = Field(default=None, max_length=128)
    etag: str | None = Field(default=None, max_length=512)
    language: str | None = Field(default=None, max_length=16)
    metadata: dict[str, Any] = Field(default_factory=dict)
