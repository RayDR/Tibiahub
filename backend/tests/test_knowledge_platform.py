from __future__ import annotations

from uuid import UUID

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB

from app.knowledge.events import KnowledgeEventType
from app.knowledge.models import (
    KnowledgeDocument,
    KnowledgeDomainEvent,
    KnowledgeEntity,
    KnowledgeEntityAlias,
    KnowledgeEntityType,
    KnowledgeProvider,
    KnowledgeSearchMetadata,
)
from app.knowledge.registry import EntityTypeRegistry, ProviderRegistry
from app.knowledge.registry.entity_types import EntityTypeDefinition
from app.knowledge.schemas import KnowledgeDocumentCreate, KnowledgeEntityCreate
from app.knowledge.services import (
    DuplicateKnowledgeAliasError,
    DuplicateKnowledgeEntityError,
    KnowledgeEntityService,
)
from app.knowledge.storage import KnowledgeDocumentStore


@pytest.fixture
def knowledge_registry(db):
    EntityTypeRegistry.register_initial(db)
    ProviderRegistry.register_initial(db)
    db.flush()


def create_demon(db) -> KnowledgeEntity:
    return KnowledgeEntityService.create(
        db,
        KnowledgeEntityCreate(
            entity_type="creature",
            canonical_name="Demon",
            language_neutral_id="creature:demon",
            aliases=["The Demon", "demons"],
        ),
    )


def test_provider_registry_contains_capabilities_and_priority(db, knowledge_registry):
    providers = ProviderRegistry.enabled(db)
    assert [provider.provider_id for provider in providers] == ["tibiadata", "tibiamaps"]
    tibiadata = ProviderRegistry.get(db, "tibiadata")
    tibiamaps = ProviderRegistry.get(db, "tibiamaps")
    assert tibiadata is not None and tibiadata.supports_search is False
    assert set(tibiadata.supports_entities) == {"character", "guild", "world", "creature", "spell"}
    assert set(tibiadata.provider_roles) == {"current_facts", "live_observations", "historical_snapshot_upstream"}
    assert {"highscores", "killstatistics", "houses", "boosted_bosses"}.issubset(
        set(tibiadata.observation_capabilities)
    )
    assert tibiamaps is not None and tibiamaps.supports_media is True
    assert tibiamaps.rate_limit == {"requests": 30, "window_seconds": 60}
    assert set(tibiamaps.supports_entities) == {"map_point", "map_region"}
    assert tibiamaps.provider_roles == ["spatial_authority"]
    assert set(tibiamaps.spatial_capabilities) == {
        "dataset", "floors", "markers", "coordinates", "pathfinding", "map_version",
    }
    assert tibiadata.health == "unknown" and tibiadata.last_sync_at is None


def test_initial_and_future_entity_types_need_no_schema_change(db, knowledge_registry):
    initial = {entry.entity_type for entry in EntityTypeRegistry.enabled(db)}
    assert {
        "creature",
        "item",
            "quest",
            "mission",
        "npc",
        "spell",
        "achievement",
        "imbuement",
        "bestiary",
        "boss",
        "guild",
        "character",
        "world",
        "hunt_zone",
        "access",
        "area",
            "town",
            "location",
            "map_point",
            "map_region",
            "route",
        } == initial

    future = EntityTypeRegistry.register(
        db,
        EntityTypeDefinition("world_event", "World Event", {"introduced_by": "future-stage"}),
    )
    db.flush()
    assert future.type_metadata == {"introduced_by": "future-stage"}
    entity = KnowledgeEntityService.create(
        db,
        KnowledgeEntityCreate(
            entity_type="world_event",
            canonical_name="Test Event",
            language_neutral_id="world-event:test",
        ),
    )
    assert entity.entity_type == "world_event"


def test_canonical_entity_has_permanent_provider_neutral_uuid_and_search_metadata(db, knowledge_registry):
    entity = create_demon(db)
    original_uuid = entity.uuid
    db.flush()

    assert isinstance(original_uuid, UUID)
    assert entity.language_neutral_id == "creature:demon"
    assert entity.slug == "demon"
    assert entity.media_id is None and entity.thumbnail_id is None and entity.icon_id is None
    assert {alias.alias for alias in entity.aliases} == {"Demon", "The Demon", "demons"}
    assert entity.search_metadata.normalized_name == "demon"
    assert entity.search_metadata.search_tokens == ["demon", "demons", "the"]
    assert entity.search_metadata.future_embedding_id is None

    KnowledgeDocumentStore.persist(
        db,
        KnowledgeDocumentCreate(
            provider_id="tibiadata",
            provider_document_id="creatures/demon",
            entity_uuid=entity.uuid,
            raw_json={"creature": {"name": "Demon"}},
        ),
    )
    db.flush()
    assert entity.uuid == original_uuid


