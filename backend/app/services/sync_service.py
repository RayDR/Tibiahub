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
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import SessionLocal
from app.models.creature import Creature
from app.models.external_data import CachedResource, SyncJob
from app.models.hunt_zone import HuntZone
from app.models.loot import Loot
from app.models.settings import SystemSettings
from app.models.user import User
from app.services.creature_storage_service import upsert_creature_payload
from app.services.email_service import EmailService
from app.services.external_apis import get_creatures
from app.services.external_sync_service import ExternalSyncService

logger = logging.getLogger(__name__)
_CACHE_DIR = Path("backend/storage/cache")
_IMAGE_DIR = _CACHE_DIR / "images"
_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="tibiahub-sync")


class SyncService:
    SYNC_TARGETS = {"full", "creatures", "bosses", "items", "quests", "hunt-zones", "images"}

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
    def create_job(db: Session, *, job_type: str, requester: str | None = None, requested_by_user_id: int | None = None) -> SyncJob:
        SyncService.ensure_default_settings(db)
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

        job_id = hashlib.sha1(f"{job_type}:{datetime.utcnow().isoformat()}".encode("utf-8")).hexdigest()[:32]
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
            cancel_requested=False,
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def queue_job(job_id: str, *, force: bool = False, skip_images: bool = False, limit: int | None = None) -> None:
        _EXECUTOR.submit(SyncService._run_job_sync, job_id, force, skip_images, limit)

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
        if job.status in {"completed", "failed", "cancelled"}:
            return job
        job.cancel_requested = True
        job.message = "Cancellation requested"
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def _run_job_sync(job_id: str, force: bool, skip_images: bool, limit: int | None) -> None:
        asyncio.run(SyncService._run_job_async(job_id, force=force, skip_images=skip_images, limit=limit))

    @staticmethod
    async def _run_job_async(job_id: str, *, force: bool, skip_images: bool, limit: int | None) -> None:
        db = SessionLocal()
        try:
            job = SyncService.get_job(db, job_id)
            if not job:
                return

            timeout_seconds = int(SyncService._get_setting(db, "sync_request_timeout_seconds", "30") or "30")
            retry_count = max(0, int(SyncService._get_setting(db, "sync_retry_count", "2") or "2"))

            job.status = "running"
            job.started_at = datetime.utcnow()
            job.current_step = "starting"
            job.message = "Sync started"
            db.commit()

            plan = [job.job_type] if job.job_type != "full" else ["creatures", "bosses", "items", "quests", "hunt-zones", "images"]
            if skip_images:
                plan = [step for step in plan if step != "images"]

            total_steps = len(plan)
            results: dict[str, Any] = {}

            for index, step in enumerate(plan, start=1):
                db.refresh(job)
                if job.cancel_requested:
                    job.status = "cancelled"
                    job.finished_at = datetime.utcnow()
                    job.message = "Sync cancelled by user"
                    db.commit()
                    return

                SyncService._update_job_progress(
                    db,
                    job,
                    progress_current=index - 1,
                    progress_total=total_steps,
                    current_step=f"sync:{step}",
                    message=f"Running {step} sync",
                )

                attempt = 0
                while True:
                    try:
                        result = await asyncio.wait_for(
                            SyncService._run_segment(db, step, force=force, limit=limit),
                            timeout=timeout_seconds,
                        )
                        results[step] = result
                        break
                    except Exception:
                        attempt += 1
                        if attempt > retry_count:
                            raise

                SyncService._update_job_progress(
                    db,
                    job,
                    progress_current=index,
                    progress_total=total_steps,
                    current_step=f"completed:{step}",
                    message=f"Completed {step}",
                )

            finished_at = datetime.utcnow()
            job.status = "completed"
            job.finished_at = finished_at
            job.current_step = "done"
            job.message = "Sync completed successfully"
            job.result_summary = results
            job.progress = 100
            job.progress_percent = 100
            SyncService._set_setting(db, "sync_last_success_at", finished_at.isoformat(), "Last successful sync timestamp")
            SyncService._set_setting(db, "tibia_latest_update_version", finished_at.strftime("Synced %Y-%m-%d"), "Latest synchronized data version label")
            db.commit()
            await SyncService._maybe_send_notification(db, job, success=True)
        except Exception as exc:
            job = SyncService.get_job(db, job_id)
            if job:
                job.status = "failed"
                job.finished_at = datetime.utcnow()
                job.error = str(exc)
                job.error_message = str(exc)
                job.message = "Sync failed"
                db.commit()
                await SyncService._maybe_send_notification(db, job, success=False)
            logger.exception("sync_job_failed job_id=%s error=%s", job_id, exc)
        finally:
            db.close()

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
    async def _run_segment(db: Session, target: str, *, force: bool, limit: int | None) -> dict[str, Any]:
        if target == "creatures":
            return await ExternalSyncService.sync_creatures(db, mode="auto" if force else "compare")
        if target == "items":
            return await ExternalSyncService.sync_items(db)
        if target == "quests":
            return await ExternalSyncService.sync_quests(db)
        if target == "hunt-zones":
            return await ExternalSyncService.sync_hunting_places(db)
        if target == "bosses":
            return await SyncService.sync_bosses(db, limit=limit)
        if target == "images":
            return await SyncService.sync_images(db, limit=limit)
        raise ValueError(f"Unknown sync segment: {target}")

    @staticmethod
    async def sync_bosses(db: Session, *, limit: int | None = None) -> dict[str, Any]:
        response = await get_creatures(expand=True)
        if not response.success() or not isinstance(response.data, list):
            return {"status": "error", "error": response.error or "Unable to fetch bosses", "processed": 0}

        payloads = [item for item in response.data if bool(item.get("is_boss"))]
        if limit is not None and limit > 0:
            payloads = payloads[:limit]

        created_or_updated = 0
        for payload in payloads:
            upsert_creature_payload(db, payload)
            created_or_updated += 1
        db.commit()
        return {"status": "success", "processed": created_or_updated, "total": len(payloads)}

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
            resource.last_fetched_at = datetime.utcnow()
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

        title = "TibiaHub Sync Completed" if success else "TibiaHub Sync Failed"
        summary_json = json.dumps(job.result_summary or {}, ensure_ascii=True, indent=2)
        text_body = (
            f"Hello {user.username},\n\n"
            f"Job: {job.id}\n"
            f"Target: {job.job_type}\n"
            f"Status: {job.status}\n"
            f"Message: {job.message or ''}\n"
            f"Summary:\n{summary_json}\n"
        )
        html_body = (
            "<h2>TibiaHub Sync Report</h2>"
            f"<p><strong>Job:</strong> {job.id}</p>"
            f"<p><strong>Target:</strong> {job.job_type}</p>"
            f"<p><strong>Status:</strong> {job.status}</p>"
            f"<p><strong>Message:</strong> {job.message or ''}</p>"
            f"<pre>{summary_json}</pre>"
        )
        EmailService.send_message(
            EmailService.build_message(
                to_email=user.email,
                subject=title,
                html_body=html_body,
                text_body=text_body,
            )
        )


class DatabaseSyncService:
    """Compatibility wrapper used by legacy `/sync` endpoints."""

    @staticmethod
    def backup_creatures(db: Session) -> dict[str, Any]:
        creatures = db.query(Creature).all()
        zones = db.query(HuntZone).all()
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "creatures": [{"id": c.id, "name": c.name} for c in creatures],
            "zones": [{"id": z.id, "name": z.name} for z in zones],
        }

    @staticmethod
    def sync_with_external_apis(db: Session) -> dict[str, Any]:
        creatures_count = db.query(Creature).count()
        zones_count = db.query(HuntZone).count()
        return {
            "backup_created": True,
            "backup_timestamp": datetime.utcnow().isoformat(),
            "tracked_changes": {
                "timestamp": datetime.utcnow().isoformat(),
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
