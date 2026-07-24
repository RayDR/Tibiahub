"""In-process adapter resolution; durable job ownership remains in PostgreSQL."""

from __future__ import annotations

from app.knowledge.adapters.protocol import KnowledgeProviderAdapter
from app.knowledge.adapters.reference import ReferenceKnowledgeAdapter
from app.knowledge.adapters.tibiawiki_creatures import TibiaWikiCreatureAdapter
from app.knowledge.adapters.tibiawiki_items import TibiaWikiItemAdapter
from app.knowledge.adapters.tibiawiki_quests import TibiaWikiQuestAdapter
from app.knowledge.adapters.tibiawiki_npcs_locations import TibiaWikiLocationAdapter, TibiaWikiNpcAdapter


class AdapterNotFoundError(LookupError):
    pass


class KnowledgeAdapterRegistry:
    def __init__(self, adapters: tuple[KnowledgeProviderAdapter, ...] | None = None):
        configured = adapters if adapters is not None else (
            ReferenceKnowledgeAdapter(),
            TibiaWikiCreatureAdapter(),
            TibiaWikiItemAdapter(),
            TibiaWikiQuestAdapter(),
            TibiaWikiNpcAdapter(),
            TibiaWikiLocationAdapter(),
        )
        self._adapters: dict[str, list[KnowledgeProviderAdapter]] = {}
        for adapter in configured:
            self._adapters.setdefault(adapter.provider_code, []).append(adapter)

    def resolve(self, provider_code: str, job_type: str, entity_type: str | None) -> KnowledgeProviderAdapter:
        for adapter in self._adapters.get(provider_code, []):
            if adapter.supports(job_type, entity_type):
                return adapter
        raise AdapterNotFoundError("No registered adapter supports this knowledge job")

    def supported_job_types(self, provider_code: str, entity_types: list[str]) -> list[str]:
        adapters = self._adapters.get(provider_code, [])
        if not adapters:
            return []
        return sorted(
            job_type
            for adapter in adapters
            for job_type in adapter.job_types
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
