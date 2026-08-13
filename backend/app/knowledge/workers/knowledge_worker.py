"""Single-process durable knowledge worker; PostgreSQL owns all job state."""

from __future__ import annotations

import logging
import asyncio
import random
import signal
import threading
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Callable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.database import SessionLocal, verify_connection_and_schema
from app.knowledge.adapters import (
    AdapterNotFoundError,
    KnowledgeAdapterRegistry,
    KnowledgeDocumentDTO,
    KnowledgeFetchRequest,
    KnowledgeNormalizationContext,
    KnowledgeNormalizationMetrics,
)
from app.knowledge.events import KnowledgeEventType, emit_event
from app.knowledge.models import KnowledgeDocument, KnowledgeJob, KnowledgeProvider, KnowledgeProviderCursor
from app.knowledge.schemas import KnowledgeDocumentCreate
from app.knowledge.services.failures import (
    EmptyProviderResponseError,
    InvalidProviderConfigurationError,
    MalformedProviderPayloadError,
    OversizedProviderResponseError,
    ProviderResponseEnvelopeError,
    UnsafeProviderTextError,
    UnsupportedKnowledgeJobError,
    classify_failure,
)
from app.knowledge.services.jobs import (
    EnqueueKnowledgeJob,
    KnowledgeJobOwnershipError,
    KnowledgeJobService,
)
from app.knowledge.services.normalization import KnowledgeNormalizationService
from app.knowledge.services.observations import KnowledgeObservationService
from app.knowledge.services.provider_health import (
    record_provider_attempt,
    record_provider_failure,
    record_provider_success,
)
from app.knowledge.services.idempotency import scope_hash
from app.knowledge.storage import KnowledgeDocumentStore
from app.services.character_ownership_service import CharacterOwnershipService


logger = logging.getLogger("app.knowledge.worker")


