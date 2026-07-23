"""PostgreSQL-only integration coverage for the foundation baseline.

Set TEST_DATABASE_URL to a disposable database whose name visibly contains
``test``. The fixture destroys only that database's public schema.
"""
from __future__ import annotations

import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
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
from app.models.guild_member_snapshot import GuildMemberSnapshot
from app.models.leadership import GuildLeadershipApplication, GuildLeadershipOpening, GuildLeadershipRole
from app.models.raffle import InternalNotification, Raffle
from app.models.user import User
from app.models.user_character import UserCharacter
from app.models.workspace_audit import WorkspaceAudit
from app.knowledge.models import KnowledgeDocument
from app.knowledge.registry import EntityTypeRegistry, ProviderRegistry
from app.knowledge.schemas import KnowledgeDocumentCreate, KnowledgeEntityCreate
from app.knowledge.services import KnowledgeEntityService
from app.knowledge.storage import KnowledgeDocumentStore
from app.services.raffle_scheduler_service import RaffleSchedulerService


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
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
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


def test_empty_database_upgrades_to_complete_postgresql_schema(pg_engine):
    tables = set(inspect(pg_engine).get_table_names())
    assert {
        "users", "user_characters", "announcements", "events", "event_participants",
        "raffles", "raffle_scheduler_attempts", "internal_notifications", "sync_jobs",
        "workspace_audits", "guild_leadership_openings", "media_assets", "creatures",
    }.issubset(tables)
    with pg_engine.connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == expected_schema_revision()
        extensions = set(connection.execute(text("SELECT extname FROM pg_extension")).scalars())
        assert {"pg_trgm", "unaccent"}.issubset(extensions)
        json_type = connection.execute(text(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_name='raffle_participants' AND column_name='source_data'"
        )).scalar_one()
        assert json_type == "jsonb"
        constraints = set(connection.execute(text(
            "SELECT conname FROM pg_constraint WHERE connamespace = 'public'::regnamespace"
        )).scalars())
        assert {"uq_event_participant_user", "uq_raffle_participant_user", "fk_leadership_application_assignment"}.issubset(constraints)
        index_definitions = "\n".join(connection.execute(text(
            "SELECT indexdef FROM pg_indexes WHERE schemaname='public'"
        )).scalars())
        assert "uq_leadership_active_application" in index_definitions and " WHERE " in index_definitions
        assert "ix_raffles_scheduler_due" in index_definitions
        user_columns = {column["name"]: column for column in inspect(pg_engine).get_columns("users")}
        assert {"is_superuser", "is_moderator", "is_writer"}.issubset(user_columns)
        assert all(user_columns[name]["nullable"] is False for name in ("is_superuser", "is_moderator", "is_writer"))


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


def test_auth_profile_guild_membership_event_and_join_flow(pg_client, pg_session, monkeypatch):
    from app.api.v1.endpoints import auth as auth_endpoint

    async def skip_provider_sync(*_args, **_kwargs):
        return None

    monkeypatch.setattr(config.settings, "TIBIA_VALIDATION_ENABLED", False)
    monkeypatch.setattr(auth_endpoint, "try_sync_user_character_snapshot", skip_provider_sync)
    registered = pg_client.post(
        "/api/v1/auth/register",
        json={
            "username": "postgres-auth",
            "email": "postgres-auth@example.test",
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
    assert profile.status_code == 200 and profile.json()["tibia_character_name"] == "Postgres Knight"

    member = pg_session.query(User).filter_by(username="postgres-auth").one()
    member.guild_name = "Postgres Guild"
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
