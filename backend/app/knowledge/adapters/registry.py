"""In-process adapter resolution; durable job ownership remains in PostgreSQL."""

from __future__ import annotations

from app.knowledge.adapters.protocol import KnowledgeProviderAdapter
from app.knowledge.adapters.reference import ReferenceKnowledgeAdapter


class AdapterNotFoundError(LookupError):
    pass


class KnowledgeAdapterRegistry:
    def __init__(self, adapters: tuple[KnowledgeProviderAdapter, ...] | None = None):
        configured = adapters if adapters is not None else (ReferenceKnowledgeAdapter(),)
        self._adapters = {adapter.provider_code: adapter for adapter in configured}

    def resolve(self, provider_code: str, job_type: str, entity_type: str | None) -> KnowledgeProviderAdapter:
        adapter = self._adapters.get(provider_code)
        if adapter is None or not adapter.supports(job_type, entity_type):
            raise AdapterNotFoundError("No registered adapter supports this knowledge job")
        return adapter

    def supported_job_types(self, provider_code: str, entity_types: list[str]) -> list[str]:
        adapter = self._adapters.get(provider_code)
        if adapter is None:
            return []
        candidates = ("reference_import", "full_sync", "incremental_sync", "detail_import", "renormalize")
        return sorted(
            job_type
            for job_type in candidates
            if any(adapter.supports(job_type, entity_type) for entity_type in entity_types)
        )
