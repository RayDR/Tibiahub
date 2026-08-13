"""Persistence boundary for real, append-only provider observations."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.knowledge.adapters import KnowledgeNormalizationResult
from app.knowledge.models import KnowledgeDocument, KnowledgeProviderObservation


@dataclass(frozen=True, slots=True)
class AppliedObservation:
    created: bool
    observation_uuid: UUID | None


class KnowledgeObservationService:
    @staticmethod
    def apply(
        db: Session,
        result: KnowledgeNormalizationResult,
        *,
        document: KnowledgeDocument,
        entity_uuid: UUID | None,
    ) -> AppliedObservation:
        if result.observation_data is None:
            return AppliedObservation(False, None)
        observation_type = (result.observation_type or "").strip()
        observation_key = (result.observation_key or "").strip()
        if not observation_type or not observation_key:
            raise ValueError("Provider observations require a type and stable key")
        existing = db.query(KnowledgeProviderObservation).filter_by(
            provider_id=document.provider_id,
            observation_type=observation_type,
            observation_key=observation_key,
            document_uuid=document.uuid,
            normalization_version=result.observation_version,
        ).first()
        if existing is not None:
            return AppliedObservation(False, existing.uuid)
        db.query(KnowledgeProviderObservation).filter_by(
            provider_id=document.provider_id,
            observation_type=observation_type,
            observation_key=observation_key,
            is_current=True,
        ).update({KnowledgeProviderObservation.is_current: False}, synchronize_session=False)
        payload = dict(result.observation_data)
        supplied = sorted(key for key, value in payload.items() if value is not None)
        row = KnowledgeProviderObservation(
            provider_id=document.provider_id,
            observation_type=observation_type,
            observation_key=observation_key,
            entity_uuid=entity_uuid,
            document_uuid=document.uuid,
            normalized_payload=payload,
            supplied_fields=supplied,
            source_url=result.observation_source_url,
            normalization_version=result.observation_version,
            observed_at=document.retrieved_at,
            is_current=True,
        )
        db.add(row)
        db.flush()
        return AppliedObservation(True, row.uuid)
