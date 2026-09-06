"""Item adapter for TibiaHub's configured TibiaWiki MediaWiki source."""

from __future__ import annotations

import json
import re
from dataclasses import replace
from typing import Any, Protocol

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
from app.knowledge.adapters.tibiawiki_creatures import (
    HttpTibiaWikiCreatureClient,
    MAX_CREATURE_PAYLOAD_BYTES,
)
from app.knowledge.dto import ItemCreatureReference, ItemKnowledgeDTO, ItemNpcReference
from app.knowledge.indexing import normalize_name
from app.knowledge.services.failures import (
    MalformedProviderPayloadError,
    OversizedProviderResponseError,
    ProviderResponseEnvelopeError,
)
from app.services.bestiary_source import (
    _build_wiki_page_url,
    _extract_infobox_param_map,
    _extract_links,
    _strip_markup,
    _to_bool,
    _to_int,
)
from app.services.media_evidence_service import explicit_provider_media_reference
from app.services.text_utils import slugify


MAX_ITEM_PAYLOAD_BYTES = MAX_CREATURE_PAYLOAD_BYTES
MAX_ITEM_CATALOG_BATCH = 50
_UNSAFE_TEXT = re.compile(r"<\s*script\b|javascript\s*:|\bon(?:error|load)\s*=", re.I)
_INVALID_ITEM_PLACEHOLDER_NAME_RE = re.compile(
    r"^\d+\s*-\s*\?$"
)


def _is_invalid_item_placeholder_name(
    value: str | None,
) -> bool:
    return bool(
        _INVALID_ITEM_PLACEHOLDER_NAME_RE.fullmatch(
            str(value or "").strip()
        )
    )


class TibiaWikiItemClient(Protocol):
    def fetch_catalog(self, *, continuation: str | None, limit: int) -> dict[str, Any]: ...

    def fetch_detail(self, *, external_id: str | None, page_title: str | None) -> dict[str, Any]: ...


class HttpTibiaWikiItemClient(HttpTibiaWikiCreatureClient):
    def fetch_catalog(self, *, continuation: str | None, limit: int) -> dict[str, Any]:
        params: dict[str, Any] = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": "Category:Pickupable Objects",
            "cmtype": "page",
            "cmlimit": limit,
            "format": "json",
        }
        if continuation:
            params["cmcontinue"] = continuation
        return self._request(params)


def _serialized_size(value: dict[str, Any]) -> int:
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def _catalog_members(raw: dict[str, Any]) -> list[Any] | None:
    query = raw.get("query") or {}
    members = query.get("categorymembers")
    if isinstance(members, list):
        return members
    legacy_members = query.get("embeddedin")
    return legacy_members if isinstance(legacy_members, list) else None


def _catalog_continuation(raw: dict[str, Any]) -> str | None:
    continuation = raw.get("continue") or {}
    return str(
        continuation.get("cmcontinue")
        or continuation.get("eicontinue")
        or ""
    ).strip() or None


def _first_param(params: dict[str, str], *keys: str) -> tuple[str | None, bool]:
    for key in keys:
        if key in params:
            return params[key], True
    return None, False


def _text_param(params: dict[str, str], *keys: str) -> tuple[str | None, bool]:
    raw, supplied = _first_param(params, *keys)
    return (_strip_markup(raw or "") or None), supplied


def _int_param(params: dict[str, str], *keys: str) -> tuple[int | None, bool]:
    raw, supplied = _first_param(params, *keys)
    return _to_int(raw), supplied


def _float_param(params: dict[str, str], *keys: str) -> tuple[float | None, bool]:
    raw, supplied = _first_param(params, *keys)
    if raw in (None, "", "--"):
        return None, supplied
    match = re.search(r"-?\d+(?:[.,]\d+)?", raw.replace(",", ""))
    return (float(match.group(0)) if match else None), supplied


def _list_param(params: dict[str, str], *keys: str) -> tuple[tuple[str, ...], bool]:
    raw, supplied = _first_param(params, *keys)
    if raw is None:
        return (), supplied

    text = _strip_markup(raw).strip()
    if text == "--":
        return (), supplied

    linked = _extract_links(raw)
    if linked:
        return tuple(dict.fromkeys(item.strip() for item in linked if item.strip())), supplied

    values = [item.strip() for item in re.split(r"[,;/]", text) if item.strip()]
    return tuple(dict.fromkeys(values)), supplied


