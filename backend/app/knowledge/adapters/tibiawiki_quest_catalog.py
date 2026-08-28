"""Quest discovery and spoiler enrichment from TibiaWiki's canonical Quest sources."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import re
from typing import Any

from app.knowledge.adapters.protocol import (
    KnowledgeChildJobRequest,
    KnowledgeDocumentDTO,
    KnowledgeFetchRequest,
    KnowledgeFetchResult,
    KnowledgeNormalizationContext,
    KnowledgeNormalizationResult,
    KnowledgeValidationResult,
)
from app.knowledge.adapters.tibiawiki_quests import (
    MAX_QUEST_PAYLOAD_BYTES,
    HttpTibiaWikiQuestClient,
    TibiaWikiQuestAdapter,
    _serialized_size,
)
from app.knowledge.indexing import normalize_name
from app.knowledge.services.failures import OversizedProviderResponseError


QUEST_OVERVIEW_CATALOG = "Category:Quest Overview Pages"
QUEST_SPOILER_SUFFIX = "/Spoiler"
# Match exactly level-two headings. Without the negative lookahead, a line like
# ``=== Statistics ===`` also matches the level-two expression because the
# third ``=`` can be consumed by the capture group. That prematurely ends a
# Method section and lets nested evidence headings become fake missions.
_LEVEL_TWO_HEADING = re.compile(r"^\s*==(?!=)\s*(.+?)\s*==\s*$")
_NESTED_HEADING = re.compile(r"^\s*={3,5}\s*(.+?)\s*={3,5}\s*$")


def _has_template_param(wikitext: str, name: str) -> bool:
    return bool(re.search(rf"(?mi)^\s*\|\s*{re.escape(name)}\s*=", wikitext))


def _rename_template_param(wikitext: str, source: str, target: str) -> str:
    """Map a TibiaWiki template alias only when the canonical parser key is absent."""
    if _has_template_param(wikitext, target) or not _has_template_param(wikitext, source):
        return wikitext
    return re.sub(
        rf"(?mi)^(\s*\|\s*){re.escape(source)}(\s*=)",
        rf"\1{target}\2",
        wikitext,
        count=1,
    )


def _promote_method_to_mission(wikitext: str) -> str:
    """Expose a standalone ``Method`` section as one conservative mission.

    TibiaWiki keeps many short Quest walkthroughs in a top-level ``Method``
    section rather than under ``Missions``. The provider-neutral parser only
    treats nested headings under a mission container as mission records. This
    compatibility transform operates on a temporary parsing copy only: the
    retained KnowledgeDocument remains unchanged.

    Nested sections such as statistics are promoted back to level two so they
    do not become fake missions. Only the direct Method prose is treated as the
    mission body.
    """
    lines = wikitext.splitlines()
    for index, line in enumerate(lines):
        match = _LEVEL_TWO_HEADING.match(line)
        if not match or normalize_name(match.group(1)) != "method":
            continue

        end = len(lines)
        for candidate in range(index + 1, len(lines)):
            if _LEVEL_TWO_HEADING.match(lines[candidate]):
                end = candidate
                break

        first_nested = end
        for candidate in range(index + 1, end):
            if _NESTED_HEADING.match(lines[candidate]):
                first_nested = candidate
                break

        direct_text = "\n".join(lines[index + 1:first_nested]).strip()
        if not direct_text:
            return wikitext

        replacement = ["== Missions ==", "=== Method ==="]
        transformed = [*lines[:index], *replacement, *lines[index + 1:]]
        shift = len(replacement) - 1
        transformed_end = end + shift
        for candidate in range(index + len(replacement), transformed_end):
            nested = _NESTED_HEADING.match(transformed[candidate])
            if nested:
                transformed[candidate] = f"== {nested.group(1).strip()} =="
        return "\n".join(transformed)
    return wikitext


def _compatibility_document(document: KnowledgeDocumentDTO) -> KnowledgeDocumentDTO:
    """Adapt current TibiaWiki markup without mutating retained raw evidence."""
    if not isinstance(document.raw_json, dict):
        return document
    parsed = document.raw_json.get("parse")
    if not isinstance(parsed, dict):
        return document
    node = parsed.get("wikitext")
    wikitext = node.get("*") if isinstance(node, dict) else None
    if not isinstance(wikitext, str):
        return document

    # Current Infobox Quest pages use `lvl` for the required level and
    # `legend` for the short quest description. Translate aliases only in the
    # parsing copy. Also expose a standalone Method section as one mission.
    patched = _rename_template_param(wikitext, "lvl", "level")
    patched = _rename_template_param(patched, "legend", "description")
    patched = _promote_method_to_mission(patched)
    if patched == wikitext:
        return document

    raw = deepcopy(document.raw_json)
    raw["parse"]["wikitext"]["*"] = patched
    return replace(document, raw_json=raw)


class HttpTibiaWikiQuestOverviewClient(HttpTibiaWikiQuestClient):
    """Discover quest overview pages, never the mixed parent quest category."""

    def fetch_catalog(self, *, continuation: str | None, limit: int) -> dict[str, Any]:
        params: dict[str, Any] = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": QUEST_OVERVIEW_CATALOG,
            "cmtype": "page",
            "cmlimit": limit,
            "format": "json",
        }
        if continuation:
            params["cmcontinue"] = continuation
        return self._request(params)


class TibiaWikiOverviewQuestAdapter(TibiaWikiQuestAdapter):
    """Production Quest adapter using overview discovery plus auxiliary spoiler evidence."""

    job_types = (*TibiaWikiQuestAdapter.job_types, "quest_spoiler_detail")

    def __init__(self, client=None):
        super().__init__(client or HttpTibiaWikiQuestOverviewClient())

    def validate_enqueue(self, job_type: str, scope: dict, payload: dict) -> None:
        if job_type != "quest_spoiler_detail":
            return super().validate_enqueue(job_type, scope, payload)
        if scope or set(payload) != {"parent_external_id", "page_title"}:
            raise ValueError("Quest spoiler jobs require parent_external_id and page_title only")
        parent_external_id = str(payload.get("parent_external_id") or "").strip()
        page_title = str(payload.get("page_title") or "").strip()
        if not parent_external_id.isdigit() or not page_title.endswith(QUEST_SPOILER_SUFFIX):
            raise ValueError("Quest spoiler jobs require a numeric parent and a /Spoiler page")
        if len(page_title) > 263 or any(ord(character) < 32 for character in page_title):
            raise ValueError("Quest spoiler page titles must be safe")

    def fetch(self, request: KnowledgeFetchRequest) -> KnowledgeFetchResult:
        if request.job_type == "quest_spoiler_detail":
            raw = self.client.fetch_detail(
                external_id=None,
                page_title=str(request.payload.get("page_title") or "").strip(),
            )
            if _serialized_size(raw) > MAX_QUEST_PAYLOAD_BYTES:
                raise OversizedProviderResponseError()
            if raw.get("error"):
                # Most Quests do not have a dedicated spoiler page. Absence is
                # a successful no-op, not a failed knowledge job.
                return KnowledgeFetchResult(
                    documents=(),
                    provider_metadata={"spoiler_missing": True},
                )
            parsed = raw.get("parse") or {}
            spoiler_page_id = str(parsed.get("pageid") or "").strip()
            parent_external_id = str(request.payload["parent_external_id"])
            parent_title = str(request.payload["page_title"])[:-len(QUEST_SPOILER_SUFFIX)]
            document = KnowledgeDocumentDTO(
                self.provider_code,
                f"quest_spoiler:{parent_external_id}",
                raw,
                version="mediawiki-v1",
                language="en",
                metadata={
                    "document_kind": "quest_spoiler",
                    "parent_external_id": parent_external_id,
                    "parent_page_title": parent_title,
                    "spoiler_page_id": spoiler_page_id,
                    "page_title": str(request.payload["page_title"]),
                },
            )
            return KnowledgeFetchResult(
                documents=(document,),
                provider_metadata={"source": "tibiawiki_spoiler"},
            )

        result = super().fetch(request)
        if request.job_type != "quest_detail" or not result.documents:
            return result

        document = result.documents[0]
        external_id = str(document.metadata.get("external_id") or "").strip()
        page_title = str(document.metadata.get("page_title") or "").strip()
        if not external_id.isdigit() or not page_title or page_title.endswith(QUEST_SPOILER_SUFFIX):
            return result
        spoiler = KnowledgeChildJobRequest(
            job_type="quest_spoiler_detail",
            entity_type="quest",
            payload={
                "parent_external_id": external_id,
                "page_title": f"{page_title}{QUEST_SPOILER_SUFFIX}",
            },
            priority=95,
            allow_completed_recreate=True,
        )
        return replace(result, child_jobs=(*result.child_jobs, spoiler))

    def validate(self, result: KnowledgeFetchResult) -> KnowledgeValidationResult:
        if result.provider_metadata.get("spoiler_missing") and not result.documents:
            return KnowledgeValidationResult(True)
        compatible = replace(
            result,
            documents=tuple(_compatibility_document(document) for document in result.documents),
        )
        return super().validate(compatible)

    def normalize(
        self,
        document: KnowledgeDocumentDTO,
        context: KnowledgeNormalizationContext,
    ) -> KnowledgeNormalizationResult:
        compatible = _compatibility_document(document)
        if compatible.metadata.get("document_kind") != "quest_spoiler":
            return super().normalize(compatible, context)

        parent_external_id = str(compatible.metadata.get("parent_external_id") or "").strip()
        parent_title = str(compatible.metadata.get("parent_page_title") or "").strip()
        if not parent_external_id.isdigit() or not parent_title or not isinstance(compatible.raw_json, dict):
            return KnowledgeNormalizationResult(action="noop", warnings=("invalid_quest_spoiler_parent",))

        # Normalize the spoiler as additional evidence for the parent Quest,
        # never as a separate public Quest entity. The persisted raw document
        # keeps its actual spoiler page ID and title.
        raw = deepcopy(compatible.raw_json)
        parsed = raw.get("parse")
        if not isinstance(parsed, dict):
            return KnowledgeNormalizationResult(action="noop", warnings=("invalid_quest_spoiler_document",))
        parsed["pageid"] = int(parent_external_id)
        parsed["title"] = parent_title
        parent_document = replace(
            compatible,
            raw_json=raw,
            metadata={
                **compatible.metadata,
                "document_kind": "quest_detail",
                "external_id": parent_external_id,
                "page_title": parent_title,
            },
        )
        return TibiaWikiQuestAdapter.normalize(self, parent_document, context)
