"""Canonical entity lifecycle services."""

from app.knowledge.services.entities import (
    DuplicateKnowledgeAliasError,
    DuplicateKnowledgeEntityError,
    KnowledgeEntityService,
    UnknownEntityTypeError,
)

__all__ = [
    "DuplicateKnowledgeAliasError",
    "DuplicateKnowledgeEntityError",
    "KnowledgeEntityService",
    "UnknownEntityTypeError",
]
