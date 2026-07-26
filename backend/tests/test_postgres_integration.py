"""PostgreSQL-only integration coverage for the foundation baseline.

Set TEST_DATABASE_URL to a disposable database whose name visibly contains
``test``. The fixture destroys only that database's public schema.
"""
from __future__ import annotations

import os
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, or_, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.core import config
from app.core.security import create_access_token, get_password_hash
from app.db.database import (
    DatabaseNotReadyError,
    create_database_engine,
    expected_schema_revision,
    readiness_status,
    verify_connection_and_schema,
)
from app.models.events import Event, EventParticipant
from app.models.external_data import Item, QuestMission, TibiaWikiLocation, TibiaWikiNpc, TibiaWikiQuest
from app.models.creature import Creature
from app.models.guild_member_snapshot import GuildMemberSnapshot
from app.models.leadership import GuildLeadershipApplication, GuildLeadershipOpening, GuildLeadershipRole
from app.models.raffle import InternalNotification, Raffle
from app.models.user import User
from app.models.user_character import UserCharacter
from app.models.auth_security import AuthOneTimeToken, AuthRequestEvent
from app.models.character_ownership import CharacterOwnershipClaim, CharacterOwnershipHistory
from app.models.workspace_audit import WorkspaceAudit
from app.knowledge.adapters import (
    KnowledgeDocumentDTO, KnowledgeNormalizationContext, TibiaWikiItemAdapter,
    TibiaWikiLocationAdapter, TibiaWikiNpcAdapter, TibiaWikiQuestAdapter,
)
from app.knowledge.dto import MapPointDTO, MapRegionDTO, RouteDTO, RouteStepDTO
from app.knowledge.models import KnowledgeAccess, KnowledgeCreatureItemDrop, KnowledgeDocument, KnowledgeEntity, KnowledgeExternalMapping, KnowledgeJob, KnowledgeProvider, KnowledgeQuestRelation, KnowledgeRelationship, KnowledgeRelationshipType, SpatialEntityLocationLink, SpatialRoute
from app.knowledge.registry import EntityTypeRegistry, ProviderRegistry, RelationshipTypeRegistry
from app.knowledge.schemas import KnowledgeDocumentCreate, KnowledgeEntityCreate
from app.knowledge.services import EnqueueKnowledgeJob, KnowledgeEntityService, KnowledgeJobService, KnowledgeGraphService, RelationshipInput
from app.knowledge.storage import KnowledgeDocumentStore
from app.knowledge.services.item_relationships import upsert_drop_relationship
from app.knowledge.services.normalization import KnowledgeNormalizationService
from app.knowledge.services.spatial import entities_inside_region, link_entity_to_location, nearby_entities, persist_map_point, persist_map_region, persist_route
from app.services.raffle_scheduler_service import RaffleSchedulerService
from app.services.auth_token_service import AuthTokenService, PASSWORD_RESET


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _test_url() -> str:
    value = os.environ.get("TEST_DATABASE_URL", "")
    if not value:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL integration tests")
    url = make_url(value)
    database_name = (url.database or "").lower()
    if url.get_backend_name() != "postgresql":
        raise RuntimeError("TEST_DATABASE_URL must use PostgreSQL")
    if "test" not in database_name or database_name == "tibiahub":
        raise RuntimeError("TEST_DATABASE_URL must name a clearly isolated test database")
    return value


@pytest.fixture(scope="session")
def pg_engine():
    test_url = _test_url()
    engine = create_engine(test_url, pool_pre_ping=True)
    with engine.begin() as connection:
        if not connection.execute(text(
            "SELECT EXISTS (SELECT 1 FROM pg_available_extensions WHERE name='postgis')"
        )).scalar_one():
            pytest.skip("The disposable PostgreSQL server does not provide PostGIS")
        connection.execute(text("DROP EXTENSION IF EXISTS postgis CASCADE"))
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
        connection.execute(text("CREATE EXTENSION postgis"))
    environment = os.environ.copy()
    environment.update(APP_ENV="test", DATABASE_URL=test_url)
    subprocess.run(
        ["venv/bin/alembic", "-c", "alembic.ini", "upgrade", "head"],
        cwd=BACKEND_ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    yield engine
    engine.dispose()


@pytest.fixture()
def pg_session(pg_engine):
    factory = sessionmaker(bind=pg_engine, expire_on_commit=False)
    session = factory()
    yield session
    session.close()
    names = [name for name in inspect(pg_engine).get_table_names() if name != "alembic_version"]
    quoted = ", ".join(f'"{name}"' for name in names)
    if quoted:
        with pg_engine.begin() as connection:
            connection.execute(text(f"TRUNCATE TABLE {quoted} RESTART IDENTITY CASCADE"))


@pytest.fixture()
def pg_client(pg_session):
    from app.db.database import get_db
    from main import app

    def override_get_db():
        yield pg_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=True) as client:
        yield client
    app.dependency_overrides.pop(get_db, None)


def _user(session: Session, username: str, *, guild: str = "Postgres Guild", rank: str = "Member") -> User:
    user = User(
        username=username,
        email=f"{username}@example.test",
        hashed_password=get_password_hash("postgres-password"),
        guild_name=guild,
        guild_rank=rank,
        is_active=True,
        is_superuser=False,
    )
    session.add(user)
    session.flush()
    return user


def _register_reference_provider(session: Session) -> None:
    EntityTypeRegistry.register_initial(session)
    provider = session.get(KnowledgeProvider, "reference")
    if provider is None:
        provider = KnowledgeProvider(
            provider_id="reference",
            provider_name="Reference Adapter",
            priority=1000,
            enabled=True,
            version="stage-2a-2",
            rate_limit={"requests": 1, "window_seconds": 1},
            health="unknown",
            supports_entities=["creature"],
            supports_media=False,
            supports_search=False,
        )
        session.add(provider)
    else:
        provider.enabled = True
        provider.health = "unknown"
    session.flush()


def _register_tibiawiki_provider(session: Session) -> None:
    EntityTypeRegistry.register_initial(session)
    ProviderRegistry.register_initial(session)
    provider = session.get(KnowledgeProvider, "tibiawiki")
    assert provider is not None
    provider.enabled = True
    provider.health = "unknown"
    session.flush()


def _reference_job(*, payload_suffix: str = "demon", priority: int = 100) -> EnqueueKnowledgeJob:
    return EnqueueKnowledgeJob(
        provider_id="reference",
        job_type="reference_import",
        entity_type="creature",
        scope={"language": "en"},
        payload={
            "canonical_name": payload_suffix.title(),
            "language_neutral_id": f"creature:{payload_suffix}",
            "provider_document_id": f"reference:{payload_suffix}",
        },
        priority=priority,
        scheduled_at=datetime.now(UTC) - timedelta(seconds=1),
    )


