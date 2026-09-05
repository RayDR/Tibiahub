from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import config
from app.core.security import create_access_token
from app.db.database import Base
from app.knowledge.adapters import (
    KnowledgeAdapterRegistry,
    KnowledgeFetchResult,
    KnowledgeValidationResult,
    ReferenceKnowledgeAdapter,
)
from app.knowledge.models import (
    KnowledgeDocument,
    KnowledgeDomainEvent,
    KnowledgeEntity,
    KnowledgeEntityType,
    KnowledgeJob,
    KnowledgeJobAttempt,
    KnowledgeProvider,
    KnowledgeProviderCursor,
    KnowledgeWorkerHeartbeat,
)
from app.knowledge.registry import EntityTypeRegistry
from app.knowledge.services import (
    CompletedJobRecreationError,
    EnqueueKnowledgeJob,
    KnowledgeJobConflictError,
    KnowledgeJobOwnershipError,
    KnowledgeJobService,
)
from app.knowledge.services.failures import (
    MalformedProviderPayloadError,
    ProviderHTTPError,
    ProviderTimeoutError,
    classify_failure,
    retry_delay_seconds,
)
from app.knowledge.services.idempotency import knowledge_job_idempotency_key
from app.knowledge.services.provider_health import record_provider_failure, record_provider_success
from app.knowledge.workers.knowledge_worker import KnowledgeWorker
from app.models.workspace_audit import WorkspaceAudit
from tests.conftest import make_user


@pytest.fixture
def knowledge_jobs_registry(db):
    EntityTypeRegistry.register_initial(db)
    db.add(
        KnowledgeProvider(
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
            consecutive_failures=0,
        )
    )
    db.flush()


def enqueue(db, **overrides) -> KnowledgeJob:
    values = {
        "provider_id": "reference",
        "job_type": "reference_import",
        "entity_type": "creature",
        "scope": {"language": "en"},
        "payload": {
            "canonical_name": "Demon",
            "language_neutral_id": "creature:demon",
            "provider_document_id": "reference:demon",
        },
    }
    values.update(overrides)
    return KnowledgeJobService.enqueue(db, EnqueueKnowledgeJob(**values)).job


def test_job_schema_has_json_fields_foreign_keys_and_partial_idempotency_index(engine):
    inspector = inspect(engine)
    assert {
        "knowledge_jobs",
        "knowledge_job_attempts",
        "knowledge_worker_heartbeats",
        "knowledge_provider_cursors",
    } <= set(inspector.get_table_names())
    job_columns = {column["name"] for column in inspector.get_columns("knowledge_jobs")}
    assert {"scope", "payload", "lease_expires_at", "idempotency_key", "correlation_id"} <= job_columns
    indexes = {index["name"]: index for index in inspector.get_indexes("knowledge_jobs")}
    assert indexes["uq_knowledge_jobs_active_idempotency"]["unique"] == 1
    foreign_tables = {
        foreign_key["referred_table"] for foreign_key in inspector.get_foreign_keys("knowledge_jobs")
    }
    assert {"knowledge_providers", "knowledge_entity_types", "knowledge_jobs", "users"} <= foreign_tables


def test_idempotency_normalizes_json_and_separates_sync_semantics():
    first = knowledge_job_idempotency_key(
        provider_id="reference",
        job_type="full_sync",
        entity_type="creature",
        scope={"language": " en ", "page": 1},
        payload={"b": 2, "a": [1, 2]},
    )
    equivalent = knowledge_job_idempotency_key(
        provider_id="reference",
        job_type="full_sync",
        entity_type="creature",
        scope={"page": 1, "language": "en"},
        payload={"a": [1, 2], "b": 2},
    )
    incremental = knowledge_job_idempotency_key(
        provider_id="reference",
        job_type="incremental_sync",
        entity_type="creature",
        scope={"page": 1, "language": "en"},
        payload={"a": [1, 2], "b": 2},
    )
    scheduled = knowledge_job_idempotency_key(
        provider_id="reference",
        job_type="full_sync",
        entity_type="creature",
        scope={"page": 1, "language": "en"},
        payload={"a": [1, 2], "b": 2},
        time_bucket="2026-07-23T21:00Z",
    )
    assert first == equivalent
    assert len({first, incremental, scheduled}) == 3


