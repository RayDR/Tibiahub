from __future__ import annotations

from copy import deepcopy
from uuid import uuid4

from app.knowledge.adapters import (
    KnowledgeAdapterRegistry,
    KnowledgeDocumentDTO,
    KnowledgeFetchRequest,
    KnowledgeNormalizationContext,
)
from app.knowledge.adapters.tibiawiki_quest_catalog import (
    QUEST_OVERVIEW_CATALOG,
    HttpTibiaWikiQuestOverviewClient,
    TibiaWikiOverviewQuestAdapter,
    _compatibility_document,
)
from app.knowledge.dto import QuestKnowledgeDTO


class RecordingOverviewClient(HttpTibiaWikiQuestOverviewClient):
    def __init__(self):
        self.params = None

    def _request(self, params):
        self.params = dict(params)
        return {"query": {"categorymembers": []}}


class RepairFixtureClient:
    def fetch_catalog(self, *, continuation: str | None, limit: int):
        return {
            "query": {
                "categorymembers": [
                    {"pageid": 700, "ns": 0, "title": "Bored Mini World Change"},
                ],
            },
        }

    def fetch_detail(self, *, external_id: str | None, page_title: str | None):
        if page_title and page_title.endswith("/Spoiler"):
            return {
                "parse": {
                    "pageid": 1700,
                    "title": page_title,
                    "links": [
                        {"*": "Wyda", "ns": 0, "exists": ""},
                        {"*": "Blood Herb", "ns": 0, "exists": ""},
                    ],
                    "wikitext": {
                        "*": """{{Infobox Quest
|name=Bored Mini World Change
|lvl=0
|legend=The witch Wyda is bored.
|location=[[Green Claw Swamp]]
|premium=no
}}
== Method ==
Visit [[Wyda]] in the [[Green Claw Swamp]]. Bring a [[Blood Herb]] when she is bored.
=== Statistics ===
This statistics table is evidence, not a separate mission.
== Transcripts ==
Dialogue omitted.
""",
                    },
                }
            }
        return {
            "parse": {
                "pageid": int(external_id or 700),
                "title": page_title or "Bored Mini World Change",
                # This ordinary related-Quest link used to make the base parser
                # classify an overview page as a non-public group.
                "links": [{"*": "Blood Herb Quest", "ns": 0, "exists": ""}],
                "wikitext": {
                    "*": """{{Infobox Quest
|name=Bored Mini World Change
|lvl=0
|legend=The witch Wyda is bored.
|location=[[Green Claw Swamp]]
|premium=no
}}""",
                },
            }
        }


class MixedMissionFixtureClient(RepairFixtureClient):
    def fetch_detail(self, *, external_id: str | None, page_title: str | None):
        if page_title and page_title.endswith("/Spoiler"):
            return {
                "parse": {
                    "pageid": 51842,
                    "title": page_title,
                    "links": [],
                    "wikitext": {
                        "*": """{{Infobox Quest
|name=Children of the Revolution Quest
|description=Help the lizard resistance.
}}
== Missions ==
=== Prove Your Worzz! ===
intro text
=== Mission 1: Corruption ===
mission text
=== Mission 2: Something Else ===
mission text
""",
                    },
                }
            }
        return super().fetch_detail(external_id=external_id, page_title=page_title)


def _request(
    job_type: str,
    payload: dict | None = None,
    scope: dict | None = None,
) -> KnowledgeFetchRequest:
    return KnowledgeFetchRequest(
        job_id=uuid4(),
        attempt_id=uuid4(),
        correlation_id=uuid4(),
        provider_code="tibiawiki",
        job_type=job_type,
        entity_type="quest",
        scope=scope or {},
        payload=payload or {},
    )


def _context() -> KnowledgeNormalizationContext:
    return KnowledgeNormalizationContext(
        job_id=uuid4(),
        attempt_id=uuid4(),
        correlation_id=uuid4(),
        provider_code="tibiawiki",
        entity_type="quest",
    )


def test_production_quest_catalog_uses_overview_pages():
    client = RecordingOverviewClient()
    client.fetch_catalog(continuation=None, limit=50)
    assert client.params["cmtitle"] == QUEST_OVERVIEW_CATALOG
    assert QUEST_OVERVIEW_CATALOG == "Category:Quest Overview Pages"


def test_catalog_child_carries_overview_membership_evidence():
    adapter = TibiaWikiOverviewQuestAdapter(RepairFixtureClient())
    result = adapter.fetch(_request("quest_catalog", scope={"batch_limit": 50}))
    detail = next(child for child in result.child_jobs if child.job_type == "quest_detail")
    assert detail.payload == {
        "external_id": "700",
        "page_title": "Bored Mini World Change",
        "catalog_source": QUEST_OVERVIEW_CATALOG,
    }


