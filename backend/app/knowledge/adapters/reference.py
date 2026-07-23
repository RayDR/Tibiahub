"""Deterministic development/test adapter; it never performs network access."""

from __future__ import annotations

from app.knowledge.adapters.protocol import (
    CanonicalEntityCandidate,
    KnowledgeDocumentDTO,
    KnowledgeFetchRequest,
    KnowledgeFetchResult,
    KnowledgeNormalizationContext,
    KnowledgeNormalizationResult,
    KnowledgeValidationResult,
)


class ReferenceKnowledgeAdapter:
    provider_code = "reference"

    def supports(self, job_type: str, entity_type: str | None) -> bool:
        return job_type == "reference_import" and entity_type is not None

    def fetch(self, request: KnowledgeFetchRequest) -> KnowledgeFetchResult:
        payload = dict(request.payload)
        provider_document_id = str(payload.get("provider_document_id") or request.job_id)
        raw_json = {
            "canonical_name": payload.get("canonical_name"),
            "language_neutral_id": payload.get("language_neutral_id"),
            "aliases": list(payload.get("aliases") or []),
            "entity_type": request.entity_type,
            "provider_payload": payload,
        }
        return KnowledgeFetchResult(
            documents=(
                KnowledgeDocumentDTO(
                    provider_code=self.provider_code,
                    provider_document_id=provider_document_id,
                    raw_json=raw_json,
                    version="reference-v1",
                    language=str(payload.get("language") or "en"),
                    metadata={"synthetic": True},
                ),
            ),
            cursor={"last_document_id": provider_document_id},
        )

    def validate(self, result: KnowledgeFetchResult) -> KnowledgeValidationResult:
        if len(result.documents) != 1:
            return KnowledgeValidationResult(valid=False, safe_errors=("reference_document_count",))
        payload = result.documents[0].raw_json
        if not isinstance(payload, dict):
            return KnowledgeValidationResult(valid=False, safe_errors=("reference_payload_shape",))
        if not payload.get("canonical_name") or not payload.get("language_neutral_id") or not payload.get("entity_type"):
            return KnowledgeValidationResult(valid=False, safe_errors=("reference_required_fields",))
        return KnowledgeValidationResult(valid=True)

    def normalize(
        self,
        document: KnowledgeDocumentDTO,
        context: KnowledgeNormalizationContext,
    ) -> KnowledgeNormalizationResult:
        payload = document.raw_json
        if not isinstance(payload, dict) or context.entity_type is None:
            return KnowledgeNormalizationResult(action="noop", warnings=("normalization_payload_ignored",))
        return KnowledgeNormalizationResult(
            action="upsert",
            candidate=CanonicalEntityCandidate(
                entity_type=context.entity_type,
                canonical_name=str(payload["canonical_name"]),
                language_neutral_id=str(payload["language_neutral_id"]),
                aliases=tuple(str(alias) for alias in payload.get("aliases") or []),
            ),
        )