def test_empty_database_upgrades_to_complete_postgresql_schema(pg_engine):
    tables = set(inspect(pg_engine).get_table_names())
    assert {
        "users", "user_characters", "announcements", "events", "event_participants",
        "raffles", "raffle_scheduler_attempts", "internal_notifications", "sync_jobs",
        "workspace_audits", "guild_leadership_openings", "media_assets", "creatures",
        "auth_one_time_tokens", "auth_request_events", "character_ownership_claims",
        "character_ownership_history",
        "knowledge_external_mappings",
        "knowledge_creature_item_drops", "tibiawiki_items",
        "quest_missions", "knowledge_accesses", "knowledge_quest_relations",
            "knowledge_relationship_types", "knowledge_relationships",
            "tibiawiki_npcs", "tibiawiki_locations", "spatial_map_points",
            "spatial_map_regions", "spatial_routes", "spatial_route_steps",
            "spatial_entity_location_links",
    }.issubset(tables)
    with pg_engine.connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == expected_schema_revision()
        extensions = set(connection.execute(text("SELECT extname FROM pg_extension")).scalars())
        assert {"pg_trgm", "unaccent", "postgis"}.issubset(extensions)
        json_type = connection.execute(text(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_name='raffle_participants' AND column_name='source_data'"
        )).scalar_one()
        assert json_type == "jsonb"
        constraints = set(connection.execute(text(
            "SELECT conname FROM pg_constraint WHERE connamespace = 'public'::regnamespace"
        )).scalars())
        assert {"uq_event_participant_user", "uq_raffle_participant_user", "fk_leadership_application_assignment"}.issubset(constraints)
        assert {
            "ck_auth_token_purpose", "ck_auth_token_hash_length", "ck_auth_request_purpose",
            "ck_character_claim_status", "ck_character_claim_hash_length",
            "ck_user_character_ownership_status",
        }.issubset(constraints)
        assert {
            "uq_knowledge_external_mapping_identifier",
            "uq_knowledge_external_mapping_entity",
            "fk_creatures_knowledge_entity",
        }.issubset(constraints)
        index_definitions = "\n".join(connection.execute(text(
            "SELECT indexdef FROM pg_indexes WHERE schemaname='public'"
        )).scalars())
        assert "uq_leadership_active_application" in index_definitions and " WHERE " in index_definitions
        assert "ix_raffles_scheduler_due" in index_definitions
        assert "uq_creatures_knowledge_entity_id" in index_definitions
        assert "ix_spatial_map_points_geom" in index_definitions and "USING gist" in index_definitions
        assert "ix_spatial_map_regions_geom" in index_definitions
        assert "ix_spatial_routes_geom" in index_definitions
        assert "uq_user_characters_verified_normalized_name" in index_definitions
        assert "uq_character_active_claim_user_name" in index_definitions
        user_columns = {column["name"]: column for column in inspect(pg_engine).get_columns("users")}
        assert {"is_superuser", "is_moderator", "is_writer"}.issubset(user_columns)
        assert all(user_columns[name]["nullable"] is False for name in ("is_superuser", "is_moderator", "is_writer"))
        creature_columns = {column["name"] for column in inspect(pg_engine).get_columns("creatures")}
        assert {"knowledge_entity_id", "data_version", "protected_fields"} <= creature_columns
        item_columns = {column["name"] for column in inspect(pg_engine).get_columns("tibiawiki_items")}
        assert {"knowledge_entity_id", "external_id", "normalized_name", "data_version", "category"} <= item_columns
        provider_enabled, provider_health, supported_entities = connection.execute(
            text("SELECT enabled, health, supports_entities FROM knowledge_providers WHERE provider_id='tibiawiki'")
        ).one()
        assert provider_enabled is False and provider_health == "disabled"
        assert supported_entities == ["creature", "item", "quest", "npc", "location", "area", "town"]


