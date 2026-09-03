"""Bounded TibiaWiki Hunting Place adapter with vocation-specific parsing."""

from __future__ import annotations

import json
import re
from dataclasses import replace
from typing import Any
from urllib.parse import quote

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
    HttpTibiaWikiNamedEntityClient,
    TibiaWikiNamedEntityClient,
    _access_body_evidence,
    _envelope,
    _first,
    _text,
)
from app.knowledge.adapters.tibiawiki_creatures import MAX_CREATURE_PAYLOAD_BYTES
from app.knowledge.dto import HuntVocationRecommendation, HuntZoneKnowledgeDTO
from app.knowledge.indexing import normalize_name
from app.knowledge.services.failures import (
    MalformedProviderPayloadError,
    OversizedProviderResponseError,
    ProviderResponseEnvelopeError,
)
from app.services.bestiary_source import (
    _build_wiki_page_url,
    _extract_links,
    _strip_markup,
    _to_bool,
    _to_int,
)
from app.services.text_utils import slugify


MAX_HUNT_ZONE_CATALOG_BATCH = 50
_UNSAFE_TEXT = re.compile(r"<\s*script\b|javascript\s*:|\bon(?:error|load)\s*=", re.I)
_CREATURE_LIST = re.compile(r"\{\{\s*CreatureList\b(.*?)\n\s*\}\}", re.I | re.S)
_RECOMMENDATION_KEY = re.compile(r"^(lvl|sk|def)([a-z]+)$", re.I)
_RECOMMENDATION_FIELD = {"lvl": "level", "sk": "skill", "def": "defense"}
_MAPPER_COORDS_REFERENCE = re.compile(
    r"\s*,?\s*\{\{\s*Mapper Coords\b[^{}]*\}\}",
    re.I,
)
_MAPPER_EXTERNAL_REFERENCE = re.compile(
    r"\s*,?\s*\[https?://[^\]\s]+/wiki/Mapper\?coords=[^\]]+\]",
    re.I,
)
_HUNT_INFOBOX = re.compile(r"\{\{\s*Infobox[ _]Hunt\b", re.I)
_FILE_REFERENCE = re.compile(r"^(?:file|image)\s*:\s*", re.I)


def _serialized_size(value: dict[str, Any]) -> int:
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode())


