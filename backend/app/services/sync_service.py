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
import os
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import desc, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import SessionLocal
from app.models.creature import Creature
from app.models.external_data import CachedResource, Item, SyncJob, SyncJobError, TibiaWikiQuest
from app.models.hunt_zone import HuntZone
from app.models.loot import Loot
from app.models.settings import SystemSettings
from app.models.user import User
from app.services.bestiary_source import (
    get_category_members,
    get_creature_detail_by_name,
    get_page_links,
    get_quest_page_summary,
    get_tibiamaps_bounds,
    get_tibiamaps_markers,
)
from app.services.creature_storage_service import upsert_creature_payload
from app.services.email_service import EmailService
from app.services.text_utils import normalize_search_text

logger = logging.getLogger(__name__)
_CACHE_DIR = Path("backend/storage/cache")
_IMAGE_DIR = _CACHE_DIR / "images"
_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="tibiahub-sync")
_FORCE_FAIL_NAME = (os.getenv("SYNC_FORCE_FAIL_NAME") or "").strip().lower()
_FORCE_FATAL_AFTER = int(os.getenv("SYNC_FORCE_FATAL_AFTER") or "0")
_SYNC_STALE_RUNNING_MINUTES = int(os.getenv("SYNC_STALE_RUNNING_MINUTES") or "45")
_SYNC_HEARTBEAT_EVERY_ITEMS = max(1, int(os.getenv("SYNC_HEARTBEAT_EVERY_ITEMS") or "25"))