def test_auth_token_consumption_and_request_cooldown_are_atomic_on_postgresql(pg_engine, pg_session):
    user = _user(pg_session, "atomic_auth_user")
    raw = AuthTokenService.issue(pg_session, user=user, purpose=PASSWORD_RESET, ttl=timedelta(minutes=10))
    pg_session.commit()
    factory = sessionmaker(bind=pg_engine, expire_on_commit=False)

    def consume_once() -> bool:
        with factory.begin() as session:
            return AuthTokenService.consume(session, purpose=PASSWORD_RESET, raw_token=raw) is not None

    with ThreadPoolExecutor(max_workers=2) as executor:
        consumed = list(executor.map(lambda _index: consume_once(), range(2)))
    assert sorted(consumed) == [False, True]
    with factory() as session:
        token = session.query(AuthOneTimeToken).filter_by(user_id=user.id).one()
        assert token.consumed_at is not None and token.token_hash != raw

    def request_once() -> bool:
        with factory.begin() as session:
            return AuthTokenService.allow_request(
                session, purpose=PASSWORD_RESET,
                subject="atomic-auth@example.test", requester="127.0.0.1",
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        allowed = list(executor.map(lambda _index: request_once(), range(2)))
    assert sorted(allowed) == [False, True]
    with factory() as session:
        assert session.query(AuthRequestEvent).filter_by(purpose=PASSWORD_RESET).count() == 1


def test_verified_owner_uniqueness_and_ownership_history_immutability_on_postgresql(pg_session):
    first = _user(pg_session, "unique_owner_first")
    second = _user(pg_session, "unique_owner_second")
    now = datetime.now(UTC)
    pg_session.add(UserCharacter(
        user_id=first.id, character_name="Unique Knight", normalized_name="unique knight",
        ownership_status="verified", ownership_verified_at=now,
    ))
    pg_session.flush()
    pg_session.add(UserCharacter(
        user_id=second.id, character_name="UNIQUE KNIGHT", normalized_name="unique knight",
        ownership_status="verified", ownership_verified_at=now,
    ))
    with pytest.raises(IntegrityError):
        pg_session.flush()
    pg_session.rollback()

    owner = _user(pg_session, "history_owner")
    claim = CharacterOwnershipClaim(
        user_id=owner.id, character_name="History Knight", normalized_name="history knight",
        challenge_hash="c" * 64, status="verified", expires_at=now + timedelta(minutes=10),
        verified_at=now, consumed_at=now,
    )
    pg_session.add(claim)
    pg_session.flush()
    history = CharacterOwnershipHistory(
        normalized_name=claim.normalized_name, character_name=claim.character_name,
        claim_id=claim.id, action="ownership_verified", to_user_id=owner.id,
        safe_metadata={},
    )
    pg_session.add(history)
    pg_session.commit()
    history.action = "rewritten"
    with pytest.raises(Exception, match="immutable"):
        pg_session.commit()
    pg_session.rollback()


def test_postgis_point_region_route_nearby_and_inside_region(pg_session):
    EntityTypeRegistry.register_initial(pg_session)
    ProviderRegistry.register_initial(pg_session)
    RelationshipTypeRegistry.register_initial(pg_session)
    location = KnowledgeEntityService.create(pg_session, KnowledgeEntityCreate(
        entity_type="location", canonical_name="PostGIS Test Square",
        language_neutral_id="location:postgis-test-square",
    ))
    creature = KnowledgeEntityService.create(pg_session, KnowledgeEntityCreate(
        entity_type="creature", canonical_name="PostGIS Test Rat",
        language_neutral_id="creature:postgis-test-rat",
    ))
    point = persist_map_point(pg_session, MapPointDTO(
        "pg-square-point", "Square Marker", 32369, 32241, 7,
        location_name="PostGIS Test Square", confidence="high",
    ))
    region = persist_map_region(pg_session, MapRegionDTO(
        "pg-square-region", "Square Region",
        {"type": "Polygon", "coordinates": [[
            [32360, 32230, 7], [32380, 32230, 7], [32380, 32250, 7],
            [32360, 32250, 7], [32360, 32230, 7],
        ]]},
        location_name="PostGIS Test Square", minimum_z=7, maximum_z=7, confidence="high",
    ))
    route = persist_route(pg_session, RouteDTO(
        "pg-test-route", "PostGIS Test Route",
        (
            RouteStepDTO(1, "Begin", "PostGIS Test Square", 32369, 32241, 7),
            RouteStepDTO(2, "Finish", "PostGIS Test Square", 32372, 32243, 7),
        ),
        start_location_name="PostGIS Test Square", end_location_name="PostGIS Test Square",
    ))
    link_entity_to_location(
        pg_session, source_entity=creature, location_name="PostGIS Test Square",
        external_id="pg-rat-square", map_point_id=point.id,
    )
    pg_session.commit()

    dimensions = pg_session.execute(text(
        "SELECT ST_NDims(point.geom), ST_NDims(region.geom), ST_NDims(route.geom) "
        "FROM spatial_map_points point, spatial_map_regions region, spatial_routes route "
        "WHERE point.id=:point AND region.id=:region AND route.id=:route"
    ), {"point": point.id, "region": region.id, "route": route.id}).one()
    assert dimensions == (3, 3, 3)
    nearby = nearby_entities(pg_session, x=32369, y=32241, z=7, distance=10, skip=0, limit=10)
    assert any(row["source_entity_id"] == creature.uuid for row in nearby)
    inside = entities_inside_region(pg_session, region.id, skip=0, limit=10)
    assert any(row["source_entity_id"] == creature.uuid for row in inside)
    assert pg_session.query(SpatialRoute).filter_by(id=route.id).one().steps[0].sequence == 1
    assert pg_session.query(SpatialEntityLocationLink).filter_by(source_entity_id=creature.uuid).count() == 1


def test_graph_schema_registry_dedup_inverse_and_resolution_on_postgresql(pg_session):
    EntityTypeRegistry.register_initial(pg_session)
    ProviderRegistry.register_initial(pg_session)
    RelationshipTypeRegistry.register_initial(pg_session)
    creature = KnowledgeEntityService.create(pg_session, KnowledgeEntityCreate(
        entity_type="creature", canonical_name="Postgres Demon", language_neutral_id="creature:postgres-demon",
    ))
    item = KnowledgeEntityService.create(pg_session, KnowledgeEntityCreate(
        entity_type="item", canonical_name="Postgres Horn", language_neutral_id="item:postgres-horn",
    ))
    first = KnowledgeGraphService.upsert(pg_session, RelationshipInput(
        source_entity_id=creature.uuid, relationship_type="drops", target_entity_id=item.uuid,
        source_provider_id="tibiawiki",
    ))
    second = KnowledgeGraphService.upsert(pg_session, RelationshipInput(
        source_entity_id=creature.uuid, relationship_type="drops", target_entity_id=item.uuid,
        source_provider_id="tibiawiki",
    ))
    assert first.created and not second.created
    assert pg_session.query(KnowledgeRelationship).count() == 1
    assert pg_session.get(KnowledgeRelationshipType, "drops").inverse_code == "dropped_by"
    assert KnowledgeGraphService.incoming(pg_session, item.uuid)[0].target_entity_id == creature.uuid
    unresolved = KnowledgeGraphService.upsert(pg_session, RelationshipInput(
        source_entity_id=creature.uuid, relationship_type="drops", target_entity_type="item",
        unresolved_name="Postgres Horn Variant", resolution_state="ambiguous", confidence="low",
        source_provider_id="tibiawiki",
    )).relationship
    admin = _user(pg_session, "graph_pg_admin")
    resolved = KnowledgeGraphService.resolve_reference(
        pg_session, unresolved, item.uuid, admin_id=admin.id, reason="Existing exact catalog entity",
    )
    pg_session.commit()
    assert unresolved.is_current is False and unresolved.superseded_by_id == resolved.id
    assert resolved.confidence == "verified"


def test_graph_migration_bridges_legacy_facts_once_without_inverse_rows(pg_engine):
    test_url = _test_url()
    environment = os.environ.copy()
    environment.update(APP_ENV="test", DATABASE_URL=test_url)
    subprocess.run(
        ["venv/bin/alembic", "downgrade", "knowledge_quest_20260724"],
        cwd=BACKEND_ROOT, env=environment, check=True, capture_output=True, text=True,
    )
    # Other PostgreSQL tests intentionally truncate seed rows between cases;
    # recreate the pre-graph registry state that a real upgraded database has.
    with Session(pg_engine) as registry_session:
        EntityTypeRegistry.register_initial(registry_session)
        ProviderRegistry.register_initial(registry_session)
        registry_session.commit()
    creature_id, item_id, quest_id = uuid4(), uuid4(), uuid4()
    drop_id, quest_relation_id = uuid4(), uuid4()
    try:
        with pg_engine.begin() as connection:
            connection.execute(text("""
                INSERT INTO knowledge_entities (uuid, entity_type, canonical_name, slug, language_neutral_id)
                VALUES (:creature, 'creature', 'Bridge Demon', 'bridge-demon', 'creature:bridge-demon'),
                       (:item, 'item', 'Bridge Horn', 'bridge-horn', 'item:bridge-horn'),
                       (:quest, 'quest', 'Bridge Quest', 'bridge-quest', 'quest:bridge-quest')
            """), {"creature": creature_id, "item": item_id, "quest": quest_id})
            connection.execute(text("""
                INSERT INTO knowledge_creature_item_drops
                    (id, provider_id, creature_entity_uuid, item_entity_uuid, creature_name, item_name,
                     normalized_creature_name, normalized_item_name, resolution_status, confidence,
                     source_document_ids, source_directions, metadata)
                VALUES (:id, 'tibiawiki', :creature, :item, 'Bridge Demon', 'Bridge Horn',
                        'bridge demon', 'bridge horn', 'resolved', 'exact', '[]'::jsonb, '["creature"]'::jsonb, '{}'::jsonb)
            """), {"id": drop_id, "creature": creature_id, "item": item_id})
            connection.execute(text("""
                INSERT INTO knowledge_quest_relations
                    (id, provider_id, quest_entity_uuid, scope_key, relation_type, target_entity_type,
                     target_entity_uuid, target_name, normalized_target_name, resolution_status, confidence,
                     source_document_ids, source_contexts, metadata, protected)
                VALUES (:id, 'tibiawiki', :quest, 'quest', 'requires_item', 'item', :item,
                        'Bridge Horn', 'bridge horn', 'resolved', 'exact', '[]'::jsonb, '[]'::jsonb, '{}'::jsonb, false)
            """), {"id": quest_relation_id, "quest": quest_id, "item": item_id})
        subprocess.run(
            ["venv/bin/alembic", "upgrade", "head"], cwd=BACKEND_ROOT,
            env=environment, check=True, capture_output=True, text=True,
        )
        with pg_engine.connect() as connection:
            facts = connection.execute(text("""
                SELECT source_entity_id, relationship_type_code, target_entity_id
                FROM knowledge_relationships ORDER BY relationship_type_code
            """)).all()
            assert facts == [(creature_id, "drops", item_id), (quest_id, "requires_item", item_id)]
            assert connection.execute(text(
                "SELECT count(*) FROM knowledge_relationships WHERE relationship_type_code IN ('dropped_by','required_by_quest')"
            )).scalar_one() == 0
    finally:
        subprocess.run(
            ["venv/bin/alembic", "upgrade", "head"], cwd=BACKEND_ROOT,
            env=environment, check=True, capture_output=True, text=True,
        )
        with pg_engine.begin() as connection:
            connection.execute(text("DELETE FROM knowledge_relationships WHERE source_entity_id IN (:creature, :quest)"),
                               {"creature": creature_id, "quest": quest_id})
            connection.execute(text("DELETE FROM knowledge_creature_item_drops WHERE id=:id"), {"id": drop_id})
            connection.execute(text("DELETE FROM knowledge_quest_relations WHERE id=:id"), {"id": quest_relation_id})
            connection.execute(text("DELETE FROM knowledge_entities WHERE uuid IN (:creature, :item, :quest)"),
                               {"creature": creature_id, "item": item_id, "quest": quest_id})


def test_npc_location_backfill_resolves_only_unique_exact_historical_references(pg_engine):
    test_url = _test_url()
    environment = os.environ.copy()
    environment.update(APP_ENV="test", DATABASE_URL=test_url)
    subprocess.run(
        ["venv/bin/alembic", "downgrade", "knowledge_npc_location_20260724"],
        cwd=BACKEND_ROOT, env=environment, check=True, capture_output=True, text=True,
    )
    relationship_ids: dict[str, object] = {}
    quest_id = None
    try:
        with Session(pg_engine) as session:
            EntityTypeRegistry.register_initial(session)
            ProviderRegistry.register_initial(session)
            RelationshipTypeRegistry.register_initial(session)
            quest = KnowledgeEntityService.create(session, KnowledgeEntityCreate(
                entity_type="quest", canonical_name="Backfill Quest",
                language_neutral_id="quest:backfill-reference-test",
            ))
            quest_id = quest.uuid
            npc = KnowledgeEntityService.create(session, KnowledgeEntityCreate(
                entity_type="npc", canonical_name="Backfill Angus",
                language_neutral_id="npc:backfill-angus",
            ))
            KnowledgeEntityService.add_alias(session, npc, "Backfill Explorer")
            location = KnowledgeEntityService.create(session, KnowledgeEntityCreate(
                entity_type="location", canonical_name="Backfill Port Hope",
                language_neutral_id="location:backfill-port-hope",
            ))
            KnowledgeEntityService.create(session, KnowledgeEntityCreate(
                entity_type="npc", canonical_name="Backfill Guide",
                language_neutral_id="npc:backfill-guide-one",
            ))
            KnowledgeEntityService.create(session, KnowledgeEntityCreate(
                entity_type="npc", canonical_name="Backfill Guide",
                language_neutral_id="npc:backfill-guide-two",
                allow_name_collision=True, slug_suffix="two",
            ))
            values = {
                "npc": RelationshipInput(
                    source_entity_id=quest.uuid, source_scope="quest",
                    relationship_type="references_npc", target_entity_type="npc",
                    unresolved_name="Backfill Angus", resolution_state="unresolved",
                    source_provider_id="tibiawiki",
                    source_context={"fixture": "canonical"},
                ),
                "npc_alias": RelationshipInput(
                    source_entity_id=quest.uuid, source_scope="mission:backfill",
                    relationship_type="mission_references_npc", target_entity_type="npc",
                    unresolved_name="Backfill Explorer", resolution_state="unresolved",
                    source_provider_id="tibiawiki",
                    source_context={"fixture": "alias"},
                ),
                "location": RelationshipInput(
                    source_entity_id=quest.uuid, source_scope="quest",
                    relationship_type="occurs_at_location", target_entity_type="location",
                    unresolved_name="Backfill Port Hope", resolution_state="unresolved",
                    source_provider_id="tibiawiki",
                ),
                "ambiguous": RelationshipInput(
                    source_entity_id=quest.uuid, source_scope="quest:ambiguous",
                    relationship_type="references_npc", target_entity_type="npc",
                    unresolved_name="Backfill Guide", resolution_state="ambiguous",
                    source_provider_id="tibiawiki",
                ),
                "manual": RelationshipInput(
                    source_entity_id=quest.uuid, source_scope="quest:manual",
                    relationship_type="references_npc", target_entity_type="npc",
                    unresolved_name="Backfill Angus", resolution_state="unresolved",
                    source_provider_id="tibiawiki", manual_override=True,
                ),
            }
            for key, value in values.items():
                relationship_ids[key] = KnowledgeGraphService.upsert(session, value).relationship.id
            expected_targets = {"npc": npc.uuid, "npc_alias": npc.uuid, "location": location.uuid}
            session.commit()

        subprocess.run(
            ["venv/bin/alembic", "upgrade", "head"], cwd=BACKEND_ROOT,
            env=environment, check=True, capture_output=True, text=True,
        )
        with Session(pg_engine) as session:
            for key, target_id in expected_targets.items():
                original = session.get(KnowledgeRelationship, relationship_ids[key])
                replacement = session.get(KnowledgeRelationship, original.superseded_by_id)
                assert original.is_current is False and original.resolution_state == "superseded"
                assert replacement.is_current is True and replacement.target_entity_id == target_id
                assert replacement.source_provider_id == "tibiawiki"
                assert replacement.source_context["resolution_policy"] == "exact_name_or_alias_only"
                assert replacement.source_context["resolution_migration"] == "knowledge_npc_loc_ref_20260724"
            ambiguous = session.get(KnowledgeRelationship, relationship_ids["ambiguous"])
            manual = session.get(KnowledgeRelationship, relationship_ids["manual"])
            assert ambiguous.is_current is True and ambiguous.resolution_state == "ambiguous"
            assert manual.is_current is True and manual.resolution_state == "unresolved"
    finally:
        subprocess.run(
            ["venv/bin/alembic", "upgrade", "head"], cwd=BACKEND_ROOT,
            env=environment, check=True, capture_output=True, text=True,
        )
        if quest_id is not None:
            with pg_engine.begin() as connection:
                connection.execute(text(
                    "DELETE FROM knowledge_relationships WHERE source_entity_id=:quest"
                ), {"quest": quest_id})
                connection.execute(text(
                    "DELETE FROM knowledge_entities WHERE language_neutral_id LIKE :pattern"
                ), {"pattern": "%:backfill-%"})


def test_named_place_migration_reclassifies_and_backfills_exact_edges_idempotently(pg_engine):
    test_url = _test_url()
    environment = os.environ.copy()
    environment.update(APP_ENV="test", DATABASE_URL=test_url)
    subprocess.run(
        ["venv/bin/alembic", "downgrade", "knowledge_npc_loc_ref_20260724"],
        cwd=BACKEND_ROOT, env=environment, check=True, capture_output=True, text=True,
    )
    entity_ids = []
    try:
        with Session(pg_engine, expire_on_commit=False) as session:
            town = KnowledgeEntityService.create(session, KnowledgeEntityCreate(
                entity_type="location", canonical_name="Migration Port Hope",
                language_neutral_id="location:tibiawiki:migration-port-hope",
            ))
            area = KnowledgeEntityService.create(session, KnowledgeEntityCreate(
                entity_type="area", canonical_name="Migration Tiquanda",
                language_neutral_id="area:tibiawiki:migration-tiquanda",
            ))
            location = KnowledgeEntityService.create(session, KnowledgeEntityCreate(
                entity_type="location", canonical_name="Migration Banuta",
                language_neutral_id="location:tibiawiki:migration-banuta",
            ))
            npc = KnowledgeEntityService.create(session, KnowledgeEntityCreate(
                entity_type="npc", canonical_name="Migration Angus",
                language_neutral_id="npc:tibiawiki:migration-angus",
            ))
            access = KnowledgeEntityService.create(session, KnowledgeEntityCreate(
                entity_type="access", canonical_name="Migration passage",
                language_neutral_id="access:migration-passage",
            ))
            quest = KnowledgeEntityService.create(session, KnowledgeEntityCreate(
                entity_type="quest", canonical_name="Migration Quest",
                language_neutral_id="quest:migration-place-test",
            ))
            entity_ids = [town.uuid, area.uuid, location.uuid, npc.uuid, access.uuid, quest.uuid]
            session.add(KnowledgeExternalMapping(
                provider_id="tibiawiki", entity_type_id="location", external_id="m1900",
                entity_uuid=town.uuid, provider_metadata={},
            ))
            session.add_all([
                TibiaWikiLocation(
                    name="Migration Port Hope", normalized_name="migration port hope", slug=town.slug,
                    external_id="m1900", source_name="tibiawiki", knowledge_entity_id=town.uuid,
                    location_kind="City", description="Migration fixture",
                ),
                TibiaWikiLocation(
                    name="Migration Tiquanda", normalized_name="migration tiquanda", slug=area.slug,
                    external_id="m1901", source_name="tibiawiki", knowledge_entity_id=area.uuid,
                    location_kind="Region", parent_location="Migration Port Hope", description="Migration fixture",
                ),
                TibiaWikiLocation(
                    name="Migration Banuta", normalized_name="migration banuta", slug=location.slug,
                    external_id="m1902", source_name="tibiawiki", knowledge_entity_id=location.uuid,
                    location_kind="Hunting Place", parent_location="Migration Tiquanda", description="Migration fixture",
                ),
                TibiaWikiNpc(
                    name="Migration Angus", normalized_name="migration angus", slug=npc.slug,
                    external_id="m1800", source_name="tibiawiki", knowledge_entity_id=npc.uuid,
                    location_name="Migration Port Hope", description="Migration fixture",
                ),
                KnowledgeAccess(
                    knowledge_entity_id=access.uuid, access_code="migration:passage",
                    canonical_name="Migration passage", normalized_name="migration passage",
                    destination_name="Migration Banuta", provider_metadata={"provider": "tibiawiki"},
                ),
            ])
            unresolved = KnowledgeGraphService.upsert(session, RelationshipInput(
                source_entity_id=quest.uuid, relationship_type="occurs_at_location",
                target_entity_type="location", unresolved_name="Migration Port Hope",
                resolution_state="unresolved", source_provider_id="tibiawiki",
            )).relationship
            unresolved_id = unresolved.id
            session.commit()

        subprocess.run(
            ["venv/bin/alembic", "upgrade", "head"], cwd=BACKEND_ROOT,
            env=environment, check=True, capture_output=True, text=True,
        )
        with Session(pg_engine) as session:
            assert session.get(KnowledgeEntity, town.uuid).entity_type == "town"
            mapping = session.query(KnowledgeExternalMapping).filter_by(external_id="m1900").one()
            assert mapping.entity_type_id == "town"
            edges = session.query(KnowledgeRelationship).filter(
                KnowledgeRelationship.relationship_type_code.in_(["located_at", "contained_in", "leads_to"]),
                KnowledgeRelationship.is_current.is_(True),
            ).all()
            assert {(edge.source_entity_id, edge.relationship_type_code, edge.target_entity_id) for edge in edges} == {
                (npc.uuid, "located_at", town.uuid),
                (area.uuid, "contained_in", town.uuid),
                (location.uuid, "contained_in", area.uuid),
                (access.uuid, "leads_to", location.uuid),
            }
            original = session.get(KnowledgeRelationship, unresolved_id)
            assert original.resolution_state == "superseded" and not original.is_current
            replacement = session.get(KnowledgeRelationship, original.superseded_by_id)
            assert replacement.target_entity_id == town.uuid
            edge_count = len(edges)

        subprocess.run(
            ["venv/bin/alembic", "upgrade", "head"], cwd=BACKEND_ROOT,
            env=environment, check=True, capture_output=True, text=True,
        )
        with Session(pg_engine) as session:
            assert session.query(KnowledgeRelationship).filter(
                KnowledgeRelationship.relationship_type_code.in_(["located_at", "contained_in", "leads_to"]),
                KnowledgeRelationship.is_current.is_(True),
            ).count() == edge_count
    finally:
        subprocess.run(
            ["venv/bin/alembic", "upgrade", "head"], cwd=BACKEND_ROOT,
            env=environment, check=True, capture_output=True, text=True,
        )
        if entity_ids:
            with Session(pg_engine) as session:
                session.query(KnowledgeRelationship).filter(or_(
                    KnowledgeRelationship.source_entity_id.in_(entity_ids),
                    KnowledgeRelationship.target_entity_id.in_(entity_ids),
                )).delete(synchronize_session=False)
                session.query(KnowledgeEntity).filter(KnowledgeEntity.uuid.in_(entity_ids)).delete(
                    synchronize_session=False,
                )
                session.commit()


def test_knowledge_platform_persists_nested_jsonb_and_provider_neutral_ids(pg_engine, pg_session):
    EntityTypeRegistry.register_initial(pg_session)
    ProviderRegistry.register_initial(pg_session)
    pg_session.flush()
    entity = KnowledgeEntityService.create(
        pg_session,
        KnowledgeEntityCreate(
            entity_type="creature",
            canonical_name="Demon",
            language_neutral_id="creature:demon",
            aliases=["The Demon", "demons"],
        ),
    )
    document = KnowledgeDocumentStore.persist(
        pg_session,
        KnowledgeDocumentCreate(
            provider_id="tibiadata",
            provider_document_id="creatures/demon",
            entity_uuid=entity.uuid,
            raw_json={
                "creature": {
                    "name": "Demon",
                    "stats": {"hitpoints": 8200},
                    "voices": ["Your soul will be mine!"],
                }
            },
            metadata={"retrieval": {"attempt": 1}},
        ),
    )
    pg_session.commit()

    stored = pg_session.get(KnowledgeDocument, document.uuid)
    assert stored.raw_json["creature"]["stats"]["hitpoints"] == 8200
    assert stored.document_metadata == {"retrieval": {"attempt": 1}}
    assert stored.entity.uuid == entity.uuid
    with pg_engine.connect() as connection:
        jsonb_columns = set(
            connection.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name='knowledge_documents' AND data_type='jsonb'"
                )
            ).scalars()
        )
    assert jsonb_columns == {"raw_json", "metadata"}


