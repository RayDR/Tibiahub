"""Centralized synchronization orchestration service.

This module is the single source of truth for:
- async sync job lifecycle
- segmented/full sync execution
- persistent progress updates
- optional image resource caching
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import random
from uuid import UUID
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import desc, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import SessionLocal
from app.models.creature import Creature
from app.models.external_data import CachedResource, Item, SyncJob, SyncJobError, TibiaWikiQuest
from app.models.hunt_zone import HuntZone
from app.models.loot import Loot
from app.models.settings import SystemSettings
from app.models.user import User
from app.models.guild_management import GuildDirectory
from app.models.maintenance_sync import SyncJobPhase, SyncWorkerHeartbeat
from app.models.workspace_audit import WorkspaceAudit
from app.knowledge.models import ACTIVE_KNOWLEDGE_JOB_STATES, KnowledgeJob
from app.knowledge.services.bootstrap import KnowledgeBootstrapService, TIBIAWIKI_BOOTSTRAP_CONFIRMATION
from app.services.guild_roster_service import GuildRosterService, GuildRosterSyncError
from app.services.maintenance_mode_service import MaintenanceModeService, TERMINAL_SYNC_STATES
from app.services.bestiary_source import (
    get_category_members,
    get_creature_detail_by_name,
    get_page_links,
    get_quest_page_summary,
    get_tibiamaps_bounds,
    get_tibiamaps_markers,
)
from app.services.creature_storage_service import upsert_creature_payload
from app.services.email_outbox_service import EmailOutboxService
from app.services.text_utils import normalize_search_text

logger = logging.getLogger(__name__)
_CACHE_DIR = Path("backend/storage/cache")
_IMAGE_DIR = _CACHE_DIR / "images"
_FORCE_FAIL_NAME = (os.getenv("SYNC_FORCE_FAIL_NAME") or "").strip().lower()
_FORCE_FATAL_AFTER = int(os.getenv("SYNC_FORCE_FATAL_AFTER") or "0")
_SYNC_STALE_RUNNING_MINUTES = int(os.getenv("SYNC_STALE_RUNNING_MINUTES") or "45")
_SYNC_HEARTBEAT_EVERY_ITEMS = max(1, int(os.getenv("SYNC_HEARTBEAT_EVERY_ITEMS") or "25"))


class SyncService:
    SYNC_TARGETS = {"full", "creatures", "bosses", "items", "quests", "hunt-zones", "images", "knowledge", "guild-rosters"}
    FULL_PLAN = (
        ("creatures", "tibiawiki", False), ("bosses", "tibiawiki", False),
        ("items", "tibiawiki", False), ("quests", "tibiawiki", False),
        ("hunt-zones", "tibiamaps", False), ("images", "resources", False),
        ("knowledge", "knowledge-platform", False), ("guild-rosters", "tibiadata", False),
    )
    WORKER_VERSION = "sync-worker-v1"

    SUMMARY_KEYS = [
        "creatures_created",
        "creatures_updated",
        "creatures_failed",
        "bosses_created",
        "bosses_updated",
        "bosses_failed",
        "items_created",
        "items_updated",
        "items_failed",
        "quests_created",
        "quests_updated",
        "quests_failed",
        "hunt_zones_created",
        "hunt_zones_updated",
        "hunt_zones_failed",
        "images_cached",
        "images_failed",
        "total_processed",
    ]

    @staticmethod
    def _get_setting(db: Session, key: str, default: str) -> str:
        value = db.query(SystemSettings).filter(SystemSettings.key == key).first()
        return value.value if value and value.value is not None else default

    @staticmethod
    def _set_setting(db: Session, key: str, value: str, description: str = "") -> None:
        setting = db.query(SystemSettings).filter(SystemSettings.key == key).first()
        if setting:
            setting.value = value
            if description:
                setting.description = description
        else:
            db.add(SystemSettings(key=key, value=value, description=description, is_active=True))

    @staticmethod
    def ensure_default_settings(db: Session) -> None:
        defaults = {
            "external_auto_fallback_enabled": ("0", "Allow public API on-demand external fallback"),
            "auto_fetch_missing_images_enabled": ("0", "Allow public endpoints to fetch missing images"),
            "scheduled_sync_enabled": ("0", "Enable scheduled automatic sync"),
            "sync_request_timeout_seconds": ("30", "Per-step sync timeout in seconds"),
            "sync_retry_count": ("2", "Retry attempts for sync steps"),
            "sync_notify_email_enabled": ("0", "Send completion/failure sync notifications by email"),
            "sync_last_success_at": ("", "Last successful sync timestamp"),
            "tibia_latest_update_version": ("", "Latest synchronized data version label"),
        }
        for key, (value, description) in defaults.items():
            if not db.query(SystemSettings).filter(SystemSettings.key == key).first():
                db.add(SystemSettings(key=key, value=value, description=description, is_active=True))
        db.commit()

    @staticmethod
    def create_job(
        db: Session,
        *,
        job_type: str,
        requester: str | None = None,
        requested_by_user_id: int | None = None,
        job_limit: int | None = None,
        batch_size: int = 100,
        max_retries: int = 3,
        external_timeout_seconds: int = 15,
        force_refresh: bool = False,
        skip_images: bool = False,
        include_knowledge: bool = False,
        include_guild_rosters: bool = False,
        continue_on_error: bool = True,
        maintenance_requested: bool = False,
        operation_label: str | None = None,
    ) -> SyncJob:
        SyncService.ensure_default_settings(db)
        SyncService.recover_stale_running_jobs(db, reason="stale after backend recovery")
        if job_type not in SyncService.SYNC_TARGETS:
            raise ValueError(f"Unknown sync target '{job_type}'")

        if job_type == "full":
            active_full = (
                db.query(SyncJob)
                .filter(SyncJob.job_type == "full", SyncJob.status.in_(["pending", "running"]))
                .first()
            )
            if active_full:
                raise RuntimeError("A full sync job is already running")

        job_id = hashlib.sha1(f"{job_type}:{datetime.now(UTC).isoformat()}".encode("utf-8")).hexdigest()[:32]
        job = SyncJob(
            id=job_id,
            job_type=job_type,
            status="pending",
            progress=0,
            progress_current=0,
            progress_total=0,
            progress_percent=0,
            current_step="queued",
            message="Job queued",
            requester=requester,
            requested_by_user_id=requested_by_user_id,
            job_limit=job_limit,
            cancel_requested=False,
            current_offset=0,
            processed_count=0,
            failed_count=0,
            checkpoint={},
            batch_size=max(10, min(batch_size, 500)),
            max_retries=max(0, min(max_retries, 10)),
            external_timeout_seconds=max(5, min(external_timeout_seconds, 120)),
            force_refresh=force_refresh, skip_images=skip_images,
            include_knowledge=include_knowledge, include_guild_rosters=include_guild_rosters,
            continue_on_error=continue_on_error, maintenance_requested=maintenance_requested,
            operation_label=(operation_label or "").strip()[:255] or None,
        )
        db.add(job)
        try:
            db.flush()
        except IntegrityError as exc:
            db.rollback()
            raise RuntimeError("A full sync job is already running") from exc
        plan = [(job_type, "external", False)] if job_type != "full" else list(SyncService.FULL_PLAN)
        if skip_images:
            plan = [row for row in plan if row[0] != "images"]
        if job_type == "full" and not include_knowledge:
            plan = [row for row in plan if row[0] != "knowledge"]
        if job_type == "full" and not include_guild_rosters:
            plan = [row for row in plan if row[0] != "guild-rosters"]
        for index, (phase_key, provider, required) in enumerate(plan):
            db.add(SyncJobPhase(
                job_id=job.id, phase_key=phase_key, order_index=index,
                provider=provider, required=required, max_attempts=max(1, max_retries + 1),
            ))
        if maintenance_requested:
            MaintenanceModeService.acquire_sync(
                db, job=job, actor_id=requested_by_user_id,
                reason=operation_label or "Full synchronization in progress",
            )
        if requested_by_user_id:
            db.add(WorkspaceAudit(
                actor_id=requested_by_user_id, workspace_type="admin", action="full_sync_started" if job_type == "full" else "sync_started",
                target_type="sync_job", target_id=job.id, assisted=False,
                safe_metadata={"job_type": job_type, "maintenance": maintenance_requested, "continue_on_error": continue_on_error},
            ))
        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def recover_stale_running_jobs(
        db: Session,
        *,
        stale_minutes: int | None = None,
        reason: str = "stale after backend recovery",
    ) -> list[str]:
        threshold_minutes = stale_minutes if stale_minutes is not None else _SYNC_STALE_RUNNING_MINUTES
        now = datetime.now(UTC)
        stale_ids: list[str] = []
        try:
            rows = db.query(SyncJob).filter(SyncJob.status == "running").all()
            for job in rows:
                heartbeat = job.lease_expires_at or job.updated_at or job.started_at or job.created_at
                if heartbeat is None:
                    continue
                heartbeat = heartbeat.replace(tzinfo=UTC) if heartbeat.tzinfo is None else heartbeat.astimezone(UTC)
                expired = heartbeat <= now if job.lease_expires_at else (now - heartbeat).total_seconds() >= threshold_minutes * 60
                if not expired:
                    continue
                stale_ids.append(job.id)
                if job.cancel_requested:
                    job.status = "cancelled"; job.finished_at = now; job.terminal_reason = "cancelled_after_stale_worker"
                    MaintenanceModeService.release_sync(db, job=job, reason="sync_terminal:cancelled")
                else:
                    job.status = "pending"; job.message = reason; job.worker_id = None
                    job.claimed_at = None; job.lease_expires_at = None; job.next_retry_at = now
                    for phase in db.query(SyncJobPhase).filter(SyncJobPhase.job_id == job.id, SyncJobPhase.status == "running").all():
                        phase.status = "retrying"; phase.error_category = "worker_interrupted"; phase.safe_error = "The prior worker lease expired."
            if stale_ids:
                db.commit()
        except Exception:
            db.rollback()
            logger.exception("sync_stale_recovery_failed")
        return stale_ids

    @staticmethod
    def _heartbeat(db: Session, job: SyncJob, *, message: str | None = None) -> None:
        now = datetime.now(UTC)
        job.updated_at = now
        if job.worker_id:
            from datetime import timedelta
            job.lease_expires_at = now + timedelta(seconds=settings.SYNC_WORKER_LEASE_SECONDS)
            heartbeat = db.get(SyncWorkerHeartbeat, job.worker_id)
            if heartbeat is None:
                heartbeat = SyncWorkerHeartbeat(worker_id=job.worker_id, state="running", last_seen_at=now, version=SyncService.WORKER_VERSION)
                db.add(heartbeat)
            heartbeat.state = "running"; heartbeat.last_seen_at = now; heartbeat.current_job_id = job.id
            heartbeat.version = SyncService.WORKER_VERSION; heartbeat.enabled = settings.SYNC_WORKER_ENABLED
        MaintenanceModeService.heartbeat_sync(db, job.id)
        if message is not None:
            job.message = message
        db.add(job)
        db.commit()

    @staticmethod
    def queue_job(
        job_id: str,
        *,
        force: bool = False,
        skip_images: bool = False,
        limit: int | None = None,
        resume: bool = False,
    ) -> None:
        # Durable workers poll pending rows. This compatibility method no longer
        # starts request-process threads.
        _ = (job_id, force, skip_images, limit, resume)

    @staticmethod
    def resume_job(db: Session, job_id: str) -> SyncJob | None:
        job = SyncService.get_job(db, job_id)
        if not job:
            return None
        if job.status not in {"failed", "cancelled", "completed_with_errors"}:
            raise RuntimeError("Only failed, cancelled, or partially completed jobs can be resumed")
        job.status = "pending"
        job.cancel_requested = False
        job.error = None
        job.error_message = None
        job.message = "Resume requested"
        job.finished_at = None; job.worker_id = None; job.claimed_at = None; job.lease_expires_at = None
        for phase in db.query(SyncJobPhase).filter(
            SyncJobPhase.job_id == job.id,
            SyncJobPhase.status.in_(["failed", "cancelled", "retrying", "running"]),
        ).all():
            phase.status = "pending"; phase.error_category = None; phase.safe_error = None; phase.finished_at = None
        if job.maintenance_requested:
            MaintenanceModeService.acquire_sync(db, job=job, actor_id=job.requested_by_user_id, reason=job.operation_label or "Synchronization resumed")
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def list_jobs(db: Session, limit: int = 50) -> list[SyncJob]:
        return db.query(SyncJob).order_by(desc(SyncJob.created_at)).limit(limit).all()

    @staticmethod
    def get_job(db: Session, job_id: str) -> SyncJob | None:
        return db.query(SyncJob).filter(SyncJob.id == job_id).first()

    @staticmethod
    def request_cancel(db: Session, job_id: str) -> SyncJob | None:
        job = SyncService.get_job(db, job_id)
        if not job:
            return None
        if job.status in TERMINAL_SYNC_STATES:
            return job
        job.cancel_requested = True
        job.message = "Cancellation requested"
        if job.status == "pending":
            job.status = "cancelled"; job.finished_at = datetime.now(UTC); job.terminal_reason = "cancelled_before_claim"
            for phase in db.query(SyncJobPhase).filter(SyncJobPhase.job_id == job.id, SyncJobPhase.status.in_(["pending", "retrying"])).all():
                phase.status = "cancelled"; phase.finished_at = job.finished_at
            MaintenanceModeService.release_sync(db, job=job, reason="sync_terminal:cancelled")
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def worker_heartbeat(db: Session, worker_id: str, state: str, current_job_id: str | None = None, failure_category: str | None = None) -> None:
        now = datetime.now(UTC)
        row = db.get(SyncWorkerHeartbeat, worker_id)
        if row is None:
            row = SyncWorkerHeartbeat(worker_id=worker_id, state=state, last_seen_at=now, version=SyncService.WORKER_VERSION)
            db.add(row)
        row.state = state; row.last_seen_at = now; row.current_job_id = current_job_id
        row.version = SyncService.WORKER_VERSION; row.enabled = settings.SYNC_WORKER_ENABLED
        if failure_category:
            row.last_failure_category = failure_category

    @staticmethod
    def claim_next(db: Session, worker_id: str) -> str | None:
        SyncService.recover_stale_running_jobs(db)
        now = datetime.now(UTC)
        statement = select(SyncJob).where(
            SyncJob.status == "pending",
            or_(SyncJob.next_retry_at.is_(None), SyncJob.next_retry_at <= now),
        ).order_by(SyncJob.created_at, SyncJob.id).with_for_update(skip_locked=True).limit(1)
        job = db.execute(statement).scalars().first()
        if job is None:
            SyncService.worker_heartbeat(db, worker_id, "idle")
            return None
        job.status = "running"; job.worker_id = worker_id; job.claimed_at = now
        job.started_at = job.started_at or now; job.lease_expires_at = now + timedelta(seconds=settings.SYNC_WORKER_LEASE_SECONDS)
        job.message = "Claimed by durable sync worker"
        SyncService.worker_heartbeat(db, worker_id, "running", job.id)
        return job.id

    @staticmethod
    def _run_job_sync(job_id: str, worker_id: str) -> None:
        asyncio.run(SyncService._run_job_async(job_id, worker_id=worker_id))

    @staticmethod
    async def _run_job_async(job_id: str, *, worker_id: str) -> None:
        db = SessionLocal()
        try:
            job = SyncService.get_job(db, job_id)
            if not job or job.status != "running" or job.worker_id != worker_id:
                return
            timeout_seconds = job.external_timeout_seconds or int(SyncService._get_setting(db, "sync_request_timeout_seconds", "30") or "30")
            retry_count = job.max_retries if job.max_retries is not None else max(0, int(SyncService._get_setting(db, "sync_retry_count", "2") or "2"))
            if job.result_summary is None:
                job.current_step = "starting"
                job.message = "Sync started"
                job.result_summary = SyncService._empty_summary()
            db.commit()
            summary = dict(job.result_summary or SyncService._empty_summary())
            phases = db.query(SyncJobPhase).filter(SyncJobPhase.job_id == job.id).order_by(SyncJobPhase.order_index).all()
            for phase_index, phase in enumerate(phases):
                if phase.status in {"completed", "skipped", "failed", "cancelled"}:
                    continue
                result: dict[str, Any] | None = None
                while result is None:
                    db.refresh(job)
                    if job.cancel_requested:
                        phase.status = "cancelled"; phase.finished_at = datetime.now(UTC)
                        phase.checkpoint = job.checkpoint or phase.checkpoint
                        SyncService._terminalize(db, job, "cancelled", "Sync cancelled by administrator")
                        return
                    if job.current_entity_type == phase.phase_key and job.checkpoint:
                        phase.checkpoint = job.checkpoint
                    job.checkpoint = phase.checkpoint or {}
                    job.current_entity_type = phase.phase_key
                    phase.status = "running"; phase.started_at = phase.started_at or datetime.now(UTC)
                    phase.attempt_count += 1; phase.error_category = None; phase.safe_error = None
                    phase.next_retry_at = None
                    SyncService._heartbeat(db, job, message=f"Running {phase.phase_key}")
                    try:
                        if phase.phase_key == "knowledge":
                            result = await SyncService._run_knowledge_phase(db, job, phase)
                        elif phase.phase_key == "guild-rosters":
                            result = await SyncService._run_guild_rosters_phase(db, job, phase)
                        else:
                            result = await SyncService._run_segment(
                                db, job, phase.phase_key, force=bool(job.force_refresh), limit=job.job_limit,
                                retry_count=retry_count, timeout_seconds=timeout_seconds,
                            )
                    except Exception as exc:
                        db.refresh(job)
                        phase.checkpoint = job.checkpoint or phase.checkpoint or {}
                        if job.cancel_requested or str(exc) == "sync_cancelled":
                            phase.status = "cancelled"; phase.finished_at = datetime.now(UTC)
                            SyncService._terminalize(db, job, "cancelled", "Sync cancelled by administrator")
                            return
                        category, retryable, retry_after = SyncService.classify_provider_error(exc)
                        if retryable and phase.attempt_count < phase.max_attempts:
                            phase.status = "retrying"; phase.error_category = category
                            phase.safe_error = "The provider is temporarily unavailable; retrying safely."
                            delay = SyncService.retry_delay(phase.attempt_count, retry_after)
                            phase.next_retry_at = datetime.now(UTC) + timedelta(seconds=delay)
                            job.next_retry_at = phase.next_retry_at
                            db.commit(); SyncService._heartbeat(db, job, message=f"Retrying {phase.phase_key}")
                            await SyncService._sleep_with_heartbeat(db, job, delay)
                            continue
                        phase.status = "failed"; phase.error_category = category
                        phase.safe_error = "The synchronization phase exhausted its safe retries."
                        phase.failed_count = max(1, phase.failed_count); phase.finished_at = datetime.now(UTC)
                        job.failed_count = int(job.failed_count or 0) + 1
                        job.next_retry_at = None
                        db.commit()
                        if phase.required or not job.continue_on_error:
                            SyncService._terminalize(db, job, "failed", f"Required phase failed: {phase.phase_key}")
                            return
                        break
                if result is None:
                    continue
                summary = SyncService._merge_summary(summary, result.get("summary") or {})
                summary["total_processed"] = int(summary.get("total_processed") or 0) + int(result.get("processed") or 0)
                job.result_summary = summary
                phase.processed_count += int(result.get("processed") or 0)
                phase.failed_count += int(result.get("failed") or sum(
                    int(value or 0) for key, value in (result.get("summary") or {}).items() if key.endswith("_failed")
                ))
                phase.current_offset = int(job.current_offset or 0); phase.current_entity = job.last_successful_external_id
                phase.checkpoint = job.checkpoint or {}; phase.finished_at = datetime.now(UTC)
                phase.status = "failed" if phase.failed_count else "completed"
                phase.error_category = "item_failures" if phase.failed_count else None
                phase.safe_error = "Some records could not be synchronized and remain resumable." if phase.failed_count else None
                job.current_step = f"completed:{phase.phase_key}"
                job.message = f"Completed {phase.phase_key}"
                job.progress_current = phase_index + 1; job.progress_total = len(phases)
                job.progress_percent = int(((phase_index + 1) / max(len(phases), 1)) * 100); job.progress = job.progress_percent
                job.checkpoint = {}; job.current_offset = 0
                db.commit()
            finished_at = datetime.now(UTC)
            failed_phases = db.query(SyncJobPhase).filter(SyncJobPhase.job_id == job.id, SyncJobPhase.status == "failed").count()
            terminal = "completed_with_errors" if failed_phases else "completed"
            if terminal == "completed":
                SyncService._set_setting(db, "sync_last_success_at", finished_at.isoformat(), "Last successful sync timestamp")
            SyncService._set_setting(db, "tibia_latest_update_version", finished_at.strftime("Synced %Y-%m-%d"), "Latest synchronized data version label")
            SyncService._terminalize(db, job, terminal, "Sync completed with resumable errors" if failed_phases else "Sync completed successfully")
            await SyncService._maybe_send_notification(db, job, success=terminal == "completed")
        except Exception as exc:
            job = SyncService.get_job(db, job_id)
            if job:
                category, _, _ = SyncService.classify_provider_error(exc)
                job.error = category; job.error_message = "The synchronization worker stopped safely."
                SyncService._terminalize(db, job, "failed", "Sync worker stopped safely")
                await SyncService._maybe_send_notification(db, job, success=False)
            logger.exception("sync_job_failed job_id=%s error_type=%s", job_id, type(exc).__name__)
        finally:
            db.close()

    @staticmethod
    def _terminalize(db: Session, job: SyncJob, status: str, message: str) -> None:
        now = datetime.now(UTC)
        job.status = status; job.finished_at = now; job.current_step = "done"; job.message = message
        job.terminal_reason = message; job.lease_expires_at = None; job.next_retry_at = None
        job.progress = 100; job.progress_percent = 100
        MaintenanceModeService.release_sync(db, job=job, reason=f"sync_terminal:{status}")
        if job.requested_by_user_id:
            db.add(WorkspaceAudit(
                actor_id=job.requested_by_user_id, workspace_type="admin", action="full_sync_terminal" if job.job_type == "full" else "sync_terminal",
                target_type="sync_job", target_id=job.id, assisted=False,
                safe_metadata={"status": status},
            ))
        if job.worker_id:
            SyncService.worker_heartbeat(db, job.worker_id, "idle", failure_category="sync_failed" if status == "failed" else None)
            heartbeat = db.get(SyncWorkerHeartbeat, job.worker_id)
            if heartbeat and status in {"completed", "completed_with_errors"}:
                heartbeat.last_success_at = now
        db.commit()

    @staticmethod
    def classify_provider_error(exc: Exception) -> tuple[str, bool, int | None]:
        if isinstance(exc, httpx.HTTPStatusError):
            status = exc.response.status_code
            retry_after = exc.response.headers.get("Retry-After")
            parsed = int(retry_after) if retry_after and retry_after.isdigit() else None
            if status == 429:
                return "rate_limited", True, parsed
            if 500 <= status < 600:
                return "provider_5xx", True, parsed
            return "provider_rejected", False, None
        if isinstance(exc, (httpx.TimeoutException, TimeoutError, OSError)):
            return "provider_timeout", True, None
        if isinstance(exc, (ValueError, TypeError)):
            return "invalid_payload", False, None
        return "temporary_provider_failure", True, None

    @staticmethod
    def retry_delay(attempt: int, retry_after: int | None = None) -> float:
        if retry_after is not None:
            return float(max(1, min(retry_after, 3600)))
        return min(60.0, float(2 ** max(0, attempt - 1)) + random.uniform(0.1, 0.9))

    @staticmethod
    async def _sleep_with_heartbeat(db: Session, job: SyncJob, seconds: float) -> None:
        remaining = max(0.0, seconds)
        while remaining > 0:
            interval = min(30.0, remaining)
            await asyncio.sleep(interval)
            remaining -= interval
            SyncService._heartbeat(db, job)

    @staticmethod
    async def _run_knowledge_phase(db: Session, job: SyncJob, phase: SyncJobPhase) -> dict[str, Any]:
        checkpoint = phase.checkpoint or {}
        correlation_texts = list(checkpoint.get("correlation_ids") or [])
        if not correlation_texts and checkpoint.get("correlation_id"):
            correlation_texts = [checkpoint["correlation_id"]]
        if not correlation_texts:
            if job.requested_by_user_id is None:
                raise ValueError("Knowledge synchronization requires an administrator owner")
            result = KnowledgeBootstrapService.activate_tibiawiki(
                db, actor_id=job.requested_by_user_id,
                confirmation=TIBIAWIKI_BOOTSTRAP_CONFIRMATION,
                batch_limit=min(50, max(1, int(job.batch_size or 50))),
            )
            correlation_texts = sorted({str(row.correlation_id) for row in result.jobs})
            phase.checkpoint = {"correlation_ids": correlation_texts, "root_job_ids": [str(row.id) for row in result.jobs]}
            db.commit()
        correlations = [UUID(value) for value in correlation_texts]
        while True:
            db.refresh(job)
            if job.cancel_requested:
                raise RuntimeError("sync_cancelled")
            rows = db.query(KnowledgeJob).filter(KnowledgeJob.correlation_id.in_(correlations)).all()
            active = [row for row in rows if row.state in ACTIVE_KNOWLEDGE_JOB_STATES]
            phase.processed_count = len([row for row in rows if row.state not in ACTIVE_KNOWLEDGE_JOB_STATES])
            phase.failed_count = len([row for row in rows if row.state in {"failed", "cancelled", "partially_succeeded"}])
            phase.current_entity = active[0].entity_type_id if active else None
            phase.checkpoint = {**(phase.checkpoint or {}), "job_count": len(rows), "active_count": len(active)}
            db.commit(); SyncService._heartbeat(db, job, message=f"Knowledge jobs active: {len(active)}")
            if not active:
                return {"processed": len(rows), "failed": phase.failed_count, "summary": {"knowledge_jobs": len(rows), "knowledge_failed": phase.failed_count}}
            await asyncio.sleep(settings.SYNC_WORKER_POLL_SECONDS)

    @staticmethod
    async def _run_guild_rosters_phase(db: Session, job: SyncJob, phase: SyncJobPhase) -> dict[str, Any]:
        rows = db.query(GuildDirectory).filter(GuildDirectory.is_active.is_(True)).order_by(GuildDirectory.id).all()
        offset = int((phase.checkpoint or {}).get("current_offset") or 0)
        failed = 0
        while offset < len(rows):
            db.refresh(job)
            if job.cancel_requested:
                raise RuntimeError("sync_cancelled")
            directory = rows[offset]
            try:
                await GuildRosterService.synchronize(db, directory.guild_name)
            except GuildRosterSyncError:
                db.rollback()
                job = SyncService.get_job(db, job.id)
                phase = db.get(SyncJobPhase, phase.id)
                failed += 1
            offset += 1
            phase.current_offset = offset; phase.current_entity = directory.guild_name
            phase.processed_count = offset; phase.failed_count = failed
            phase.checkpoint = {"current_offset": offset, "last_guild_id": directory.id}
            db.commit(); SyncService._heartbeat(db, job, message=f"Guild rosters {offset}/{len(rows)}")
        return {"processed": len(rows), "failed": failed, "summary": {"guild_rosters": len(rows), "guild_rosters_failed": failed}}

    @staticmethod
    def _update_job_progress(
        db: Session,
        job: SyncJob,
        *,
        progress_current: int,
        progress_total: int,
        current_step: str,
        message: str,
    ) -> None:
        percent = int((progress_current / max(progress_total, 1)) * 100)
        job.progress_current = progress_current
        job.progress_total = progress_total
        job.progress_percent = percent
        job.progress = percent
        job.current_step = current_step
        job.message = message
        db.add(job)
        db.commit()

    @staticmethod
    def _empty_summary() -> dict[str, int]:
        return {key: 0 for key in SyncService.SUMMARY_KEYS}

    @staticmethod
    def _merge_summary(base: dict[str, Any], delta: dict[str, Any]) -> dict[str, Any]:
        merged = dict(base)
        for key, value in delta.items():
            if isinstance(value, int):
                merged[key] = int(merged.get(key) or 0) + value
            else:
                merged[key] = value
        return merged

    @staticmethod
    def _save_checkpoint(
        db: Session,
        job: SyncJob,
        *,
        entity_type: str,
        offset: int,
        message: str | None = None,
        last_successful_external_id: str | None = None,
    ) -> None:
        checkpoint = {
            "current_entity_type": entity_type,
            "current_offset": max(0, offset),
            "processed_count": int(job.processed_count or 0),
            "failed_count": int(job.failed_count or 0),
            "last_successful_external_id": last_successful_external_id or job.last_successful_external_id,
            "batch_size": int(job.batch_size or 100),
            "updated_at": datetime.now(UTC).isoformat(),
        }
        job.current_entity_type = entity_type
        job.current_offset = max(0, offset)
        if last_successful_external_id:
            job.last_successful_external_id = last_successful_external_id
        job.checkpoint = checkpoint
        if message:
            job.message = message
        db.add(job)
        db.commit()

    @staticmethod
    def _upsert_item(db: Session, payload: dict[str, Any]) -> str:
        name = payload.get("name")
        if not name:
            raise ValueError("Missing item name")
        existing = db.query(Item).filter(Item.name == name).first()
        created = existing is None
        if not existing:
            existing = Item(name=name)
            db.add(existing)
        existing.item_id = payload.get("item_id") or existing.item_id
        existing.description = payload.get("description") or existing.description
        existing.type = payload.get("type") or existing.type
        existing.weight = payload.get("weight") if payload.get("weight") is not None else existing.weight
        existing.value = payload.get("value") if payload.get("value") is not None else existing.value
        existing.attack = payload.get("attack") if payload.get("attack") is not None else existing.attack
        existing.defense = payload.get("defense") if payload.get("defense") is not None else existing.defense
        existing.armor = payload.get("armor") if payload.get("armor") is not None else existing.armor
        existing.level_required = payload.get("levelrequired") if payload.get("levelrequired") is not None else existing.level_required
        existing.vocation_required = payload.get("vocationrequired") or existing.vocation_required
        existing.tradeable = payload.get("tradeable", existing.tradeable)
        existing.stackable = payload.get("stackable", existing.stackable)
        existing.raw_data = payload
        existing.updated_at = datetime.now(UTC)
        return "created" if created else "updated"

    @staticmethod
    def _upsert_quest(db: Session, payload: dict[str, Any]) -> str:
        name = payload.get("name")
        if not name:
            raise ValueError("Missing quest name")
        existing = db.query(TibiaWikiQuest).filter(TibiaWikiQuest.name == name).first()
        if not existing:
            # SessionLocal uses autoflush=False; inspect pending objects to avoid duplicates.
            for pending in db.new:
                if isinstance(pending, TibiaWikiQuest) and pending.name == name:
                    existing = pending
                    break
        created = existing is None
        if not existing:
            existing = TibiaWikiQuest(name=name)
            db.add(existing)
        existing.slug = payload.get("slug") or existing.slug
        existing.description = payload.get("description") or existing.description
        existing.source_url = payload.get("source_url") or existing.source_url
        existing.group_name = payload.get("group_name") or existing.group_name
        existing.parent_page = payload.get("parent_page") or existing.parent_page
        if payload.get("is_group") is not None:
            existing.is_group = bool(payload.get("is_group"))
        existing.min_level = payload.get("min_level") if payload.get("min_level") is not None else existing.min_level
        existing.max_level = payload.get("max_level") if payload.get("max_level") is not None else existing.max_level
        existing.experience_reward = payload.get("experience_reward") if payload.get("experience_reward") is not None else existing.experience_reward
        existing.treasure = payload.get("treasure") or existing.treasure
        existing.location = payload.get("location") or existing.location
        existing.npc = payload.get("npc") or existing.npc
        existing.rewards = payload.get("rewards") or existing.rewards
        existing.requirements = payload.get("requirements") or existing.requirements
        existing.related_creatures = payload.get("related_creatures") or existing.related_creatures
        existing.last_synced_at = datetime.now(UTC)
        existing.raw_data = payload
        return "created" if created else "updated"

    @staticmethod
    def _upsert_hunt_zone(db: Session, payload: dict[str, Any]) -> str:
        name = payload.get("name")
        if not name:
            raise ValueError("Missing hunt zone name")
        normalized_name = normalize_search_text(name)
        zone = db.query(HuntZone).filter(HuntZone.normalized_name == normalized_name).first()
        created = zone is None
        if not zone:
            zone = HuntZone(name=name, normalized_name=normalized_name, min_level=0)
            db.add(zone)
        zone.name = name
        zone.slug = payload.get("slug") or zone.slug
        zone.normalized_name = normalized_name
        zone.city = payload.get("city") or payload.get("location") or zone.city
        zone.region = payload.get("region") or zone.region
        zone.source_provider = payload.get("source_provider") or zone.source_provider
        zone.description = payload.get("description") or zone.description
        zone.source_name = payload.get("source_name") or zone.source_name or "tibiawiki"
        zone.source_url = payload.get("source_url") or zone.source_url
        zone.recommended_level = payload.get("recommended_level") if payload.get("recommended_level") is not None else zone.recommended_level
        zone.min_level = payload.get("min_level") if payload.get("min_level") is not None else zone.min_level
        zone.max_level = payload.get("max_level") if payload.get("max_level") is not None else zone.max_level
        zone.recommended_vocations = payload.get("recommended_vocations") or zone.recommended_vocations
        zone.recommended_party_size = payload.get("recommended_party_size") or zone.recommended_party_size
        zone.exp_rating = payload.get("exp_rating") or zone.exp_rating
        zone.profit_rating = payload.get("profit_rating") or zone.profit_rating
        zone.danger_rating = payload.get("danger_rating") or zone.danger_rating
        zone.map_x = payload.get("map_x") if payload.get("map_x") is not None else zone.map_x
        zone.map_y = payload.get("map_y") if payload.get("map_y") is not None else zone.map_y
        zone.map_z = payload.get("map_z") if payload.get("map_z") is not None else zone.map_z
        zone.map_bounds = payload.get("map_bounds") or zone.map_bounds
        zone.map_image_url = payload.get("map_image_url") or zone.map_image_url
        zone.raw_data = payload
        zone.last_synced_at = datetime.now(UTC)
        return "created" if created else "updated"

    @staticmethod
    async def _run_segment(
        db: Session,
        job: SyncJob,
        target: str,
        *,
        force: bool,
        limit: int | None,
        retry_count: int,
        timeout_seconds: int,
    ) -> dict[str, Any]:
        if target == "images":
            result = await SyncService.sync_images(db, limit=limit)
            return {
                "processed": int(result.get("total") or 0),
                "summary": {
                    "images_cached": int(result.get("created") or 0) + int(result.get("updated") or 0),
                    "images_failed": int(result.get("errors") or 0),
                },
            }

        if target == "creatures":
            return await SyncService._sync_creatures_batched(
                db,
                job,
                only_bosses=False,
                limit=limit,
                retry_count=retry_count,
                timeout_seconds=timeout_seconds,
                force=force,
            )

        if target == "bosses":
            return await SyncService._sync_creatures_batched(
                db,
                job,
                only_bosses=True,
                limit=limit,
                retry_count=retry_count,
                timeout_seconds=timeout_seconds,
                force=force,
            )

        if target == "quests":
            result = await SyncService.sync_quests(
                db,
                limit=limit,
                recursive=True,
                timeout_seconds=timeout_seconds,
            )
            return {
                "processed": int(result.get("total") or 0),
                "summary": {
                    "quests_created": int(result.get("created") or 0),
                    "quests_updated": int(result.get("updated") or 0),
                    "quests_failed": int(result.get("errors") or 0),
                },
            }

        if target == "hunt-zones":
            result = await SyncService.sync_hunt_zones_from_tibiamaps(db, limit=limit)
            return {
                "processed": int(result.get("total") or 0),
                "summary": {
                    "hunt_zones_created": int(result.get("created") or 0),
                    "hunt_zones_updated": int(result.get("updated") or 0),
                    "hunt_zones_failed": int(result.get("errors") or 0),
                },
            }

        if target == "items":
            return await SyncService._sync_catalog_batched(
                db,
                job,
                target=target,
                limit=limit,
                retry_count=retry_count,
                timeout_seconds=timeout_seconds,
            )

        raise ValueError(f"Unknown sync segment: {target}")

    @staticmethod
    async def _sync_creatures_batched(
        db: Session,
        job: SyncJob,
        *,
        only_bosses: bool,
        limit: int | None,
        retry_count: int,
        timeout_seconds: int,
        force: bool,
    ) -> dict[str, Any]:
        _ = force
        names = await get_category_members("Creatures")
        if limit is not None and limit > 0:
            names = names[:limit]

        total = len(names)
        checkpoint = job.checkpoint or {}
        offset = int(checkpoint.get("current_offset") or 0) if checkpoint.get("current_entity_type") in {"creatures", "bosses"} else 0
        processed = 0
        counters = defaultdict(int)
        batch_size = int(job.batch_size or 100)
        key_prefix = "bosses" if only_bosses else "creatures"

        while offset < total:
            db.refresh(job)
            if job.cancel_requested:
                SyncService._save_checkpoint(db, job, entity_type="bosses" if only_bosses else "creatures", offset=offset)
                break

            batch_names = names[offset: offset + batch_size]
            if not batch_names:
                break

            for name in batch_names:
                operation = "updated"
                normalized_name = normalize_search_text(name)
                if not db.query(Creature).filter(Creature.normalized_name == normalized_name).first():
                    operation = "created"

                success = False
                last_error: Exception | None = None
                for attempt in range(retry_count + 1):
                    try:
                        if _FORCE_FAIL_NAME and _FORCE_FAIL_NAME in name.lower():
                            raise RuntimeError(f"Injected sync failure for '{name}'")
                        payload = await asyncio.wait_for(get_creature_detail_by_name(name), timeout=timeout_seconds)
                        if only_bosses and not bool(payload.get("is_boss")):
                            success = True
                            break
                        upsert_creature_payload(db, payload)
                        counters[f"{key_prefix}_{operation}"] += 1
                        job.last_successful_external_id = payload.get("slug") or payload.get("name") or name
                        success = True
                        break
                    except Exception as exc:
                        last_error = exc
                        if attempt >= retry_count:
                            break
                        _category, retryable, retry_after = SyncService.classify_provider_error(exc)
                        if not retryable:
                            break
                        await SyncService._sleep_with_heartbeat(db, job, SyncService.retry_delay(attempt + 1, retry_after))

                processed += 1
                job.processed_count = int(job.processed_count or 0) + 1
                if not success:
                    counters[f"{key_prefix}_failed"] += 1
                    job.failed_count = int(job.failed_count or 0) + 1
                    error_category = SyncService.classify_provider_error(last_error)[0] if last_error else "unknown_failure"
                    db.add(
                        SyncJobError(
                            job_id=job.id,
                            entity_type="boss" if only_bosses else "creature",
                            external_id=name,
                            entity_name=name,
                            error_message="The provider record could not be synchronized safely.",
                            error_category=error_category,
                            retry_count=retry_count,
                            status="failed",
                        )
                    )

                db.add(job)
                if processed % _SYNC_HEARTBEAT_EVERY_ITEMS == 0:
                    SyncService._heartbeat(db, job)

            offset += len(batch_names)
            db.commit()

            SyncService._update_job_progress(
                db,
                job,
                progress_current=offset,
                progress_total=max(total, 1),
                current_step=f"sync:{key_prefix}",
                message=f"{key_prefix} {offset}/{total}",
            )
            SyncService._save_checkpoint(
                db,
                job,
                entity_type="bosses" if only_bosses else "creatures",
                offset=offset,
                last_successful_external_id=job.last_successful_external_id,
            )
            if _FORCE_FATAL_AFTER > 0 and processed >= _FORCE_FATAL_AFTER:
                raise RuntimeError("Injected fatal sync stop after checkpoint")

        db.commit()
        return {"processed": processed, "summary": dict(counters)}

    @staticmethod
    async def _sync_catalog_batched(
        db: Session,
        job: SyncJob,
        *,
        target: str,
        limit: int | None,
        retry_count: int,
        timeout_seconds: int,
    ) -> dict[str, Any]:
        _ = timeout_seconds
        category = {
            "items": "Items",
            "quests": "Quests",
            "hunt-zones": "Hunting Places",
        }[target]
        names = await get_category_members(category)
        if limit is not None and limit > 0:
            names = names[:limit]

        total = len(names)
        checkpoint = job.checkpoint or {}
        offset = int(checkpoint.get("current_offset") or 0) if checkpoint.get("current_entity_type") == target else 0
        processed = 0
        counters = defaultdict(int)
        batch_size = int(job.batch_size or 100)
        summary_prefix = {
            "items": "items",
            "quests": "quests",
            "hunt-zones": "hunt_zones",
        }[target]

        while offset < total:
            db.refresh(job)
            if job.cancel_requested:
                SyncService._save_checkpoint(db, job, entity_type=target, offset=offset)
                break

            batch_names = names[offset: offset + batch_size]
            if not batch_names:
                break

            for name in batch_names:
                payload = {
                    "name": name,
                    "description": None,
                    "location": None,
                    "min_level": None,
                    "max_level": None,
                    "experience_reward": None,
                    "treasure": [],
                    "npc": None,
                    "item_id": None,
                    "type": None,
                    "weight": None,
                    "value": None,
                    "attack": None,
                    "defense": None,
                    "armor": None,
                    "levelrequired": None,
                    "vocationrequired": None,
                    "tradeable": True,
                    "stackable": False,
                }

                success = False
                last_error: Exception | None = None
                for attempt in range(retry_count + 1):
                    try:
                        if _FORCE_FAIL_NAME and _FORCE_FAIL_NAME in name.lower():
                            raise RuntimeError(f"Injected sync failure for '{name}'")
                        if target == "items":
                            outcome = SyncService._upsert_item(db, payload)
                        elif target == "quests":
                            outcome = SyncService._upsert_quest(db, payload)
                        else:
                            outcome = SyncService._upsert_hunt_zone(db, payload)
                        counters[f"{summary_prefix}_{outcome}"] += 1
                        job.last_successful_external_id = name
                        success = True
                        break
                    except Exception as exc:
                        last_error = exc
                        if attempt >= retry_count:
                            break
                        _category, retryable, retry_after = SyncService.classify_provider_error(exc)
                        if not retryable:
                            break
                        await SyncService._sleep_with_heartbeat(db, job, SyncService.retry_delay(attempt + 1, retry_after))

                processed += 1
                job.processed_count = int(job.processed_count or 0) + 1
                if not success:
                    counters[f"{summary_prefix}_failed"] += 1
                    job.failed_count = int(job.failed_count or 0) + 1
                    error_category = SyncService.classify_provider_error(last_error)[0] if last_error else "unknown_failure"
                    db.add(
                        SyncJobError(
                            job_id=job.id,
                            entity_type=target,
                            external_id=name,
                            entity_name=name,
                            error_message="The provider record could not be synchronized safely.",
                            error_category=error_category,
                            retry_count=retry_count,
                            status="failed",
                        )
                    )

                db.add(job)
                if processed % _SYNC_HEARTBEAT_EVERY_ITEMS == 0:
                    SyncService._heartbeat(db, job)

            offset += len(batch_names)
            db.commit()
            SyncService._update_job_progress(
                db,
                job,
                progress_current=offset,
                progress_total=max(total, 1),
                current_step=f"sync:{target}",
                message=f"{target} {offset}/{total}",
            )
            SyncService._save_checkpoint(
                db,
                job,
                entity_type=target,
                offset=offset,
                last_successful_external_id=job.last_successful_external_id,
            )
            if _FORCE_FATAL_AFTER > 0 and processed >= _FORCE_FATAL_AFTER:
                raise RuntimeError("Injected fatal sync stop after checkpoint")

        db.commit()
        return {"processed": processed, "summary": dict(counters)}

    # Pages that are navigation/utility rather than actual quests (skip as children)
    _QUEST_SKIP_PAGES = frozenset({
        "quest log", "quests", "access quests", "main page", "tibia", "help",
        "category", "template", "file", "image",
    })

    # Top-level mega-hub pages that just list all quests — skip recursive processing
    # to avoid fetching hundreds of links (items, creatures, etc.)
    _QUEST_MEGA_HUBS = frozenset({
        "quests",  # The "Quests" umbrella page lists everything — skip children
    })

    @staticmethod
    def _is_candidate_quest_link(link_name: str) -> bool:
        """Return True if a wiki link looks like an individual quest page (not navigation).

        We require either 'quest' in the name OR a pattern like 'Arena', 'Challenge', etc.
        This prevents syncing hundreds of item/creature links from hub pages.
        """
        n = normalize_search_text(link_name)
        if not n or len(n) < 3:
            return False
        if n in SyncService._QUEST_SKIP_PAGES:
            return False
        # Skip list/category/template/file pages
        if n.startswith(("list of", "category:", "template:", "file:")):
            return False
        # Must contain 'quest' OR known quest-like suffixes to avoid syncing items/creatures
        quest_keywords = ("quest", "challenge", "arena", "mission", "task", "adventure")
        if not any(kw in n for kw in quest_keywords):
            return False
        return True

    @staticmethod
    async def sync_quests(
        db: Session,
        *,
        limit: int | None = None,
        recursive: bool = True,
        timeout_seconds: int = 15,
    ) -> dict[str, Any]:
        """Sync quests from TibiaWiki with group/hub detection and recursive child extraction.

        Strategy:
        1. Get Category:Quests members — these are hub/group pages.
        2. Mark each hub page as is_group=True.
        3. For each hub page, get ALL its wiki links (not restricted to category members).
        4. Process each non-navigation link as a potential individual quest.
        """
        quest_pages = await get_category_members("Quests")
        if limit is not None and limit > 0:
            quest_pages = quest_pages[:limit]

        # All hub-page names (normalized) so we don't recurse into them as children
        hub_set = {normalize_search_text(name) for name in quest_pages}

        created = 0
        updated = 0
        errors = 0
        processed = 0

        for page_name in quest_pages:
            try:
                summary = await asyncio.wait_for(get_quest_page_summary(page_name), timeout=timeout_seconds)
                child_links: list[str] = []
                is_mega_hub = normalize_search_text(page_name) in SyncService._QUEST_MEGA_HUBS

                if recursive and not is_mega_hub:
                    links = await asyncio.wait_for(get_page_links(page_name), timeout=timeout_seconds)
                    for link_name in links:
                        normalized = normalize_search_text(link_name)
                        if normalized == normalize_search_text(page_name):
                            continue
                        # Skip other hub-pages (we'll process them as top-level)
                        if normalized in hub_set:
                            continue
                        if SyncService._is_candidate_quest_link(link_name):
                            child_links.append(link_name)

                # Mega hubs always stay as is_group=True (no children to process)
                is_group = bool(child_links) or is_mega_hub
                group_payload = {
                    **summary,
                    "name": page_name,
                    "slug": normalize_search_text(page_name).replace(" ", "-"),
                    "is_group": is_group,
                    "group_name": page_name if is_group else summary.get("group_name"),
                    "parent_page": None,
                    "related_creatures": summary.get("related_creatures") or [],
                }
                op = SyncService._upsert_quest(db, group_payload)
                if op == "created":
                    created += 1
                else:
                    updated += 1
                processed += 1

                for child_name in child_links:
                    try:
                        child_summary = await asyncio.wait_for(
                            get_quest_page_summary(child_name), timeout=timeout_seconds
                        )
                        child_payload = {
                            **child_summary,
                            "name": child_name,
                            "slug": normalize_search_text(child_name).replace(" ", "-"),
                            "is_group": False,
                            "group_name": page_name,
                            "parent_page": page_name,
                        }
                        child_op = SyncService._upsert_quest(db, child_payload)
                        if child_op == "created":
                            created += 1
                        else:
                            updated += 1
                        processed += 1
                    except Exception as child_exc:
                        errors += 1
                        logger.warning(
                            "sync_quests_child_failed parent=%s child=%s error=%s",
                            page_name, child_name, child_exc,
                        )
                        continue
            except Exception as exc:
                errors += 1
                logger.warning("sync_quests_page_failed page=%s error=%s", page_name, exc)
                continue

        db.commit()
        return {
            "status": "success",
            "created": created,
            "updated": updated,
            "errors": errors,
            "total": processed,
            "recursive": recursive,
        }

    @staticmethod
    async def sync_hunt_zones_from_tibiamaps(
        db: Session,
        *,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Seed/refresh hunt-zone map infrastructure from tibiamaps metadata.

        tibiamaps does not provide canonical "hunt zones" as first-class entities.
        We keep existing local zone names and enrich map metadata/provider references.
        """
        bounds = await get_tibiamaps_bounds()
        markers = await get_tibiamaps_markers(limit=5000)

        zones = db.query(HuntZone).order_by(HuntZone.id.asc()).all()
        if limit is not None and limit > 0:
            zones = zones[:limit]

        created = 0
        updated = 0
        errors = 0

        bounds_center = None
        if bounds:
            try:
                min_x = int(bounds.get("minX"))
                max_x = int(bounds.get("maxX"))
                min_y = int(bounds.get("minY"))
                max_y = int(bounds.get("maxY"))
                bounds_center = {
                    "x": int((min_x + max_x) / 2),
                    "y": int((min_y + max_y) / 2),
                    "z": 7,
                }
            except Exception:
                bounds_center = None

        for zone in zones:
            try:
                before_provider = zone.source_provider
                zone.source_provider = "tibiamaps"
                zone.source_name = zone.source_name or "tibiamaps"
                zone.source_url = zone.source_url or "https://github.com/tibiamaps/tibia-map-data"
                zone.map_bounds = bounds or zone.map_bounds
                if bounds_center:
                    zone.map_x = zone.map_x or bounds_center["x"]
                    zone.map_y = zone.map_y or bounds_center["y"]
                    zone.map_z = zone.map_z if zone.map_z is not None else bounds_center["z"]

                # If no custom preview exists, use a stable floor preview from tibiamaps CDN.
                if not zone.map_image_url:
                    floor = zone.map_z if zone.map_z is not None else 7
                    floor = max(0, min(15, int(floor)))
                    zone.map_image_url = f"https://tibiamaps.github.io/tibia-map-data/floor-{floor:02d}-map.png"

                zone.raw_data = {
                    **(zone.raw_data or {}),
                    "source_provider": "tibiamaps",
                    "tibiamaps_marker_count": len(markers),
                }
                zone.last_synced_at = datetime.now(UTC)
                if before_provider is None:
                    created += 1
                else:
                    updated += 1
                db.add(zone)
            except Exception as exc:
                errors += 1
                logger.warning("sync_hunt_zones_tibiamaps_failed zone=%s error=%s", zone.name, exc)

        db.commit()
        return {
            "status": "success",
            "created": created,
            "updated": updated,
            "errors": errors,
            "total": len(zones),
            "provider": "tibiamaps",
            "marker_count": len(markers),
            "has_bounds": bool(bounds),
        }

    @staticmethod
    async def sync_bosses(db: Session, *, limit: int | None = None) -> dict[str, Any]:
        _ = (db, limit)
        return {"status": "deprecated", "processed": 0, "total": 0}

    @staticmethod
    async def sync_images(db: Session, *, limit: int | None = None) -> dict[str, Any]:
        _IMAGE_DIR.mkdir(parents=True, exist_ok=True)
        queued: list[tuple[str, str, int, str]] = []

        for creature in db.query(Creature).filter(Creature.image_url.isnot(None)).all():
            queued.append(("creature_image", "creature", creature.id, creature.image_url))
        for loot in db.query(Loot).filter(Loot.item_image_url.isnot(None)).all():
            queued.append(("item_image", "item", loot.id, loot.item_image_url))
        for zone in db.query(HuntZone).filter(HuntZone.map_image_url.isnot(None)).all():
            queued.append(("hunt_zone_map", "hunt_zone", zone.id, zone.map_image_url))

        if limit is not None and limit > 0:
            queued = queued[:limit]

        created = 0
        updated = 0
        errors = 0
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True, headers={"User-Agent": settings.TIBIAWIKI_USER_AGENT}) as client:
            for resource_type, entity_type, entity_id, url in queued:
                ok = await SyncService._cache_remote_resource(
                    db,
                    client=client,
                    resource_type=resource_type,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    source_url=url,
                )
                if ok == "created":
                    created += 1
                elif ok == "updated":
                    updated += 1
                else:
                    errors += 1

        db.commit()
        return {"status": "success", "created": created, "updated": updated, "errors": errors, "total": len(queued)}

    @staticmethod
    async def _cache_remote_resource(
        db: Session,
        *,
        client: httpx.AsyncClient,
        resource_type: str,
        entity_type: str,
        entity_id: int,
        source_url: str,
    ) -> str:
        resource = (
            db.query(CachedResource)
            .filter(
                CachedResource.resource_type == resource_type,
                CachedResource.entity_type == entity_type,
                CachedResource.entity_id == entity_id,
            )
            .first()
        )
        created = False
        if not resource:
            resource = CachedResource(
                resource_type=resource_type,
                entity_type=entity_type,
                entity_id=entity_id,
                source_url=source_url,
                status="pending",
            )
            created = True
            db.add(resource)

        try:
            response = await client.get(source_url)
            response.raise_for_status()
            content = response.content
            checksum = hashlib.sha1(content).hexdigest()
            local_name = f"{resource_type}-{entity_type}-{entity_id}-{checksum[:10]}.bin"
            local_path = _IMAGE_DIR / local_name
            local_path.write_bytes(content)

            resource.resolved_url = str(response.url)
            resource.local_path = str(local_path)
            resource.resource_key = hashlib.sha1(source_url.encode("utf-8")).hexdigest()
            resource.content_type = (response.headers.get("content-type") or "application/octet-stream").split(";")[0]
            resource.size_bytes = len(content)
            resource.checksum = checksum
            resource.etag_hash = checksum
            resource.status = "ready"
            resource.last_fetched_at = datetime.now(UTC)
            resource.fetch_attempts = (resource.fetch_attempts or 0) + 1
            resource.error = None
            resource.error_message = None
            db.add(resource)
            db.commit()
            return "created" if created else "updated"
        except Exception as exc:
            resource.status = "failed"
            resource.fetch_attempts = (resource.fetch_attempts or 0) + 1
            resource.error = str(exc)
            resource.error_message = str(exc)
            db.add(resource)
            db.commit()
            return "error"

    @staticmethod
    async def _maybe_send_notification(db: Session, job: SyncJob, *, success: bool) -> None:
        enabled = SyncService._get_setting(db, "sync_notify_email_enabled", "0") == "1"
        if not enabled or not job.requested_by_user_id:
            return
        user = db.query(User).filter(User.id == job.requested_by_user_id).first()
        if not user or not user.email:
            return

        title = "TibiaHub synchronization completed" if success else "TibiaHub synchronization needs attention"
        EmailOutboxService.enqueue_notification(
            db, user=user, subject=title,
            message=f"Operation {job.id} finished with status {job.status}. {job.message or ''}",
            event_key=f"sync:{job.id}:{job.status}", locale="en",
        )
        db.commit()


