from __future__ import annotations

from uuid import uuid4

from app.knowledge.adapters import KnowledgeAdapterRegistry
from app.knowledge.adapters.protocol import (
    KnowledgeDocumentDTO,
    KnowledgeNormalizationContext,
)
from app.knowledge.adapters.tibiawiki_quest_catalog import (
    HttpTibiaWikiQuestOverviewClient,
    QUEST_OVERVIEW_CATALOG,
    TibiaWikiOverviewQuestAdapter,
)
from app.knowledge.dto import QuestKnowledgeDTO


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


def test_overview_adapter_parses_lvl_and_legend_without_mutating_raw_document():
    raw = {
        "parse": {
            "pageid": 123,
            "title": "Naginata Quest",
            "links": [],
            "wikitext": {
                "*": """{{Infobox Quest
| name = Naginata Quest
| lvl = 40
| premium = no
| location = [[Thais Dragon Lair]]
| reward = [[Naginata]]
| legend = Deep inside a dragon-filled place a treasure is hidden...
}}"""
            },
        }
    }
    document = KnowledgeDocumentDTO(
        provider_code="tibiawiki",
        provider_document_id="quest:123",
        raw_json=raw,
        metadata={"document_kind": "quest_detail"},
    )
    context = KnowledgeNormalizationContext(
        job_id=uuid4(),
        attempt_id=uuid4(),
        correlation_id=uuid4(),
        provider_code="tibiawiki",
        entity_type="quest",
    )

    normalized = TibiaWikiOverviewQuestAdapter().normalize(document, context)
    dto = QuestKnowledgeDTO.from_canonical_data(normalized.canonical_data)

    assert normalized.action == "upsert"
    assert dto.minimum_level == 40
    assert dto.description == "Deep inside a dragon-filled place a treasure is hidden..."
    assert "minimum_level" in dto.supplied_fields
    assert "description" in dto.supplied_fields
    assert "| lvl = 40" in document.raw_json["parse"]["wikitext"]["*"]
    assert "| legend = Deep inside" in document.raw_json["parse"]["wikitext"]["*"]
    assert "| level = 40" not in document.raw_json["parse"]["wikitext"]["*"]
