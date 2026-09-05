from __future__ import annotations

import asyncio
import hashlib
import io
from datetime import UTC, datetime
from uuid import UUID, uuid4

from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.security import create_access_token
from app.db.database import Base
from app.knowledge.models import (
    KnowledgeDocument,
    KnowledgeEntity,
    KnowledgeJob,
    KnowledgeJobAttempt,
    KnowledgeProvider,
)
from app.knowledge.registry import EntityTypeRegistry, ProviderRegistry
from app.knowledge.services.failures import MalformedProviderPayloadError
from app.knowledge.services.jobs import KnowledgeJobService
from app.knowledge.workers.knowledge_worker import KnowledgeWorker
from app.models.external_data import TibiaWikiLocation, TibiaWikiNpc
from app.models.media_asset import MediaAsset
from app.services import media_asset_service as media
from app.services import media_path_service as media_paths
from app.services.entity_media_ingestion_service import EntityMediaIngestionService
from app.services.media_evidence_service import (
    evidence_for_entities,
    explicit_provider_media_reference,
)
from tests.conftest import make_user


def _png_bytes() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (2, 2), color=(30, 50, 70)).save(output, format="PNG")
    return output.getvalue()


def _registry(db):
    EntityTypeRegistry.register_initial(db)
    ProviderRegistry.register_initial(db)
    db.flush()
    provider = db.get(KnowledgeProvider, "tibiawiki")
    provider.enabled = True
    provider.health = "healthy"
    provider.rate_limit = {}
    db.flush()


def _entity(db, entity_type: str, name: str) -> KnowledgeEntity:
    row = KnowledgeEntity(
        entity_type=entity_type,
        canonical_name=name,
        slug=name.casefold().replace(" ", "-"),
        language_neutral_id=f"media-coverage:{entity_type}:{name}",
    )
    db.add(row)
    db.flush()
    return row


def _npc(db, name: str, external_id: str = "800") -> TibiaWikiNpc:
    entity = _entity(db, "npc", name)
    row = TibiaWikiNpc(
        name=name,
        normalized_name=name.casefold(),
        slug=entity.slug,
        external_id=external_id,
        source_name="tibiawiki",
        source_url=f"https://tibia.fandom.com/wiki/{entity.slug}",
        image_url=f"https://provider.invalid/{entity.slug}.gif",
        knowledge_entity_id=entity.uuid,
        provider_metadata={},
        supplied_fields=[],
    )
    db.add(row)
    db.flush()
    return row


def _location(db, name: str, external_id: str = "900") -> TibiaWikiLocation:
    entity = _entity(db, "location", name)
    row = TibiaWikiLocation(
        name=name,
        normalized_name=name.casefold(),
        slug=entity.slug,
        external_id=external_id,
        source_name="tibiawiki",
        source_url=f"https://tibia.fandom.com/wiki/{entity.slug}",
        image_url=f"https://provider.invalid/{entity.slug}.png",
        knowledge_entity_id=entity.uuid,
        provider_metadata={},
        supplied_fields=[],
    )
    db.add(row)
    db.flush()
    return row


def _document(db, entity_type: str, row, wikitext: str, *, title: str | None = None):
    raw = {
        "parse": {
            "pageid": int(row.external_id),
            "title": title or row.name,
            "wikitext": {"*": wikitext},
        },
    }
    encoded = repr(raw).encode()
    db.add(KnowledgeDocument(
        provider_id="tibiawiki",
        provider_document_id=f"{entity_type}:{row.external_id}",
        entity_uuid=row.knowledge_entity_id,
        raw_json=raw,
        checksum=hashlib.sha256(encoded).hexdigest(),
        content_identity=hashlib.sha256(encoded + uuid4().bytes).hexdigest(),
        document_metadata={"document_kind": f"{entity_type}_detail"},
    ))
    db.flush()


def _auth(user) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.username)}"}


