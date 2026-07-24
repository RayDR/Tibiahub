"""In-process adapter resolution; durable job ownership remains in PostgreSQL."""

from __future__ import annotations

from app.knowledge.adapters.protocol import KnowledgeProviderAdapter
from app.knowledge.adapters.reference import ReferenceKnowledgeAdapter
from app.knowledge.adapters.tibiawiki_creatures import TibiaWikiCreatureAdapter


class AdapterNotFoundError(LookupError):
    pass


class KnowledgeAdapterRegistry:
    def __init__(self, adapters: tuple[KnowledgeProviderAdapter, ...] | None = None):
        configured = adapters if adapters is not None else (ReferenceKnowledgeAdapter(), TibiaWikiCreatureAdapter())
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
        candidates = adapter.job_types
        return sorted(
            job_type
            for job_type in candidates
            if any(adapter.supports(job_type, entity_type) for entity_type in entity_types)
        )

    def validate_enqueue(
        self,
        provider_code: str,
        job_type: str,
        entity_type: str | None,
        scope: dict,
        payload: dict,
    ) -> None:
        adapter = self.resolve(provider_code, job_type, entity_type)
        adapter.validate_enqueue(job_type, scope, payload)
