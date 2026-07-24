"""Creature adapter for TibiaHub's configured TibiaWiki MediaWiki source."""

from __future__ import annotations

import json
import re
from typing import Any, Protocol

import httpx

from app.core.config import settings
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
from app.knowledge.dto import CreatureKnowledgeDTO
from app.knowledge.services.failures import (
    MalformedProviderPayloadError,
    OversizedProviderResponseError,
    ProviderConnectionError,
    ProviderHTTPError,
    ProviderResponseEnvelopeError,
    ProviderTimeoutError,
)
from app.services.bestiary_source import _build_creature_payload


MAX_CREATURE_PAYLOAD_BYTES = 2 * 1024 * 1024
MAX_CATALOG_BATCH = 50
_UNSAFE_TEXT = re.compile(r"<\s*script\b|javascript\s*:|\bon(?:error|load)\s*=", re.I)


class TibiaWikiCreatureClient(Protocol):
    def fetch_catalog(self, *, continuation: str | None, limit: int) -> dict[str, Any]: ...

    def fetch_detail(self, *, external_id: str | None, page_title: str | None) -> dict[str, Any]: ...


class HttpTibiaWikiCreatureClient:
    """Small synchronous MediaWiki client suitable for the synchronous worker."""

    def __init__(self, *, timeout_seconds: float = 20.0, maximum_bytes: int = MAX_CREATURE_PAYLOAD_BYTES):
        self.timeout_seconds = timeout_seconds
        self.maximum_bytes = maximum_bytes

    def _request(self, params: dict[str, Any]) -> dict[str, Any]:
        try:
            with httpx.Client(
                timeout=self.timeout_seconds,
                follow_redirects=True,
                headers={"User-Agent": settings.TIBIAWIKI_USER_AGENT, "Accept": "application/json"},
            ) as client:
                with client.stream("GET", settings.TIBIAWIKI_API_URL, params=params) as response:
                    if response.status_code != 200:
                        retry_after = response.headers.get("Retry-After")
                        raise ProviderHTTPError(
                            response.status_code,
                            retry_after_seconds=int(retry_after) if retry_after and retry_after.isdigit() else None,
                        )
                    content_length = response.headers.get("Content-Length")
                    if content_length and content_length.isdigit() and int(content_length) > self.maximum_bytes:
                        raise OversizedProviderResponseError()
                    body = bytearray()
                    for chunk in response.iter_bytes():
                        body.extend(chunk)
                        if len(body) > self.maximum_bytes:
                            raise OversizedProviderResponseError()
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError() from exc
        except httpx.RequestError as exc:
            raise ProviderConnectionError() from exc
        try:
            value = json.loads(body)
        except (UnicodeDecodeError, ValueError) as exc:
            raise MalformedProviderPayloadError() from exc
        if not isinstance(value, dict):
            raise MalformedProviderPayloadError()
        if value.get("error"):
            raise ProviderResponseEnvelopeError()
        return value

    def fetch_catalog(self, *, continuation: str | None, limit: int) -> dict[str, Any]:
        params: dict[str, Any] = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": "Category:Creatures",
            "cmtype": "page",
            "cmlimit": limit,
            "format": "json",
        }
        if continuation:
            params["cmcontinue"] = continuation
        return self._request(params)

    def fetch_detail(self, *, external_id: str | None, page_title: str | None) -> dict[str, Any]:
        params: dict[str, Any] = {"action": "parse", "prop": "wikitext", "format": "json"}
        if external_id and external_id.isdigit():
            params["pageid"] = external_id
        elif page_title:
            params["page"] = page_title
        else:
            raise ValueError("Creature detail requires an external ID or page title")
        return self._request(params)


def _serialized_size(value: dict[str, Any]) -> int:
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def _detail_parts(raw: dict[str, Any]) -> tuple[str, str, str, dict[str, Any]]:
    parsed = raw.get("parse")
    if not isinstance(parsed, dict):
        raise MalformedProviderPayloadError()
    external_id = str(parsed.get("pageid") or "").strip()
    page_title = str(parsed.get("title") or "").strip()
    wikitext_node = parsed.get("wikitext")
    wikitext = wikitext_node.get("*") if isinstance(wikitext_node, dict) else None
    if not external_id or not page_title or not isinstance(wikitext, str) or not wikitext.strip():
        raise MalformedProviderPayloadError()
    return external_id, page_title, wikitext, _build_creature_payload(page_title, wikitext)


