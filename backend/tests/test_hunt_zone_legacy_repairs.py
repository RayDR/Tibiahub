from __future__ import annotations

from app.knowledge.adapters.protocol import CanonicalEntityCandidate, KnowledgeNormalizationResult
from app.knowledge.dto import HuntVocationRecommendation, HuntZoneKnowledgeDTO
from app.knowledge.models import KnowledgeRelationship
from app.knowledge.providers import INITIAL_PROVIDERS
from app.knowledge.registry import EntityTypeRegistry, ProviderRegistry
from app.knowledge.schemas import KnowledgeEntityCreate
from app.knowledge.services import KnowledgeEntityService
from app.knowledge.services.normalization import KnowledgeNormalizationService
from app.models import HuntZone
from app.services.text_utils import normalize_search_text


def _registry(db) -> None:
    EntityTypeRegistry.register_initial(db)
    for definition in INITIAL_PROVIDERS:
        ProviderRegistry.register(db, definition)
    db.flush()


def _result(dto: HuntZoneKnowledgeDTO) -> KnowledgeNormalizationResult:
    return KnowledgeNormalizationResult(
        action="upsert",
        candidate=CanonicalEntityCandidate(
            entity_type="hunt_zone",
            canonical_name=dto.canonical_name,
            language_neutral_id=dto.language_neutral_id,
            aliases=dto.aliases,
            identity_strategy="exact_unique_or_create",
        ),
        provider_code="tibiawiki",
        external_id=dto.external_id,
        canonical_data=dto.to_canonical_data(),
    )


def _iksupan(*, location: str, premium_required=None, premium_supplied: bool = False):
    supplied = {
        "canonical_name",
        "slug",
        "location",
        "source_reference",
        "vocation_recommendations",
    }
    if premium_supplied:
        supplied.add("premium_required")
    return HuntZoneKnowledgeDTO(
        external_id="101544",
        canonical_name="Iksupan",
        slug="iksupan",
        location=location,
        vocation_recommendations={
            "knights": HuntVocationRecommendation(level=150),
            "paladins": HuntVocationRecommendation(level=150),
            "mages": HuntVocationRecommendation(level=150),
        },
        premium_required=premium_required,
        source_reference="https://tibia.fandom.com/wiki/Iksupan",
        supplied_fields=frozenset(supplied),
    )


def test_renormalization_clears_unproven_legacy_booleans_and_skips_prose_location_edge(db):
    _registry(db)
    prose = "Entered through a secret passage in Tiquanda."
    db.add(HuntZone(
        name="Iksupan",
        normalized_name=normalize_search_text("Iksupan"),
        source_provider="tibiawiki",
        source_name="tibiawiki",
        external_id="101544",
        requires_premium=False,
        requires_quest=False,
        knights_recommended=False,
        paladins_recommended=False,
        sorcerers_recommended=False,
        druids_recommended=False,
        monks_recommended=False,
        protected_fields=["knights_recommended"],
        data_version=1,
    ))
    db.flush()

    KnowledgeNormalizationService.apply(db, _result(_iksupan(location=prose)))
    db.flush()

    zone = db.query(HuntZone).filter_by(external_id="101544").one()
    assert zone.region == prose
    assert zone.requires_premium is None
    assert zone.requires_quest is None
    assert zone.knights_recommended is False  # protected legacy/manual value survives
    assert zone.paladins_recommended is None
    assert zone.sorcerers_recommended is None
    assert zone.druids_recommended is None
    assert zone.monks_recommended is None
    assert not db.query(KnowledgeRelationship).filter_by(
        source_entity_id=zone.knowledge_entity_id,
        unresolved_name=prose,
        is_current=True,
    ).first()

    KnowledgeNormalizationService.apply(
        db,
        _result(_iksupan(location=prose, premium_required=False, premium_supplied=True)),
    )
    db.flush()
    assert db.query(HuntZone).filter_by(external_id="101544").one().requires_premium is False


def test_free_form_location_projects_graph_edge_only_when_exact_place_exists(db):
    _registry(db)
    tiquanda = KnowledgeEntityService.create(db, KnowledgeEntityCreate(
        entity_type="area",
        canonical_name="Tiquanda",
        language_neutral_id="area:test:tiquanda",
    ))

    KnowledgeNormalizationService.apply(db, _result(_iksupan(location="Tiquanda")))
    db.flush()

    zone = db.query(HuntZone).filter_by(external_id="101544").one()
    relation = db.query(KnowledgeRelationship).filter_by(
        source_entity_id=zone.knowledge_entity_id,
        relationship_type_code="located_at",
        is_current=True,
    ).one()
    assert relation.resolution_state == "resolved"
    assert relation.target_entity_id == tiquanda.uuid