def _npc_trade_param(
    params: dict[str, str],
    *keys: str,
) -> tuple[tuple[ItemNpcReference, ...], bool]:
    """Parse only explicit per-NPC prices; unspecified prices stay unknown."""
    raw, supplied = _first_param(params, *keys)
    if raw is None:
        return (), supplied
    text = _strip_markup(raw).strip()
    if not text or text.casefold() in {"-", "--", "n/a", "none", "unknown"}:
        return (), supplied
    protected = re.sub(r"(?<=\d),(?=\d)", "", text)
    values: list[ItemNpcReference] = []
    seen: set[tuple[str, int | float | None, str | None]] = set()
    for token in protected.split(","):
        candidate, separator, raw_qualifier = token.partition(";")
        candidate = candidate.strip()
        qualifier = raw_qualifier.strip() if separator else None
        # ``sayname`` is a MediaWiki display directive. Other suffixes (for
        # example a liquid contained by a vial) are real offer qualifiers.
        if qualifier and qualifier.casefold() == "sayname":
            qualifier = None
        if not candidate:
            continue
        match = re.match(r"^(.*?):\s*(\d+(?:\.\d+)?)(?:\s+(.+?))?$", candidate)
        name = (match.group(1) if match else candidate).strip()
        price_text = match.group(2) if match else None
        price = (
            float(price_text) if price_text and "." in price_text
            else int(price_text) if price_text
            else None
        )
        raw_currency = match.group(3).strip() if match and match.group(3) else None
        currency = (
            re.sub(r"[^a-z0-9]+", "_", raw_currency.casefold()).strip("_")
            if raw_currency
            else "gold_coin" if isinstance(price, int)
            else None
        )
        normalized = normalize_name(name)
        identity = (normalized, price, qualifier)
        if not normalized or name.casefold() in {"-", "--", "n/a", "none", "unknown"} or identity in seen:
            continue
        values.append(ItemNpcReference(
            name=name,
            price=price,
            currency=currency,
            qualifier=qualifier,
        ))
        seen.add(identity)
    return tuple(values), supplied


def _structured_values(params: dict[str, str], keys: tuple[str, ...]) -> tuple[dict[str, str], bool]:
    values: dict[str, str] = {}
    supplied = False
    for key in keys:
        if key not in params:
            continue
        supplied = True
        value = _strip_markup(params[key])
        if value:
            values[key] = value
    return values, supplied


