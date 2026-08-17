"""Quest catalog discovery using TibiaWiki's canonical overview-page category."""

from __future__ import annotations

from typing import Any

from app.knowledge.adapters.tibiawiki_quests import (
    HttpTibiaWikiQuestClient,
    TibiaWikiQuestAdapter,
)


QUEST_OVERVIEW_CATALOG = "Category:Quest Overview Pages"


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
    """Production quest adapter wired to overview-only catalog discovery."""

    def __init__(self, client=None):
        super().__init__(client or HttpTibiaWikiQuestOverviewClient())
