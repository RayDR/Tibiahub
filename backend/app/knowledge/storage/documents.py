"""Persistence for full provider responses and provider import events."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.knowledge.events import KnowledgeEventType, emit_event
from app.knowledge.models import KnowledgeDocument, KnowledgeEntity, KnowledgeProvider
from app.knowledge.schemas import KnowledgeDocumentCreate


class UnknownProviderError(ValueError):
    pass


class KnowledgeDocumentStore:
    @staticmethod
    def _checksum(payload: dict | list) -> str:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @classmethod
    def persist(cls, db: Session, command: KnowledgeDocumentCreate) -> KnowledgeDocument:
        provider = db.get(KnowledgeProvider, command.provider_id)
        if provider is None:
            raise UnknownProviderError(f"Provider is not registered: {command.provider_id}")
        if command.entity_uuid is not None and db.get(KnowledgeEntity, command.entity_uuid) is None:
            raise ValueError("Canonical entity does not exist")

        raw_payload = deepcopy(command.raw_json)
        document = KnowledgeDocument(
            provider_id=command.provider_id,
            provider_document_id=command.provider_document_id,
            entity_uuid=command.entity_uuid,
            raw_json=raw_payload,
            retrieved_at=command.retrieved_at or datetime.now(UTC),
            checksum=cls._checksum(raw_payload),
            version=command.version,
            etag=command.etag,
            language=command.language,
            document_metadata=deepcopy(command.metadata),
        )
        db.add(document)
        provider.health = "healthy"
        provider.last_sync_at = document.retrieved_at
        emit_event(
            db,
            KnowledgeEventType.PROVIDER_IMPORTED,
            entity_uuid=command.entity_uuid,
            provider_id=command.provider_id,
            payload={"provider_document_id": command.provider_document_id},
        )
        return document

    @staticmethod
    def record_failure(db: Session, provider_id: str, failure_code: str) -> None:
        provider = db.get(KnowledgeProvider, provider_id)
        if provider is None:
            raise UnknownProviderError(f"Provider is not registered: {provider_id}")
        provider.health = "failed"
        emit_event(
            db,
            KnowledgeEventType.PROVIDER_FAILED,
            provider_id=provider_id,
            payload={"failure_code": failure_code},
        )
