"""Bounded TibiaWiki Quest adapter with conservative wikitext normalization."""

from __future__ import annotations

import json
import re
from dataclasses import replace
from typing import Any, Protocol
from urllib.parse import quote

from app.core.config import settings
from app.knowledge.adapters.protocol import (
    CanonicalEntityCandidate, KnowledgeChildJobRequest, KnowledgeDocumentDTO,
    KnowledgeFetchRequest, KnowledgeFetchResult, KnowledgeNormalizationContext,
    KnowledgeNormalizationResult, KnowledgeValidationResult,
)
from app.knowledge.adapters.tibiawiki_creatures import HttpTibiaWikiCreatureClient, MAX_CREATURE_PAYLOAD_BYTES
from app.knowledge.dto import (
    QuestAccessReference, QuestItemReference, QuestKnowledgeDTO, QuestMissionDTO, QuestNamedReference,
)
from app.knowledge.indexing import normalize_name
from app.knowledge.services.failures import (
    MalformedProviderPayloadError, OversizedProviderResponseError, ProviderResponseEnvelopeError,
)
from app.services.bestiary_source import (
    _build_wiki_page_url, _extract_infobox_param_map, _extract_links, _strip_markup, _to_bool, _to_int,
)
from app.services.text_utils import slugify


MAX_QUEST_PAYLOAD_BYTES = MAX_CREATURE_PAYLOAD_BYTES
MAX_QUEST_CATALOG_BATCH = 50
MAX_QUEST_CHILDREN = 50
_UNSAFE_TEXT = re.compile(r"<\s*script\b|javascript\s*:|\bon(?:error|load)\s*=", re.I)
_HEADING = re.compile(r"^(={2,5})\s*(.+?)\s*\1\s*$")
_MISSION_TITLE = re.compile(r"^(?:(?:mission|task|chapter)\s*(\d+)\s*[:\-]?\s*)?(.+)$", re.I)
_QUEST_LINK_WORDS = ("quest", "challenge", "arena", "mission", "task", "adventure")
_SKIP_LINKS = {"quests", "quest log", "access quests", "main page", "help"}


class TibiaWikiQuestClient(Protocol):
    def fetch_catalog(self, *, continuation: str | None, limit: int) -> dict[str, Any]: ...
    def fetch_detail(self, *, external_id: str | None, page_title: str | None) -> dict[str, Any]: ...


class HttpTibiaWikiQuestClient(HttpTibiaWikiCreatureClient):
    def fetch_catalog(self, *, continuation: str | None, limit: int) -> dict[str, Any]:
        params: dict[str, Any] = {
            "action": "query", "list": "categorymembers", "cmtitle": "Category:Quests",
            "cmtype": "page", "cmlimit": limit, "format": "json",
        }
        if continuation:
            params["cmcontinue"] = continuation
        return self._request(params)

    def fetch_detail(self, *, external_id: str | None, page_title: str | None) -> dict[str, Any]:
        params: dict[str, Any] = {"action": "parse", "prop": "wikitext|links", "format": "json"}
        if external_id and external_id.isdigit():
            params["pageid"] = external_id
        elif page_title:
            params["page"] = page_title
        else:
            raise ValueError("Quest detail requires an external ID or page title")
        return self._request(params)


def _serialized_size(value: dict[str, Any]) -> int:
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def _first(params: dict[str, str], *keys: str) -> tuple[str | None, bool]:
    for key in keys:
        if key in params:
            return params[key], True
    return None, False


def _text(params: dict[str, str], *keys: str) -> tuple[str | None, bool]:
    raw, supplied = _first(params, *keys)
    return (_strip_markup(raw or "") or None), supplied


def _number(params: dict[str, str], *keys: str) -> tuple[int | None, bool]:
    raw, supplied = _first(params, *keys)
    return _to_int(raw), supplied


def _boolean(params: dict[str, str], *keys: str) -> tuple[bool | None, bool]:
    raw, supplied = _first(params, *keys)
    return (_to_bool(raw) if supplied else None), supplied


