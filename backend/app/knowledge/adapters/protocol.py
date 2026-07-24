"""Provider adapter contracts containing no SQLAlchemy entities."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol
from uuid import UUID


JsonObject = dict[str, Any]
JsonValue = JsonObject | list[Any]


@dataclass(frozen=True, slots=True)
class KnowledgeFetchRequest:
    job_id: UUID
    attempt_id: UUID
    correlation_id: UUID
    provider_code: str
    job_type: str
    entity_type: str | None
    scope: JsonObject
    payload: JsonObject
    cursor: JsonObject | None = None


@dataclass(frozen=True, slots=True)
class KnowledgeDocumentDTO:
    provider_code: str
    provider_document_id: str
    raw_json: JsonValue
    version: str | None = None
    etag: str | None = None
    language: str | None = None
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class KnowledgeChildJobRequest:
    job_type: str
    entity_type: str | None
    scope: JsonObject = field(default_factory=dict)
    payload: JsonObject = field(default_factory=dict)
    priority: int = 100
    allow_completed_recreate: bool = False


@dataclass(frozen=True, slots=True)
class KnowledgeFetchResult:
    documents: tuple[KnowledgeDocumentDTO, ...]
    cursor: JsonObject | None = None
    partial: bool = False
    provider_metadata: JsonObject = field(default_factory=dict)
    child_jobs: tuple[KnowledgeChildJobRequest, ...] = ()


@dataclass(frozen=True, slots=True)
class KnowledgeValidationResult:
    valid: bool
    classification: Literal["valid", "partial", "invalid", "empty", "provider_error", "oversized"] = "valid"
    warnings: tuple[str, ...] = ()
    safe_errors: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CanonicalEntityCandidate:
    entity_type: str
    canonical_name: str
    language_neutral_id: str
    aliases: tuple[str, ...] = ()
    status: str = "active"
    source_priority: int = 100
    visibility: str = "public"
    search_weight: float = 1.0


@dataclass(frozen=True, slots=True)
class KnowledgeNormalizationContext:
    job_id: UUID
    attempt_id: UUID
    correlation_id: UUID
    provider_code: str
    entity_type: str | None


@dataclass(frozen=True, slots=True)
class KnowledgeNormalizationResult:
    action: Literal["noop", "upsert"] = "noop"
    candidate: CanonicalEntityCandidate | None = None
    warnings: tuple[str, ...] = ()
    provider_code: str | None = None
    external_id: str | None = None
    canonical_data: JsonObject | None = None


@dataclass(frozen=True, slots=True)
class KnowledgeNormalizationMetrics:
    documents_received: int = 0
    entities_created: int = 0
    entities_updated: int = 0
    entities_unchanged: int = 0
    aliases_created: int = 0
    warnings: int = 0
    child_jobs_enqueued: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "documents_received": self.documents_received,
            "entities_created": self.entities_created,
            "entities_updated": self.entities_updated,
            "entities_unchanged": self.entities_unchanged,
            "aliases_created": self.aliases_created,
            "warnings": self.warnings,
            "child_jobs_enqueued": self.child_jobs_enqueued,
        }


class KnowledgeProviderAdapter(Protocol):
    provider_code: str
    job_types: tuple[str, ...]

    def supports(self, job_type: str, entity_type: str | None) -> bool: ...

    def validate_enqueue(self, job_type: str, scope: JsonObject, payload: JsonObject) -> None: ...

    def fetch(self, request: KnowledgeFetchRequest) -> KnowledgeFetchResult: ...

    def validate(self, result: KnowledgeFetchResult) -> KnowledgeValidationResult: ...

    def normalize(
        self,
        document: KnowledgeDocumentDTO,
        context: KnowledgeNormalizationContext,
    ) -> KnowledgeNormalizationResult: ...
