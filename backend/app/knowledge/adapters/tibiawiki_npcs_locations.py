"""Bounded TibiaWiki adapters for NPCs and named locations."""

from __future__ import annotations

import json
import re
from dataclasses import replace
from typing import Any, Protocol

from app.knowledge.adapters.protocol import (
    CanonicalEntityCandidate, KnowledgeChildJobRequest, KnowledgeDocumentDTO,
    KnowledgeFetchRequest, KnowledgeFetchResult, KnowledgeNormalizationContext,
    KnowledgeNormalizationResult, KnowledgeValidationResult,
)
from app.knowledge.adapters.tibiawiki_creatures import HttpTibiaWikiCreatureClient, MAX_CREATURE_PAYLOAD_BYTES
from app.knowledge.dto import (
    LocationKnowledgeDTO, NamedKnowledgeReference, NpcDestinationReference,
    NpcKnowledgeDTO, NpcTradeReference,
)
from app.knowledge.indexing import normalize_name
from app.knowledge.services.failures import (
    MalformedProviderPayloadError, OversizedProviderResponseError, ProviderResponseEnvelopeError,
)
from app.services.bestiary_source import (
    _build_sprite_url, _build_wiki_page_url, _extract_infobox_param_map,
    _extract_links, _strip_markup, _to_bool, _to_int,
)
from app.services.text_utils import slugify


MAX_REFERENCE_PAYLOAD_BYTES = MAX_CREATURE_PAYLOAD_BYTES
MAX_REFERENCE_CATALOG_BATCH = 50
MAX_NPC_DETAIL_BATCH_BYTES = 10 * 1024 * 1024
NPC_CATALOG_CONTINUATION_PRIORITY = 190
_UNSAFE_TEXT = re.compile(r"<\s*script\b|javascript\s*:|\bon(?:error|load)\s*=", re.I)
_NON_ENTITY_NPC_TITLES = frozenset({
    "...", "deprecated npcs", "npc outfitter codes", "npc sounds", "npcs", "traders",
})


class TibiaWikiNamedEntityClient(Protocol):
    def fetch_catalog(self, *, continuation: str | None, limit: int) -> dict[str, Any]: ...
    def fetch_detail(self, *, external_id: str | None, page_title: str | None) -> dict[str, Any]: ...
    def fetch_details(self, *, members: list[dict[str, str]]) -> dict[str, Any]: ...


class HttpTibiaWikiNamedEntityClient(HttpTibiaWikiCreatureClient):
    def __init__(self, category: str):
        super().__init__()
        self.category = category

    def fetch_catalog(self, *, continuation: str | None, limit: int) -> dict[str, Any]:
        params: dict[str, Any] = {
            "action": "query", "list": "categorymembers",
            "cmtitle": f"Category:{self.category}", "cmtype": "page",
            "cmlimit": limit, "format": "json",
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
            raise ValueError("Detail jobs require an external ID or page title")
        return self._request(params)

    def fetch_details(self, *, members: list[dict[str, str]]) -> dict[str, Any]:
        page_ids = [member["external_id"] for member in members]
        return self._request({
            "action": "query",
            "pageids": "|".join(page_ids),
            "prop": "revisions",
            "rvprop": "content",
            "rvslots": "main",
            "format": "json",
            "formatversion": "2",
        })


def _size(value: dict[str, Any]) -> int:
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode())


def _first(params: dict[str, str], *keys: str) -> tuple[str | None, bool]:
    for key in keys:
        if key in params:
            return params[key], True
    return None, False


def _text(params: dict[str, str], *keys: str) -> tuple[str | None, bool]:
    value, supplied = _first(params, *keys)
    return (_strip_markup(value or "") or None), supplied


def _names(params: dict[str, str], *keys: str) -> tuple[tuple[NamedKnowledgeReference, ...], bool]:
    value, supplied = _first(params, *keys)
    if not value:
        return (), supplied
    names = _extract_links(value)
    if not names:
        names = [part.strip() for part in re.split(r"[,;\n]", _strip_markup(value)) if part.strip()]
    # Provider placeholders are absence markers, not named canonical evidence.
    names = [name for name in names if name.strip().casefold() not in {"-", "--", "n/a", "none", "unknown"}]
    if not names:
        return (), False
    return tuple(NamedKnowledgeReference(name=name) for name in dict.fromkeys(names)), supplied


