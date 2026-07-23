"""Persistence for full provider responses and provider import events."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.knowledge.events import KnowledgeEventType, emit_event
from app.knowledge.models import KnowledgeDocument, KnowledgeEntity, KnowledgeProvider
from app.knowledge.schemas import KnowledgeDocumentCreate


class UnknownProviderError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class DocumentPersistenceResult:
    document: KnowledgeDocument
    created: bool


class KnowledgeDocumentStore:
    @staticmethod
    def _checksum(payload: dict | list) -> str:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @classmethod
    def _content_identity(cls, provider_id: str, provider_document_id: str, checksum: str) -> str:
        value = f"{provider_id}\0{provider_document_id}\0{checksum}"
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @classmethod
    def persist_with_status(cls, db: Session, command: KnowledgeDocumentCreate) -> DocumentPersistenceResult:
        provider = db.get(KnowledgeProvider, command.provider_id)
        if provider is None:
            raise UnknownProviderError(f"Provider is not registered: {command.provider_id}")
        if command.entity_uuid is not None and db.get(KnowledgeEntity, command.entity_uuid) is None:
            raise ValueError("Canonical entity does not exist")

        raw_payload = deepcopy(command.raw_json)
        checksum = cls._checksum(raw_payload)
        identity = cls._content_identity(command.provider_id, command.provider_document_id, checksum)
        existing = db.query(KnowledgeDocument).filter(KnowledgeDocument.content_identity == identity).first()
        if existing is not None:
            emit_event(
                db,
                KnowledgeEventType.PROVIDER_IMPORTED,
                entity_uuid=existing.entity_uuid,
                provider_id=command.provider_id,
                payload={"provider_document_id": command.provider_document_id, "deduplicated": True},
            )
            return DocumentPersistenceResult(existing, False)
        document = KnowledgeDocument(
            provider_id=command.provider_id,
            provider_document_id=command.provider_document_id,
            entity_uuid=command.entity_uuid,
            raw_json=raw_payload,
            retrieved_at=command.retrieved_at or datetime.now(UTC),
            checksum=checksum,
            version=command.version,
            etag=command.etag,
            language=command.language,
            document_metadata=deepcopy(command.metadata),
            content_identity=identity,
        )
        try:
            with db.begin_nested():
                db.add(document)
                db.flush()
        except IntegrityError:
            existing = db.query(KnowledgeDocument).filter(KnowledgeDocument.content_identity == identity).one()
            emit_event(
                db,
                KnowledgeEventType.PROVIDER_IMPORTED,
                entity_uuid=existing.entity_uuid,
                provider_id=command.provider_id,
                payload={"provider_document_id": command.provider_document_id, "deduplicated": True},
            )
            return DocumentPersistenceResult(existing, False)
        emit_event(
            db,
            KnowledgeEventType.PROVIDER_IMPORTED,
            entity_uuid=command.entity_uuid,
            provider_id=command.provider_id,
            payload={"provider_document_id": command.provider_document_id, "deduplicated": False},
        )
        return DocumentPersistenceResult(document, True)

    @classmethod
    def persist(cls, db: Session, command: KnowledgeDocumentCreate) -> KnowledgeDocument:
        return cls.persist_with_status(db, command).document

    @staticmethod
    def record_failure(db: Session, provider_id: str, failure_code: str) -> None:
        provider = db.get(KnowledgeProvider, provider_id)
        if provider is None:
            raise UnknownProviderError(f"Provider is not registered: {provider_id}")
        provider.health = "unavailable"
        emit_event(
            db,
            KnowledgeEventType.PROVIDER_FAILED,
            provider_id=provider_id,
            payload={"failure_code": failure_code},
        )