def _isolated_factory(tmp_path, name: str):
    engine = create_engine(f"sqlite:///{tmp_path / name}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


def _provider_health_snapshot(provider: KnowledgeProvider):
    return provider.health, provider.last_success_at, provider.consecutive_failures


def test_explicit_primary_infobox_media_is_required_and_maps_are_rejected():
    accepted = explicit_provider_media_reference(
        "{{Infobox NPC\n| name = Exact Guide\n| image = [[File:Exact Guide.gif|64px]]\n}}",
        "npc",
    )
    assert accepted.eligible is True
    assert accepted.source_url.endswith("/Special:FilePath/Exact_Guide.gif")

    absent = explicit_provider_media_reference("{{Infobox NPC\n| name = Exact Guide\n}}", "npc")
    malformed = explicit_provider_media_reference(
        "{{Infobox NPC\n| image = https://unsafe.invalid/image.gif\n}}",
        "npc",
    )
    unrelated = explicit_provider_media_reference(
        "{{Infobox Geography\n| map = [[Image:Map edron.jpg|150px]]\n}}\n"
        "[[File:Unrelated Screenshot.png]]",
        "location",
    )
    assert absent.state == "no_source_evidence"
    assert malformed.state == "malformed_source"
    assert unrelated.state == "no_source_evidence"
    assert unrelated.rejected_unrelated_reference is True


def test_evidence_binding_is_exact_and_does_not_use_nearby_titles(db):
    _registry(db)
    row = _npc(db, "Exact Guide")
    _document(
        db,
        "npc",
        row,
        "{{Infobox NPC\n| name = Different Guide\n| image = File:Different Guide.gif\n}}",
        title="Different Guide",
    )
    evidence = evidence_for_entities(db, "npc", [row])[row.id]
    # Stable numeric provider identity is exact even when the provider title is
    # an alias; no fuzzy title search participates in the binding.
    assert evidence.eligible is True

    reference = _location(db, "Exact Place", external_id="reference:exact-place")
    resolved = evidence_for_entities(db, "location", [reference])[reference.id]
    assert resolved.state == "unresolved_source"


def test_canonical_npc_and_location_keys_and_exact_legacy_bridge(client, db, tmp_path):
    _registry(db)
    npc = _npc(db, "Legacy Keeper", external_id="801")
    location = _location(db, "Exact Place", external_id="901")
    npc_file = tmp_path / "npc.gif"
    location_file = tmp_path / "location.png"
    npc_file.write_bytes(b"GIF89a")
    location_file.write_bytes(_png_bytes())
    db.add_all([
        MediaAsset(
            asset_key=media.build_legacy_npc_asset_key(npc),
            status="cached",
            local_path=str(npc_file),
            content_type="image/gif",
        ),
        MediaAsset(
            asset_key=media.build_location_asset_key(location),
            status="cached",
            local_path=str(location_file),
            content_type="image/png",
        ),
        MediaAsset(
            asset_key="npc:tibiawiki:nearby",
            status="cached",
            local_path=str(npc_file),
            content_type="image/gif",
        ),
    ])
    db.commit()

    assert media.build_npc_asset_key(npc) == f"npc:knowledge:{npc.knowledge_entity_id}"
    assert media.build_location_asset_key(location) == f"location:knowledge:{location.knowledge_entity_id}"
    npc_response = client.get(f"/api/v1/npcs/{npc.knowledge_entity_id}/image")
    location_response = client.get(f"/api/v1/locations/{location.knowledge_entity_id}/image")
    assert npc_response.status_code == location_response.status_code == 200
    assert npc_response.headers["x-asset-key"] == media.build_legacy_npc_asset_key(npc)
    assert location_response.headers["x-asset-key"] == media.build_location_asset_key(location)
    location_detail = client.get(f"/api/v1/locations/{location.slug}").json()
    assert location_detail["image_url"].startswith("/api/v1/locations/")
    assert "provider.invalid" not in str(location_detail)
    assert client.get("/api/v1/locations/exact-place-nearby/image").status_code == 404


def test_unavailable_location_and_npc_never_expose_provider_image_urls(client, db):
    _registry(db)
    npc = _npc(db, "Uncached Guide", external_id="802")
    location = _location(db, "Uncached Place", external_id="902")
    db.commit()

    npc_detail = client.get(f"/api/v1/npcs/{npc.knowledge_entity_id}").json()
    location_detail = client.get(f"/api/v1/locations/{location.knowledge_entity_id}").json()
    assert npc_detail["media"]["status"] == "unavailable"
    assert npc_detail["media"]["url"] is None and npc_detail["media"]["source_url"] is None
    assert location_detail["image_url"] is None
    assert "provider.invalid" not in str(npc_detail) and "provider.invalid" not in str(location_detail)
    assert client.get(f"/api/v1/locations/{location.knowledge_entity_id}/image").status_code == 404


def test_missing_local_file_is_not_advertised_as_cached_media(client, db, tmp_path):
    _registry(db)
    location = _location(db, "Missing File Place", external_id="904")
    db.add(MediaAsset(
        asset_key=media.build_location_asset_key(location),
        status="cached",
        local_path=str(tmp_path / "does-not-exist.png"),
        content_type="image/png",
    ))
    db.commit()

    detail = client.get(f"/api/v1/locations/{location.knowledge_entity_id}")
    image = client.get(f"/api/v1/locations/{location.knowledge_entity_id}/image")

    assert detail.status_code == 200 and detail.json()["image_url"] is None
    assert image.status_code == 404
    assert image.headers["x-image-status"] == "local_file_missing"


def test_admin_media_controls_are_bounded_canary_gated_and_deduplicated(client, db):
    _registry(db)
    admin = make_user(db, username="entity_media_admin", is_superuser=True)
    db.commit()
    headers = _auth(admin)

    assert client.post("/api/v1/admin/sync/media/npcs/canary", json={}).status_code == 401
    blocked = client.post(
        "/api/v1/admin/sync/media/npcs/batch",
        json={"after_id": 0, "batch_size": 10},
        headers=headers,
    )
    assert blocked.status_code == 409
    canary = client.post("/api/v1/admin/sync/media/npcs/canary", json={}, headers=headers)
    duplicate = client.post(
        "/api/v1/admin/sync/media/npcs/canary",
        json={"after_id": 99},
        headers=headers,
    )
    assert canary.status_code == duplicate.status_code == 202
    assert canary.json()["batch_size"] == 3
    assert duplicate.json()["created"] is False
    assert duplicate.json()["job_id"] == canary.json()["job_id"]
    assert client.post(
        "/api/v1/admin/sync/media/npcs/batch",
        json={"batch_size": 26},
        headers=headers,
    ).status_code == 422

    job = db.get(KnowledgeJob, UUID(canary.json()["job_id"]))
    job.state = "succeeded"
    job.attempt_count = 1
    job.completed_at = datetime.now(UTC)
    db.add(KnowledgeJobAttempt(
        job_id=job.id,
        attempt_number=1,
        worker_id="completed-canary",
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        outcome="succeeded",
        metrics={"eligible": 1, "failure_codes": {}},
    ))
    db.commit()
    batch = client.post(
        "/api/v1/admin/sync/media/npcs/batch",
        json={"after_id": 3, "batch_size": 10},
        headers=headers,
    )
    assert batch.status_code == 202
    assert batch.json()["cursor"] == {"after_id": 3}


def test_bounded_ingestion_is_idempotent_and_fetches_without_a_db_transaction(tmp_path, monkeypatch):
    monkeypatch.setattr(media_paths.settings, "MEDIA_STORAGE_ROOT", str(tmp_path / "media"))
    factory = _isolated_factory(tmp_path, "idempotent.db")
    with factory() as db:
        _registry(db)
        eligible = _npc(db, "Evidence Guide", external_id="803")
        absent = _npc(db, "No Evidence Guide", external_id="804")
        _document(
            db,
            "npc",
            eligible,
            "{{Infobox NPC\n| name = Evidence Guide\n| image = File:Evidence Guide.png\n}}",
        )
        _document(db, "npc", absent, "{{Infobox NPC\n| name = No Evidence Guide\n}}")
        absent_id = absent.id
        db.commit()
    active_db = None
    fetches = 0

    original_cache = media.cache_media_asset

    async def fetched(_source_url):
        nonlocal fetches
        fetches += 1
        assert active_db is not None and active_db.in_transaction() is False
        return _png_bytes(), "image/png", "https://static.wikia.nocookie.net/tibia/evidence.png"

    async def checked_cache(media_db, **kwargs):
        nonlocal active_db
        active_db = media_db
        return await original_cache(media_db, **kwargs)

    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr(media, "_fetch_image", fetched)
    monkeypatch.setattr(media, "cache_media_asset", checked_cache)
    first = asyncio.run(EntityMediaIngestionService.run_batch(
        factory,
        entity_type="npc",
        after_id=0,
        batch_size=2,
        canary=True,
        sleep=no_sleep,
    ))
    second = asyncio.run(EntityMediaIngestionService.run_batch(
        factory,
        entity_type="npc",
        after_id=0,
        batch_size=2,
        canary=True,
        sleep=no_sleep,
    ))

    assert first["eligible"] == 1 and first["network_attempts"] == 1
    assert first["counts"]["created"] == 1
    assert first["counts"]["no_source_evidence"] == 1
    assert first["cursor"]["next_after_id"] == absent_id
    assert second["counts"]["cached"] == 1 and second["network_attempts"] == 0
    assert fetches == 1


def test_unsafe_location_media_failure_is_bounded_and_sanitized(tmp_path, monkeypatch):
    factory = _isolated_factory(tmp_path, "unsafe.db")
    with factory() as db:
        _registry(db)
        row = _location(db, "Evidence Place", external_id="903")
        _document(
            db,
            "location",
            row,
            "{{Infobox Location\n| name = Evidence Place\n| image = File:Evidence Place.png\n}}",
        )
        db.commit()

    async def unsafe(_source_url):
        raise media.UnsafeMediaError("raw unsafe detail", error_code="unsafe_source")

    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr(media, "_fetch_image", unsafe)
    result = asyncio.run(EntityMediaIngestionService.run_batch(
        factory,
        entity_type="location",
        after_id=0,
        batch_size=1,
        canary=True,
        sleep=no_sleep,
    ))
    assert result["counts"]["skipped"] == 1
    assert result["failure_codes"] == {"unsafe_source": 1}
    assert "raw unsafe detail" not in str(result)


def test_knowledge_worker_completes_durable_media_job_with_cursor_metrics(tmp_path, monkeypatch):
    monkeypatch.setattr(media_paths.settings, "MEDIA_STORAGE_ROOT", str(tmp_path / "worker-media"))
    factory = _isolated_factory(tmp_path, "worker.db")
    with factory() as db:
        _registry(db)
        admin = make_user(db, username="media_worker_admin", is_superuser=True)
        row = _npc(db, "Worker Evidence Guide", external_id="805")
        _document(
            db,
            "npc",
            row,
            "{{Infobox NPC\n| name = Worker Evidence Guide\n| image = File:Worker Evidence Guide.png\n}}",
        )
        enqueued = EntityMediaIngestionService.enqueue(
            db,
            entity_type="npc",
            after_id=0,
            batch_size=1,
            canary=True,
            created_by_id=admin.id,
        )
        job_id = enqueued.job.id
        row_id = row.id
        provider = db.get(KnowledgeProvider, "tibiawiki")
        provider.health = "degraded"
        provider.last_success_at = datetime(2025, 1, 2, 3, 4, 5)
        provider.consecutive_failures = 2
        db.commit()
        expected_health = _provider_health_snapshot(provider)

    async def fetched(_source_url):
        return _png_bytes(), "image/png", "https://static.wikia.nocookie.net/tibia/worker.png"

    monkeypatch.setattr(media, "_fetch_image", fetched)
    worker = KnowledgeWorker(
        worker_id="media-test-worker",
        lease_seconds=60,
        poll_seconds=0.1,
        max_idle_seconds=1,
        session_factory=factory,
        enable_ownership_claims=False,
    )

    assert worker.run_once() is True
    with factory() as db:
        job = db.get(KnowledgeJob, job_id)
        assert job.state == "succeeded"
        assert job.attempts[0].metrics["counts"]["created"] == 1
        assert job.attempts[0].metrics["cursor"]["next_after_id"] == row_id
        assert _provider_health_snapshot(db.get(KnowledgeProvider, "tibiawiki")) == expected_health


def test_zero_evidence_media_canary_noops_without_changing_provider_health(tmp_path, monkeypatch):
    factory = _isolated_factory(tmp_path, "zero-evidence-worker.db")
    with factory() as db:
        _registry(db)
        admin = make_user(db, username="zero_evidence_media_admin", is_superuser=True)
        _npc(db, "No Evidence Worker Guide", external_id="806")
        enqueued = EntityMediaIngestionService.enqueue(
            db,
            entity_type="npc",
            after_id=0,
            batch_size=1,
            canary=True,
            created_by_id=admin.id,
        )
        job_id = enqueued.job.id
        claimed = KnowledgeJobService.claim_one(
            db,
            "zero-evidence-media-worker",
            lease_seconds=60,
        )
        assert claimed is not None and claimed.id == job_id
        provider = db.get(KnowledgeProvider, "tibiawiki")
        # Simulate an operator disabling the provider after claim. A normal
        # Knowledge fetch would be rejected by the availability guard, while
        # this retained-evidence/no-network job must remain locally runnable.
        provider.enabled = False
        provider.health = "degraded"
        provider.last_success_at = datetime(2025, 2, 3, 4, 5, 6)
        provider.consecutive_failures = 4
        db.commit()
        expected_health = _provider_health_snapshot(provider)

    worker = KnowledgeWorker(
        worker_id="zero-evidence-media-worker",
        lease_seconds=60,
        poll_seconds=0.1,
        max_idle_seconds=1,
        session_factory=factory,
        enable_ownership_claims=False,
    )
    monkeypatch.setattr(worker, "_claim", lambda: job_id)
    assert worker.run_once() is True
    with factory() as db:
        job = db.get(KnowledgeJob, job_id)
        assert job.state == "succeeded"
        assert job.attempts[0].metrics["eligible"] == 0
        assert job.attempts[0].metrics["network_attempts"] == 0
        assert job.attempts[0].metrics["counts"]["unresolved_source"] == 1
        assert _provider_health_snapshot(db.get(KnowledgeProvider, "tibiawiki")) == expected_health


def test_failed_media_job_does_not_record_provider_failure(tmp_path, monkeypatch):
    factory = _isolated_factory(tmp_path, "failed-media-worker.db")
    with factory() as db:
        _registry(db)
        admin = make_user(db, username="failed_media_admin", is_superuser=True)
        enqueued = EntityMediaIngestionService.enqueue(
            db,
            entity_type="location",
            after_id=0,
            batch_size=1,
            canary=True,
            created_by_id=admin.id,
        )
        job_id = enqueued.job.id
        provider = db.get(KnowledgeProvider, "tibiawiki")
        provider.health = "degraded"
        provider.last_success_at = datetime(2025, 3, 4, 5, 6, 7)
        provider.consecutive_failures = 2
        db.commit()
        expected_health = _provider_health_snapshot(provider)

    async def failed_batch(*_args, **_kwargs):
        raise MalformedProviderPayloadError()

    monkeypatch.setattr(EntityMediaIngestionService, "run_batch", failed_batch)
    worker = KnowledgeWorker(
        worker_id="failed-media-worker",
        lease_seconds=60,
        poll_seconds=0.1,
        max_idle_seconds=1,
        session_factory=factory,
        enable_ownership_claims=False,
    )

    assert worker.run_once() is True
    with factory() as db:
        job = db.get(KnowledgeJob, job_id)
        assert job.state == "failed"
        assert job.last_error_code == "malformed_provider_payload"
        assert _provider_health_snapshot(db.get(KnowledgeProvider, "tibiawiki")) == expected_health
