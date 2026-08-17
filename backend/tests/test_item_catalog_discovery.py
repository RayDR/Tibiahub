from __future__ import annotations

from uuid import uuid4

from app.knowledge.adapters.protocol import KnowledgeFetchRequest
from app.knowledge.adapters.tibiawiki_items import (
    HttpTibiaWikiItemClient,
    TibiaWikiItemAdapter,
)


class CaptureItemClient(HttpTibiaWikiItemClient):
    def __init__(self):
        super().__init__()
        self.params: dict | None = None

    def _request(self, params: dict) -> dict:
        self.params = dict(params)
        return {"batchcomplete": "", "query": {"embeddedin": []}}


class EmbeddedInFixtureClient:
    def fetch_catalog(self, *, continuation: str | None, limit: int) -> dict:
        assert continuation is None
        assert limit == 2
        return {
            "continue": {
                "eicontinue": "10|Infobox_Item|222",
                "continue": "-||",
            },
            "query": {
                "embeddedin": [
                    {"pageid": 111, "ns": 0, "title": "Magic Sword"},
                    {"pageid": 222, "ns": 0, "title": "Demon Shield"},
                ]
            },
        }

    def fetch_detail(self, *, external_id: str | None, page_title: str | None) -> dict:
        raise AssertionError("detail fetch is not expected")


def _catalog_request() -> KnowledgeFetchRequest:
    return KnowledgeFetchRequest(
        job_id=uuid4(),
        attempt_id=uuid4(),
        correlation_id=uuid4(),
        provider_code="tibiawiki",
        job_type="item_catalog",
        entity_type="item",
        scope={"batch_limit": 2},
        payload={},
    )


def test_live_item_catalog_discovers_infobox_item_transclusions():
    client = CaptureItemClient()

    client.fetch_catalog(continuation="10|Infobox_Item|222", limit=25)

    assert client.params == {
        "action": "query",
        "list": "embeddedin",
        "eititle": "Template:Infobox Item",
        "einamespace": 0,
        "eilimit": 25,
        "format": "json",
        "eicontinue": "10|Infobox_Item|222",
    }
    assert "cmtitle" not in client.params
    assert "cmcontinue" not in client.params


def test_embeddedin_catalog_enqueues_details_and_continuation():
    adapter = TibiaWikiItemAdapter(EmbeddedInFixtureClient())

    result = adapter.fetch(_catalog_request())

    assert adapter.validate(result).classification == "valid"
    assert [child.job_type for child in result.child_jobs] == [
        "item_detail",
        "item_detail",
        "item_catalog",
    ]
    assert [
        child.payload.get("external_id")
        for child in result.child_jobs[:2]
    ] == ["111", "222"]
    assert result.child_jobs[-1].scope == {
        "batch_limit": 2,
        "continuation": "10|Infobox_Item|222",
    }
    assert result.cursor == {
        "continuation": "10|Infobox_Item|222",
        "members_processed": 2,
    }
    assert result.documents[0].metadata["catalog_source"] == "Template:Infobox Item"
    assert result.provider_metadata["catalog_source"] == "Template:Infobox Item"
