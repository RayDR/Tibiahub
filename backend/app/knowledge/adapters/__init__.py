"""Provider adapter protocols and deterministic reference implementation."""

from app.knowledge.adapters.protocol import (
    CanonicalEntityCandidate,
    KnowledgeChildJobRequest,
    KnowledgeDocumentDTO,
    KnowledgeFetchRequest,
    KnowledgeFetchResult,
    KnowledgeNormalizationContext,
    KnowledgeNormalizationMetrics,
    KnowledgeNormalizationResult,
    KnowledgeProviderAdapter,
    KnowledgeValidationResult,
)
from app.knowledge.adapters.reference import ReferenceKnowledgeAdapter
from app.knowledge.adapters.registry import AdapterNotFoundError, KnowledgeAdapterRegistry

__all__ = [
    "AdapterNotFoundError",
    "CanonicalEntityCandidate",
    "KnowledgeAdapterRegistry",
    "KnowledgeChildJobRequest",
    "KnowledgeDocumentDTO",
    "KnowledgeFetchRequest",
    "KnowledgeFetchResult",
    "KnowledgeNormalizationContext",
    "KnowledgeNormalizationMetrics",
    "KnowledgeNormalizationResult",
    "KnowledgeProviderAdapter",
    "KnowledgeValidationResult",
    "ReferenceKnowledgeAdapter",
]