def test_compatibility_copy_maps_current_aliases_and_standalone_method_without_mutating_raw():
    raw = RepairFixtureClient().fetch_detail(external_id=None, page_title="Bored Mini World Change/Spoiler")
    original = deepcopy(raw)
    document = KnowledgeDocumentDTO(
        provider_code="tibiawiki",
        provider_document_id="quest_spoiler:700",
        raw_json=raw,
        metadata={"document_kind": "quest_spoiler"},
    )

    compatible = _compatibility_document(document)
    patched = compatible.raw_json["parse"]["wikitext"]["*"]

    assert raw == original
    assert "|level=0" in patched
    assert "|description=The witch Wyda is bored." in patched
    assert "== Missions ==\n=== Method ===" in patched
    assert "== Statistics ==" in patched
    assert "=== Statistics ===" not in patched


def test_quest_detail_enqueues_spoiler_and_preserves_overview_leaf_evidence():
    adapter = TibiaWikiOverviewQuestAdapter(RepairFixtureClient())
    result = adapter.fetch(_request(
        "quest_detail",
        {
            "external_id": "700",
            "page_title": "Bored Mini World Change",
            "catalog_source": QUEST_OVERVIEW_CATALOG,
        },
    ))

    assert result.documents[0].metadata["catalog_source"] == QUEST_OVERVIEW_CATALOG
    spoiler_children = [child for child in result.child_jobs if child.job_type == "quest_spoiler_detail"]
    assert len(spoiler_children) == 1
    assert spoiler_children[0].payload == {
        "parent_external_id": "700",
        "page_title": "Bored Mini World Change/Spoiler",
    }

    normalized = adapter.normalize(result.documents[0], _context())
    dto = QuestKnowledgeDTO.from_canonical_data(normalized.canonical_data)
    assert dto.is_group is False
    assert "is_group" in dto.supplied_fields
    assert dto.provider_metadata["catalog_source"] == QUEST_OVERVIEW_CATALOG


def test_spoiler_normalizes_into_parent_quest_with_one_method_mission_and_retains_raw_identity():
    adapter = TibiaWikiOverviewQuestAdapter(RepairFixtureClient())
    result = adapter.fetch(_request(
        "quest_spoiler_detail",
        {
            "parent_external_id": "700",
            "page_title": "Bored Mini World Change/Spoiler",
        },
    ))
    assert adapter.validate(result).valid
    document = result.documents[0]
    raw_before = deepcopy(document.raw_json)

    normalized = adapter.normalize(document, _context())
    dto = QuestKnowledgeDTO.from_canonical_data(normalized.canonical_data)

    assert normalized.external_id == "700"
    assert dto.external_id == "700"
    assert dto.canonical_name == "Bored Mini World Change"
    assert dto.minimum_level == 0
    assert dto.description == "The witch Wyda is bored."
    assert dto.is_group is False
    assert dto.provider_metadata["catalog_source"] == QUEST_OVERVIEW_CATALOG
    assert [mission.title for mission in dto.missions] == ["Method"]
    assert "Bring a Blood Herb" in (dto.missions[0].description or "")
    assert "Statistics" not in [mission.title for mission in dto.missions]
    assert document.raw_json == raw_before
    assert document.raw_json["parse"]["pageid"] == 1700
    assert document.raw_json["parse"]["title"].endswith("/Spoiler")


def test_spoiler_recovers_mixed_mission_sequence_collision_in_provider_order():
    adapter = TibiaWikiOverviewQuestAdapter(MixedMissionFixtureClient())
    result = adapter.fetch(_request(
        "quest_spoiler_detail",
        {
            "parent_external_id": "41842",
            "page_title": "Children of the Revolution Quest/Spoiler",
        },
    ))

    assert adapter.validate(result).valid

    normalized = adapter.normalize(result.documents[0], _context())
    dto = QuestKnowledgeDTO.from_canonical_data(normalized.canonical_data)

    assert [mission.sequence for mission in dto.missions] == [1, 2, 3]
    assert [mission.title for mission in dto.missions] == [
        "Prove Your Worzz!",
        "Corruption",
        "Something Else",
    ]


def test_manual_detail_without_catalog_evidence_does_not_claim_overview_membership():
    adapter = TibiaWikiOverviewQuestAdapter(RepairFixtureClient())
    result = adapter.fetch(_request(
        "quest_detail",
        {"external_id": "700", "page_title": "Bored Mini World Change"},
    ))
    assert "catalog_source" not in result.documents[0].metadata
    assert not any(child.job_type == "quest_spoiler_detail" for child in result.child_jobs)


def test_registry_exposes_production_adapter_for_replay_and_spoiler_jobs():
    registry = KnowledgeAdapterRegistry()
    replay = registry.resolve("tibiawiki", "quest_renormalize", "quest")
    spoiler = registry.resolve("tibiawiki", "quest_spoiler_detail", "quest")
    assert isinstance(replay, TibiaWikiOverviewQuestAdapter)
    assert spoiler is replay