def _structured_location_names(
    params: dict[str, str],
    raw_location: str | None,
) -> tuple[tuple[NamedKnowledgeReference, ...], str | None]:
    """Keep provider place fields separate from arbitrary location prose."""
    values: list[str] = []
    subarea = _strip_markup(params.get("subarea") or "").strip()
    if subarea:
        values.append(subarea)
    for key, value in params.items():
        if not re.fullmatch(r"city\d*", key):
            continue
        name = _strip_markup(value).strip()
        if name:
            values.append(name)
    if not values and raw_location:
        links = _extract_links(raw_location)
        stripped = _strip_markup(raw_location).strip(" .")
        if len(links) == 1 and normalize_name(stripped) == normalize_name(links[0]):
            values.append(links[0])
    unique = tuple(
        NamedKnowledgeReference(name=value)
        for value in dict.fromkeys(values)
        if normalize_name(value)
    )
    if not unique:
        return (), "text_only" if raw_location else None
    if "predictloc" in params:
        return unique, "moving"
    if len([key for key in params if re.fullmatch(r"city\d*", key)]) > 1:
        return unique, "multiple"
    return unique, "static"


_TRANSPORT_CELL_RE = re.compile(
    r"\{\{\s*TransportCell\s*\|\s*([^|}\n]+?)(?:\|\s*([\d,]+))?(?:\||}})",
    re.IGNORECASE,
)


def _transport_destinations(wikitext: str) -> tuple[NpcDestinationReference, ...]:
    values: list[NpcDestinationReference] = []
    seen: set[str] = set()
    for match in _TRANSPORT_CELL_RE.finditer(wikitext):
        name = _strip_markup(match.group(1)).strip()
        normalized = normalize_name(name)
        if not normalized or normalized in seen:
            continue
        price_text = (match.group(2) or "").replace(",", "")
        price = int(price_text) if price_text.isdigit() else None
        values.append(NpcDestinationReference(
            name=name,
            price=price,
            currency="gold_coin" if price is not None else None,
        ))
        seen.add(normalized)
    return tuple(values)


def _envelope(raw: dict[str, Any]) -> tuple[str, str, str, dict[str, str]]:
    parsed = raw.get("parse")
    if not isinstance(parsed, dict):
        raise MalformedProviderPayloadError()
    external_id = str(parsed.get("pageid") or "").strip()
    title = str(parsed.get("title") or "").strip()
    node = parsed.get("wikitext")
    wikitext = node.get("*") if isinstance(node, dict) else None
    if not external_id.isdigit() or not title or not isinstance(wikitext, str) or not wikitext.strip():
        raise MalformedProviderPayloadError()
    return external_id, title, wikitext, _extract_infobox_param_map(wikitext)