def _name_values(raw: str | None) -> tuple[QuestNamedReference, ...]:
    if not raw:
        return ()
    names = _extract_links(raw)
    if not names:
        names = [part.strip() for part in re.split(r"[,;\n]", _strip_markup(raw)) if part.strip()]
    return tuple(QuestNamedReference(name=name) for name in dict.fromkeys(names) if name)


def _item_values(raw: str | None) -> tuple[QuestItemReference, ...]:
    if not raw:
        return ()
    found: list[QuestItemReference] = []
    for match in re.finditer(r"(?:(\d+)\s*[xX]?\s*)?\[\[([^\]|#]+)(?:\|[^\]]+)?\]\]", raw):
        found.append(QuestItemReference(name=_strip_markup(match.group(2)), amount=int(match.group(1) or 1)))
    if not found:
        for name in _name_values(raw):
            amount_match = re.match(r"^(\d+)\s*[xX]?\s+(.+)$", name.name)
            found.append(QuestItemReference(
                name=amount_match.group(2) if amount_match else name.name,
                amount=int(amount_match.group(1)) if amount_match else 1,
            ))
    deduped: dict[tuple[str, int], QuestItemReference] = {}
    for item in found:
        if item.name:
            deduped[(normalize_name(item.name), item.amount)] = item
    return tuple(deduped.values())


def _sections(wikitext: str) -> list[tuple[int, str, list[str]]]:
    result: list[tuple[int, str, list[str]]] = []
    current: tuple[int, str, list[str]] | None = None
    for line in wikitext.splitlines():
        match = _HEADING.match(line.strip())
        if match:
            current = (len(match.group(1)), _strip_markup(match.group(2)), [])
            result.append(current)
        elif current is not None:
            current[2].append(line)
    return result


def _labeled_references(lines: list[str], labels: tuple[str, ...], *, items: bool = False):
    values: list[Any] = []
    for line in lines:
        cleaned = line.strip().lstrip("*#;: ")
        match = re.match(r"^([^:]{2,40}):\s*(.+)$", cleaned)
        if not match or normalize_name(match.group(1)) not in labels:
            continue
        values.extend(_item_values(match.group(2)) if items else _name_values(match.group(2)))
    return tuple(values)


def _parse_missions(wikitext: str) -> tuple[tuple[QuestMissionDTO, ...], list[dict[str, str]], bool]:
    in_missions = False
    missions: list[QuestMissionDTO] = []
    unparsed: list[dict[str, str]] = []
    saw_mission_section = False
    for level, heading, lines in _sections(wikitext):
        normalized_heading = normalize_name(heading)
        if level == 2:
            in_missions = normalized_heading in {"mission", "missions", "tasks", "walkthrough"}
            saw_mission_section = saw_mission_section or in_missions
            if not in_missions and lines:
                safe_text = _strip_markup("\n".join(lines))[:4000]
                if safe_text:
                    unparsed.append({"heading": heading[:255], "text": safe_text})
            continue
        if not in_missions or level < 3:
            continue
        title_match = _MISSION_TITLE.match(heading)
        if not title_match:
            continue
        sequence = int(title_match.group(1)) if title_match.group(1) else len(missions) + 1
        title = (title_match.group(2) or heading).strip()
        objectives: list[str] = []
        prose: list[str] = []
        labels = {"required item", "required items", "requirements", "reward", "rewards", "npc", "npcs", "creature", "creatures", "location", "locations"}
        for line in lines:
            raw = line.strip()
            if not raw:
                continue
            label = re.match(r"^[*#]?\s*([^:]{2,40}):\s*(.+)$", raw)
            if label and normalize_name(label.group(1)) in labels:
                continue
            safe = _strip_markup(raw.lstrip("*#;: "))
            if not safe:
                continue
            (objectives if raw.startswith(("*", "#")) else prose).append(safe)
        required_items = _labeled_references(lines, ("required item", "required items", "requirements"), items=True)
        rewarded_items = _labeled_references(lines, ("reward", "rewards"), items=True)
        npcs = _labeled_references(lines, ("npc", "npcs"))
        creatures = _labeled_references(lines, ("creature", "creatures"))
        locations = _labeled_references(lines, ("location", "locations"))
        supplied = {key for key, value in {
            "description": prose, "objectives": objectives, "required_items": required_items,
            "rewarded_items": rewarded_items, "related_npcs": npcs,
            "related_creatures": creatures, "locations": locations,
        }.items() if value}
        missions.append(QuestMissionDTO(
            external_id=None, title=title, sequence=sequence,
            description=" ".join(prose) or None, objectives=tuple(objectives),
            required_items=required_items, rewarded_items=rewarded_items,
            related_npcs=npcs, related_creatures=creatures, locations=locations,
            supplied_fields=frozenset(supplied),
        ))
    return tuple(missions), unparsed, saw_mission_section