class DatabaseSyncService:
    """Compatibility wrapper used by legacy `/sync` endpoints."""

    @staticmethod
    def backup_creatures(db: Session) -> dict[str, Any]:
        creatures = db.query(Creature).all()
        zones = db.query(HuntZone).all()
        return {
            "timestamp": datetime.now(UTC).isoformat(),
            "creatures": [{"id": c.id, "name": c.name} for c in creatures],
            "zones": [{"id": z.id, "name": z.name} for z in zones],
        }

    @staticmethod
    def sync_with_external_apis(db: Session) -> dict[str, Any]:
        creatures_count = db.query(Creature).count()
        zones_count = db.query(HuntZone).count()
        return {
            "backup_created": True,
            "backup_timestamp": datetime.now(UTC).isoformat(),
            "tracked_changes": {
                "timestamp": datetime.now(UTC).isoformat(),
                "total_changes": 0,
                "pending": 0,
                "changes": [],
            },
            "total_pending_approvals": 0,
            "api_status": {"tibia_data": "unknown", "tibia_wiki": "unknown"},
            "stats": {"creatures": creatures_count, "zones": zones_count},
        }

    @staticmethod
    def apply_approved_changes(db: Session, change_indices: list[int], tracker_data: dict[str, Any]) -> dict[str, Any]:
        _ = (db, tracker_data)
        return {"applied": 0, "failed": 0, "total_requested": len(change_indices)}
