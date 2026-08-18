"""Durable knowledge worker runtime."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.knowledge.workers.knowledge_worker import KnowledgeWorker as KnowledgeWorker

__all__ = ["KnowledgeWorker"]


def __getattr__(name: str) -> Any:
    """Load the worker class lazily without pre-importing the ``-m`` runtime."""
    if name == "KnowledgeWorker":
        from app.knowledge.workers.knowledge_worker import KnowledgeWorker

        return KnowledgeWorker
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