def _npc_parts(raw: dict[str, Any]) -> tuple[str, str, str, NpcKnowledgeDTO]:
    external_id, page_title, wikitext, params = _envelope(raw)
    name, name_supplied = _text(params, "name", "actualname")
    canonical_name = name or page_title
    title, title_supplied = _text(params, "title")
    occupation, occupation_supplied = _text(params, "job", "occupation", "profession")
    sex, sex_supplied = _text(params, "sex", "gender")
    raw_location, location_supplied = _first(params, "location")
    location_text = _strip_markup(raw_location or "") or None
    location_names, location_mode = _structured_location_names(params, raw_location)
    location = location_names[0].name if location_names and location_mode == "static" else None
    description, description_supplied = _text(params, "description", "notes")
    buys, buys_supplied = _names(params, "buys", "buyfrom", "buy from")
    sells, sells_supplied = _names(params, "sells", "sellsto", "sells to")
    named_destinations, destinations_supplied = _names(params, "destinations", "destination", "travelsto")
    transport_destinations = _transport_destinations(wikitext)
    destinations = transport_destinations or tuple(
        NpcDestinationReference(name=value.name) for value in named_destinations
    )
    destinations_supplied = destinations_supplied or bool(transport_destinations)
    quests, quests_supplied = _names(params, "quests", "relatedquests", "related quests")
    supplied = frozenset(key for key, flag in {
        "canonical_name": name_supplied, "title": title_supplied, "occupation": occupation_supplied,
        "sex": sex_supplied, "location_name": bool(location_names),
        "location_text": location_supplied, "location_names": bool(location_names),
        "location_mode": location_mode is not None, "description": description_supplied,
        "buys": buys_supplied, "sells": sells_supplied, "destinations": destinations_supplied,
        "related_quests": quests_supplied, "image_reference": True, "source_reference": True, "slug": True,
    }.items() if flag)
    aliases = () if normalize_name(page_title) == normalize_name(canonical_name) else (page_title,)
    dto = NpcKnowledgeDTO(
        external_id=external_id, canonical_name=canonical_name, slug=slugify(canonical_name), aliases=aliases,
        title=title, occupation=occupation, sex=sex, location_name=location,
        location_text=location_text, location_names=location_names, location_mode=location_mode,
        description=description,
        buys=tuple(NpcTradeReference(name=value.name) for value in buys),
        sells=tuple(NpcTradeReference(name=value.name) for value in sells),
        destinations=destinations, related_quests=quests,
        image_reference=_build_sprite_url(canonical_name), source_reference=_build_wiki_page_url(page_title),
        provider_metadata={
            "page_title": page_title,
            "template_parameters": sorted(params),
            "location_text": location_text,
            "location_names": [value.name for value in location_names],
            "location_mode": location_mode,
        },
        supplied_fields=supplied,
    )
    return external_id, page_title, wikitext, replace(dto, is_partial=not dto.sufficient_detail)


_VOCATION_LEVEL_TOKENS = (
    "knight", "paladin", "mage", "sorcerer", "druid", "monk",
)

_ACCESS_BODY_HINT = re.compile(
    r"\b(?:access\s+to|to\s+access|gain(?:ing)?\s+access|access\s+(?:is|can|requires?))\b",
    re.IGNORECASE,
)


def _vocation_level_requirement(
    params: dict[str, str],
) -> tuple[int | None, tuple[str, ...]]:
    candidates: list[int] = []
    supplied_keys: list[str] = []
    for key, raw_value in params.items():
        compact_key = re.sub(r"[^a-z0-9]", "", key.lower())
        if not any(token in compact_key for token in _VOCATION_LEVEL_TOKENS):
            continue
        if (
            "level" not in compact_key
            and "lvl" not in compact_key
            and not re.search(r"\blevel\b", raw_value or "", re.IGNORECASE)
        ):
            continue
        value = _to_int(raw_value)
        if value is None or value <= 0:
            continue
        candidates.append(value)
        supplied_keys.append(key)
    if not candidates:
        return None, ()
    return min(candidates), tuple(sorted(set(supplied_keys)))


def _access_body_evidence(
    wikitext: str,
) -> tuple[str | None, tuple[NamedKnowledgeReference, ...]]:
    access_note: str | None = None
    quest_names: list[str] = []
    for raw_line in wikitext.splitlines():
        candidate = raw_line.strip()
        if not candidate:
            continue
        cleaned = _strip_markup(candidate).strip()
        if not cleaned or len(cleaned) > 600 or not _ACCESS_BODY_HINT.search(cleaned):
            continue
        if access_note is None:
            access_note = cleaned
        for linked_name in _extract_links(candidate):
            name = linked_name.split("#", 1)[0].strip()
            if name and "quest" in name.casefold() and name not in quest_names:
                quest_names.append(name)
    return access_note, tuple(NamedKnowledgeReference(name=name) for name in quest_names)


