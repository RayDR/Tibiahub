"""Bounded TibiaWiki route ingestion into the existing spatial route model."""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from typing import Any

from app.knowledge.adapters.protocol import (
    CanonicalEntityCandidate,
    KnowledgeChildJobRequest,
    KnowledgeDocumentDTO,
    KnowledgeFetchRequest,
    KnowledgeFetchResult,
    KnowledgeNormalizationContext,
    KnowledgeNormalizationResult,
    KnowledgeValidationResult,
)
from app.knowledge.adapters.tibiawiki_npcs_locations import (
    MAX_REFERENCE_CATALOG_BATCH,
    MAX_REFERENCE_PAYLOAD_BYTES,
    HttpTibiaWikiNamedEntityClient,
    TibiaWikiNamedEntityClient,
)
from app.knowledge.dto import RouteDTO, RouteStepDTO
from app.knowledge.services.failures import (
    MalformedProviderPayloadError,
    OversizedProviderResponseError,
    ProviderResponseEnvelopeError,
)
from app.services.bestiary_source import _build_wiki_page_url, _strip_markup


_UNSAFE_TEXT = re.compile(r"<\s*script\b|javascript\s*:|\bon(?:error|load)\s*=", re.I)
_IMAGE = re.compile(r"\[\[(?:File|Image):([^\]|]+)", re.I)
_MAPPER_COORDS_WRAPPER = re.compile(
    r"\s*\(\s*\{\{\s*Mapper Coords\b[^{}]*\}\}\s*\)",
    re.I,
)


def _size(value: dict[str, Any]) -> int:
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode())


def _parts(raw: dict[str, Any]) -> tuple[str, str, str, RouteDTO]:
    parsed = raw.get("parse")
    if not isinstance(parsed, dict):
        raise MalformedProviderPayloadError()
    external_id = str(parsed.get("pageid") or "").strip()
    title = str(parsed.get("title") or "").strip()
    node = parsed.get("wikitext")
    wikitext = node.get("*") if isinstance(node, dict) else None
    if not external_id.isdigit() or not title.lower().startswith("route:") or not isinstance(wikitext, str):
        raise MalformedProviderPayloadError()
    destination = title.split(":", 1)[1].strip()
    if not destination or "/map" in destination.casefold():
        raise MalformedProviderPayloadError()
    instructions: list[str] = []
    for line in wikitext.splitlines():
        if not re.match(r"^\s*\*", line) or re.match(r"^\s*\*\s*\[\[(?:File|Image):", line, re.I):
            continue
        raw_instruction = re.sub(r"^\s*\*+\s*", "", line)
        raw_instruction = _MAPPER_COORDS_WRAPPER.sub("", raw_instruction)
        instruction = _strip_markup(raw_instruction).strip()
        if instruction and instruction.casefold() not in {value.casefold() for value in instructions}:
            instructions.append(instruction[:2000])
        if len(instructions) >= 250:
            break
    if not instructions:
        raise MalformedProviderPayloadError()
    steps = tuple(
        RouteStepDTO(
            sequence=index,
            instruction=instruction,
            location_name=destination if index == len(instructions) else None,
            provider_metadata={"source_line": index},
        )
        for index, instruction in enumerate(instructions, 1)
    )
    dto = RouteDTO(
        external_id=external_id,
        name=title,
        steps=steps,
        end_location_name=destination,
        confidence="medium",
        source_reference=_build_wiki_page_url(title),
        provider_metadata={
            "page_title": title,
            "map_images": [
                _build_wiki_page_url(f"Special:FilePath/{value.strip()}")
                for value in list(dict.fromkeys(_IMAGE.findall(wikitext)))[:100]
            ],
            "coordinate_policy": "unresolved_unless_trusted_tibia_coordinates",
        },
    )
    return external_id, title, wikitext, dto