def test_duplicate_active_enqueue_and_completed_recreation_policy(db, knowledge_jobs_registry):
    first = enqueue(db)
    duplicate = enqueue(db)
    assert duplicate.id == first.id
    first.state = "succeeded"
    first.completed_at = datetime.now(UTC)
    db.flush()
    with pytest.raises(CompletedJobRecreationError):
        enqueue(db)
    recreated = enqueue(db, allow_completed_recreate=True)
    assert recreated.id != first.id


def test_priority_schedule_cancel_and_attempt_number_constraint(db, knowledge_jobs_registry):
    now = datetime.now(UTC)
    due_at = now - timedelta(seconds=1)
    low = enqueue(
        db,
        payload={"canonical_name": "Low", "language_neutral_id": "creature:low"},
        priority=10,
        scheduled_at=due_at,
    )
    high = enqueue(
        db,
        payload={"canonical_name": "High", "language_neutral_id": "creature:high"},
        priority=500,
        scheduled_at=due_at,
    )
    future = enqueue(
        db,
        payload={"canonical_name": "Future", "language_neutral_id": "creature:future"},
        priority=1000,
        scheduled_at=now + timedelta(hours=1),
    )
    cancelled = enqueue(db, payload={"canonical_name": "Cancelled", "language_neutral_id": "creature:cancelled"})
    KnowledgeJobService.cancel(db, cancelled.id, now=now)
    claimed = KnowledgeJobService.claim_one(db, "worker-a", lease_seconds=60, now=now)
    assert claimed.id == high.id
    attempt = KnowledgeJobService.start_attempt(db, claimed.id, "worker-a", now=now + timedelta(seconds=1))
    duplicate_attempt = KnowledgeJobAttempt(
        job_id=claimed.id,
        attempt_number=attempt.attempt_number,
        worker_id="worker-a",
        outcome="running",
    )
    with pytest.raises(IntegrityError), db.begin_nested():
        db.add(duplicate_attempt)
        db.flush()
    assert future.state == "pending" and cancelled.state == "cancelled" and low.state == "pending"


def test_expired_lease_reassignment_blocks_stale_worker_completion(db, knowledge_jobs_registry):
    start = datetime.now(UTC)
    job = enqueue(db, scheduled_at=start - timedelta(seconds=1))
    KnowledgeJobService.claim_one(db, "worker-old", lease_seconds=30, now=start)
    old_attempt = KnowledgeJobService.start_attempt(db, job.id, "worker-old", now=start + timedelta(seconds=1))
    recovered = KnowledgeJobService.recover_expired(db, now=start + timedelta(seconds=31))
    assert recovered == [job.id] and job.state == "retrying"
    KnowledgeJobService.claim_one(db, "worker-new", lease_seconds=60, now=start + timedelta(seconds=31))
    new_attempt = KnowledgeJobService.start_attempt(db, job.id, "worker-new", now=start + timedelta(seconds=32))
    with pytest.raises(KnowledgeJobOwnershipError):
        KnowledgeJobService.complete(
            db,
            job.id,
            old_attempt.id,
            "worker-old",
            partial=False,
            metrics={},
            now=start + timedelta(seconds=33),
        )
    KnowledgeJobService.complete(
        db,
        job.id,
        new_attempt.id,
        "worker-new",
        partial=False,
        metrics={},
        now=start + timedelta(seconds=34),
    )
    assert job.state == "succeeded" and job.attempt_count == 2