def test_auth_profile_guild_membership_event_and_join_flow(pg_client, pg_session):
    registered = pg_client.post(
        "/api/v1/auth/register",
        json={
            "username": "postgres-auth",
            "email": "postgres-auth@example.com",
            "password": "postgres-password",
            "tibia_character_name": "Postgres Knight",
        },
    )
    assert registered.status_code == 200
    login = pg_client.post(
        "/api/v1/auth/login",
        data={"username": "postgres-auth", "password": "postgres-password"},
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    profile = pg_client.get("/api/v1/profile/me", headers=headers)
    assert profile.status_code == 200 and profile.json()["tibia_character_name"] is None

    member = pg_session.query(User).filter_by(username="postgres-auth").one()
    member.guild_name = "Postgres Guild"
    member.tibia_character_name = "Postgres Knight"
    member.tibia_status = "ownership_verified"
    pg_session.add(UserCharacter(
        user_id=member.id, character_name="Postgres Knight", normalized_name="postgres knight",
        ownership_status="verified", ownership_verified_at=datetime.now(UTC),
        guild_name="Postgres Guild", guild_rank="Member",
    ))
    manager = _user(pg_session, "postgres-leader", rank="Leader")
    pg_session.add(GuildMemberSnapshot(guild_name="Postgres Guild", character_name="Postgres Knight"))
    event = Event(
        type="hunt_event", title="PostgreSQL Hunt", description="Integration flow",
        start_date=datetime.now(UTC) + timedelta(hours=1), status="active", is_active=True,
        is_public=False, registration_enabled=True, guild_name="Postgres Guild",
        creator_id=manager.id,
    )
    pg_session.add(event)
    pg_session.commit()
    joined = pg_client.post(f"/api/v1/events/{event.id}/join", headers=headers)
    assert joined.status_code == 200
    assert pg_session.query(EventParticipant).filter_by(event_id=event.id, user_id=member.id).one()


def test_leadership_notifications_admin_audit_and_transaction_rollback(pg_session):
    leader = _user(pg_session, "postgres-audit-leader", rank="Leader")
    applicant = _user(pg_session, "postgres-applicant")
    pg_session.add(UserCharacter(user_id=applicant.id, character_name="Applicant PG", guild_name="Postgres Guild"))
    role = GuildLeadershipRole(
        guild_name="Postgres Guild", role_code="vice", display_name_key="vice",
        description_key="vice-description", target_count=1, is_active=True,
        recruitment_enabled=True, created_by_id=leader.id,
    )
    pg_session.add(role)
    pg_session.flush()
    opening = GuildLeadershipOpening(
        guild_name="Postgres Guild", role_id=role.id, title="Viceleader",
        responsibilities="Lead", requirements="Be active", openings_count=1,
        status="open", created_by_id=leader.id,
    )
    pg_session.add(opening)
    pg_session.flush()
    application = GuildLeadershipApplication(
        opening_id=opening.id, applicant_user_id=applicant.id, character_name="Applicant PG",
        status="applied", why_apply="Help", contribution="Organize", availability="Weekly",
        leadership_experience="Prior guild", profile_snapshot={"level": 500},
        conduct_agreed_at=datetime.now(UTC), conduct_version="v1", submitted_at=datetime.now(UTC),
    )
    pg_session.add_all([
        application,
        InternalNotification(
            recipient_user_id=leader.id, guild_name="Postgres Guild",
            notification_type="leadership_application_received", title_key="received",
            message_key="received", interpolation={"applicant": "Applicant PG"},
            deduplication_key="pg-application-1",
        ),
        WorkspaceAudit(
            actor_id=leader.id, workspace_type="guild", guild_name="Postgres Guild",
            action="admin_assistance", assisted=True, safe_metadata={"source": "integration"},
        ),
    ])
    pg_session.commit()
    assert pg_session.query(GuildLeadershipApplication).one().profile_snapshot["level"] == 500
    assert pg_session.query(InternalNotification).one()
    assert pg_session.query(WorkspaceAudit).one().assisted is True

    rolled_back = _user(pg_session, "postgres-rollback")
    rolled_back_id = rolled_back.id
    pg_session.rollback()
    assert pg_session.get(User, rolled_back_id) is None


def test_postgresql_capabilities_guild_reconciliation_and_system_audit(pg_client, pg_session, monkeypatch):
    from app.api.v1.endpoints import admin as admin_endpoint

    admin = _user(pg_session, "postgres-global-admin", guild="Admin Home")
    admin.is_superuser = True
    staying = _user(pg_session, "postgres-staying", guild="Postgres Guild")
    departed = _user(pg_session, "postgres-departed", guild="Postgres Guild")
    staying.tibia_character_name = "Ray On"
    departed.tibia_character_name = "Gone Away"
    pg_session.add_all([
        UserCharacter(user_id=staying.id, character_name="Ray On", guild_name="Postgres Guild", guild_rank="Member"),
        UserCharacter(user_id=departed.id, character_name="Gone Away", guild_name="Postgres Guild", guild_rank="Member"),
    ])
    pg_session.commit()
    headers = {"Authorization": f"Bearer {create_access_token(admin.username)}"}

    final_admin = pg_client.put(
        f"/api/v1/guild-management/users/{admin.id}", headers=headers, json={"is_superuser": False},
    )
    assert final_admin.status_code == 409

    capability_update = pg_client.put(
        f"/api/v1/guild-management/users/{staying.id}", headers=headers,
        json={"is_superuser": True, "is_moderator": True, "is_writer": True},
    )
    assert capability_update.status_code == 200
    assert capability_update.json()["guild_rank"] == "Member"

    async def guild_info(_name):
        return {"name": "Postgres Guild", "world": "Antica", "members": [
            {"name": "Ray On", "rank": "Leader", "level": 500, "vocation": "Knight"},
        ]}

    monkeypatch.setattr(admin_endpoint, "get_guild_info", guild_info)
    synchronized = pg_client.post(
        "/api/v1/guild-management/sync-guild?guild_name=Postgres%20Guild", headers=headers,
    )
    assert synchronized.status_code == 200 and synchronized.json()["unlinked_users"] == 1
    pg_session.expire_all()
    assert pg_session.get(User, staying.id).guild_name == "Postgres Guild"
    assert pg_session.get(User, staying.id).guild_rank == "Leader"
    assert pg_session.get(User, departed.id).guild_name is None
    audits = {row.action: row for row in pg_session.query(WorkspaceAudit).all()}
    assert audits["user_capabilities_updated"].safe_metadata["actor_context"] == "system"
    assert audits["guild_membership_synchronized"].safe_metadata["source"] == "tibiadata"


def test_postgresql_scheduler_claim_is_single_across_workers(pg_engine, pg_session, monkeypatch):
    monkeypatch.setattr(config.settings, "RAFFLE_SCHEDULER_MAX_RETRIES", 3)
    owner = _user(pg_session, "postgres-raffle-owner", rank="Leader")
    raffle = Raffle(
        title="Concurrent claim", public_code="PGCLM1", guild_name="Postgres Guild",
        run_mode="automatic", purpose="test", scheduled_run_at=datetime.now(UTC) - timedelta(seconds=1),
        execution_state="pending", status="open", created_by_id=owner.id, is_active=True,
    )
    pg_session.add(raffle)
    pg_session.commit()

    factory = sessionmaker(bind=pg_engine)

    def claim(worker_id: str):
        with factory() as session:
            return RaffleSchedulerService(worker_id).claim_one(session)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(claim, ["pg-worker-1", "pg-worker-2"]))
    successful = [result for result in results if result is not None]
    assert len(successful) == 1
    pg_session.expire_all()
    assert pg_session.get(Raffle, raffle.id).execution_state == "claimed"


