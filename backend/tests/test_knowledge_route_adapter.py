from uuid import uuid4

from app.knowledge.adapters import (
    KnowledgeFetchRequest,
    KnowledgeNormalizationContext,
    TibiaWikiRouteAdapter,
)
from app.knowledge.models import KnowledgeEntity, KnowledgeProvider, SpatialRoute
from app.knowledge.registry import EntityTypeRegistry, ProviderRegistry, RelationshipTypeRegistry
from app.knowledge.services.normalization import KnowledgeNormalizationService


ROUTE_WIKITEXT = """* Go to the [[Ancient Temple]], north of [[Thais]].
* Follow the documented path east and go down the ladder.
[[Image:Route to Mintwallin 1.png]]
* Continue until you stand by the gate of [[Mintwallin]].
[[Category:Routes]]"""


class RouteClient:
    def fetch_catalog(self, *, continuation: str | None, limit: int):
        return {
            "query": {"categorymembers": [
                {"pageid": 6826, "title": "Route:Mintwallin"},
                {"pageid": 6827, "title": "Route:Mintwallin/map01"},
            ]},
        }

    def fetch_detail(self, *, external_id: str | None, page_title: str | None):
        return {"parse": {"pageid": int(external_id or 6826), "title": page_title or "Route:Mintwallin", "wikitext": {"*": ROUTE_WIKITEXT}}}


def _request(suffix: str, *, scope=None, payload=None):
    return KnowledgeFetchRequest(
        job_id=uuid4(), attempt_id=uuid4(), correlation_id=uuid4(), provider_code="tibiawiki",
        job_type=f"route_{suffix}", entity_type="route", scope=scope or {}, payload=payload or {},
    )


def test_route_catalog_is_bounded_and_ignores_map_fragment_pages():
    adapter = TibiaWikiRouteAdapter(RouteClient())
    result = adapter.fetch(_request("catalog", scope={"batch_limit": 20}))

    assert adapter.validate(result).valid is True
    assert len(result.child_jobs) == 1
    assert result.child_jobs[0].payload == {"external_id": "6826", "page_title": "Route:Mintwallin"}
    assert result.partial is False
    assert result.provider_metadata["skipped_map_fragments"] == 1


def test_route_detail_persists_source_instructions_idempotently(db):
    EntityTypeRegistry.register_initial(db)
    ProviderRegistry.register_initial(db)
    RelationshipTypeRegistry.register_initial(db)
    provider = db.get(KnowledgeProvider, "tibiawiki")
    provider.enabled = True
    provider.health = "unknown"
    db.flush()
    adapter = TibiaWikiRouteAdapter(RouteClient())
    fetched = adapter.fetch(_request("detail", payload={"external_id": "6826", "page_title": "Route:Mintwallin"}))
    document = fetched.documents[0]
    context = KnowledgeNormalizationContext(
        job_id=uuid4(), attempt_id=uuid4(), correlation_id=uuid4(), provider_code="tibiawiki", entity_type="route",
    )
    normalized = adapter.normalize(document, context)

    first = KnowledgeNormalizationService.apply(db, normalized)
    second = KnowledgeNormalizationService.apply(db, normalized)
    route = db.query(SpatialRoute).filter_by(external_id="6826", is_current=True).one()

    assert first.entity_uuid == second.entity_uuid == route.knowledge_entity_id
    assert first.status == "created"
    assert second.status == "unchanged"
    assert db.query(KnowledgeEntity).filter_by(entity_type="route").count() == 1
    assert route.end_location_entity_id is None
    assert route.unresolved_end_name == "Mintwallin"
    assert route.step_count == 3
    assert route.source_metadata["map_images"][0].endswith("/Special:FilePath/Route_to_Mintwallin_1.png")
    assert [step.instruction for step in route.steps][0].startswith("Go to the Ancient Temple")