def test_retry_taxonomy_backoff_retry_after_and_maximum_attempts(db, knowledge_jobs_registry):
    assert classify_failure(ProviderTimeoutError()).retryable is True
    rate_limit = classify_failure(ProviderHTTPError(429, retry_after_seconds=120))
    assert rate_limit.retryable is True and rate_limit.retry_after_seconds == 120
    assert classify_failure(ProviderHTTPError(400)).retryable is False
    assert classify_failure(MalformedProviderPayloadError()).retryable is False
    assert 10 <= retry_delay_seconds(2, jitter_fraction=0.0) <= retry_delay_seconds(2, jitter_fraction=1.0) <= 12
    assert retry_delay_seconds(1, retry_after_seconds=120) == 120

    job = enqueue(db, max_attempts=1)
    now = datetime.now(UTC)
    KnowledgeJobService.claim_one(db, "worker", lease_seconds=60, now=now)
    attempt = KnowledgeJobService.start_attempt(db, job.id, "worker", now=now + timedelta(seconds=1))
    KnowledgeJobService.fail(
        db,
        job.id,
        attempt.id,
        "worker",
        classify_failure(ProviderTimeoutError()),
        now=now + timedelta(seconds=2),
    )
    assert job.state == "failed"
    with pytest.raises(KnowledgeJobConflictError):
        KnowledgeJobService.manual_retry(db, job.id)


def test_provider_health_success_failure_and_cooldown(knowledge_jobs_registry, db):
    provider = db.get(KnowledgeProvider, "reference")
    failure = classify_failure(ProviderTimeoutError())
    now = datetime.now(UTC)
    record_provider_failure(provider, failure, now=now)
    assert provider.health == "degraded" and provider.consecutive_failures == 1
    assert provider.cooldown_until > now
    record_provider_failure(provider, failure, now=now)
    record_provider_failure(provider, failure, now=now)
    assert provider.health == "unavailable" and provider.consecutive_failures == 3
    record_provider_success(provider, now=now)
    assert provider.health == "healthy" and provider.consecutive_failures == 0 and provider.cooldown_until is None


def worker_database():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory.begin() as session:
        EntityTypeRegistry.register_initial(session)
        session.add(
            KnowledgeProvider(
                provider_id="reference",
                provider_name="Reference Adapter",
                priority=1000,
                enabled=True,
                version="stage-2a-2",
                rate_limit={},
                health="unknown",
                supports_entities=["creature"],
                supports_media=False,
                supports_search=False,
                consecutive_failures=0,
            )
        )
    return engine, factory


def test_reference_worker_persists_document_normalizes_and_heartbeats():
    engine, factory = worker_database()
    with factory.begin() as db:
        job = enqueue(db)
        job_id = job.id
        provider = db.get(KnowledgeProvider, "reference")
        provider.health = "degraded"
        provider.consecutive_failures = 2
    worker = KnowledgeWorker(
        worker_id="reference-worker",
        lease_seconds=60,
        poll_seconds=0.1,
        max_idle_seconds=1,
        session_factory=factory,
        random_source=lambda: 0,
    )
    assert worker.run_once() is True
    with factory() as db:
        job = db.get(KnowledgeJob, job_id)
        assert job.state == "succeeded"
        assert db.query(KnowledgeDocument).count() == 1
        assert db.query(KnowledgeEntity).filter_by(language_neutral_id="creature:demon").one()
        assert db.query(KnowledgeProviderCursor).count() == 1
        heartbeat = db.get(KnowledgeWorkerHeartbeat, "reference-worker")
        assert heartbeat.state == "idle" and heartbeat.node_id != ""
        event_types = {event.event_type for event in db.query(KnowledgeDomainEvent).all()}
        assert {"ProviderImported", "KnowledgeNormalized", "EntityCreated"} <= event_types
        metrics = job.attempts[0].metrics
        assert metrics["documents_received"] == 1 and metrics["entities_created"] == 1
        provider = db.get(KnowledgeProvider, "reference")
        assert provider.health == "healthy"
        assert provider.last_success_at is not None
        assert provider.consecutive_failures == 0
    engine.dispose()


