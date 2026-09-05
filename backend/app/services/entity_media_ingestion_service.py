"""Durable, bounded NPC and Location media ingestion."""
from __future__ import annotations

import asyncio
from collections import Counter
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.knowledge.models import ACTIVE_KNOWLEDGE_JOB_STATES, KnowledgeJob, KnowledgeProvider
from app.knowledge.services.jobs import EnqueueKnowledgeJob, EnqueueResult, KnowledgeJobService
from app.models.external_data import TibiaWikiLocation, TibiaWikiNpc
from app.services import media_asset_service
from app.services.media_evidence_service import EntityMediaEvidence, evidence_for_entities


MEDIA_BATCH_MAX = 25
MEDIA_CANARY_SIZE = 3
MEDIA_JOB_TYPES = frozenset({"npc_media_batch", "location_media_batch"})


class MediaCanaryRequiredError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class MediaCandidate:
    row_id: int
    canonical_id: str
    name: str
    asset_key: str
    evidence: EntityMediaEvidence


class EntityMediaIngestionService:
    @staticmethod
    def validate_scope(entity_type: str, scope: dict[str, Any], payload: dict[str, Any]) -> None:
        if entity_type not in {"npc", "location"} or payload or set(scope) != {
            "after_id",
            "batch_size",
            "canary",
        }:
            raise ValueError("Media batches accept only a bounded cursor scope")
        after_id = scope.get("after_id")
        batch_size = scope.get("batch_size")
        canary = scope.get("canary")
        if not isinstance(after_id, int) or isinstance(after_id, bool) or after_id < 0:
            raise ValueError("Media batch cursor is invalid")
        if (
            not isinstance(batch_size, int)
            or isinstance(batch_size, bool)
            or not 1 <= batch_size <= MEDIA_BATCH_MAX
        ):
            raise ValueError(f"Media batch_size must be between 1 and {MEDIA_BATCH_MAX}")
        if not isinstance(canary, bool):
            raise ValueError("Media canary flag is invalid")
        if canary and batch_size > MEDIA_CANARY_SIZE:
            raise ValueError(f"Media canaries are limited to {MEDIA_CANARY_SIZE} entities")

    @staticmethod
    def enqueue(
        db: Session,
        *,
        entity_type: str,
        after_id: int,
        batch_size: int,
        canary: bool,
        created_by_id: int,
    ) -> EnqueueResult:
        scope = {"after_id": after_id, "batch_size": batch_size, "canary": canary}
        EntityMediaIngestionService.validate_scope(entity_type, scope, {})
        job_type = f"{entity_type}_media_batch"
        if db.get_bind().dialect.name == "postgresql":
            lock_key = 0x4D4544494101 if entity_type == "npc" else 0x4D4544494102
            db.execute(text("SELECT pg_advisory_xact_lock(:lock_key)"), {"lock_key": lock_key})
        if not canary:
            completed = (
                db.query(KnowledgeJob)
                .filter(
                    KnowledgeJob.job_type == job_type,
                    KnowledgeJob.entity_type_id == entity_type,
                    KnowledgeJob.state == "succeeded",
                )
                .order_by(KnowledgeJob.completed_at.desc())
                .all()
            )
            passed = any(
                (job.scope or {}).get("canary") is True
                and any(
                    attempt.outcome == "succeeded"
                    and int((attempt.metrics or {}).get("eligible") or 0) > 0
                    and not (attempt.metrics or {}).get("failure_codes")
                    for attempt in job.attempts
                )
                for job in completed
            )
            if not passed:
                raise MediaCanaryRequiredError("A successful media canary is required")
        active = (
            db.query(KnowledgeJob)
            .filter(
                KnowledgeJob.job_type == job_type,
                KnowledgeJob.entity_type_id == entity_type,
                KnowledgeJob.state.in_(ACTIVE_KNOWLEDGE_JOB_STATES),
            )
            .order_by(KnowledgeJob.created_at.asc(), KnowledgeJob.id.asc())
            .first()
        )
        if active is not None:
            return EnqueueResult(active, False)
        return KnowledgeJobService.enqueue(
            db,
            EnqueueKnowledgeJob(
                provider_id="tibiawiki",
                job_type=job_type,
                entity_type=entity_type,
                scope=scope,
                payload={},
                priority=120 if canary else 100,
                max_attempts=5,
                created_by_id=created_by_id,
                trigger="manual",
                allow_completed_recreate=True,
            ),
        )

    @staticmethod
    def _plan(
        db: Session,
        *,
        entity_type: str,
        after_id: int,
        batch_size: int,
    ) -> tuple[list[MediaCandidate], bool, float]:
        model = TibiaWikiNpc if entity_type == "npc" else TibiaWikiLocation
        rows = (
            db.query(model)
            .filter(model.id > after_id)
            .order_by(model.id.asc())
            .limit(batch_size + 1)
            .all()
        )
        has_more = len(rows) > batch_size
        rows = rows[:batch_size]
        evidence = evidence_for_entities(db, entity_type, rows)
        candidates = []
        for row in rows:
            asset_key = (
                media_asset_service.build_canonical_npc_asset_key(row.knowledge_entity_id)
                if entity_type == "npc"
                else media_asset_service.build_location_asset_key(row)
            )
            candidates.append(MediaCandidate(
                row_id=row.id,
                canonical_id=str(row.knowledge_entity_id),
                name=row.name,
                asset_key=asset_key,
                evidence=evidence[row.id],
            ))
        provider = db.get(KnowledgeProvider, "tibiawiki")
        rate_limit = provider.rate_limit if provider and isinstance(provider.rate_limit, dict) else {}
        requests = rate_limit.get("requests")
        window = rate_limit.get("window_seconds")
        throttle_seconds = (
            float(window) / float(requests)
            if isinstance(requests, int) and requests > 0 and isinstance(window, int) and window > 0
            else 0.0
        )
        return candidates, has_more, throttle_seconds

    @staticmethod
    async def run_batch(
        session_factory: sessionmaker,
        *,
        entity_type: str,
        after_id: int,
        batch_size: int,
        canary: bool,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> dict[str, Any]:
        scope = {"after_id": after_id, "batch_size": batch_size, "canary": canary}
        EntityMediaIngestionService.validate_scope(entity_type, scope, {})
        with session_factory() as db:
            candidates, has_more, throttle_seconds = EntityMediaIngestionService._plan(
                db,
                entity_type=entity_type,
                after_id=after_id,
                batch_size=batch_size,
            )
            db.rollback()

        counts: Counter[str] = Counter({
            "created": 0,
            "updated": 0,
            "cached": 0,
            "skipped": 0,
            "failed": 0,
            "no_source_evidence": 0,
            "malformed_source": 0,
            "unresolved_source": 0,
        })
        failure_codes: Counter[str] = Counter()
        samples: list[dict[str, Any]] = []
        network_attempts = 0
        for candidate in candidates:
            evidence = candidate.evidence
            if not evidence.eligible:
                counts[evidence.state] += 1
                result = evidence.state
                failure_code = None
            else:
                if network_attempts and throttle_seconds > 0:
                    await sleep(throttle_seconds)
                with session_factory() as db:
                    outcome = await media_asset_service.cache_media_asset(
                        db,
                        asset_key=candidate.asset_key,
                        source_url=evidence.source_url,
                        retry_failed=True,
                        release_transaction_before_fetch=True,
                    )
                network_attempts += int(outcome.network_performed)
                result = outcome.result
                failure_code = outcome.error_category
                if result == "failed":
                    counts["failed"] += 1
                else:
                    counts[result] += 1
                if failure_code:
                    failure_codes[failure_code] += 1
            if len(samples) < 10:
                sample = {
                    "entity_id": candidate.canonical_id,
                    "name": candidate.name,
                    "evidence": evidence.state,
                    "result": result,
                }
                if failure_code:
                    sample["error_code"] = failure_code
                samples.append(sample)

        next_cursor = candidates[-1].row_id if candidates else after_id
        return {
            "entity_type": entity_type,
            "mode": "canary" if canary else "batch",
            "requested": batch_size,
            "examined": len(candidates),
            "eligible": sum(candidate.evidence.eligible for candidate in candidates),
            "network_attempts": network_attempts,
            "counts": dict(counts),
            "failure_codes": dict(sorted(failure_codes.items())),
            "cursor": {"after_id": after_id, "next_after_id": next_cursor, "has_more": has_more},
            "samples": samples,
        }