def _linked_names(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    names = _extract_links(value)
    if not names:
        cleaned = _strip_markup(value)
        names = [part.strip() for part in re.split(r"[,;\n]", cleaned) if part.strip()]
    return tuple(dict.fromkeys(names))


def _creature_names(wikitext: str) -> tuple[str, ...]:
    names: list[str] = []
    for match in _CREATURE_LIST.finditer(wikitext):
        body = match.group(1)
        for raw_line in body.splitlines():
            value = raw_line.strip()
            if not value.startswith("|"):
                continue
            value = value[1:].strip()
            if not value or "=" in value:
                continue
            name = _strip_markup(value)
            if name and name not in names:
                names.append(name)
    return tuple(names)


def _is_structured_hunt_entity(wikitext: str) -> bool:
    """Require the provider's explicit Hunting Place entity template."""

    return bool(_HUNT_INFOBOX.search(wikitext))


def _provider_image_reference(value: str | None) -> str | None:
    """Build a provider file URL only from an explicitly supplied image field."""

    if not value:
        return None
    links = _extract_links(value)
    asset_name = (links[0] if links else _strip_markup(value)).strip()
    asset_name = _FILE_REFERENCE.sub("", asset_name).strip()
    if not asset_name:
        return None
    if not re.search(r"\.(?:gif|png|jpe?g|webp)$", asset_name, re.I):
        asset_name = f"{asset_name}.gif"
    encoded = quote(asset_name.replace(" ", "_"), safe="_.-()")
    return f"{_build_wiki_page_url('Special:FilePath').rstrip('/')}/{encoded}"


def _recommendations(params: dict[str, str]) -> tuple[dict[str, HuntVocationRecommendation], tuple[str, ...]]:
    grouped: dict[str, dict[str, int | None]] = {}
    supplied: list[str] = []
    for key, raw_value in params.items():
        compact = re.sub(r"[^a-z]", "", key.lower())
        match = _RECOMMENDATION_KEY.fullmatch(compact)
        if not match:
            continue
        prefix, vocation = match.groups()
        field_name = _RECOMMENDATION_FIELD[prefix]
        grouped.setdefault(vocation, {"level": None, "skill": None, "defense": None})[field_name] = _to_int(raw_value)
        supplied.append(key)
    return (
        {name: HuntVocationRecommendation(**values) for name, values in grouped.items()},
        tuple(sorted(supplied)),
    )


def _hunt_zone_parts(raw: dict[str, Any]) -> tuple[str, str, str, HuntZoneKnowledgeDTO]:
    external_id, page_title, wikitext, params = _envelope(raw)
    name, name_supplied = _text(params, "name", "actualname")
    canonical_name = name or page_title
    city, city_supplied = _text(params, "city")
    location_raw, location_supplied = _first(params, "location")
    location_without_coordinates = _MAPPER_EXTERNAL_REFERENCE.sub(
        "",
        _MAPPER_COORDS_REFERENCE.sub("", location_raw or ""),
    )
    location = _strip_markup(location_without_coordinates) or None
    implemented, implemented_supplied = _text(params, "implemented")
    vocation_text, vocation_supplied = _text(params, "vocation", "vocations")
    experience, experience_supplied = _text(params, "exp", "experience")
    loot, loot_supplied = _text(params, "loot", "profit")
    experience_rating_raw, experience_rating_supplied = _first(params, "expstar", "expstars")
    loot_rating_raw, loot_rating_supplied = _first(params, "lootstar", "lootstars")
    premium_raw, premium_supplied = _first(params, "premium", "premiumonly", "premium required")
    access_notes, access_supplied = _text(params, "access", "accessnotes", "access notes")
    body_access, explicit_quests = _access_body_evidence(wikitext)
    if access_notes is None and body_access:
        access_notes = body_access
        access_supplied = True

    recommendations, recommendation_keys = _recommendations(params)
    creatures = _creature_names(wikitext)
    creature_lists_supplied = bool(_CREATURE_LIST.search(wikitext))
    best_loot_values = [params[key] for key in sorted(params) if re.fullmatch(r"bestloot\d+", key)]
    best_loot = tuple(dict.fromkeys(name for value in best_loot_values for name in _linked_names(value)))
    maps_raw, maps_supplied = _first(params, "maps", "map")
    map_references = _linked_names(maps_raw)
    image_raw, image_supplied = _first(params, "image")
    image_reference = _provider_image_reference(image_raw)

    supplied = frozenset(key for key, flag in {
        "canonical_name": name_supplied,
        "city": city_supplied,
        "location": location_supplied,
        "implemented": implemented_supplied,
        "vocation_text": vocation_supplied,
        "vocation_recommendations": bool(recommendation_keys),
        "premium_required": premium_supplied,
        "access_notes": access_supplied,
        "access_quests": bool(explicit_quests),
        "creatures": creature_lists_supplied,
        "experience": experience_supplied,
        "experience_rating": experience_rating_supplied,
        "loot": loot_supplied,
        "loot_rating": loot_rating_supplied,
        "best_loot": bool(best_loot_values),
        "map_references": maps_supplied,
        "image_reference": image_supplied and image_reference is not None,
        "source_reference": True,
        "slug": True,
    }.items() if flag)
    aliases = () if normalize_name(page_title) == normalize_name(canonical_name) else (page_title,)
    dto = HuntZoneKnowledgeDTO(
        external_id=external_id,
        canonical_name=canonical_name,
        slug=slugify(canonical_name),
        aliases=aliases,
        city=city,
        location=location,
        implemented=implemented,
        vocation_text=vocation_text,
        vocation_recommendations=recommendations,
        premium_required=_to_bool(premium_raw) if premium_supplied and str(premium_raw).strip() else None,
        access_notes=access_notes,
        access_quests=tuple(value.name for value in explicit_quests),
        creatures=creatures,
        experience=experience,
        experience_rating=_to_int(experience_rating_raw),
        loot=loot,
        loot_rating=_to_int(loot_rating_raw),
        best_loot=best_loot,
        map_references=map_references,
        image_reference=image_reference,
        source_reference=_build_wiki_page_url(page_title),
        provider_metadata={
            "page_title": page_title,
            "template_parameters": sorted(params),
            "recommendation_parameters": list(recommendation_keys),
            "access_evidence": "body" if body_access else "infobox" if access_supplied else None,
            "image_asset_name": _strip_markup(image_raw or "") or None,
            "source_entity_evidence": (
                "category:hunting_places+template:infobox_hunt"
                if _is_structured_hunt_entity(wikitext)
                else "category_membership_only"
            ),
        },
        supplied_fields=supplied,
    )
    return external_id, page_title, wikitext, replace(dto, is_partial=not dto.sufficient_detail)


class TibiaWikiHuntZoneAdapter:
    provider_code = "tibiawiki"
    job_types = ("hunt_zone_catalog", "hunt_zone_detail", "hunt_zone_renormalize")

    def __init__(self, client: TibiaWikiNamedEntityClient | None = None):
        self.client = client or HttpTibiaWikiNamedEntityClient("Hunting Places")

    def supports(self, job_type: str, entity_type: str | None) -> bool:
        return entity_type == "hunt_zone" and job_type in self.job_types

    def validate_enqueue(self, job_type: str, scope: dict, payload: dict) -> None:
        if job_type == "hunt_zone_catalog":
            limit = scope.get("batch_limit")
            if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= MAX_HUNT_ZONE_CATALOG_BATCH:
                raise ValueError("Catalog jobs require an explicit batch_limit between 1 and 50")
            if payload or set(scope) != {"batch_limit"}:
                raise ValueError("Manual catalog jobs accept only batch_limit")
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
        if job_type == "hunt_zone_renormalize" and not external_id:
            raise ValueError("Renormalization requires the stable external ID")

    def fetch(self, request: KnowledgeFetchRequest) -> KnowledgeFetchResult:
        if request.job_type == "hunt_zone_catalog":
            return self._fetch_catalog(request)
        stored = request.job_type == "hunt_zone_renormalize" and "_stored_document" in request.payload
        raw = request.payload.get("_stored_document") if stored else self.client.fetch_detail(
            external_id=str(request.payload.get("external_id") or "").strip() or None,
            page_title=str(request.payload.get("page_title") or "").strip() or None,
        )
        if not isinstance(raw, dict):
            raise MalformedProviderPayloadError()
        if _serialized_size(raw) > MAX_CREATURE_PAYLOAD_BYTES:
            raise OversizedProviderResponseError()
        if raw.get("error"):
            raise ProviderResponseEnvelopeError()
        external_id, page_title, _wikitext, dto = _hunt_zone_parts(raw)
        return KnowledgeFetchResult(
            documents=(KnowledgeDocumentDTO(
                self.provider_code,
                f"hunt_zone:{external_id}",
                raw,
                version="mediawiki-v1",
                language="en",
                metadata={"document_kind": "hunt_zone_detail", "external_id": external_id, "page_title": page_title},
            ),),
            partial=dto.is_partial,
            provider_metadata={"source": "stored_document" if stored else "tibiawiki"},
        )

    def _fetch_catalog(self, request: KnowledgeFetchRequest) -> KnowledgeFetchResult:
        continuation = str(request.scope.get("continuation") or "").strip() or None
        limit = int(request.scope["batch_limit"])
        raw = self.client.fetch_catalog(continuation=continuation, limit=limit)
        if not isinstance(raw, dict) or _serialized_size(raw) > MAX_CREATURE_PAYLOAD_BYTES:
            raise OversizedProviderResponseError()
        if raw.get("error"):
            raise ProviderResponseEnvelopeError()
        members = (raw.get("query") or {}).get("categorymembers")
        if not isinstance(members, list):
            raise MalformedProviderPayloadError()
        children: list[KnowledgeChildJobRequest] = []
        invalid = 0
        for member in members:
            external_id = str(member.get("pageid") or "").strip() if isinstance(member, dict) else ""
            title = str(member.get("title") or "").strip() if isinstance(member, dict) else ""
            if (
                not external_id.isdigit()
                or not title
                or ":" in title
                or len(title) > 255
                or normalize_name(title) == "hunting places"
            ):
                invalid += 1
                continue
            children.append(KnowledgeChildJobRequest(
                job_type="hunt_zone_detail",
                entity_type="hunt_zone",
                payload={"external_id": external_id, "page_title": title},
                priority=100,
                allow_completed_recreate=True,
            ))
        next_token = str((raw.get("continue") or {}).get("cmcontinue") or "").strip() or None
        if next_token:
            children.append(KnowledgeChildJobRequest(
                job_type="hunt_zone_catalog",
                entity_type="hunt_zone",
                scope={"batch_limit": limit, "continuation": next_token},
                priority=90,
                allow_completed_recreate=True,
            ))
        return KnowledgeFetchResult(
            documents=(KnowledgeDocumentDTO(
                self.provider_code,
                f"catalog:hunt_zone:{continuation or 'first'}",
                raw,
                version="mediawiki-v1",
                metadata={"document_kind": "hunt_zone_catalog", "batch_limit": limit},
            ),),
            cursor={"continuation": next_token} if next_token else None,
            partial=bool(invalid),
            provider_metadata={"invalid_members": invalid},
            child_jobs=tuple(children),
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
            if document.metadata.get("document_kind") == "hunt_zone_catalog":
                if not isinstance((document.raw_json.get("query") or {}).get("categorymembers"), list):
                    return KnowledgeValidationResult(False, classification="invalid", safe_errors=("invalid_catalog",))
                continue
            try:
                _external_id, _title, wikitext, dto = _hunt_zone_parts(document.raw_json)
            except (KeyError, TypeError, ValueError, MalformedProviderPayloadError):
                return KnowledgeValidationResult(False, classification="invalid", safe_errors=("invalid_detail",))
            if _UNSAFE_TEXT.search(wikitext):
                return KnowledgeValidationResult(False, classification="invalid", safe_errors=("unsafe_text",))
            if not dto.external_id or not dto.canonical_name.strip():
                return KnowledgeValidationResult(False, classification="invalid", safe_errors=("required_fields",))
            partial = partial or dto.is_partial
        return KnowledgeValidationResult(True, classification="partial" if partial else "valid")

    def normalize(self, document: KnowledgeDocumentDTO, context: KnowledgeNormalizationContext) -> KnowledgeNormalizationResult:
        if document.metadata.get("document_kind") != "hunt_zone_detail":
            return KnowledgeNormalizationResult(action="noop")
        _external_id, _title, wikitext, dto = _hunt_zone_parts(document.raw_json)
        if not _is_structured_hunt_entity(wikitext):
            return KnowledgeNormalizationResult(
                action="noop",
                warnings=("unstructured_hunt_zone_page",),
                provider_code=self.provider_code,
                external_id=dto.external_id,
            )
        return KnowledgeNormalizationResult(
            action="upsert",
            candidate=CanonicalEntityCandidate(
                entity_type="hunt_zone",
                canonical_name=dto.canonical_name,
                language_neutral_id=dto.language_neutral_id,
                aliases=dto.aliases,
                source_priority=20,
            ),
            warnings=("partial_hunt_zone_detail",) if dto.is_partial else (),
            provider_code=self.provider_code,
            external_id=dto.external_id,
            canonical_data=dto.to_canonical_data(),
        )