def _location_parts(raw: dict[str, Any]) -> tuple[str, str, str, LocationKnowledgeDTO]:
    external_id, page_title, wikitext, params = _envelope(raw)
    name, name_supplied = _text(params, "name", "actualname")
    canonical_name = name or page_title
    kind, kind_supplied = _text(params, "type", "locationtype", "location type")
    region, region_supplied = _text(params, "region", "city", "continent")
    parent, parent_supplied = _text(params, "parent", "parentlocation", "parent location")
    description, description_supplied = _text(params, "description", "notes")
    premium_raw, premium_supplied = _first(params, "premium", "premiumonly", "premium required")
    minimum_raw, minimum_supplied = _first(params, "level", "minlevel", "minimumlevel")
    maximum_raw, maximum_supplied = _first(params, "maxlevel", "maximumlevel")

    minimum_level = _to_int(minimum_raw)
    _vocation_minimum, vocation_level_keys = _vocation_level_requirement(params)

    npcs, npcs_supplied = _names(params, "npcs", "npc")
    creatures, creatures_supplied = _names(params, "creatures", "monsters")
    quests, quests_supplied = _names(params, "quests", "relatedquests")
    sublocations, sublocations_supplied = _names(params, "sublocations", "subareas", "areas")
    access, access_supplied = _text(params, "access", "accessnotes", "access notes")

    # Body prose can describe access to a subarea rather than this canonical
    # location. Preserve it only in the immutable raw document.
    access_quests: tuple[NamedKnowledgeReference, ...] = ()

    supplied = frozenset(key for key, flag in {
        "canonical_name": name_supplied, "location_kind": kind_supplied, "region": region_supplied,
        "parent_location": parent_supplied, "description": description_supplied,
        "premium_required": premium_supplied, "minimum_level": minimum_supplied,
        "maximum_level": maximum_supplied, "npcs": npcs_supplied, "creatures": creatures_supplied,
        "quests": quests_supplied, "sublocations": sublocations_supplied, "access_notes": access_supplied,
        "image_reference": True, "source_reference": True, "slug": True,
    }.items() if flag)
    aliases = () if normalize_name(page_title) == normalize_name(canonical_name) else (page_title,)
    dto = LocationKnowledgeDTO(
        external_id=external_id, canonical_name=canonical_name, slug=slugify(canonical_name), aliases=aliases,
        location_kind=kind, region=region, parent_location=parent, description=description,
        premium_required=_to_bool(premium_raw) if premium_supplied else None,
        minimum_level=minimum_level, maximum_level=_to_int(maximum_raw),
        npcs=npcs, creatures=creatures, quests=quests, sublocations=sublocations, access_notes=access,
        image_reference=_build_sprite_url(canonical_name), source_reference=_build_wiki_page_url(page_title),
        provider_metadata={
            "page_title": page_title,
            "template_parameters": sorted(params),
            "access_quest_names": [value.name for value in access_quests],
            "vocation_level_parameters": list(vocation_level_keys),
        },
        supplied_fields=supplied,
    )
    return external_id, page_title, wikitext, replace(dto, is_partial=not dto.sufficient_detail)