def test_knowledge_worker_schema_uses_jsonb_foreign_keys_and_partial_idempotency(pg_engine):
    inspector = inspect(pg_engine)
    assert {
        "knowledge_jobs",
        "knowledge_job_attempts",
        "knowledge_worker_heartbeats",
        "knowledge_provider_cursors",
    }.issubset(inspector.get_table_names())
    with pg_engine.connect() as connection:
        jsonb_columns = set(
            connection.execute(
                text(
                    "SELECT table_name || '.' || column_name "
                    "FROM information_schema.columns "
                    "WHERE table_schema='public' AND data_type='jsonb' "
                    "AND table_name IN ('knowledge_jobs','knowledge_job_attempts',"
                    "'knowledge_worker_heartbeats','knowledge_provider_cursors')"
                )
            ).scalars()
        )
        index_definition = connection.execute(
            text(
                "SELECT indexdef FROM pg_indexes WHERE schemaname='public' "
                "AND indexname='uq_knowledge_jobs_active_idempotency'"
            )
        ).scalar_one()
    assert {
        "knowledge_jobs.scope",
        "knowledge_jobs.payload",
        "knowledge_job_attempts.metrics",
        "knowledge_worker_heartbeats.safe_metadata",
        "knowledge_provider_cursors.cursor",
    } == jsonb_columns
    assert "UNIQUE" in index_definition and " WHERE " in index_definition
    foreign_tables = {
        key["referred_table"] for key in inspector.get_foreign_keys("knowledge_jobs")
    }
    assert {"knowledge_providers", "knowledge_entity_types", "knowledge_jobs", "users"} <= foreign_tables


