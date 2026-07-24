"""Public and administrative Knowledge Graph API contracts."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class KnowledgeRelationshipResponse(BaseModel):
    id: UUID
    source_entity_id: UUID
    source_name: str
    source_type: str
    relationship_type: str
    display_translation_key: str
    target_entity_id: UUID | None
    target_name: str
    target_type: str
    target_slug: str | None
    resolution_state: str
    confidence: str
    contributing_providers: list[str]
    manual_verified: bool
    freshness: datetime
    source_scope: str
    provenance_count: int


class KnowledgeRelationshipPage(BaseModel):
    items: list[KnowledgeRelationshipResponse]
    total: int
    skip: int
    limit: int


class KnowledgeGraphReviewItem(BaseModel):
    id: UUID
    source_entity_id: UUID
    source_name: str
    source_type: str
    source_scope: str
    relationship_type: str
    target_type: str
    target_name: str | None
    unresolved_name: str | None
    resolution_state: str
    confidence: str
    provider_id: str | None
    document_id: UUID | None
    candidates: list[dict[str, str]]
    created_at: datetime


class KnowledgeGraphReviewPage(BaseModel):
    items: list[KnowledgeGraphReviewItem]
    total: int
    skip: int
    limit: int


class KnowledgeRelationshipAction(BaseModel):
    reason: str = Field(min_length=3, max_length=500)
    target_entity_id: UUID | None = None


class KnowledgeProvenanceResponse(BaseModel):
    relationship_id: UUID
    provider_id: str | None
    document_id: UUID | None
    job_id: UUID | None
    confidence: str
    manual_override: bool
    verified_at: datetime | None
    valid_from: datetime
    valid_until: datetime | None
    is_current: bool
    superseded_by_id: UUID | None
    safe_context: dict