class TibiaWikiCreatureAdapter:
    provider_code = "tibiawiki"
    job_types = ("creature_catalog", "creature_detail", "creature_renormalize")

    def __init__(self, client: TibiaWikiCreatureClient | None = None):
        self.client = client or HttpTibiaWikiCreatureClient()

    def supports(self, job_type: str, entity_type: str | None) -> bool:
        return entity_type == "creature" and job_type in self.job_types

    def validate_enqueue(self, job_type: str, scope: dict, payload: dict) -> None:
        if job_type == "creature_catalog":
            batch_limit = scope.get("batch_limit")
            if not isinstance(batch_limit, int) or isinstance(batch_limit, bool) or not 1 <= batch_limit <= MAX_CATALOG_BATCH:
                raise ValueError("Creature catalog jobs require an explicit batch_limit between 1 and 50")
            if payload:
                raise ValueError("Creature catalog jobs do not accept a payload")
            if set(scope) != {"batch_limit"}:
                raise ValueError("Manual creature catalog jobs accept only batch_limit")
            return
        allowed = {"external_id", "page_title"}
        if set(payload) - allowed or set(scope) - {"language"}:
            raise ValueError("Creature detail jobs accept only stable identifiers")
        external_id = str(payload.get("external_id") or "").strip()
        page_title = str(payload.get("page_title") or "").strip()
        if not external_id and not page_title:
            raise ValueError("Creature detail jobs require an external ID or page title")
        if external_id and (not external_id.isdigit() or len(external_id) > 20):
            raise ValueError("TibiaWiki creature external IDs must be numeric page IDs")
        if page_title and (len(page_title) > 255 or any(ord(character) < 32 for character in page_title)):
            raise ValueError("Creature page titles must be safe and no longer than 255 characters")
        if job_type == "creature_renormalize" and not external_id:
            raise ValueError("Creature renormalization requires the stable external ID")

    def fetch(self, request: KnowledgeFetchRequest) -> KnowledgeFetchResult:
        if request.job_type == "creature_catalog":
            return self._fetch_catalog(request)
        if request.job_type == "creature_renormalize" and "_stored_document" in request.payload:
            raw = request.payload["_stored_document"]
            if not isinstance(raw, dict):
                raise MalformedProviderPayloadError()
            external_id, page_title, _wikitext, payload = _detail_parts(raw)
            return KnowledgeFetchResult(
                documents=(self._detail_document(raw, external_id, page_title),),
                partial=bool(payload.get("missing_fields")),
                provider_metadata={"source": "stored_document"},
            )
        raw = self.client.fetch_detail(
            external_id=str(request.payload.get("external_id") or "").strip() or None,
            page_title=str(request.payload.get("page_title") or "").strip() or None,
        )
        if _serialized_size(raw) > MAX_CREATURE_PAYLOAD_BYTES:
            raise OversizedProviderResponseError()
        if raw.get("error"):
            raise ProviderResponseEnvelopeError()
        external_id, page_title, _wikitext, payload = _detail_parts(raw)
        return KnowledgeFetchResult(
            documents=(self._detail_document(raw, external_id, page_title),),
            partial=bool(payload.get("missing_fields")),
            provider_metadata={"source": "tibiawiki"},
        )

    def _fetch_catalog(self, request: KnowledgeFetchRequest) -> KnowledgeFetchResult:
        continuation = str(request.scope.get("continuation") or "").strip() or None
        limit = int(request.scope["batch_limit"])
        raw = self.client.fetch_catalog(continuation=continuation, limit=limit)
        if _serialized_size(raw) > MAX_CREATURE_PAYLOAD_BYTES:
            raise OversizedProviderResponseError()
        if raw.get("error"):
            raise ProviderResponseEnvelopeError()
        members = (raw.get("query") or {}).get("categorymembers")
        if not isinstance(members, list):
            raise MalformedProviderPayloadError()
        children: list[KnowledgeChildJobRequest] = []
        invalid_members = 0
        for member in members:
            external_id = str(member.get("pageid") or "").strip() if isinstance(member, dict) else ""
            title = str(member.get("title") or "").strip() if isinstance(member, dict) else ""
            if not external_id or not title or ":" in title:
                invalid_members += 1
                continue
            children.append(
                KnowledgeChildJobRequest(
                    job_type="creature_detail",
                    entity_type="creature",
                    payload={"external_id": external_id, "page_title": title},
                    priority=100,
                    allow_completed_recreate=True,
                )
            )
        next_token = str((raw.get("continue") or {}).get("cmcontinue") or "").strip() or None
        if next_token:
            children.append(
                KnowledgeChildJobRequest(
                    job_type="creature_catalog",
                    entity_type="creature",
                    scope={"batch_limit": limit, "continuation": next_token},
                    priority=90,
                    allow_completed_recreate=True,
                )
            )
        document = KnowledgeDocumentDTO(
            provider_code=self.provider_code,
            provider_document_id=f"catalog:creatures:{continuation or 'first'}",
            raw_json=raw,
            version="mediawiki-v1",
            metadata={"document_kind": "creature_catalog", "batch_limit": limit},
        )
        return KnowledgeFetchResult(
            documents=(document,),
            cursor={"continuation": next_token, "members_processed": len(children) - int(bool(next_token))},
            partial=invalid_members > 0,
            provider_metadata={"invalid_members": invalid_members},
            child_jobs=tuple(children),
        )

    def _detail_document(self, raw: dict[str, Any], external_id: str, page_title: str) -> KnowledgeDocumentDTO:
        return KnowledgeDocumentDTO(
            provider_code=self.provider_code,
            provider_document_id=f"creature:{external_id}",
            raw_json=raw,
            version="mediawiki-v1",
            language="en",
            metadata={
                "document_kind": "creature_detail",
                "external_id": external_id,
                "page_title": page_title,
            },
        )

    def validate(self, result: KnowledgeFetchResult) -> KnowledgeValidationResult:
        if not result.documents:
            return KnowledgeValidationResult(False, classification="empty", safe_errors=("empty_response",))
        partial = result.partial
        for document in result.documents:
            if not isinstance(document.raw_json, dict):
                return KnowledgeValidationResult(False, classification="invalid", safe_errors=("invalid_envelope",))
            if _serialized_size(document.raw_json) > MAX_CREATURE_PAYLOAD_BYTES:
                return KnowledgeValidationResult(False, classification="oversized", safe_errors=("oversized",))
            if document.raw_json.get("error"):
                return KnowledgeValidationResult(False, classification="provider_error", safe_errors=("provider_error",))
            if document.metadata.get("document_kind") == "creature_catalog":
                members = (document.raw_json.get("query") or {}).get("categorymembers")
                if not isinstance(members, list) or not members:
                    return KnowledgeValidationResult(False, classification="empty", safe_errors=("empty_catalog",))
                continue
            try:
                external_id, page_title, wikitext, payload = _detail_parts(document.raw_json)
                dto = CreatureKnowledgeDTO.from_tibiawiki_payload(
                    payload,
                    external_id=external_id,
                    page_title=page_title,
                )
            except (KeyError, TypeError, ValueError, MalformedProviderPayloadError):
                return KnowledgeValidationResult(False, classification="invalid", safe_errors=("invalid_detail",))
            if _UNSAFE_TEXT.search(wikitext):
                return KnowledgeValidationResult(False, classification="invalid", safe_errors=("unsafe_text",))
            if not dto.external_id or not dto.canonical_name.strip():
                return KnowledgeValidationResult(False, classification="invalid", safe_errors=("required_fields",))
            for value in (dto.hitpoints, dto.experience, dto.speed, dto.armor, dto.charm_points):
                if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value < 0 or value > 2_147_483_647):
                    return KnowledgeValidationResult(False, classification="invalid", safe_errors=("numeric_range",))
            partial = partial or not dto.sufficient_detail
        return KnowledgeValidationResult(True, classification="partial" if partial else "valid")

    def normalize(
        self,
        document: KnowledgeDocumentDTO,
        context: KnowledgeNormalizationContext,
    ) -> KnowledgeNormalizationResult:
        if document.metadata.get("document_kind") != "creature_detail":
            return KnowledgeNormalizationResult(action="noop")
        external_id, page_title, _wikitext, payload = _detail_parts(document.raw_json)
        dto = CreatureKnowledgeDTO.from_tibiawiki_payload(payload, external_id=external_id, page_title=page_title)
        if not dto.sufficient_detail:
            return KnowledgeNormalizationResult(
                action="noop",
                warnings=("partial_creature_detail_not_normalized",),
            )
        return KnowledgeNormalizationResult(
            action="upsert",
            candidate=CanonicalEntityCandidate(
                entity_type="creature",
                canonical_name=dto.canonical_name,
                language_neutral_id=dto.language_neutral_id,
                aliases=dto.aliases,
                source_priority=20,
                search_weight=1.0,
            ),
            warnings=("partial_creature_detail",) if not dto.sufficient_detail else (),
            provider_code=self.provider_code,
            external_id=dto.external_id,
            canonical_data=dto.to_canonical_data(),
        )
