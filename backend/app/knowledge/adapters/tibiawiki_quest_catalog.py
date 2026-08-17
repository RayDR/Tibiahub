"""Quest catalog discovery using TibiaWiki's canonical overview-page category."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import re
from typing import Any

from app.knowledge.adapters.protocol import (
    KnowledgeDocumentDTO,
    KnowledgeFetchResult,
    KnowledgeNormalizationContext,
    KnowledgeNormalizationResult,
    KnowledgeValidationResult,
)
from app.knowledge.adapters.tibiawiki_quests import (
    HttpTibiaWikiQuestClient,
    TibiaWikiQuestAdapter,
)


QUEST_OVERVIEW_CATALOG = "Category:Quest Overview Pages"


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


def _compatibility_document(document: KnowledgeDocumentDTO) -> KnowledgeDocumentDTO:
    """Adapt current TibiaWiki Quest parameter names without mutating retained raw evidence."""
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
    # `legend` for the short quest description. The provider-neutral parser
    # intentionally uses descriptive canonical keys, so translate aliases only
    # for parsing. The original KnowledgeDocument remains byte-for-byte raw.
    patched = _rename_template_param(wikitext, "lvl", "level")
    patched = _rename_template_param(patched, "legend", "description")
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
    """Production quest adapter wired to overview-only discovery and current template aliases."""

    def __init__(self, client=None):
        super().__init__(client or HttpTibiaWikiQuestOverviewClient())

    def validate(self, result: KnowledgeFetchResult) -> KnowledgeValidationResult:
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
        return super().normalize(_compatibility_document(document), context)
