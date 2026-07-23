"""Persistent provider and entity-type registries."""

from app.knowledge.registry.entity_types import INITIAL_ENTITY_TYPES, EntityTypeRegistry
from app.knowledge.registry.providers import ProviderRegistry

__all__ = ["EntityTypeRegistry", "INITIAL_ENTITY_TYPES", "ProviderRegistry"]