def _item_parts(raw: dict[str, Any]) -> tuple[str, str, str, ItemKnowledgeDTO]:
    parsed = raw.get("parse")
    if not isinstance(parsed, dict):
        raise MalformedProviderPayloadError()
    external_id = str(parsed.get("pageid") or "").strip()
    page_title = str(parsed.get("title") or "").strip()
    wikitext_node = parsed.get("wikitext")
    wikitext = wikitext_node.get("*") if isinstance(wikitext_node, dict) else None
    if not external_id or not page_title or not isinstance(wikitext, str) or not wikitext.strip():
        raise MalformedProviderPayloadError()

    params = _extract_infobox_param_map(wikitext)
    media_evidence = explicit_provider_media_reference(wikitext, "item")
    canonical_raw, name_supplied = _text_param(params, "name", "actualname")
    canonical_name = canonical_raw or page_title
    game_item_id, game_item_id_supplied = _int_param(params, "itemid", "item id", "clientid", "client id")
    item_class, item_class_supplied = _text_param(params, "itemclass", "class")
    item_type, item_type_supplied = _text_param(params, "type", "primarytype", "primary type")
    category, category_supplied = _text_param(params, "category", "secondarytype", "secondary type")
    if category is None and item_type is not None:
        category = item_type
        category_supplied = item_type_supplied
    weight, weight_supplied = _float_param(params, "weight")
    value, value_supplied = _int_param(params, "value", "npcvalue", "sellvalue")
    level_requirement, level_supplied = _int_param(params, "levelrequired", "requiredlevel", "level")
    vocations, vocation_supplied = _list_param(params, "vocationrequired", "vocation", "vocations")
    attack, attack_supplied = _int_param(params, "attack", "atk")
    defense, defense_supplied = _int_param(params, "defense", "def")
    armor, armor_supplied = _int_param(params, "armor", "arm")
    item_range, range_supplied = _int_param(params, "range")
    slots, slots_supplied = _list_param(params, "slots", "slot", "bodyposition")
    imbuement_slots, imbuement_supplied = _int_param(params, "imbueslots", "imbuementslots")
    description, description_supplied = _text_param(params, "flavortext", "description")
    notes, notes_supplied = _text_param(params, "notes", "note")
    buy_from, buy_supplied = _npc_trade_param(params, "buyfrom", "buy from")
    sell_to, sell_supplied = _npc_trade_param(params, "sellto", "sell to")
    creature_names, dropped_supplied = _list_param(params, "droppedby", "dropped by")
    rewards_from, rewards_supplied = _list_param(params, "rewardfrom", "rewardsfrom", "reward from")
    required_for, required_supplied = _list_param(params, "requiredfor", "required for")
    trade_raw, trade_supplied = _first_param(params, "tradeable", "tradable")
    stack_raw, stack_supplied = _first_param(params, "stackable")
    attributes, attributes_supplied = _structured_values(
        params,
        ("skillboost", "magicboost", "attackmodifier", "defensemodifier", "charges"),
    )
    resistances, resistances_supplied = _structured_values(
        params,
        ("physical", "earth", "fire", "energy", "ice", "holy", "death", "lifedrain", "manadrain"),
    )
    bonuses, bonuses_supplied = _structured_values(
        params,
        ("speed", "capacity", "regeneration", "criticalhit", "hitpoints", "manapoints"),
    )

    supplied_flags = {
        "canonical_name": name_supplied,
        "game_item_id": game_item_id_supplied,
        "item_class": item_class_supplied,
        "item_type": item_type_supplied,
        "category": category_supplied,
        "weight": weight_supplied,
        "value": value_supplied,
        "level_requirement": level_supplied,
        "vocation_requirements": vocation_supplied,
        "attack": attack_supplied,
        "defense": defense_supplied,
        "armor": armor_supplied,
        "range": range_supplied,
        "slots": slots_supplied,
        "imbuement_slots": imbuement_supplied,
        "attributes": attributes_supplied,
        "resistances": resistances_supplied,
        "bonuses": bonuses_supplied,
        "description": description_supplied,
        "notes": notes_supplied,
        "buy_from": buy_supplied,
        "sell_to": sell_supplied,
        "dropped_by": dropped_supplied,
        "rewards_from": rewards_supplied,
        "required_for": required_supplied,
        "tradeable": trade_supplied,
        "stackable": stack_supplied,
        "image_reference": media_evidence.eligible,
        "source_reference": True,
        "slug": True,
    }
    supplied_fields = frozenset(key for key, supplied in supplied_flags.items() if supplied)
    aliases = () if normalize_name(page_title) == normalize_name(canonical_name) else (page_title,)
    dto = ItemKnowledgeDTO(
        external_id=external_id,
        canonical_name=canonical_name,
        slug=slugify(canonical_name),
        aliases=aliases,
        game_item_id=game_item_id,
        item_class=item_class,
        item_type=item_type,
        category=category,
        weight=weight,
        value=value,
        level_requirement=level_requirement,
        vocation_requirements=vocations,
        attack=attack,
        defense=defense,
        armor=armor,
        range=item_range,
        slots=slots,
        imbuement_slots=imbuement_slots,
        attributes=attributes,
        resistances=resistances,
        bonuses=bonuses,
        description=description,
        notes=notes,
        buy_from=buy_from,
        sell_to=sell_to,
        dropped_by=tuple(ItemCreatureReference(name=name) for name in creature_names),
        rewards_from=rewards_from,
        required_for=required_for,
        tradeable=_to_bool(trade_raw) if trade_supplied else None,
        stackable=_to_bool(stack_raw) if stack_supplied else None,
        image_reference=media_evidence.source_url,
        source_reference=_build_wiki_page_url(page_title),
        provider_metadata={
            "page_title": page_title,
            "provider_category": category,
            "template_parameters": sorted(params),
            "media_evidence_status": media_evidence.state,
            "media_evidence_field": media_evidence.field_name,
        },
        supplied_fields=supplied_fields,
    )
    return external_id, page_title, wikitext, replace(dto, is_partial=not dto.sufficient_detail)