class SyncService:
    SYNC_TARGETS = {"full", "creatures", "bosses", "items", "quests", "hunt-zones", "images"}

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
            job_limit=job_limit,
            cancel_requested=False,
            current_offset=0,
            processed_count=0,
            failed_count=0,
            checkpoint={},
            batch_size=max(10, min(batch_size, 500)),
            max_retries=max(0, min(max_retries, 10)),
            external_timeout_seconds=max(5, min(external_timeout_seconds, 120)),
        )
        db.add(job)
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
        now = datetime.utcnow()
        now_str = now.strftime("%Y-%m-%d %H:%M:%S")
        stale_ids: list[str] = []

        try:
            rows = db.execute(
                text(
                    """
                    SELECT id, COALESCE(updated_at, started_at, created_at) AS heartbeat_at
                    FROM sync_jobs
                    WHERE status = 'running'
                    """
                )
            ).mappings().all()

            for row in rows:
                heartbeat_raw = row.get("heartbeat_at")
                if heartbeat_raw is None:
                    continue

                if isinstance(heartbeat_raw, datetime):
                    heartbeat = heartbeat_raw
                else:
                    heartbeat_text = str(heartbeat_raw).replace("T", " ").replace("Z", "")
                    try:
                        heartbeat = datetime.fromisoformat(heartbeat_text)
                    except ValueError:
                        continue

                elapsed_minutes = (now - heartbeat).total_seconds() / 60
                if elapsed_minutes < threshold_minutes:
                    continue

                db.execute(
                    text(
                        """
                        UPDATE sync_jobs
                        SET status = 'failed',
                            cancel_requested = 1,
                            message = :reason,
                            error = :reason,
                            error_message = :reason,
                            finished_at = :now,
                            updated_at = :now
                        WHERE id = :job_id
                        """
                    ),
                    {"reason": reason, "now": now_str, "job_id": row["id"]},
                )
                stale_ids.append(row["id"])

            if stale_ids:
                db.commit()
        except Exception:
            db.rollback()
            logger.exception("sync_stale_recovery_failed")
        return stale_ids

    @staticmethod
    def _heartbeat(db: Session, job: SyncJob, *, message: str | None = None) -> None:
        job.updated_at = datetime.utcnow()
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
        _EXECUTOR.submit(SyncService._run_job_sync, job_id, force, skip_images, limit, resume)

    @staticmethod
    def resume_job(db: Session, job_id: str) -> SyncJob | None:
        job = SyncService.get_job(db, job_id)
        if not job:
            return None
        if job.status not in {"failed", "cancelled"}:
            raise RuntimeError("Only failed/cancelled jobs can be resumed")
        job.status = "pending"
        job.cancel_requested = False
        job.error = None
        job.error_message = None
        job.message = "Resume requested"
        db.add(job)
        db.commit()
        db.refresh(job)
        SyncService.queue_job(job.id, limit=job.job_limit, resume=True)
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
        if job.status in {"completed", "failed", "cancelled"}:
            return job
        job.cancel_requested = True
        job.message = "Cancellation requested"
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def _run_job_sync(job_id: str, force: bool, skip_images: bool, limit: int | None, resume: bool = False) -> None:
        asyncio.run(SyncService._run_job_async(job_id, force=force, skip_images=skip_images, limit=limit, resume=resume))

    @staticmethod
    async def _run_job_async(job_id: str, *, force: bool, skip_images: bool, limit: int | None, resume: bool) -> None:
        db = SessionLocal()
        try:
            job = SyncService.get_job(db, job_id)
            if not job:
                return

            timeout_seconds = job.external_timeout_seconds or int(SyncService._get_setting(db, "sync_request_timeout_seconds", "30") or "30")
            retry_count = job.max_retries if job.max_retries is not None else max(0, int(SyncService._get_setting(db, "sync_retry_count", "2") or "2"))

            job.status = "running"
            job.started_at = datetime.utcnow()
            job.updated_at = datetime.utcnow()
            if not resume:
                job.current_step = "starting"
                job.message = "Sync started"
                job.result_summary = SyncService._empty_summary()
                job.current_offset = 0
                job.processed_count = 0
                job.failed_count = 0
                job.last_successful_external_id = None
                job.checkpoint = {}
            db.commit()

            plan = [job.job_type] if job.job_type != "full" else ["creatures", "bosses", "items", "quests", "hunt-zones", "images"]
            if skip_images:
                plan = [step for step in plan if step != "images"]

            checkpoint = job.checkpoint or {}
            resume_step = checkpoint.get("current_entity_type") if resume else None
            step_start_index = plan.index(resume_step) if resume_step in plan else 0
            summary = dict(job.result_summary or SyncService._empty_summary())

            for step in plan[step_start_index:]:
                db.refresh(job)
                if job.cancel_requested:
                    SyncService._save_checkpoint(
                        db,
                        job,
                        entity_type=step,
                        offset=job.current_offset or 0,
                        message="Sync cancelled by user",
                    )
                    job.status = "cancelled"
                    job.finished_at = datetime.utcnow()
                    job.message = "Sync cancelled by user"
                    db.commit()
                    return

                SyncService._heartbeat(db, job, message=f"Running {step}")

                result = await SyncService._run_segment(
                    db,
                    job,
                    step,
                    force=force,
                    limit=limit,
                    retry_count=retry_count,
                    timeout_seconds=timeout_seconds,
                )
                summary = SyncService._merge_summary(summary, result.get("summary") or {})
                summary["total_processed"] = int(summary.get("total_processed") or 0) + int(result.get("processed") or 0)
                job.result_summary = summary
                job.current_step = f"completed:{step}"
                job.message = f"Completed {step}"
                db.add(job)
                db.commit()

            finished_at = datetime.utcnow()
            job.status = "completed"
            job.finished_at = finished_at
            job.current_step = "done"
            job.message = "Sync completed successfully"
            job.checkpoint = {}
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
            "updated_at": datetime.utcnow().isoformat(),
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
        existing.updated_at = datetime.utcnow()
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
        existing.last_synced_at = datetime.utcnow()
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
        zone.last_synced_at = datetime.utcnow()
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
                        await asyncio.sleep(min(2 ** attempt, 4))

                processed += 1
                job.processed_count = int(job.processed_count or 0) + 1
                if not success:
                    counters[f"{key_prefix}_failed"] += 1
                    job.failed_count = int(job.failed_count or 0) + 1
                    db.add(
                        SyncJobError(
                            job_id=job.id,
                            entity_type="boss" if only_bosses else "creature",
                            external_id=name,
                            entity_name=name,
                            error_message=str(last_error) if last_error else "Unknown sync failure",
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
                        await asyncio.sleep(min(2 ** attempt, 4))

                processed += 1
                job.processed_count = int(job.processed_count or 0) + 1
                if not success:
                    counters[f"{summary_prefix}_failed"] += 1
                    job.failed_count = int(job.failed_count or 0) + 1
                    db.add(
                        SyncJobError(
                            job_id=job.id,
                            entity_type=target,
                            external_id=name,
                            entity_name=name,
                            error_message=str(last_error) if last_error else "Unknown sync failure",
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
                zone.last_synced_at = datetime.utcnow()
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