def _candidate_quest_links(raw: dict[str, Any], page_title: str) -> list[str]:
    links = (raw.get("parse") or {}).get("links") or []
    candidates: list[str] = []
    seen: set[str] = set()
    for entry in links:
        title = str((entry or {}).get("*") or "").strip() if isinstance(entry, dict) else ""
        normalized = normalize_name(title)
        if not title or ":" in title or normalized == normalize_name(page_title) or normalized in _SKIP_LINKS or normalized in seen or not any(word in normalized for word in _QUEST_LINK_WORDS):
            continue
        seen.add(normalized)
        candidates.append(title)
        if len(candidates) >= MAX_QUEST_CHILDREN:
            break
    return candidates


def _quest_parts(raw: dict[str, Any]) -> tuple[str, str, str, QuestKnowledgeDTO]:
    parsed = raw.get("parse")
    if not isinstance(parsed, dict):
        raise MalformedProviderPayloadError()
    external_id = str(parsed.get("pageid") or "").strip()
    page_title = str(parsed.get("title") or "").strip()
    node = parsed.get("wikitext")
    wikitext = node.get("*") if isinstance(node, dict) else None
    if not external_id or not external_id.isdigit() or not page_title or not isinstance(wikitext, str) or not wikitext.strip():
        raise MalformedProviderPayloadError()
    params = _extract_infobox_param_map(wikitext)
    canonical, canonical_supplied = _text(params, "name", "actualname")
    canonical_name = canonical or page_title
    quest_type, quest_type_supplied = _text(params, "questtype", "type")
    category, category_supplied = _text(params, "category")
    difficulty, difficulty_supplied = _text(params, "difficulty")
    duration, duration_supplied = _text(params, "duration", "estimatedduration")
    minimum, minimum_supplied = _number(params, "level", "minlevel", "minimumlevel")
    maximum, maximum_supplied = _number(params, "maxlevel", "maximumlevel")
    experience, experience_supplied = _number(params, "experience", "expreward", "experience reward")
    premium, premium_supplied = _boolean(params, "premium", "premiumonly", "premium required")
    repeatable, repeatable_supplied = _boolean(params, "repeatable")
    solo, solo_supplied = _boolean(params, "solopossible", "solo")
    description, description_supplied = _text(params, "description")
    summary, summary_supplied = _text(params, "summary", "shortdescription")
    starting_raw, starting_supplied = _first(params, "questgiver", "startnpc", "npc")
    related_npcs_raw, related_npcs_supplied = _first(params, "relatednpcs", "npcs")
    required_items_raw, required_items_supplied = _first(params, "requireditems", "itemsrequired")
    rewards_raw, rewards_supplied = _first(params, "reward", "rewards", "treasure")
    required_quests_raw, required_quests_supplied = _first(params, "requiredquests", "prerequisites", "requiredquest")
    unlocked_quests_raw, unlocked_quests_supplied = _first(params, "unlockedquests", "unlocksquests")
    creatures_raw, creatures_supplied = _first(params, "creatures", "requiredcreatures")
    bosses_raw, bosses_supplied = _first(params, "bosses", "boss")
    locations_raw, locations_supplied = _first(params, "locations", "location", "startinglocation")
    access_raw, access_supplied = _first(params, "access", "accessunlocks", "unlocksaccess")
    missions, unparsed_sections, saw_mission_section = _parse_missions(wikitext)
    child_links = _candidate_quest_links(raw, page_title)
    is_group = bool(child_links) and not missions
    image_raw, image_supplied = _first(params, "image")
    image_name = (_extract_links(image_raw or "") or [_strip_markup(image_raw or "")])[0] if image_raw else ""
    image_reference = f"{settings.TIBIAWIKI_BASE_PAGE_URL}/Special:FilePath/{quote(image_name)}" if image_name else None
    flags = {
        "canonical_name": canonical_supplied, "quest_type": quest_type_supplied, "category": category_supplied,
        "difficulty": difficulty_supplied, "estimated_duration": duration_supplied,
        "minimum_level": minimum_supplied, "maximum_level": maximum_supplied,
        "experience_reward": experience_supplied, "premium_required": premium_supplied,
        "repeatable": repeatable_supplied, "solo_possible": solo_supplied,
        "description": description_supplied, "summary": summary_supplied,
        "starting_npcs": starting_supplied, "related_npcs": related_npcs_supplied,
        "required_items": required_items_supplied, "rewarded_items": rewards_supplied,
        "required_quests": required_quests_supplied, "unlocked_quests": unlocked_quests_supplied,
        "required_creatures": creatures_supplied, "bosses": bosses_supplied,
        "locations": locations_supplied, "access_unlocks": access_supplied,
        "missions": saw_mission_section, "image_reference": image_supplied,
        "source_reference": True, "slug": True, "is_group": bool(child_links),
    }
    supplied_fields = frozenset(key for key, supplied in flags.items() if supplied)
    aliases = () if normalize_name(page_title) == normalize_name(canonical_name) else (page_title,)
    dto = QuestKnowledgeDTO(
        external_id=external_id, canonical_name=canonical_name, slug=slugify(canonical_name), aliases=aliases,
        quest_type=quest_type, category=category, difficulty=difficulty, estimated_duration=duration,
        minimum_level=minimum, maximum_level=maximum, experience_reward=experience,
        premium_required=premium, repeatable=repeatable, solo_possible=solo,
        description=description, summary=summary, is_group=is_group,
        starting_npcs=_name_values(starting_raw), related_npcs=_name_values(related_npcs_raw),
        required_items=_item_values(required_items_raw), rewarded_items=_item_values(rewards_raw),
        required_quests=_name_values(required_quests_raw), unlocked_quests=_name_values(unlocked_quests_raw),
        required_creatures=_name_values(creatures_raw), bosses=_name_values(bosses_raw),
        locations=_name_values(locations_raw),
        access_unlocks=tuple(QuestAccessReference(name=value.name) for value in _name_values(access_raw)),
        missions=missions, image_reference=image_reference, source_reference=_build_wiki_page_url(page_title),
        provider_metadata={"page_title": page_title, "template_parameters": sorted(params), "unparsed_sections": unparsed_sections, "child_quest_links": child_links},
        supplied_fields=supplied_fields,
    )
    partial = (saw_mission_section and not missions) or not dto.sufficient_detail
    return external_id, page_title, wikitext, replace(dto, is_partial=partial)


