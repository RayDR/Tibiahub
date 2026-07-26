"""Database-backed provider registry."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.knowledge.models import KnowledgeProvider
from app.knowledge.providers import INITIAL_PROVIDERS, ProviderDefinition


class ProviderRegistry:
    @staticmethod
    def register(db: Session, definition: ProviderDefinition) -> KnowledgeProvider:
        provider = db.get(KnowledgeProvider, definition.provider_id)
        if provider is None:
            provider = KnowledgeProvider(provider_id=definition.provider_id, enabled=definition.enabled)
            db.add(provider)
        provider.provider_name = definition.provider_name
        provider.priority = definition.priority
        provider.version = definition.version
        provider.rate_limit = dict(definition.rate_limit)
        provider.supports_entities = list(definition.supports_entities)
        provider.supports_media = definition.supports_media
        provider.supports_search = definition.supports_search
        return provider

    @classmethod
    def register_initial(cls, db: Session) -> list[KnowledgeProvider]:
        return [cls.register(db, definition) for definition in INITIAL_PROVIDERS]

    @staticmethod
    def get(db: Session, provider_id: str) -> KnowledgeProvider | None:
        return db.get(KnowledgeProvider, provider_id)

    @staticmethod
    def enabled(db: Session) -> list[KnowledgeProvider]:
        return (
            db.query(KnowledgeProvider)
            .filter(KnowledgeProvider.enabled.is_(True))
            .order_by(KnowledgeProvider.priority.asc(), KnowledgeProvider.provider_id.asc())
            .all()
        )