def test_postgresql_concurrent_knowledge_enqueue_has_one_active_job(pg_engine, pg_session):
    _register_reference_provider(pg_session)
    pg_session.commit()
    factory = sessionmaker(bind=pg_engine, expire_on_commit=False)

    def enqueue_same_job(_worker_number: int) -> tuple[str, bool]:
        with factory() as session:
            result = KnowledgeJobService.enqueue(session, _reference_job())
            session.commit()
            return str(result.job.id), result.created

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(enqueue_same_job, range(2)))

    assert len({job_id for job_id, _created in results}) == 1
    assert sum(created for _job_id, created in results) == 1
    pg_session.expire_all()
    assert pg_session.query(KnowledgeJob).filter(KnowledgeJob.state == "pending").count() == 1


def test_postgresql_concurrent_creature_child_enqueue_is_idempotent(pg_engine, pg_session):
    _register_tibiawiki_provider(pg_session)
    parent = KnowledgeJobService.enqueue(
        pg_session,
        EnqueueKnowledgeJob(
            provider_id="tibiawiki",
            job_type="creature_catalog",
            entity_type="creature",
            scope={"batch_limit": 1},
            payload={},
            trigger="manual",
        ),
    ).job
    pg_session.commit()
    factory = sessionmaker(bind=pg_engine, expire_on_commit=False)

    def enqueue_same_child(_worker_number: int) -> tuple[str, bool]:
        with factory() as session:
            result = KnowledgeJobService.enqueue(
                session,
                EnqueueKnowledgeJob(
                    provider_id="tibiawiki",
                    job_type="creature_detail",
                    entity_type="creature",
                    scope={"external_id": "38"},
                    payload={"external_id": "38", "page_title": "Demon"},
                    parent_job_id=parent.id,
                    correlation_id=parent.correlation_id,
                    trigger="system",
                ),
            )
            session.commit()
            return str(result.job.id), result.created

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(enqueue_same_child, range(2)))

    assert len({job_id for job_id, _created in results}) == 1
    assert sum(created for _job_id, created in results) == 1
    pg_session.expire_all()
    children = pg_session.query(KnowledgeJob).filter(KnowledgeJob.parent_job_id == parent.id).all()
    assert len(children) == 1
    assert children[0].correlation_id == parent.correlation_id