class TibiaWikiQuestAdapter:
    provider_code = "tibiawiki"
    job_types = ("quest_catalog", "quest_detail", "quest_renormalize")

    def __init__(self, client: TibiaWikiQuestClient | None = None):
        self.client = client or HttpTibiaWikiQuestClient()

    def supports(self, job_type: str, entity_type: str | None) -> bool:
        return entity_type == "quest" and job_type in self.job_types

    def validate_enqueue(self, job_type: str, scope: dict, payload: dict) -> None:
        if job_type == "quest_catalog":
            limit = scope.get("batch_limit")
            if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= MAX_QUEST_CATALOG_BATCH:
                raise ValueError("Quest catalog jobs require an explicit batch_limit between 1 and 50")
            if payload or set(scope) != {"batch_limit"}:
                raise ValueError("Manual quest catalog jobs accept only batch_limit")
            return
        allowed = {"external_id", "page_title", "parent_page"}
        if set(payload) - allowed or set(scope) - {"language"}:
            raise ValueError("Quest detail jobs accept only stable identifiers and parent context")
        external_id = str(payload.get("external_id") or "").strip()
        page_title = str(payload.get("page_title") or "").strip()
        parent_page = str(payload.get("parent_page") or "").strip()
        if not external_id and not page_title:
            raise ValueError("Quest detail jobs require an external ID or page title")
        if external_id and (not external_id.isdigit() or len(external_id) > 20):
            raise ValueError("TibiaWiki quest external IDs must be numeric page IDs")
        for value in (page_title, parent_page):
            if value and (len(value) > 255 or any(ord(character) < 32 for character in value)):
                raise ValueError("Quest page titles must be safe and no longer than 255 characters")
        if job_type == "quest_renormalize" and not external_id:
            raise ValueError("Quest renormalization requires the stable external ID")

    def fetch(self, request: KnowledgeFetchRequest) -> KnowledgeFetchResult:
        if request.job_type == "quest_catalog":
            return self._fetch_catalog(request)
        if request.job_type == "quest_renormalize" and "_stored_document" in request.payload:
            raw = request.payload["_stored_document"]
            if not isinstance(raw, dict):
                raise MalformedProviderPayloadError()
        else:
            raw = self.client.fetch_detail(
                external_id=str(request.payload.get("external_id") or "").strip() or None,
                page_title=str(request.payload.get("page_title") or "").strip() or None,
            )
        if _serialized_size(raw) > MAX_QUEST_PAYLOAD_BYTES:
            raise OversizedProviderResponseError()
        if raw.get("error"):
            raise ProviderResponseEnvelopeError()
        external_id, page_title, _wikitext, dto = _quest_parts(raw)
        parent_page = str(request.payload.get("parent_page") or "").strip() or None
        children = tuple(
            KnowledgeChildJobRequest(job_type="quest_detail", entity_type="quest", payload={"page_title": child, "parent_page": page_title}, priority=100, allow_completed_recreate=True)
            for child in dto.provider_metadata.get("child_quest_links", [])
        ) if dto.is_group else ()
        return KnowledgeFetchResult(
            documents=(self._detail_document(raw, external_id, page_title, parent_page),),
            partial=dto.is_partial,
            provider_metadata={"source": "stored_document" if request.job_type == "quest_renormalize" else "tibiawiki"},
            child_jobs=children,
        )

    def _fetch_catalog(self, request: KnowledgeFetchRequest) -> KnowledgeFetchResult:
        continuation = str(request.scope.get("continuation") or "").strip() or None
        limit = int(request.scope["batch_limit"])
        raw = self.client.fetch_catalog(continuation=continuation, limit=limit)
        if _serialized_size(raw) > MAX_QUEST_PAYLOAD_BYTES:
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
            if not external_id.isdigit() or not title or ":" in title or len(title) > 255:
                invalid += 1
                continue
            children.append(KnowledgeChildJobRequest(job_type="quest_detail", entity_type="quest", payload={"external_id": external_id, "page_title": title}, priority=100, allow_completed_recreate=True))
        next_token = str((raw.get("continue") or {}).get("cmcontinue") or "").strip() or None
        if next_token:
            children.append(KnowledgeChildJobRequest(job_type="quest_catalog", entity_type="quest", scope={"batch_limit": limit, "continuation": next_token}, priority=90, allow_completed_recreate=True))
        return KnowledgeFetchResult(
            documents=(KnowledgeDocumentDTO(self.provider_code, f"catalog:quests:{continuation or 'first'}", raw, version="mediawiki-v1", metadata={"document_kind": "quest_catalog", "batch_limit": limit}),),
            cursor={"continuation": next_token, "members_processed": len(children) - int(bool(next_token))},
            partial=invalid > 0, provider_metadata={"invalid_members": invalid}, child_jobs=tuple(children),
        )

    def _detail_document(self, raw: dict[str, Any], external_id: str, page_title: str, parent_page: str | None) -> KnowledgeDocumentDTO:
        return KnowledgeDocumentDTO(
            self.provider_code, f"quest:{external_id}", raw, version="mediawiki-v1", language="en",
            metadata={"document_kind": "quest_detail", "external_id": external_id, "page_title": page_title, "parent_page": parent_page},
        )

    def validate(self, result: KnowledgeFetchResult) -> KnowledgeValidationResult:
        if not result.documents:
            return KnowledgeValidationResult(False, classification="empty", safe_errors=("empty_response",))
        partial = result.partial
        for document in result.documents:
            if not isinstance(document.raw_json, dict):
                return KnowledgeValidationResult(False, classification="invalid", safe_errors=("invalid_envelope",))
            if _serialized_size(document.raw_json) > MAX_QUEST_PAYLOAD_BYTES:
                return KnowledgeValidationResult(False, classification="oversized", safe_errors=("oversized",))
            if document.raw_json.get("error"):
                return KnowledgeValidationResult(False, classification="provider_error", safe_errors=("provider_error",))
            if document.metadata.get("document_kind") == "quest_catalog":
                members = (document.raw_json.get("query") or {}).get("categorymembers")
                if not isinstance(members, list) or not members:
                    return KnowledgeValidationResult(False, classification="empty", safe_errors=("empty_catalog",))
                continue
            try:
                _external_id, _title, wikitext, dto = _quest_parts(document.raw_json)
            except (KeyError, TypeError, ValueError, MalformedProviderPayloadError):
                return KnowledgeValidationResult(False, classification="invalid", safe_errors=("invalid_detail",))
            if _UNSAFE_TEXT.search(wikitext):
                return KnowledgeValidationResult(False, classification="invalid", safe_errors=("unsafe_text",))
            if len(dto.canonical_name) > 255:
                return KnowledgeValidationResult(False, classification="invalid", safe_errors=("required_fields",))
            for number in (dto.minimum_level, dto.maximum_level, dto.experience_reward):
                if number is not None and (number < 0 or number > 2_147_483_647):
                    return KnowledgeValidationResult(False, classification="invalid", safe_errors=("numeric_range",))
            sequences = [mission.sequence for mission in dto.missions]
            if any(sequence < 1 or sequence > 1000 for sequence in sequences) or len(sequences) != len(set(sequences)):
                return KnowledgeValidationResult(False, classification="invalid", safe_errors=("mission_sequence",))
            all_items = [*dto.required_items, *dto.rewarded_items, *(item for mission in dto.missions for item in (*mission.required_items, *mission.rewarded_items))]
            if any(item.amount < 1 or item.amount > 1_000_000 for item in all_items):
                return KnowledgeValidationResult(False, classification="invalid", safe_errors=("item_amount",))
            partial = partial or dto.is_partial
        return KnowledgeValidationResult(True, classification="partial" if partial else "valid")

    def normalize(self, document: KnowledgeDocumentDTO, context: KnowledgeNormalizationContext) -> KnowledgeNormalizationResult:
        if document.metadata.get("document_kind") != "quest_detail":
            return KnowledgeNormalizationResult(action="noop")
        external_id, _title, _wikitext, dto = _quest_parts(document.raw_json)
        parent_page = document.metadata.get("parent_page")
        if isinstance(parent_page, str) and parent_page.strip():
            dto = replace(dto, parent_page=parent_page.strip(), group_name=parent_page.strip(), supplied_fields=dto.supplied_fields | {"parent_page", "group_name"})
        if dto.is_partial or not dto.sufficient_detail:
            return KnowledgeNormalizationResult(action="noop", warnings=("partial_quest_detail_not_normalized",))
        return KnowledgeNormalizationResult(
            action="upsert",
            candidate=CanonicalEntityCandidate(entity_type="quest", canonical_name=dto.canonical_name, language_neutral_id=dto.language_neutral_id, aliases=dto.aliases, source_priority=20, search_weight=1.0),
            provider_code=self.provider_code, external_id=external_id, canonical_data=dto.to_canonical_data(),
        )