def test_duplicate_aliases_and_entities_are_rejected(db, knowledge_registry):
    entity = create_demon(db)
    with pytest.raises(DuplicateKnowledgeAliasError):
        KnowledgeEntityService.add_alias(db, entity, "demon")

    with pytest.raises(DuplicateKnowledgeEntityError):
        KnowledgeEntityService.create(
            db,
            KnowledgeEntityCreate(
                entity_type="creature",
                canonical_name="The Demon",
                language_neutral_id="creature:duplicate-demon",
            ),
        )

    item = KnowledgeEntityService.create(
        db,
        KnowledgeEntityCreate(
            entity_type="item",
            canonical_name="Demon",
            language_neutral_id="item:demon",
        ),
    )
    assert item.uuid != entity.uuid


def test_every_provider_payload_version_is_preserved_with_checksum_and_metadata(db, knowledge_registry):
    entity = create_demon(db)
    first_payload = {
        "creature": {
            "name": "Demon",
            "hitpoints": 8200,
            "voices": ["Your soul will be mine!"],
            "nested": {"elements": {"fire": 0}},
        }
    }
    first = KnowledgeDocumentStore.persist(
        db,
        KnowledgeDocumentCreate(
            provider_id="tibiadata",
            provider_document_id="creatures/demon",
            entity_uuid=entity.uuid,
            raw_json=first_payload,
            version="v4.1",
            etag="first-etag",
            language="en",
            metadata={"endpoint": "creature"},
        ),
    )
    second = KnowledgeDocumentStore.persist(
        db,
        KnowledgeDocumentCreate(
            provider_id="tibiadata",
            provider_document_id="creatures/demon",
            entity_uuid=entity.uuid,
            raw_json={**first_payload, "retrieval": {"sequence": 2}},
            version="v4.2",
        ),
    )
    db.flush()

    documents = (
        db.query(KnowledgeDocument)
        .filter_by(provider_id="tibiadata", provider_document_id="creatures/demon")
        .all()
    )
    assert len(documents) == 2
    assert first.uuid != second.uuid
    assert first.raw_json == first_payload
    assert first.document_metadata == {"endpoint": "creature"}
    assert len(first.checksum) == 64 and first.checksum != second.checksum


def test_provider_payload_columns_compile_to_jsonb():
    dialect = postgresql.dialect()
    for column in (
        KnowledgeProvider.__table__.c.rate_limit,
        KnowledgeProvider.__table__.c.supports_entities,
        KnowledgeEntityType.__table__.c.metadata,
        KnowledgeDocument.__table__.c.raw_json,
        KnowledgeDocument.__table__.c.metadata,
        KnowledgeSearchMetadata.__table__.c.search_tokens,
        KnowledgeSearchMetadata.__table__.c.aliases,
        KnowledgeDomainEvent.__table__.c.payload,
    ):
        assert isinstance(column.type.dialect_impl(dialect), JSONB)


def test_internal_domain_events_cover_entity_import_failure_update_and_merge(db, knowledge_registry):
    entity = create_demon(db)
    KnowledgeDocumentStore.persist(
        db,
        KnowledgeDocumentCreate(
            provider_id="tibiadata",
            provider_document_id="creatures/demon",
            entity_uuid=entity.uuid,
            raw_json={"name": "Demon"},
        ),
    )
    KnowledgeDocumentStore.record_failure(db, "tibiamaps", "timeout")
    KnowledgeEntityService.update_name(db, entity, "Demon Lord")
    KnowledgeEntityService.record_merge(db, entity, entity.uuid)
    db.flush()

    event_types = {event.event_type for event in db.query(KnowledgeDomainEvent).all()}
    assert {
        KnowledgeEventType.ENTITY_CREATED.value,
        KnowledgeEventType.ENTITY_UPDATED.value,
        KnowledgeEventType.PROVIDER_IMPORTED.value,
        KnowledgeEventType.PROVIDER_FAILED.value,
        KnowledgeEventType.KNOWLEDGE_MERGED.value,
    } <= event_types
    assert ProviderRegistry.get(db, "tibiamaps").health == "unavailable"


def test_schema_contains_only_provider_neutral_links():
    entity_columns = set(KnowledgeEntity.__table__.c.keys())
    alias_columns = set(KnowledgeEntityAlias.__table__.c.keys())
    assert "provider_id" not in entity_columns
    assert "provider_document_id" not in entity_columns
    assert {"entity_uuid", "entity_type", "normalized_alias"} <= alias_columns