class KnowledgeWorker:
    def __init__(
        self,
        *,
        worker_id: str,
        lease_seconds: int,
        poll_seconds: float,
        max_idle_seconds: float,
        session_factory: sessionmaker = SessionLocal,
        adapters: KnowledgeAdapterRegistry | None = None,
        random_source: Callable[[], float] = random.random,
        enable_knowledge_jobs: bool = True,
        enable_ownership_claims: bool = True,
    ):
        self.worker_id = worker_id
        self.lease_seconds = lease_seconds
        self.poll_seconds = max(0.1, poll_seconds)
        self.max_idle_seconds = max(self.poll_seconds, max_idle_seconds)
        self.session_factory = session_factory
        self.adapters = adapters or KnowledgeAdapterRegistry()
        self.random_source = random_source
        self.enable_knowledge_jobs = enable_knowledge_jobs
        self.enable_ownership_claims = enable_ownership_claims

    def _heartbeat(self, state: str, current_job_id: UUID | None = None) -> None:
        with self.session_factory.begin() as db:
            KnowledgeJobService.heartbeat(
                db,
                self.worker_id,
                state=state,
                current_job_id=current_job_id,
            )

    def _claim(self) -> UUID | None:
        with self.session_factory.begin() as db:
            KnowledgeJobService.recover_expired(db, limit=25)
            job = KnowledgeJobService.claim_one(
                db,
                self.worker_id,
                lease_seconds=self.lease_seconds,
            )
            KnowledgeJobService.heartbeat(
                db,
                self.worker_id,
                state="running" if job else "idle",
                current_job_id=job.id if job else None,
            )
            return job.id if job else None

    def _start_request(self, job_id: UUID) -> tuple[UUID, KnowledgeFetchRequest] | None:
        with self.session_factory.begin() as db:
            job = db.get(KnowledgeJob, job_id)
            provider = db.execute(
                select(KnowledgeProvider)
                .where(KnowledgeProvider.provider_id == job.provider_id)
                .with_for_update()
            ).scalar_one()
            if provider.provider_id == "tibiawiki" and not job.job_type.endswith("_renormalize"):
                requests = provider.rate_limit.get("requests") if isinstance(provider.rate_limit, dict) else None
                window_seconds = provider.rate_limit.get("window_seconds") if isinstance(provider.rate_limit, dict) else None
                if (
                    isinstance(requests, int)
                    and not isinstance(requests, bool)
                    and requests > 0
                    and isinstance(window_seconds, int)
                    and not isinstance(window_seconds, bool)
                    and window_seconds > 0
                    and provider.last_attempted_at is not None
                ):
                    attempted_at = provider.last_attempted_at
                    if attempted_at.tzinfo is None:
                        attempted_at = attempted_at.replace(tzinfo=UTC)
                    due_at = attempted_at + timedelta(seconds=window_seconds / requests)
                    if due_at > datetime.now(UTC):
                        KnowledgeJobService.defer_claim(
                            db,
                            job_id,
                            self.worker_id,
                            scheduled_at=due_at,
                        )
                        return None
            attempt = KnowledgeJobService.start_attempt(db, job_id, self.worker_id)
            record_provider_attempt(provider)
            cursor_value = None
            if job.entity_type_id:
                cursor = (
                    db.query(KnowledgeProviderCursor)
                    .filter_by(
                        provider_id=job.provider_id,
                        entity_type_id=job.entity_type_id,
                        scope_hash=scope_hash(job.scope),
                    )
                    .first()
                )
                cursor_value = deepcopy(cursor.cursor) if cursor else None
            request = KnowledgeFetchRequest(
                job_id=job.id,
                attempt_id=attempt.id,
                correlation_id=job.correlation_id,
                provider_code=job.provider_id,
                job_type=job.job_type,
                entity_type=job.entity_type_id,
                scope=deepcopy(job.scope),
                payload=deepcopy(job.payload),
                cursor=cursor_value,
            )
            return attempt.id, request

    def _require_provider_available(self, provider_id: str) -> None:
        with self.session_factory() as db:
            provider = db.get(KnowledgeProvider, provider_id)
            if provider is None or not provider.enabled or provider.health == "disabled":
                raise InvalidProviderConfigurationError()

    def _persist_result(self, request: KnowledgeFetchRequest, result) -> None:
        normalized = []
        context = KnowledgeNormalizationContext(
            job_id=request.job_id,
            attempt_id=request.attempt_id,
            correlation_id=request.correlation_id,
            provider_code=request.provider_code,
            entity_type=request.entity_type,
        )
        adapter = self.adapters.resolve(request.provider_code, request.job_type, request.entity_type)
        for document in result.documents:
            normalized.append((document, adapter.normalize(document, context)))

        with self.session_factory.begin() as db:
            job = db.execute(select(KnowledgeJob).where(KnowledgeJob.id == request.job_id).with_for_update()).scalar_one()
            KnowledgeJobService.assert_owner(job, self.worker_id, datetime.now(UTC))
            metrics = KnowledgeNormalizationMetrics(documents_received=len(result.documents))
            metric_values = metrics.as_dict()
            metric_values["discovered"] = sum(
                int(child.job_type.endswith("_detail")) for child in result.child_jobs
            )
            provider_discovered = result.provider_metadata.get("discovered")
            if isinstance(provider_discovered, int) and not isinstance(provider_discovered, bool):
                metric_values["discovered"] += max(0, provider_discovered)
            metric_values["fetched"] = len(result.documents)
            metric_values["normalized"] = 0
            metric_values["repaired"] = 0
            metric_values["skipped"] = 0
            metric_values["failed"] = 0
            metric_values["unresolved_relationships"] = 0
            invalid_members = result.provider_metadata.get("invalid_members")
            if isinstance(invalid_members, int) and not isinstance(invalid_members, bool) and invalid_members >= 0:
                metric_values["invalid_members"] = invalid_members
            for document_dto, normalization in normalized:
                persistence = KnowledgeDocumentStore.persist_with_status(
                    db,
                    KnowledgeDocumentCreate(
                        provider_id=document_dto.provider_code,
                        provider_document_id=document_dto.provider_document_id,
                        raw_json=document_dto.raw_json,
                        version=document_dto.version,
                        etag=document_dto.etag,
                        language=document_dto.language,
                        metadata={
                            **document_dto.metadata,
                            "knowledge_job_id": str(job.id),
                            "knowledge_attempt_id": str(request.attempt_id),
                            "correlation_id": str(job.correlation_id),
                        },
                    ),
                )
                applied = KnowledgeNormalizationService.apply(db, normalization)
                if applied.entity_uuid is not None:
                    persistence.document.entity_uuid = applied.entity_uuid
                observed = KnowledgeObservationService.apply(
                    db,
                    normalization,
                    document=persistence.document,
                    entity_uuid=applied.entity_uuid,
                )
                metric_values["observations_created"] = metric_values.get("observations_created", 0) + int(observed.created)
                metric_values[f"entities_{applied.status}"] += 1
                if normalization.action == "noop":
                    metric_values["skipped"] += 1
                else:
                    metric_values["normalized"] += 1
                metric_values["aliases_created"] += applied.aliases_created
                metric_values["warnings"] += applied.warnings
                for metric_name, metric_value in applied.metrics.items():
                    metric_values[metric_name] = metric_values.get(metric_name, 0) + metric_value
                metric_values["repaired"] += applied.metrics.get("entities_repaired", 0)
                if applied.status in {"created", "updated"}:
                    emit_event(
                        db,
                        KnowledgeEventType.KNOWLEDGE_NORMALIZED,
                        entity_uuid=applied.entity_uuid,
                        provider_id=job.provider_id,
                        payload={"job_id": str(job.id), "status": applied.status},
                    )
            for child in result.child_jobs:
                enqueued = KnowledgeJobService.enqueue(
                    db,
                    EnqueueKnowledgeJob(
                        provider_id=job.provider_id,
                        job_type=child.job_type,
                        entity_type=child.entity_type,
                        scope=child.scope,
                        payload=child.payload,
                        priority=child.priority,
                        parent_job_id=job.id,
                        correlation_id=job.correlation_id,
                        trigger="system",
                        allow_completed_recreate=child.allow_completed_recreate,
                    ),
                )
                metric_values["child_jobs_enqueued"] += int(enqueued.created)
            if result.cursor is not None:
                KnowledgeJobService.update_cursor(db, job, result.cursor, version=job.provider.version)
            record_provider_success(job.provider)
            KnowledgeJobService.complete(
                db,
                job.id,
                request.attempt_id,
                self.worker_id,
                partial=result.partial,
                metrics=metric_values,
            )
            KnowledgeJobService.heartbeat(db, self.worker_id, state="idle")

    def _handle_failure(self, job_id: UUID, attempt_id: UUID | None, error: BaseException) -> None:
        failure = classify_failure(error)
        if attempt_id is None:
            logger.warning("knowledge_job_start_failed job_id=%s code=%s", job_id, failure.code)
            return
        try:
            with self.session_factory.begin() as db:
                job = db.get(KnowledgeJob, job_id)
                if job is None or job.state == "cancelled":
                    return
                provider = db.get(KnowledgeProvider, job.provider_id)
                if provider is not None:
                    record_provider_failure(provider, failure)
                correlation_id = job.correlation_id
                KnowledgeJobService.fail(
                    db,
                    job_id,
                    attempt_id,
                    self.worker_id,
                    failure,
                    jitter_fraction=self.random_source(),
                )
                KnowledgeJobService.heartbeat(db, self.worker_id, state="idle")
            logger.warning(
                "knowledge_job_failed job_id=%s correlation_id=%s code=%s retryable=%s",
                job_id,
                correlation_id,
                failure.code,
                failure.retryable,
            )
        except KnowledgeJobOwnershipError:
            logger.warning("knowledge_job_ownership_lost job_id=%s code=%s", job_id, failure.code)

    def _load_stored_document(self, request: KnowledgeFetchRequest) -> KnowledgeFetchRequest:
        prefixes = {
            "creature_renormalize": "creature",
            "item_renormalize": "item",
            "quest_renormalize": "quest",
            "npc_renormalize": "npc",
            "location_renormalize": "location",
            "route_renormalize": "route",
            "hunt_zone_renormalize": "hunt_zone",
            "map_point_renormalize": "map_point",
            "map_region_renormalize": "map_region",
            "character_renormalize": "character",
            "guild_renormalize": "guild",
            "world_renormalize": "world",
            "world_catalog_renormalize": "catalog",
            "guild_catalog_renormalize": "guild_catalog",
            "spell_renormalize": "spell",
            "spell_catalog_renormalize": "catalog",
            "creature_catalog_renormalize": "catalog",
            "highscores_renormalize": "highscores",
            "killstatistics_renormalize": "killstatistics",
            "house_renormalize": "houses",
            "boosted_bosses_renormalize": "boosted_bosses",
        }
        document_prefix = prefixes.get(request.job_type)
        if document_prefix is None:
            return request
        external_id = str(request.payload.get("external_id") or "").strip()
        if not external_id:
            raise MalformedProviderPayloadError()
        with self.session_factory() as db:
            document = (
                db.query(KnowledgeDocument)
                .filter(
                    KnowledgeDocument.provider_id == request.provider_code,
                    KnowledgeDocument.provider_document_id == f"{document_prefix}:{external_id}",
                )
                .order_by(KnowledgeDocument.retrieved_at.desc())
                .first()
            )
            if document is None:
                raise EmptyProviderResponseError()
            payload = dict(request.payload)
            payload["_stored_document"] = deepcopy(document.raw_json)
            payload["_stored_metadata"] = deepcopy(document.document_metadata or {})
            payload["_stored_version"] = document.version
        return replace(request, payload=payload)

    @staticmethod
    def _raise_invalid_validation(classification: str, safe_errors: tuple[str, ...]) -> None:
        if classification == "empty":
            raise EmptyProviderResponseError()
        if classification == "provider_error":
            raise ProviderResponseEnvelopeError()
        if classification == "oversized":
            raise OversizedProviderResponseError()
        if "unsafe_text" in safe_errors:
            raise UnsafeProviderTextError()
        raise MalformedProviderPayloadError()

    def run_once(self) -> bool:
        if self.enable_knowledge_jobs:
            job_id = self._claim()
        else:
            self._heartbeat("idle")
            job_id = None
        if job_id is None:
            if self.enable_ownership_claims:
                return asyncio.run(CharacterOwnershipService.process_one(session_factory=self.session_factory))
            return False
        attempt_id: UUID | None = None
        try:
            started = self._start_request(job_id)
            if started is None:
                self._heartbeat("idle")
                return True
            attempt_id, request = started
            self._require_provider_available(request.provider_code)
            try:
                adapter = self.adapters.resolve(request.provider_code, request.job_type, request.entity_type)
            except AdapterNotFoundError as exc:
                raise UnsupportedKnowledgeJobError() from exc
            request = self._load_stored_document(request)
            result = adapter.fetch(request)
            validation = adapter.validate(result)
            if not validation.valid:
                self._raise_invalid_validation(validation.classification, validation.safe_errors)
            self._persist_result(request, result)
            return True
        except Exception as error:
            self._handle_failure(job_id, attempt_id, error)
            return True

    def run(self, stop_event: threading.Event) -> None:
        if not (settings.KNOWLEDGE_WORKER_ENABLED or settings.CHARACTER_OWNERSHIP_WORKER_ENABLED):
            logger.info("knowledge_worker_disabled worker_id=%s", self.worker_id)
            return
        idle_seconds = 0.0
        registered = False
        while not stop_event.is_set():
            try:
                if not registered:
                    self._heartbeat("idle")
                    registered = True
                processed = self.run_once()
                idle_seconds = 0.0 if processed else min(self.max_idle_seconds, idle_seconds + self.poll_seconds)
                wait_seconds = self.poll_seconds if processed else max(self.poll_seconds, idle_seconds)
            except Exception:
                logger.error("knowledge_worker_database_cycle_failed worker_id=%s", self.worker_id)
                registered = False
                wait_seconds = min(self.max_idle_seconds, max(self.poll_seconds, idle_seconds * 2 or self.poll_seconds))
            stop_event.wait(wait_seconds)
        try:
            self._heartbeat("stopping")
        except Exception:
            logger.warning("knowledge_worker_stopping_heartbeat_failed worker_id=%s", self.worker_id)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    if not (settings.KNOWLEDGE_WORKER_ENABLED or settings.CHARACTER_OWNERSHIP_WORKER_ENABLED):
        logger.info("knowledge_worker_disabled worker_id=%s", settings.KNOWLEDGE_WORKER_ID)
        return
    verify_connection_and_schema()
    stop_event = threading.Event()
    for selected_signal in (signal.SIGTERM, signal.SIGINT):
        signal.signal(selected_signal, lambda _signum, _frame: stop_event.set())
    worker = KnowledgeWorker(
        worker_id=settings.KNOWLEDGE_WORKER_ID,
        lease_seconds=settings.KNOWLEDGE_WORKER_LEASE_SECONDS,
        poll_seconds=settings.KNOWLEDGE_WORKER_POLL_SECONDS,
        max_idle_seconds=settings.KNOWLEDGE_WORKER_MAX_IDLE_SECONDS,
        enable_knowledge_jobs=settings.KNOWLEDGE_WORKER_ENABLED,
        enable_ownership_claims=settings.CHARACTER_OWNERSHIP_WORKER_ENABLED,
    )
    worker.run(stop_event)


if __name__ == "__main__":
    main()