def test_postgresql_concurrent_item_child_enqueue_is_idempotent(pg_engine, pg_session):
    _register_tibiawiki_provider(pg_session)
    parent = KnowledgeJobService.enqueue(
        pg_session,
        EnqueueKnowledgeJob(
            provider_id="tibiawiki",
            job_type="item_catalog",
            entity_type="item",
            scope={"batch_limit": 1},
            payload={},
            trigger="manual",
        ),
    ).job
    pg_session.commit()
    factory = sessionmaker(bind=pg_engine, expire_on_commit=False)

    def enqueue_same_child(_worker_number: int) -> tuple[str, bool]:
        with factory() as session:
            result = KnowledgeJobService.enqueue(
                session,
                EnqueueKnowledgeJob(
                    provider_id="tibiawiki",
                    job_type="item_detail",
                    entity_type="item",
                    payload={"external_id": "111", "page_title": "Magic Sword"},
                    parent_job_id=parent.id,
                    correlation_id=parent.correlation_id,
                    trigger="system",
                ),
            )
            session.commit()
            return str(result.job.id), result.created

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(enqueue_same_child, range(2)))

    assert len({job_id for job_id, _created in results}) == 1
    assert sum(created for _job_id, created in results) == 1
    pg_session.expire_all()
    assert pg_session.query(KnowledgeJob).filter(KnowledgeJob.parent_job_id == parent.id).count() == 1


def test_postgresql_concurrent_quest_child_enqueue_is_idempotent(pg_engine, pg_session):
    _register_tibiawiki_provider(pg_session)
    parent = KnowledgeJobService.enqueue(pg_session, EnqueueKnowledgeJob(
        provider_id="tibiawiki", job_type="quest_catalog", entity_type="quest",
        scope={"batch_limit": 1}, payload={}, trigger="manual",
    )).job
    pg_session.commit()
    factory = sessionmaker(bind=pg_engine, expire_on_commit=False)

    def enqueue_same_child(_worker_number: int) -> tuple[str, bool]:
        with factory() as session:
            result = KnowledgeJobService.enqueue(session, EnqueueKnowledgeJob(
                provider_id="tibiawiki", job_type="quest_detail", entity_type="quest",
                payload={"external_id": "700", "page_title": "Explorer Society Quest"},
                parent_job_id=parent.id, correlation_id=parent.correlation_id, trigger="system",
            ))
            session.commit()
            return str(result.job.id), result.created

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(enqueue_same_child, range(2)))
    assert len({job_id for job_id, _created in results}) == 1
    assert sum(created for _job_id, created in results) == 1
    pg_session.expire_all()
    assert pg_session.query(KnowledgeJob).filter(KnowledgeJob.parent_job_id == parent.id).count() == 1


