from __future__ import annotations

from app.knowledge.adapters import KnowledgeAdapterRegistry
from app.knowledge.adapters.tibiawiki_quest_catalog import (
    HttpTibiaWikiQuestOverviewClient,
    QUEST_OVERVIEW_CATALOG,
    TibiaWikiOverviewQuestAdapter,
)


class CaptureQuestOverviewClient(HttpTibiaWikiQuestOverviewClient):
    def __init__(self):
        super().__init__()
        self.params: dict | None = None

    def _request(self, params: dict) -> dict:
        self.params = dict(params)
        return {"batchcomplete": "", "query": {"categorymembers": []}}


def test_live_quest_catalog_discovers_overview_pages_only():
    client = CaptureQuestOverviewClient()

    client.fetch_catalog(
        continuation="page|464f52474f5454454e204b4e4f574c45444745205155455354|123",
        limit=25,
    )

    assert client.params == {
        "action": "query",
        "list": "categorymembers",
        "cmtitle": QUEST_OVERVIEW_CATALOG,
        "cmtype": "page",
        "cmlimit": 25,
        "format": "json",
        "cmcontinue": "page|464f52474f5454454e204b4e4f574c45444745205155455354|123",
    }
    assert client.params["cmtitle"] == "Category:Quest Overview Pages"
    assert client.params["cmtitle"] != "Category:Quests"
    assert client.params["cmtitle"] != "Category:Quest Spoiling Pages"


def test_default_registry_uses_overview_only_quest_adapter():
    adapter = KnowledgeAdapterRegistry().resolve("tibiawiki", "quest_catalog", "quest")

    assert isinstance(adapter, TibiaWikiOverviewQuestAdapter)
    assert isinstance(adapter.client, HttpTibiaWikiQuestOverviewClient)
