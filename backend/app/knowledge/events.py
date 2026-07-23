"""Internal transactional Knowledge Platform domain events."""

from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.knowledge.models import KnowledgeDomainEvent


class KnowledgeEventType(StrEnum):
    ENTITY_CREATED = "EntityCreated"
    ENTITY_UPDATED = "EntityUpdated"
    PROVIDER_IMPORTED = "ProviderImported"
    PROVIDER_FAILED = "ProviderFailed"
    KNOWLEDGE_MERGED = "KnowledgeMerged"


def emit_event(
    db: Session,
    event_type: KnowledgeEventType,
    *,
    entity_uuid: UUID | None = None,
    provider_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> KnowledgeDomainEvent:
    event = KnowledgeDomainEvent(
        event_type=event_type.value,
        entity_uuid=entity_uuid,
        provider_id=provider_id,
        payload=dict(payload or {}),
    )
    db.add(event)
    return event