class _TibiaWikiNamedEntityAdapter:
    provider_code = "tibiawiki"
    entity_type: str
    category: str
    parts = staticmethod(_npc_parts)

    def __init__(self, client: TibiaWikiNamedEntityClient | None = None):
        self.client = client or HttpTibiaWikiNamedEntityClient(self.category)

    @property
    def job_types(self) -> tuple[str, ...]:
        suffixes = ["catalog", "detail", "renormalize"]
        if self.entity_type == "npc":
            suffixes.append("detail_batch")
        return tuple(f"{self.entity_type}_{suffix}" for suffix in suffixes)

    def supports(self, job_type: str, entity_type: str | None) -> bool:
        return entity_type == self.entity_type and job_type in self.job_types

    def validate_enqueue(self, job_type: str, scope: dict, payload: dict) -> None:
        if job_type.endswith("_catalog"):
            limit = scope.get("batch_limit")
            if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= MAX_REFERENCE_CATALOG_BATCH:
                raise ValueError("Catalog jobs require an explicit batch_limit between 1 and 50")
            if payload or set(scope) != {"batch_limit"}:
                raise ValueError("Manual catalog jobs accept only batch_limit")
            return
        if job_type == "npc_detail_batch":
            members = payload.get("members")
            if scope or set(payload) != {"members"} or not isinstance(members, list) or not 1 <= len(members) <= 50:
                raise ValueError("NPC detail batches require between 1 and 50 stable members")
            for member in members:
                if not isinstance(member, dict) or set(member) != {"external_id", "page_title"}:
                    raise ValueError("NPC detail batches require stable page IDs and titles")
                external_id = str(member.get("external_id") or "").strip()
                page_title = str(member.get("page_title") or "").strip()
                if not external_id.isdigit() or len(external_id) > 20 or not page_title or len(page_title) > 255:
                    raise ValueError("NPC detail batch identifiers are invalid")
            return
        if set(payload) - {"external_id", "page_title"} or set(scope) - {"language"}:
            raise ValueError("Detail jobs accept only stable identifiers")
        external_id = str(payload.get("external_id") or "").strip()
        page_title = str(payload.get("page_title") or "").strip()
        if not external_id and not page_title:
            raise ValueError("Detail jobs require an external ID or page title")
        if external_id and (not external_id.isdigit() or len(external_id) > 20):
            raise ValueError("TibiaWiki external IDs must be numeric page IDs")
        if page_title and (len(page_title) > 255 or any(ord(character) < 32 for character in page_title)):
            raise ValueError("Page titles must be safe and no longer than 255 characters")
        if job_type.endswith("_renormalize") and not external_id:
            raise ValueError("Renormalization requires the stable external ID")

    def fetch(self, request: KnowledgeFetchRequest) -> KnowledgeFetchResult:
        if request.job_type.endswith("_catalog"):
            return self._fetch_catalog(request)
        if request.job_type == "npc_detail_batch":
            return self._fetch_npc_detail_batch(request)
        stored = request.job_type.endswith("_renormalize") and "_stored_document" in request.payload
        raw = request.payload.get("_stored_document") if stored else self.client.fetch_detail(
            external_id=str(request.payload.get("external_id") or "").strip() or None,
            page_title=str(request.payload.get("page_title") or "").strip() or None,
        )
        if not isinstance(raw, dict):
            raise MalformedProviderPayloadError()
        if _size(raw) > MAX_REFERENCE_PAYLOAD_BYTES:
            raise OversizedProviderResponseError()
        if raw.get("error"):
            raise ProviderResponseEnvelopeError()
        external_id, page_title, _wikitext, dto = self.parts(raw)
        return KnowledgeFetchResult(
            documents=(KnowledgeDocumentDTO(
                self.provider_code, f"{self.entity_type}:{external_id}", raw,
                version="mediawiki-v1", language="en",
                metadata={
                    "document_kind": f"{self.entity_type}_detail",
                    "external_id": external_id,
                    "page_title": page_title,
                    "normalization_mode": "renormalize" if stored else "detail",
                },
            ),), partial=dto.is_partial,
            provider_metadata={"source": "stored_document" if stored else "tibiawiki"},
        )

    def _fetch_npc_detail_batch(self, request: KnowledgeFetchRequest) -> KnowledgeFetchResult:
        members = request.payload.get("members")
        if not isinstance(members, list):
            raise MalformedProviderPayloadError()
        raw = self.client.fetch_details(members=members)
        if _size(raw) > MAX_NPC_DETAIL_BATCH_BYTES or raw.get("error"):
            raise OversizedProviderResponseError() if _size(raw) > MAX_NPC_DETAIL_BATCH_BYTES else ProviderResponseEnvelopeError()
        pages = (raw.get("query") or {}).get("pages")
        if not isinstance(pages, list):
            raise MalformedProviderPayloadError()
        documents: list[KnowledgeDocumentDTO] = []
        invalid = 0
        for page in pages:
            revisions = page.get("revisions") if isinstance(page, dict) else None
            slot = ((revisions or [{}])[0].get("slots") or {}).get("main") if revisions else None
            wikitext = slot.get("content") if isinstance(slot, dict) else None
            converted = {"parse": {
                "pageid": page.get("pageid") if isinstance(page, dict) else None,
                "title": page.get("title") if isinstance(page, dict) else None,
                "wikitext": {"*": wikitext},
            }}
            try:
                external_id, page_title, _wikitext, dto = self.parts(converted)
            except (KeyError, TypeError, ValueError, MalformedProviderPayloadError):
                invalid += 1
                raw_external_id = str(page.get("pageid") or "").strip() if isinstance(page, dict) else ""
                raw_title = str(page.get("title") or "").strip() if isinstance(page, dict) else ""
                if raw_external_id.isdigit() and raw_title:
                    documents.append(KnowledgeDocumentDTO(
                        self.provider_code,
                        f"npc_raw:{raw_external_id}",
                        converted,
                        version="mediawiki-v1",
                        language="en",
                        metadata={
                            "document_kind": "npc_raw_detail",
                            "external_id": raw_external_id,
                            "page_title": raw_title,
                            "batch_fetch": True,
                            "raw_only_reason": "malformed_or_insufficient_detail",
                        },
                    ))
                continue
            documents.append(KnowledgeDocumentDTO(
                self.provider_code,
                f"npc:{external_id}",
                converted,
                version="mediawiki-v1",
                language="en",
                metadata={
                    "document_kind": "npc_detail",
                    "external_id": external_id,
                    "page_title": page_title,
                    "batch_fetch": True,
                },
            ))
            invalid += int(dto.is_partial)
        if not documents:
            raise MalformedProviderPayloadError()
        return KnowledgeFetchResult(
            documents=tuple(documents),
            partial=invalid > 0,
            provider_metadata={"source": "tibiawiki_batch", "invalid_members": invalid},
        )

    def _fetch_catalog(self, request: KnowledgeFetchRequest) -> KnowledgeFetchResult:
        continuation = str(request.scope.get("continuation") or "").strip() or None
        limit = int(request.scope["batch_limit"])
        raw = self.client.fetch_catalog(continuation=continuation, limit=limit)
        if _size(raw) > MAX_REFERENCE_PAYLOAD_BYTES:
            raise OversizedProviderResponseError()
        if raw.get("error"):
            raise ProviderResponseEnvelopeError()
        members = (raw.get("query") or {}).get("categorymembers")
        if not isinstance(members, list):
            raise MalformedProviderPayloadError()
        children: list[KnowledgeChildJobRequest] = []
        valid_members: list[dict[str, str]] = []
        invalid = 0
        for member in members:
            external_id = str(member.get("pageid") or "").strip() if isinstance(member, dict) else ""
            title = str(member.get("title") or "").strip() if isinstance(member, dict) else ""
            if (
                not external_id.isdigit() or not title or ":" in title or len(title) > 255
                or (self.entity_type == "npc" and title.strip().casefold() in _NON_ENTITY_NPC_TITLES)
            ):
                invalid += 1
                continue
            valid_members.append({"external_id": external_id, "page_title": title})
        if self.entity_type == "npc" and valid_members:
            children.append(KnowledgeChildJobRequest(
                job_type="npc_detail_batch", entity_type="npc",
                payload={"members": valid_members}, priority=100,
                allow_completed_recreate=True,
            ))
        else:
            children.extend(
                KnowledgeChildJobRequest(
                    job_type=f"{self.entity_type}_detail", entity_type=self.entity_type,
                    payload=member, priority=100, allow_completed_recreate=True,
                )
                for member in valid_members
            )
        next_token = str((raw.get("continue") or {}).get("cmcontinue") or "").strip() or None
        if next_token:
            children.append(KnowledgeChildJobRequest(
                job_type=f"{self.entity_type}_catalog", entity_type=self.entity_type,
                scope={"batch_limit": limit, "continuation": next_token},
                priority=(NPC_CATALOG_CONTINUATION_PRIORITY if self.entity_type == "npc" else 90),
                allow_completed_recreate=True,
            ))
        return KnowledgeFetchResult(
            documents=(KnowledgeDocumentDTO(
                self.provider_code, f"catalog:{self.entity_type}:{continuation or 'first'}", raw,
                version="mediawiki-v1",
                metadata={"document_kind": f"{self.entity_type}_catalog", "batch_limit": limit},
            ),),
            cursor={"continuation": next_token, "members_processed": len(valid_members)},
            partial=invalid > 0,
            provider_metadata={
                "invalid_members": invalid,
                **({"discovered": len(valid_members)} if self.entity_type == "npc" else {}),
            },
            child_jobs=tuple(children),
        )

    def validate(self, result: KnowledgeFetchResult) -> KnowledgeValidationResult:
        if not result.documents:
            return KnowledgeValidationResult(False, classification="empty", safe_errors=("empty_response",))
        partial = result.partial
        for document in result.documents:
            if not isinstance(document.raw_json, dict) or _size(document.raw_json) > MAX_REFERENCE_PAYLOAD_BYTES:
                return KnowledgeValidationResult(False, classification="invalid", safe_errors=("invalid_envelope",))
            if document.raw_json.get("error"):
                return KnowledgeValidationResult(False, classification="provider_error", safe_errors=("provider_error",))
            if document.metadata.get("document_kind") == "npc_raw_detail":
                partial = True
                continue
            if document.metadata.get("document_kind") == f"{self.entity_type}_catalog":
                members = (document.raw_json.get("query") or {}).get("categorymembers")
                if not isinstance(members, list) or not members:
                    return KnowledgeValidationResult(False, classification="empty", safe_errors=("empty_catalog",))
                continue
            try:
                _external_id, _title, wikitext, dto = self.parts(document.raw_json)
            except (KeyError, TypeError, ValueError, MalformedProviderPayloadError):
                return KnowledgeValidationResult(False, classification="invalid", safe_errors=("invalid_detail",))
            if _UNSAFE_TEXT.search(wikitext):
                return KnowledgeValidationResult(False, classification="invalid", safe_errors=("unsafe_text",))
            if not dto.canonical_name or len(dto.canonical_name) > 255:
                return KnowledgeValidationResult(False, classification="invalid", safe_errors=("required_fields",))
            if isinstance(dto, LocationKnowledgeDTO):
                for value in (dto.minimum_level, dto.maximum_level):
                    if value is not None and not 0 <= value <= 2_147_483_647:
                        return KnowledgeValidationResult(False, classification="invalid", safe_errors=("numeric_range",))
            partial = partial or dto.is_partial
        return KnowledgeValidationResult(True, classification="partial" if partial else "valid")

    def normalize(self, document: KnowledgeDocumentDTO, context: KnowledgeNormalizationContext) -> KnowledgeNormalizationResult:
        if document.metadata.get("document_kind") != f"{self.entity_type}_detail":
            return KnowledgeNormalizationResult(action="noop")
        external_id, _title, _wikitext, dto = self.parts(document.raw_json)
        partial = dto.is_partial or not dto.sufficient_detail
        renormalize = document.metadata.get("normalization_mode") == "renormalize"

        if partial and not renormalize:
            return KnowledgeNormalizationResult(
                action="noop",
                warnings=(f"partial_{self.entity_type}_detail_not_normalized",),
            )

        return KnowledgeNormalizationResult(
            action="upsert",
            candidate=CanonicalEntityCandidate(
                entity_type=(dto.canonical_entity_type if isinstance(dto, LocationKnowledgeDTO) else self.entity_type),
                canonical_name=dto.canonical_name,
                language_neutral_id=dto.language_neutral_id,
                aliases=dto.aliases,
                source_priority=20,
                search_weight=1.0,
            ),
            warnings=(
                (f"partial_{self.entity_type}_renormalize_existing_only",)
                if partial
                else ()
            ),
            provider_code=self.provider_code,
            external_id=external_id,
            canonical_data=dto.to_canonical_data(),
        )


class TibiaWikiNpcAdapter(_TibiaWikiNamedEntityAdapter):
    entity_type = "npc"
    category = "NPCs"
    parts = staticmethod(_npc_parts)


class TibiaWikiLocationAdapter(_TibiaWikiNamedEntityAdapter):
    entity_type = "location"
    category = "Locations"
    parts = staticmethod(_location_parts)
