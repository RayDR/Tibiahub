from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from app.knowledge.adapters.protocol import KnowledgeFetchRequest
from app.knowledge.adapters.tibiawiki_items import (
    HttpTibiaWikiItemClient,
    TibiaWikiItemAdapter,
)


FIXTURES = Path(__file__).parent / "fixtures"


class CaptureItemClient(HttpTibiaWikiItemClient):
    def __init__(self):
        super().__init__()
        self.params: dict | None = None

    def _request(self, params: dict) -> dict:
        self.params = dict(params)
        return {"batchcomplete": "", "query": {"categorymembers": []}}


class PickupableCategoryFixtureClient:
    def fetch_catalog(self, *, continuation: str | None, limit: int) -> dict:
        assert continuation is None
        assert limit == 2
        return json.loads(
            (FIXTURES / "tibiawiki_pickupable_item_catalog.json").read_text(
                encoding="utf-8"
            )
        )

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


def test_live_item_catalog_discovers_pickupable_objects():
    client = CaptureItemClient()

    client.fetch_catalog(
        continuation="page|41425953532048414d4d4552|222",
        limit=25,
    )

    assert client.params == {
        "action": "query",
        "list": "categorymembers",
        "cmtitle": "Category:Pickupable Objects",
        "cmtype": "page",
        "cmlimit": 25,
        "format": "json",
        "cmcontinue": "page|41425953532048414d4d4552|222",
    }
    assert "eititle" not in client.params
    assert "eicontinue" not in client.params


def test_pickupable_catalog_enqueues_details_and_continuation():
    adapter = TibiaWikiItemAdapter(PickupableCategoryFixtureClient())

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
        "continuation": "page|41425953532048414d4d4552|222",
    }
    assert result.cursor == {
        "continuation": "page|41425953532048414d4d4552|222",
        "members_processed": 2,
    }
    assert result.documents[0].metadata["catalog_source"] == "Category:Pickupable Objects"
    assert result.provider_metadata["catalog_source"] == "Category:Pickupable Objects"