def test_worker_deduplicates_identical_documents_and_reports_unchanged_entity():
    engine, factory = worker_database()
    worker = KnowledgeWorker(
        worker_id="reference-worker",
        lease_seconds=60,
        poll_seconds=0.1,
        max_idle_seconds=1,
        session_factory=factory,
    )
    with factory.begin() as db:
        first = enqueue(db)
    worker.run_once()
    with factory.begin() as db:
        second = enqueue(db, allow_completed_recreate=True)
        second_id = second.id
    worker.run_once()
    with factory() as db:
        assert db.query(KnowledgeDocument).count() == 1
        assert db.query(KnowledgeEntity).count() == 1
        assert db.get(KnowledgeJob, second_id).attempts[0].metrics["entities_unchanged"] == 1
    engine.dispose()


class TimeoutAdapter(ReferenceKnowledgeAdapter):
    def fetch(self, request):
        raise ProviderTimeoutError()


class MalformedAdapter(ReferenceKnowledgeAdapter):
    def fetch(self, request):
        return KnowledgeFetchResult(documents=())

    def validate(self, result):
        return KnowledgeValidationResult(valid=False, safe_errors=("required",))


@pytest.mark.parametrize(
    ("adapter", "expected_state", "expected_code"),
    [(TimeoutAdapter(), "retrying", "provider_timeout"), (MalformedAdapter(), "failed", "malformed_provider_payload")],
)
def test_worker_classifies_retryable_and_permanent_adapter_failures(adapter, expected_state, expected_code):
    engine, factory = worker_database()
    with factory.begin() as db:
        job_id = enqueue(db).id
    worker = KnowledgeWorker(
        worker_id="failure-worker",
        lease_seconds=60,
        poll_seconds=0.1,
        max_idle_seconds=1,
        session_factory=factory,
        adapters=KnowledgeAdapterRegistry((adapter,)),
        random_source=lambda: 0,
    )
    worker.run_once()
    with factory() as db:
        job = db.get(KnowledgeJob, job_id)
        assert job.state == expected_state and job.last_error_code == expected_code
        assert "password" not in (job.safe_last_error or "").lower()
        provider = db.get(KnowledgeProvider, "reference")
        assert provider.health == "degraded"
        assert provider.last_failure_at is not None
        assert provider.consecutive_failures == 1
    engine.dispose()


def test_disabled_and_cooling_provider_jobs_are_not_claimed():
    engine, factory = worker_database()
    with factory.begin() as db:
        job_id = enqueue(db).id
        provider = db.get(KnowledgeProvider, "reference")
        provider.enabled = False
        provider.health = "disabled"
    worker = KnowledgeWorker(worker_id="worker", lease_seconds=60, poll_seconds=0.1, max_idle_seconds=1, session_factory=factory)
    assert worker.run_once() is False
    with factory.begin() as db:
        provider = db.get(KnowledgeProvider, "reference")
        provider.enabled = True
        provider.health = "degraded"
        provider.cooldown_until = datetime.now(UTC) + timedelta(minutes=5)
    assert worker.run_once() is False
    with factory() as db:
        assert db.get(KnowledgeJob, job_id).state == "pending"
    engine.dispose()


def test_worker_loop_stops_gracefully(monkeypatch):
    engine, factory = worker_database()
    monkeypatch.setattr(config.settings, "KNOWLEDGE_WORKER_ENABLED", True)
    worker = KnowledgeWorker(worker_id="graceful-worker", lease_seconds=60, poll_seconds=0.1, max_idle_seconds=0.2, session_factory=factory)
    stop = threading.Event()
    thread = threading.Thread(target=worker.run, args=(stop,))
    thread.start()
    stop.set()
    thread.join(timeout=2)
    assert not thread.is_alive()
    engine.dispose()


