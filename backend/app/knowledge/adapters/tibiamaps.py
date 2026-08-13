"""Staged TibiaMaps adapter; network acquisition remains in the map sync flow."""

from __future__ import annotations

import json
from typing import Any

from app.knowledge.adapters.protocol import (
    CanonicalEntityCandidate,
    KnowledgeDocumentDTO,
    KnowledgeFetchRequest,
    KnowledgeFetchResult,
    KnowledgeNormalizationContext,
    KnowledgeNormalizationResult,
    KnowledgeValidationResult,
)
from app.knowledge.dto import MapPointDTO, MapRegionDTO


MAX_SPATIAL_DOCUMENT_BYTES = 1_000_000


class TibiaMapsKnowledgeAdapter:
    provider_code = "tibiamaps"
    job_types = ("map_point_import", "map_point_renormalize", "map_region_import", "map_region_renormalize")

    def supports(self, job_type: str, entity_type: str | None) -> bool:
        return job_type in self.job_types and job_type.startswith(f"{entity_type}_")

    def validate_enqueue(self, job_type: str, scope: dict, payload: dict) -> None:
        if scope:
            raise ValueError("Staged TibiaMaps jobs do not accept scope")
        if job_type.endswith("_import"):
            if set(payload) != {"document"} or not isinstance(payload.get("document"), dict):
                raise ValueError("TibiaMaps imports require one staged document")
            if len(json.dumps(payload["document"], separators=(",", ":")).encode()) > MAX_SPATIAL_DOCUMENT_BYTES:
                raise ValueError("TibiaMaps staged document is too large")
            return
        if set(payload) != {"external_id"} or not str(payload.get("external_id") or "").strip():
            raise ValueError("TibiaMaps renormalization requires an external ID")

    def fetch(self, request: KnowledgeFetchRequest) -> KnowledgeFetchResult:
        stored = request.job_type.endswith("_renormalize")
        raw = request.payload.get("_stored_document") if stored else request.payload.get("document")
        if not isinstance(raw, dict):
            raise ValueError("A staged or stored TibiaMaps document is required")
        entity_type = request.entity_type or ""
        external_id = str(raw.get("external_id") or "").strip()
        return KnowledgeFetchResult((KnowledgeDocumentDTO(
            self.provider_code,
            f"{entity_type}:{external_id}",
            raw,
            version=str(raw.get("upstream_commit") or raw.get("version") or "1"),
            metadata={"document_kind": f"{entity_type}_detail", "external_id": external_id},
        ),), provider_metadata={"source": "stored_document" if stored else "staged_import"})

    def validate(self, result: KnowledgeFetchResult) -> KnowledgeValidationResult:
        if len(result.documents) != 1 or not isinstance(result.documents[0].raw_json, dict):
            return KnowledgeValidationResult(False, classification="invalid", safe_errors=("invalid_document",))
        document = result.documents[0]
        try:
            self._dto(str(document.metadata.get("document_kind") or ""), document.raw_json)
        except (TypeError, ValueError):
            return KnowledgeValidationResult(False, classification="invalid", safe_errors=("invalid_spatial_document",))
        return KnowledgeValidationResult(True)

    @staticmethod
    def _dto(kind: str, raw: dict[str, Any]) -> MapPointDTO | MapRegionDTO:
        fields = {
            key: value for key, value in raw.items()
            if key not in {"upstream_commit", "version", "supplied_fields", "data_version"}
        }
        return MapPointDTO(**fields) if kind == "map_point_detail" else MapRegionDTO(**fields)

    def normalize(self, document: KnowledgeDocumentDTO, context: KnowledgeNormalizationContext) -> KnowledgeNormalizationResult:
        kind = str(document.metadata.get("document_kind") or "")
        entity_type = kind.removesuffix("_detail")
        dto = self._dto(kind, document.raw_json)
        name = dto.name
        return KnowledgeNormalizationResult(
            action="upsert",
            candidate=CanonicalEntityCandidate(
                entity_type=entity_type,
                canonical_name=name,
                language_neutral_id=f"{entity_type}:tibiamaps:{dto.external_id}",
                source_priority=20,
            ),
            provider_code=self.provider_code,
            external_id=dto.external_id,
            canonical_data=document.raw_json,
        )