class TibiaWikiItemAdapter:
    provider_code = "tibiawiki"
    job_types = ("item_catalog", "item_detail", "item_renormalize")

    def __init__(self, client: TibiaWikiItemClient | None = None):
        self.client = client or HttpTibiaWikiItemClient()

    def supports(self, job_type: str, entity_type: str | None) -> bool:
        return entity_type == "item" and job_type in self.job_types

    def validate_enqueue(self, job_type: str, scope: dict, payload: dict) -> None:
        if job_type == "item_catalog":
            batch_limit = scope.get("batch_limit")
            if not isinstance(batch_limit, int) or isinstance(batch_limit, bool) or not 1 <= batch_limit <= MAX_ITEM_CATALOG_BATCH:
                raise ValueError("Item catalog jobs require an explicit batch_limit between 1 and 50")
            if payload or set(scope) != {"batch_limit"}:
                raise ValueError("Manual item catalog jobs accept only batch_limit")
            return
        allowed = {"external_id", "page_title"}
        if set(payload) - allowed or set(scope) - {"language"}:
            raise ValueError("Item detail jobs accept only stable identifiers")
        external_id = str(payload.get("external_id") or "").strip()
        page_title = str(payload.get("page_title") or "").strip()
        if not external_id and not page_title:
            raise ValueError("Item detail jobs require an external ID or page title")
        if external_id and (not external_id.isdigit() or len(external_id) > 20):
            raise ValueError("TibiaWiki item external IDs must be numeric page IDs")
        if page_title and (len(page_title) > 255 or any(ord(character) < 32 for character in page_title)):
            raise ValueError("Item page titles must be safe and no longer than 255 characters")
        if job_type == "item_renormalize" and not external_id:
            raise ValueError("Item renormalization requires the stable external ID")

    def fetch(self, request: KnowledgeFetchRequest) -> KnowledgeFetchResult:
        if request.job_type == "item_catalog":
            return self._fetch_catalog(request)
        if request.job_type == "item_renormalize" and "_stored_document" in request.payload:
            raw = request.payload["_stored_document"]
            if not isinstance(raw, dict):
                raise MalformedProviderPayloadError()
            external_id, page_title, _wikitext, dto = _item_parts(raw)
            return KnowledgeFetchResult(
                documents=(self._detail_document(raw, external_id, page_title),),
                partial=dto.is_partial,
                provider_metadata={"source": "stored_document"},
            )
        raw = self.client.fetch_detail(
            external_id=str(request.payload.get("external_id") or "").strip() or None,
            page_title=str(request.payload.get("page_title") or "").strip() or None,
        )
        if _serialized_size(raw) > MAX_ITEM_PAYLOAD_BYTES:
            raise OversizedProviderResponseError()
        if raw.get("error"):
            raise ProviderResponseEnvelopeError()
        external_id, page_title, _wikitext, dto = _item_parts(raw)
        return KnowledgeFetchResult(
            documents=(self._detail_document(raw, external_id, page_title),),
            partial=dto.is_partial,
            provider_metadata={"source": "tibiawiki"},
        )

    def _fetch_catalog(self, request: KnowledgeFetchRequest) -> KnowledgeFetchResult:
        continuation = str(request.scope.get("continuation") or "").strip() or None
        limit = int(request.scope["batch_limit"])
        raw = self.client.fetch_catalog(continuation=continuation, limit=limit)
        if _serialized_size(raw) > MAX_ITEM_PAYLOAD_BYTES:
            raise OversizedProviderResponseError()
        if raw.get("error"):
            raise ProviderResponseEnvelopeError()
        members = _catalog_members(raw)
        if members is None:
            raise MalformedProviderPayloadError()
        children: list[KnowledgeChildJobRequest] = []
        invalid_members = 0
        for member in members:
            external_id = str(member.get("pageid") or "").strip() if isinstance(member, dict) else ""
            title = str(member.get("title") or "").strip() if isinstance(member, dict) else ""
            if (
                not external_id
                or not title
                or ":" in title
                or title.lower() == "items"
                or title.lower().startswith("list of ")
                or _is_invalid_item_placeholder_name(title)
            ):
                invalid_members += 1
                continue
            children.append(
                KnowledgeChildJobRequest(
                    job_type="item_detail",
                    entity_type="item",
                    payload={"external_id": external_id, "page_title": title},
                    priority=100,
                    allow_completed_recreate=True,
                )
            )
        next_token = _catalog_continuation(raw)
        if next_token:
            children.append(
                KnowledgeChildJobRequest(
                    job_type="item_catalog",
                    entity_type="item",
                    scope={"batch_limit": limit, "continuation": next_token},
                    priority=90,
                    allow_completed_recreate=True,
                )
            )
        return KnowledgeFetchResult(
            documents=(
                KnowledgeDocumentDTO(
                    provider_code=self.provider_code,
                    provider_document_id=f"catalog:items:{continuation or 'first'}",
                    raw_json=raw,
                    version="mediawiki-v1",
                    metadata={
                        "document_kind": "item_catalog",
                        "batch_limit": limit,
                        "catalog_source": "Category:Pickupable Objects",
                    },
                ),
            ),
            cursor={"continuation": next_token, "members_processed": len(children) - int(bool(next_token))},
            partial=invalid_members > 0,
            provider_metadata={
                "invalid_members": invalid_members,
                "catalog_source": "Category:Pickupable Objects",
            },
            child_jobs=tuple(children),
        )

    def _detail_document(self, raw: dict[str, Any], external_id: str, page_title: str) -> KnowledgeDocumentDTO:
        return KnowledgeDocumentDTO(
            provider_code=self.provider_code,
            provider_document_id=f"item:{external_id}",
            raw_json=raw,
            version="mediawiki-v1",
            language="en",
            metadata={
                "document_kind": "item_detail",
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
            if _serialized_size(document.raw_json) > MAX_ITEM_PAYLOAD_BYTES:
                return KnowledgeValidationResult(False, classification="oversized", safe_errors=("oversized",))
            if document.raw_json.get("error"):
                return KnowledgeValidationResult(False, classification="provider_error", safe_errors=("provider_error",))
            if document.metadata.get("document_kind") == "item_catalog":
                members = _catalog_members(document.raw_json)
                if not isinstance(members, list) or not members:
                    return KnowledgeValidationResult(False, classification="empty", safe_errors=("empty_catalog",))
                continue
            try:
                _external_id, _page_title, wikitext, dto = _item_parts(document.raw_json)
            except (KeyError, TypeError, ValueError, MalformedProviderPayloadError):
                return KnowledgeValidationResult(False, classification="invalid", safe_errors=("invalid_detail",))
            if _UNSAFE_TEXT.search(wikitext):
                return KnowledgeValidationResult(False, classification="invalid", safe_errors=("unsafe_text",))
            if not dto.external_id or not dto.canonical_name.strip():
                return KnowledgeValidationResult(False, classification="invalid", safe_errors=("required_fields",))
            for value in (
                dto.game_item_id,
                dto.value,
                dto.level_requirement,
                dto.attack,
                dto.defense,
                dto.armor,
                dto.range,
                dto.imbuement_slots,
            ):
                if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value < 0 or value > 2_147_483_647):
                    return KnowledgeValidationResult(False, classification="invalid", safe_errors=("numeric_range",))
            if dto.weight is not None and (dto.weight < 0 or dto.weight > 1_000_000_000):
                return KnowledgeValidationResult(False, classification="invalid", safe_errors=("numeric_range",))
            for value in (dto.attributes, dto.resistances, dto.bonuses):
                if not isinstance(value, dict):
                    return KnowledgeValidationResult(False, classification="invalid", safe_errors=("nested_shape",))
            partial = partial or not dto.sufficient_detail
        return KnowledgeValidationResult(True, classification="partial" if partial else "valid")

    def normalize(
        self,
        document: KnowledgeDocumentDTO,
        context: KnowledgeNormalizationContext,
    ) -> KnowledgeNormalizationResult:
        if document.metadata.get("document_kind") != "item_detail":
            return KnowledgeNormalizationResult(action="noop")
        external_id, _page_title, _wikitext, dto = _item_parts(document.raw_json)

        if _is_invalid_item_placeholder_name(
            dto.canonical_name
        ):
            return KnowledgeNormalizationResult(
                action="noop",
                warnings=("invalid_item_placeholder_name",),
            )

        if not dto.sufficient_detail:
            return KnowledgeNormalizationResult(
                action="noop",
                warnings=("partial_item_detail_not_normalized",),
            )
        return KnowledgeNormalizationResult(
            action="upsert",
            candidate=CanonicalEntityCandidate(
                entity_type="item",
                canonical_name=dto.canonical_name,
                language_neutral_id=dto.language_neutral_id,
                aliases=dto.aliases,
                source_priority=20,
                search_weight=1.0,
            ),
            provider_code=self.provider_code,
            external_id=external_id,
            canonical_data=dto.to_canonical_data(),
        )
