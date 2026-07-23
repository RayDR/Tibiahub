"""Immutable raw document persistence."""

from app.knowledge.storage.documents import KnowledgeDocumentStore, UnknownProviderError

__all__ = ["KnowledgeDocumentStore", "UnknownProviderError"]