class TibiaWikiRouteAdapter:
    provider_code = "tibiawiki"
    job_types = ("route_catalog", "route_detail", "route_renormalize")

    def __init__(self, client: TibiaWikiNamedEntityClient | None = None):
        self.client = client or HttpTibiaWikiNamedEntityClient("Routes")

    def supports(self, job_type: str, entity_type: str | None) -> bool:
        return entity_type == "route" and job_type in self.job_types

    def validate_enqueue(self, job_type: str, scope: dict, payload: dict) -> None:
        if job_type == "route_catalog":
            limit = scope.get("batch_limit")
            if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= MAX_REFERENCE_CATALOG_BATCH:
                raise ValueError("Route catalogs require a batch limit between 1 and 50")
            if payload or set(scope) != {"batch_limit"}:
                raise ValueError("Manual route catalogs accept only batch_limit")
            return
        if set(payload) - {"external_id", "page_title"} or set(scope) - {"language"}:
            raise ValueError("Route detail jobs accept only stable identifiers")
        external_id = str(payload.get("external_id") or "").strip()
        page_title = str(payload.get("page_title") or "").strip()
        if not external_id and not page_title:
            raise ValueError("Route detail jobs require an external ID or page title")
        if external_id and not external_id.isdigit():
            raise ValueError("Route external IDs must be numeric")
        if job_type == "route_renormalize" and not external_id:
            raise ValueError("Route renormalization requires an external ID")

    def fetch(self, request: KnowledgeFetchRequest) -> KnowledgeFetchResult:
        if request.job_type == "route_catalog":
            return self._catalog(request)
        stored = request.job_type == "route_renormalize" and "_stored_document" in request.payload
        raw = request.payload.get("_stored_document") if stored else self.client.fetch_detail(
            external_id=str(request.payload.get("external_id") or "").strip() or None,
            page_title=str(request.payload.get("page_title") or "").strip() or None,
        )
        if not isinstance(raw, dict) or _size(raw) > MAX_REFERENCE_PAYLOAD_BYTES:
            raise OversizedProviderResponseError()
        if raw.get("error"):
            raise ProviderResponseEnvelopeError()
        external_id, title, _wikitext, _dto = _parts(raw)
        return KnowledgeFetchResult(documents=(KnowledgeDocumentDTO(
            self.provider_code, f"route:{external_id}", raw, version="mediawiki-v1", language="en",
            metadata={"document_kind": "route_detail", "external_id": external_id, "page_title": title},
        ),), provider_metadata={"source": "stored_document" if stored else "tibiawiki"})

    def _catalog(self, request: KnowledgeFetchRequest) -> KnowledgeFetchResult:
        continuation = str(request.scope.get("continuation") or "").strip() or None
        limit = int(request.scope["batch_limit"])
        raw = self.client.fetch_catalog(continuation=continuation, limit=limit)
        if _size(raw) > MAX_REFERENCE_PAYLOAD_BYTES:
            raise OversizedProviderResponseError()
        members = (raw.get("query") or {}).get("categorymembers")
        if not isinstance(members, list):
            raise MalformedProviderPayloadError()
        children: list[KnowledgeChildJobRequest] = []
        invalid = 0
        skipped_fragments = 0
        for member in members:
            external_id = str(member.get("pageid") or "").strip() if isinstance(member, dict) else ""
            title = str(member.get("title") or "").strip() if isinstance(member, dict) else ""
            if "/map" in title.casefold():
                skipped_fragments += 1
                continue
            if not external_id.isdigit() or not title.lower().startswith("route:"):
                invalid += 1
                continue
            children.append(KnowledgeChildJobRequest(
                job_type="route_detail", entity_type="route",
                payload={"external_id": external_id, "page_title": title}, priority=100,
                allow_completed_recreate=True,
            ))
        next_token = str((raw.get("continue") or {}).get("cmcontinue") or "").strip() or None
        if next_token:
            children.append(KnowledgeChildJobRequest(
                job_type="route_catalog", entity_type="route",
                scope={"batch_limit": limit, "continuation": next_token}, priority=90,
                allow_completed_recreate=True,
            ))
        return KnowledgeFetchResult(
            documents=(KnowledgeDocumentDTO(
                self.provider_code, f"catalog:route:{continuation or 'first'}", raw,
                version="mediawiki-v1", metadata={"document_kind": "route_catalog", "batch_limit": limit},
            ),),
            cursor={"continuation": next_token, "members_processed": len(children) - int(bool(next_token))},
            partial=invalid > 0,
            provider_metadata={"invalid_members": invalid, "skipped_map_fragments": skipped_fragments},
            child_jobs=tuple(children),
        )

    def validate(self, result: KnowledgeFetchResult) -> KnowledgeValidationResult:
        if not result.documents:
            return KnowledgeValidationResult(False, classification="empty", safe_errors=("empty_response",))
        for document in result.documents:
            if document.metadata.get("document_kind") == "route_catalog":
                members = (document.raw_json.get("query") or {}).get("categorymembers")
                if not isinstance(members, list) or not members:
                    return KnowledgeValidationResult(False, classification="empty", safe_errors=("empty_catalog",))
                continue
            try:
                _external_id, _title, wikitext, _dto = _parts(document.raw_json)
            except (TypeError, ValueError, MalformedProviderPayloadError):
                return KnowledgeValidationResult(False, classification="invalid", safe_errors=("invalid_route",))
            if _UNSAFE_TEXT.search(wikitext):
                return KnowledgeValidationResult(False, classification="invalid", safe_errors=("unsafe_text",))
        return KnowledgeValidationResult(True, classification="partial" if result.partial else "valid")

    def normalize(self, document: KnowledgeDocumentDTO, context: KnowledgeNormalizationContext) -> KnowledgeNormalizationResult:
        if document.metadata.get("document_kind") != "route_detail":
            return KnowledgeNormalizationResult(action="noop")
        external_id, title, _wikitext, dto = _parts(document.raw_json)
        return KnowledgeNormalizationResult(
            action="upsert",
            candidate=CanonicalEntityCandidate(
                entity_type="route", canonical_name=title,
                language_neutral_id=f"route:tibiawiki:{external_id}", source_priority=20, search_weight=0.8,
            ),
            provider_code=self.provider_code,
            external_id=external_id,
            canonical_data=asdict(dto),
        )
