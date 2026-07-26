"""Maintain provider-neutral search metadata for a canonical entity."""

from __future__ import annotations

from sqlalchemy.orm import object_session

from app.knowledge.indexing import normalize_name, search_tokens
from app.knowledge.models import KnowledgeEntity, KnowledgeSearchMetadata


def refresh_search_metadata(entity: KnowledgeEntity) -> KnowledgeSearchMetadata:
    alias_values = [alias.alias for alias in entity.aliases]
    metadata = entity.search_metadata
    if metadata is None:
        metadata = KnowledgeSearchMetadata(entity=entity)
        session = object_session(entity)
        if session is not None:
            session.add(metadata)
    metadata.normalized_name = normalize_name(entity.canonical_name)
    metadata.aliases = sorted(set(alias_values), key=str.casefold)
    metadata.search_tokens = search_tokens(entity.canonical_name, *alias_values)
    return metadata