def test_worker_database_failure_uses_bounded_backoff_and_stops(monkeypatch):
    class UnavailableSessionFactory:
        def __init__(self):
            self.calls = 0
            self.first_call = threading.Event()

        def begin(self):
            self.calls += 1
            self.first_call.set()
            raise ConnectionError("database unavailable")

    monkeypatch.setattr(config.settings, "KNOWLEDGE_WORKER_ENABLED", True)
    factory = UnavailableSessionFactory()
    worker = KnowledgeWorker(
        worker_id="unavailable-worker",
        lease_seconds=60,
        poll_seconds=0.1,
        max_idle_seconds=0.2,
        session_factory=factory,
    )
    stop = threading.Event()
    thread = threading.Thread(target=worker.run, args=(stop,))
    thread.start()
    assert factory.first_call.wait(timeout=1)
    threading.Event().wait(0.26)
    stop.set()
    thread.join(timeout=2)
    assert not thread.is_alive()
    assert 2 <= factory.calls <= 4


def test_admin_knowledge_api_enforces_admin_pagination_transitions_and_audit(client, db, knowledge_jobs_registry):
    admin = make_user(db, username="knowledge-admin", is_superuser=True)
    member = make_user(db, username="knowledge-member")
    db.commit()
    admin_headers = {"Authorization": f"Bearer {create_access_token(admin.username)}"}
    member_headers = {"Authorization": f"Bearer {create_access_token(member.username)}"}
    assert client.get("/api/v1/admin/knowledge/providers", headers=member_headers).status_code == 403
    assert client.get("/api/v1/admin/knowledge/providers", headers=admin_headers).status_code == 200

    created = client.post(
        "/api/v1/admin/knowledge/jobs",
        headers=admin_headers,
        json={
            "provider_id": "reference",
            "job_type": "reference_import",
            "entity_type": "creature",
            "scope": {},
            "payload": {
                "canonical_name": "Demon",
                "language_neutral_id": "creature:demon",
                "provider_document_id": "reference:demon",
            },
        },
    )
    assert created.status_code == 201 and created.json()["created"] is True
    job_id = created.json()["item"]["id"]
    page = client.get("/api/v1/admin/knowledge/jobs?state=pending&limit=1", headers=admin_headers)
    assert page.status_code == 200 and page.json()["total"] == 1 and len(page.json()["items"]) == 1
    cancelled = client.post(f"/api/v1/admin/knowledge/jobs/{job_id}/cancel", headers=admin_headers)
    assert cancelled.status_code == 200 and cancelled.json()["state"] == "cancelled"
    assert client.post(f"/api/v1/admin/knowledge/jobs/{job_id}/retry", headers=admin_headers).status_code == 409
    actions = {audit.action for audit in db.query(WorkspaceAudit).filter_by(actor_id=admin.id).all()}
    assert {"knowledge_job_enqueued", "knowledge_job_cancelled"} <= actions


def test_admin_enqueue_rejects_arbitrary_url_and_unsupported_adapter(client, db, knowledge_jobs_registry):
    admin = make_user(db, username="knowledge-secure-admin", is_superuser=True)
    db.commit()
    headers = {"Authorization": f"Bearer {create_access_token(admin.username)}"}
    unsafe = client.post(
        "/api/v1/admin/knowledge/jobs",
        headers=headers,
        json={
            "provider_id": "reference",
            "job_type": "reference_import",
            "entity_type": "creature",
            "payload": {"url": "https://example.invalid"},
        },
    )
    assert unsafe.status_code == 422
    unsupported = client.post(
        "/api/v1/admin/knowledge/jobs",
        headers=headers,
        json={"provider_id": "reference", "job_type": "full_sync", "entity_type": "creature"},
    )
    assert unsupported.status_code == 400