def test_postgresql_quest_fixture_normalizes_missions_and_deduplicates_relations(pg_session):
    _register_tibiawiki_provider(pg_session)
    raw = json.loads((Path(__file__).parent / "fixtures" / "tibiawiki_quest_detail.json").read_text(encoding="utf-8"))
    stored = KnowledgeDocumentStore.persist(pg_session, KnowledgeDocumentCreate(
        provider_id="tibiawiki", provider_document_id="quest:700", raw_json=raw,
        metadata={"document_kind": "quest_detail"},
    ))
    document = KnowledgeDocumentDTO(
        provider_code="tibiawiki", provider_document_id="quest:700", raw_json=raw,
        metadata={"document_kind": "quest_detail"},
    )
    normalized = TibiaWikiQuestAdapter().normalize(document, KnowledgeNormalizationContext(
        job_id=uuid4(), attempt_id=uuid4(), correlation_id=uuid4(),
        provider_code="tibiawiki", entity_type="quest",
    ))
    applied = KnowledgeNormalizationService.apply(pg_session, normalized)
    KnowledgeNormalizationService.apply(pg_session, normalized)
    pg_session.commit()
    quest = pg_session.query(TibiaWikiQuest).one()
    assert quest.knowledge_entity_id == applied.entity_uuid and quest.data_version == 1
    assert [mission.sequence for mission in pg_session.query(QuestMission).order_by(QuestMission.sequence)] == [1, 2]
    assert pg_session.query(KnowledgeRelationship).filter_by(source_entity_id=applied.entity_uuid, is_current=True).count() == 18
    assert pg_session.query(KnowledgeQuestRelation).count() == 0
    assert stored.raw_json["future_envelope_field"] == "retained"


def test_postgresql_npc_and_location_fixtures_normalize_idempotently(pg_session):
    _register_tibiawiki_provider(pg_session)
    cases = (
        ("npc", "800", TibiaWikiNpcAdapter(), TibiaWikiNpc),
        ("location", "900", TibiaWikiLocationAdapter(), TibiaWikiLocation),
    )
    for entity_type, external_id, adapter, model in cases:
        raw = json.loads((Path(__file__).parent / "fixtures" / f"tibiawiki_{entity_type}_detail.json").read_text(encoding="utf-8"))
        document = KnowledgeDocumentDTO(
            provider_code="tibiawiki", provider_document_id=f"{entity_type}:{external_id}", raw_json=raw,
            metadata={"document_kind": f"{entity_type}_detail"},
        )
        normalized = adapter.normalize(document, KnowledgeNormalizationContext(
            job_id=uuid4(), attempt_id=uuid4(), correlation_id=uuid4(),
            provider_code="tibiawiki", entity_type=entity_type,
        ))
        first = KnowledgeNormalizationService.apply(pg_session, normalized)
        second = KnowledgeNormalizationService.apply(pg_session, normalized)
        row = pg_session.query(model).one()
        assert first.status == "created" and second.status == "unchanged"
        assert row.knowledge_entity_id == first.entity_uuid and row.data_version == 1
    pg_session.commit()


def test_postgresql_item_fixture_normalizes_and_relationship_deduplicates(pg_session):
    _register_tibiawiki_provider(pg_session)
    raw = json.loads(
        (Path(__file__).parent / "fixtures" / "tibiawiki_item_detail.json").read_text(encoding="utf-8")
    )
    stored = KnowledgeDocumentStore.persist(
        pg_session,
        KnowledgeDocumentCreate(
            provider_id="tibiawiki",
            provider_document_id="item:111",
            raw_json=raw,
            metadata={"document_kind": "item_detail"},
        ),
    )
    adapter = TibiaWikiItemAdapter()
    document = KnowledgeDocumentDTO(
        provider_code="tibiawiki",
        provider_document_id="item:111",
        raw_json=raw,
        metadata={"document_kind": "item_detail"},
    )
    context = KnowledgeNormalizationContext(
        job_id=KnowledgeJobService.enqueue(
            pg_session,
            EnqueueKnowledgeJob(
                provider_id="tibiawiki",
                job_type="item_detail",
                entity_type="item",
                payload={"external_id": "111", "page_title": "Magic Sword"},
            ),
        ).job.id,
        attempt_id=uuid4(),
        correlation_id=uuid4(),
        provider_code="tibiawiki",
        entity_type="item",
    )
    normalized = adapter.normalize(document, context)
    applied = KnowledgeNormalizationService.apply(pg_session, normalized)
    KnowledgeNormalizationService.apply(pg_session, normalized)
    upsert_drop_relationship(
        pg_session,
        provider_id="tibiawiki",
        creature_name="Demon",
        item_name="Magic Sword",
        item_entity_uuid=applied.entity_uuid,
        source_document_id="item:111",
        source_direction="item_dropped_by",
    )
    pg_session.commit()

    item = pg_session.query(Item).one()
    assert item.knowledge_entity_id == applied.entity_uuid
    assert item.category == "Weapon" and item.data_version == 1
    assert stored.raw_json["future_envelope_field"] == "retained"
    assert pg_session.query(KnowledgeRelationship).filter_by(source_entity_id=applied.entity_uuid, is_current=True).count() == 2
    assert pg_session.query(KnowledgeCreatureItemDrop).count() == 0


def test_postgresql_creature_bridge_allows_only_one_row_per_knowledge_entity(pg_session):
    EntityTypeRegistry.register_initial(pg_session)
    entity = KnowledgeEntityService.create(
        pg_session,
        KnowledgeEntityCreate(
            entity_type="creature",
            canonical_name="Demon",
            language_neutral_id="creature:tibiawiki:38",
        ),
    )
    pg_session.add(
        Creature(
            name="Demon",
            normalized_name="demon",
            hitpoints=8200,
            experience=6000,
            knowledge_entity_id=entity.uuid,
        )
    )
    pg_session.commit()

    pg_session.add(
        Creature(
            name="Duplicate Demon",
            normalized_name="duplicate demon",
            hitpoints=8200,
            experience=6000,
            knowledge_entity_id=entity.uuid,
        )
    )
    with pytest.raises(IntegrityError):
        pg_session.flush()
    pg_session.rollback()


def test_postgresql_skip_locked_prevents_duplicate_knowledge_claim(pg_engine, pg_session):
    _register_reference_provider(pg_session)
    job = KnowledgeJobService.enqueue(pg_session, _reference_job(payload_suffix="dragon")).job
    pg_session.commit()
    factory = sessionmaker(bind=pg_engine, expire_on_commit=False)

    def claim(worker_id: str) -> str | None:
        with factory() as session:
            claimed = KnowledgeJobService.claim_one(session, worker_id, lease_seconds=60)
            session.commit()
            return str(claimed.id) if claimed else None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(claim, ["knowledge-pg-1", "knowledge-pg-2"]))

    successful = [job_id for job_id in results if job_id is not None]
    assert successful == [str(job.id)]
    pg_session.expire_all()
    stored = pg_session.get(KnowledgeJob, job.id)
    assert stored.state == "claimed" and stored.worker_id in {"knowledge-pg-1", "knowledge-pg-2"}


def test_readiness_schema_mismatch_unavailable_database_and_rollback(pg_engine):
    verify_connection_and_schema(pg_engine)
    with pg_engine.begin() as connection:
        connection.execute(text("UPDATE alembic_version SET version_num='deliberate_mismatch'"))
    try:
        with pg_engine.connect() as connection:
            assert readiness_status(connection) == (False, "schema_mismatch")
        with pytest.raises(DatabaseNotReadyError, match="schema is missing or outdated"):
            verify_connection_and_schema(pg_engine)
    finally:
        with pg_engine.begin() as connection:
            connection.execute(
                text("UPDATE alembic_version SET version_num=:revision"),
                {"revision": expected_schema_revision()},
            )

    unavailable_url = make_url(_test_url()).set(port=1)
    unavailable = create_database_engine(
        url=unavailable_url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 1},
    )
    try:
        with pytest.raises(DatabaseNotReadyError, match="unavailable"):
            verify_connection_and_schema(unavailable)
    finally:
        unavailable.dispose()
