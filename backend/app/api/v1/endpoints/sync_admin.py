"""Admin sync endpoints backed by centralized SyncService."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.api.v1.endpoints.auth import get_current_admin_user
from app.db.database import get_db
from app.models.creature import Creature
from app.models.external_data import SyncJob, SyncJobError
from app.models.maintenance_sync import MaintenanceHold, SyncJobPhase, SyncWorkerHeartbeat
from app.models.workspace_audit import WorkspaceAudit
from app.models.hunt_zone import HuntZone
from app.models.loot import Loot
from app.models.settings import SystemSettings as SettingsModel
from app.models.quest import Quest
from app.models.user import User
from app.services.sync_service import SyncService
from app.services.world_map_sync_service import WorldMapSyncService
from app.core.config import settings

router = APIRouter()


class SyncJobResponse(BaseModel):
    job_id: str
    job_type: str
    status: str
    operation_status: str
    progress_current: int
    progress_total: int
    progress_percent: int
    current_step: Optional[str] = None
    message: Optional[str] = None
    cancel_requested: bool
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    error: Optional[str] = None
    summary: Optional[dict[str, Any]] = None
    checkpoint: Optional[dict[str, Any]] = None
    current_entity_type: Optional[str] = None
    current_offset: int = 0
    processed_count: int = 0
    failed_count: int = 0
    last_successful_external_id: Optional[str] = None
    operation_label: Optional[str] = None
    worker_id: Optional[str] = None
    lease_expires_at: Optional[str] = None
    maintenance_requested: bool = False
    maintenance_active: bool = False
    continue_on_error: bool = True
    phases: list[dict[str, Any]] = Field(default_factory=list)


class FullSyncRequest(BaseModel):
    maintenance_enabled: bool = True
    continue_on_error: bool = True
    include_images: bool = True
    include_knowledge: bool = True
    include_guild_rosters: bool = True
    force_refresh: bool = False
    batch_size: int = Field(100, ge=10, le=500)
    max_retries: int = Field(3, ge=0, le=10)
    external_timeout_seconds: int = Field(30, ge=5, le=120)
    operation_label: str = Field(min_length=5, max_length=255)
    confirmation: str


class SyncRuntimeSettings(BaseModel):
    # Legacy keys still consumed by existing DataSyncPanel.
    bestiary_cache_only_reads: bool
    bestiary_allow_external_detail_fallback: bool
    bestiary_search_page_size: int
    sync_cooldown_minutes: int

    # New canonical keys.
    external_auto_fallback_enabled: bool
    auto_fetch_missing_images_enabled: bool
    scheduled_sync_enabled: bool
    sync_request_timeout_seconds: int
    sync_retry_count: int
    sync_notify_email_enabled: bool


class SyncRuntimeSettingsUpdate(BaseModel):
    # Legacy patch keys accepted for backward compatibility.
    bestiary_cache_only_reads: Optional[bool] = None
    bestiary_allow_external_detail_fallback: Optional[bool] = None
    bestiary_search_page_size: Optional[int] = None
    sync_cooldown_minutes: Optional[int] = None

    # New canonical patch keys.
    external_auto_fallback_enabled: Optional[bool] = None
    auto_fetch_missing_images_enabled: Optional[bool] = None
    scheduled_sync_enabled: Optional[bool] = None
    sync_request_timeout_seconds: Optional[int] = None
    sync_retry_count: Optional[int] = None
    sync_notify_email_enabled: Optional[bool] = None


class ImageCanaryRequest(BaseModel):
    limit: int = Field(30, ge=20, le=50)


class WorldMapImportRequest(BaseModel):
    upstream_commit: str = Field(min_length=7, max_length=64, pattern="^[0-9a-fA-F]+$")
    confirmation: str


@router.post("/world-maps/import-staged")
def import_staged_world_maps(
    payload: WorldMapImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """Import a pre-staged checkout; this endpoint never performs network I/O."""
    if payload.confirmation != "IMPORT STAGED WORLD MAPS":
        raise HTTPException(status_code=422, detail="Explicit world-map import confirmation is required")
    source = Path(settings.WORLD_MAP_STAGING_ROOT).resolve()
    if not source.is_dir():
        raise HTTPException(status_code=409, detail="Configured world-map staging directory is unavailable")
    try:
        result = WorldMapSyncService(db, settings.WORLD_MAP_STORAGE_ROOT).import_directory(source, upstream_commit=payload.upstream_commit.lower())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.add(WorkspaceAudit(
        workspace_type="global_admin", actor_id=current_user.id, action="world_map_import",
        target_type="world_map_floor", target_id=result["upstream_commit"],
        safe_metadata={"reason": "Explicit staged TibiaMaps import", "commit": result["upstream_commit"], "floors": result["floor_count"], "markers": result["marker_count"]},
    ))
    db.commit()
    return result


def _get_setting(db: Session, key: str, default: str = "") -> str:
    value = db.query(SettingsModel).filter(SettingsModel.key == key).first()
    return value.value if value and value.value is not None else default


def _set_setting(db: Session, key: str, value: str, description: str = "") -> None:
    setting = db.query(SettingsModel).filter(SettingsModel.key == key).first()
    if setting:
        setting.value = value
        if description:
            setting.description = description
    else:
        db.add(SettingsModel(key=key, value=value, description=description, is_active=True))


def _image_canary_status(db: Session) -> dict[str, Any]:
    raw = _get_setting(db, "sync_images_canary", "")
    try:
        result = json.loads(raw) if raw else {}
        checked_at = datetime.fromisoformat(result["checked_at"])
        if checked_at.tzinfo is None:
            checked_at = checked_at.replace(tzinfo=UTC)
        result["valid"] = bool(result.get("passed")) and checked_at >= datetime.now(UTC) - timedelta(hours=2)
        return result
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        return {"valid": False}


def _to_job_response(job, db: Session | None = None) -> SyncJobResponse:
    # Keep legacy status names expected by frontend polling logic.
    status_map = {
        "completed": "success",
        "failed": "error",
    }
    phase_rows = [] if db is None else db.query(SyncJobPhase).filter(
        SyncJobPhase.job_id == job.id,
    ).order_by(SyncJobPhase.order_index).all()
    latest_errors: dict[str, tuple[SyncJobError | None, int]] = {}
    if db is not None:
        for phase_row in phase_rows:
            error_query = db.query(SyncJobError).filter(
                SyncJobError.job_id == job.id, SyncJobError.phase_key == phase_row.phase_key,
            )
            latest_errors[phase_row.phase_key] = (
                error_query.order_by(func.coalesce(SyncJobError.last_seen_at, SyncJobError.created_at).desc()).first(),
                error_query.with_entities(func.count(func.distinct(func.coalesce(
                    SyncJobError.external_id, SyncJobError.entity_name,
                )))).scalar() or 0,
            )
    canary = _image_canary_status(db) if db is not None else {"valid": False}
    phases = [
        {
            "id": row.id, "phase_key": row.phase_key, "order_index": row.order_index,
            "provider": row.provider, "required": row.required, "status": row.status,
            "attempt_count": row.attempt_count, "max_attempts": row.max_attempts,
            "processed_count": row.processed_count, "failed_count": row.failed_count,
            "current_entity": row.current_entity, "current_offset": row.current_offset,
            "checkpoint": row.checkpoint or {}, "next_retry_at": row.next_retry_at,
            "started_at": row.started_at, "updated_at": row.updated_at, "finished_at": row.finished_at,
            "error_category": row.error_category, "safe_error": row.safe_error,
            "canary_validated": bool(canary.get("valid")) if row.phase_key == "images" else False,
            "last_error": ({
                "occurred_at": (latest_errors[row.phase_key][0].last_seen_at or latest_errors[row.phase_key][0].created_at),
                "entity_name": latest_errors[row.phase_key][0].entity_name,
                "category": latest_errors[row.phase_key][0].error_category,
                "http_status": latest_errors[row.phase_key][0].http_status,
                "safe_message": latest_errors[row.phase_key][0].error_message,
                "affected_count": latest_errors[row.phase_key][1],
            } if latest_errors[row.phase_key][0] else ({
                "occurred_at": row.finished_at, "entity_name": None,
                "category": row.error_category, "http_status": None,
                "safe_message": "Detailed information was not recorded for this earlier failure.",
                "affected_count": row.failed_count,
            } if row.failed_count else None)),
        }
        for row in phase_rows
    ]
    maintenance_active = bool(db and db.query(MaintenanceHold.id).filter(
        MaintenanceHold.owner_job_id == job.id, MaintenanceHold.released_at.is_(None),
    ).first())
    return SyncJobResponse(
        job_id=job.id,
        job_type=job.job_type,
        status=status_map.get(job.status, job.status),
        operation_status=job.status,
        progress_current=job.progress_current or 0,
        progress_total=job.progress_total or 0,
        progress_percent=job.progress_percent or job.progress or 0,
        current_step=job.current_step,
        message=job.message,
        cancel_requested=bool(job.cancel_requested),
        started_at=job.started_at.isoformat() if job.started_at else None,
        finished_at=job.finished_at.isoformat() if job.finished_at else None,
        created_at=job.created_at.isoformat() if job.created_at else None,
        updated_at=job.updated_at.isoformat() if job.updated_at else None,
        error=job.error_message or job.error,
        summary=job.result_summary,
        checkpoint=job.checkpoint,
        current_entity_type=job.current_entity_type,
        current_offset=job.current_offset or 0,
        processed_count=job.processed_count or 0,
        failed_count=job.failed_count or 0,
        last_successful_external_id=job.last_successful_external_id,
        operation_label=job.operation_label, worker_id=job.worker_id,
        lease_expires_at=job.lease_expires_at.isoformat() if job.lease_expires_at else None,
        maintenance_requested=bool(job.maintenance_requested), maintenance_active=maintenance_active,
        continue_on_error=bool(job.continue_on_error), phases=phases,
    )


def _to_legacy_log(job) -> dict[str, Any]:
    mapped_status = _to_job_response(job).status
    return {
        "id": job.id,
        "api_name": job.job_type,
        "endpoint": f"/sync/{job.job_type}",
        "status": mapped_status,
        "source": job.job_type,
        "total_items": job.progress_total or 0,
        "processed_items": job.progress_current or 0,
        "error_count": 1 if mapped_status == "error" else 0,
        "message": job.message,
        "error_details": job.error_message or job.error,
        "started_at": (job.started_at or job.created_at).isoformat() if (job.started_at or job.created_at) else "",
        "completed_at": job.finished_at.isoformat() if job.finished_at else None,
    }


def _normalize_target(target: str) -> str:
    value = (target or "").strip().lower()
    aliases = {
        "all": "full",
        "full": "full",
        "creatures": "creatures",
        "creature": "creatures",
        "bosses": "bosses",
        "items": "items",
        "item": "items",
        "quests": "quests",
        "quest": "quests",
        "hunting_places": "hunt-zones",
        "hunting-places": "hunt-zones",
        "hunt-zones": "hunt-zones",
        "zones": "hunt-zones",
        "images": "images",
    }
    normalized = aliases.get(value)
    if not normalized:
        raise HTTPException(status_code=404, detail=f"Unknown sync target '{target}'")
    return normalized


def _start_job(
    db: Session,
    *,
    target: str,
    requester: User,
    force: bool,
    skip_images: bool,
    limit: int | None,
    batch_size: int,
    max_retries: int,
    external_timeout_seconds: int,
    maintenance_requested: bool = False,
    continue_on_error: bool = True,
    include_knowledge: bool = False,
    include_guild_rosters: bool = False,
    operation_label: str | None = None,
) -> dict[str, Any]:
    try:
        job = SyncService.create_job(
            db,
            job_type=target,
            requester=requester.username,
            requested_by_user_id=requester.id,
            job_limit=limit,
            batch_size=batch_size,
            max_retries=max_retries,
            external_timeout_seconds=external_timeout_seconds,
            force_refresh=force, skip_images=skip_images,
            include_knowledge=include_knowledge, include_guild_rosters=include_guild_rosters,
            continue_on_error=continue_on_error, maintenance_requested=maintenance_requested,
            operation_label=operation_label,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "status": "queued",
        "job_id": job.id,
        "target": target,
        "queued_at": datetime.now(UTC).isoformat(),
    }


@router.post("/full")
def start_full_sync(
    payload: FullSyncRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    if payload.confirmation != "SYNC EVERYTHING":
        raise HTTPException(status_code=422, detail="Explicit full synchronization confirmation is required")
    return _start_job(
        db,
        target="full",
        requester=current_user,
        force=payload.force_refresh, skip_images=not payload.include_images, limit=None,
        batch_size=payload.batch_size, max_retries=payload.max_retries,
        external_timeout_seconds=payload.external_timeout_seconds,
        maintenance_requested=payload.maintenance_enabled, continue_on_error=payload.continue_on_error,
        include_knowledge=payload.include_knowledge, include_guild_rosters=payload.include_guild_rosters,
        operation_label=payload.operation_label,
    )


@router.post("/creatures")
def start_creatures_sync(
    force: bool = Query(False),
    limit: Optional[int] = Query(None, ge=1),
    batch_size: int = Query(100, ge=10, le=500),
    max_retries: int = Query(3, ge=0, le=10),
    external_timeout_seconds: int = Query(15, ge=5, le=120),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    return _start_job(
        db,
        target="creatures",
        requester=current_user,
        force=force,
        skip_images=False,
        limit=limit,
        batch_size=batch_size,
        max_retries=max_retries,
        external_timeout_seconds=external_timeout_seconds,
    )


@router.post("/bosses")
def start_bosses_sync(
    force: bool = Query(False),
    limit: Optional[int] = Query(None, ge=1),
    batch_size: int = Query(100, ge=10, le=500),
    max_retries: int = Query(3, ge=0, le=10),
    external_timeout_seconds: int = Query(15, ge=5, le=120),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    return _start_job(
        db,
        target="bosses",
        requester=current_user,
        force=force,
        skip_images=False,
        limit=limit,
        batch_size=batch_size,
        max_retries=max_retries,
        external_timeout_seconds=external_timeout_seconds,
    )


@router.post("/items")
def start_items_sync(
    force: bool = Query(False),
    limit: Optional[int] = Query(None, ge=1),
    batch_size: int = Query(100, ge=10, le=500),
    max_retries: int = Query(3, ge=0, le=10),
    external_timeout_seconds: int = Query(15, ge=5, le=120),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    return _start_job(
        db,
        target="items",
        requester=current_user,
        force=force,
        skip_images=False,
        limit=limit,
        batch_size=batch_size,
        max_retries=max_retries,
        external_timeout_seconds=external_timeout_seconds,
    )


@router.post("/quests")
def start_quests_sync(
    force: bool = Query(False),
    limit: Optional[int] = Query(None, ge=1),
    batch_size: int = Query(100, ge=10, le=500),
    max_retries: int = Query(3, ge=0, le=10),
    external_timeout_seconds: int = Query(15, ge=5, le=120),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    return _start_job(
        db,
        target="quests",
        requester=current_user,
        force=force,
        skip_images=False,
        limit=limit,
        batch_size=batch_size,
        max_retries=max_retries,
        external_timeout_seconds=external_timeout_seconds,
    )


@router.post("/hunt-zones")
def start_hunt_zones_sync(
    force: bool = Query(False),
    limit: Optional[int] = Query(None, ge=1),
    batch_size: int = Query(100, ge=10, le=500),
    max_retries: int = Query(3, ge=0, le=10),
    external_timeout_seconds: int = Query(15, ge=5, le=120),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    return _start_job(
        db,
        target="hunt-zones",
        requester=current_user,
        force=force,
        skip_images=False,
        limit=limit,
        batch_size=batch_size,
        max_retries=max_retries,
        external_timeout_seconds=external_timeout_seconds,
    )


@router.post("/images")
def start_images_sync(
    force: bool = Query(False),
    limit: Optional[int] = Query(None, ge=1),
    batch_size: int = Query(100, ge=10, le=500),
    max_retries: int = Query(3, ge=0, le=10),
    external_timeout_seconds: int = Query(15, ge=5, le=120),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    return _start_job(
        db,
        target="images",
        requester=current_user,
        force=force,
        skip_images=False,
        limit=limit,
        batch_size=batch_size,
        max_retries=max_retries,
        external_timeout_seconds=external_timeout_seconds,
    )


@router.get("/jobs", response_model=list[SyncJobResponse])
def list_sync_jobs(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    _ = current_user
    jobs = SyncService.list_jobs(db, limit=limit)
    return [_to_job_response(job, db) for job in jobs]


@router.get("/logs")
def legacy_logs(
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    _ = current_user
    jobs = SyncService.list_jobs(db, limit=limit)
    return [_to_legacy_log(job) for job in jobs]


@router.get("/stats")
def legacy_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    _ = current_user
    return {
        "creatures": db.query(Creature).count(),
        "items": db.query(Loot).count(),
        "hunting_places": db.query(HuntZone).count(),
        "quests": db.query(Quest).count(),
        "sync_logs": db.query(SyncJob).count(),
    }


@router.post("/resolve-conflicts")
def legacy_resolve_conflicts(
    payload: dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    _ = (db, current_user, payload)
    # Conflicts are no-op with the centralized sync flow; keep endpoint for legacy UI.
    return {"status": "ok", "resolved": 0}


@router.get("/jobs/{job_id}", response_model=SyncJobResponse)
def get_sync_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    _ = current_user
    job = SyncService.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _to_job_response(job, db)


@router.post("/jobs/{job_id}/cancel")
def cancel_sync_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    job = SyncService.request_cancel(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    db.add(WorkspaceAudit(actor_id=current_user.id, workspace_type="admin", action="full_sync_cancel_requested", target_type="sync_job", target_id=job.id, assisted=False, safe_metadata={}))
    db.commit()
    return _to_job_response(job, db)


@router.post("/jobs/{job_id}/resume", response_model=SyncJobResponse)
def resume_sync_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    try:
        job = SyncService.resume_job(db, job_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    db.add(WorkspaceAudit(actor_id=current_user.id, workspace_type="admin", action="full_sync_resumed", target_type="sync_job", target_id=job.id, assisted=False, safe_metadata={}))
    db.commit()
    return _to_job_response(job, db)


@router.get("/jobs/{job_id}/phases/{phase_key}/errors")
def get_sync_phase_errors(
    job_id: str,
    phase_key: str,
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    category: str | None = Query(None, max_length=80),
    http_status: int | None = Query(None, ge=100, le=599),
    retryable: bool | None = Query(None),
    search: str | None = Query(None, min_length=1, max_length=100),
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin_user),
):
    job = SyncService.get_job(db, job_id)
    phase = db.query(SyncJobPhase).filter_by(job_id=job_id, phase_key=phase_key).one_or_none()
    if not job or not phase:
        raise HTTPException(404, "Job phase not found")

    query = db.query(SyncJobError).filter(
        SyncJobError.job_id == job_id, SyncJobError.phase_key == phase_key,
    )
    if category:
        query = query.filter(SyncJobError.error_category == category)
    if http_status is not None:
        query = query.filter(SyncJobError.http_status == http_status)
    if retryable is not None:
        query = query.filter(SyncJobError.retryable.is_(retryable))
    if search:
        escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        query = query.filter(or_(
            SyncJobError.entity_name.ilike(pattern, escape="\\"),
            SyncJobError.external_id.ilike(pattern, escape="\\"),
        ))

    total = query.count()
    affected = query.with_entities(func.count(func.distinct(func.coalesce(
        SyncJobError.external_id, SyncJobError.entity_name,
    )))).scalar() or 0
    latest = query.with_entities(func.max(func.coalesce(
        SyncJobError.last_seen_at, SyncJobError.created_at,
    ))).scalar()

    def grouped(column):
        return [
            {"value": value or "unknown", "count": count}
            for value, count in query.with_entities(column, func.sum(SyncJobError.occurrence_count))
            .group_by(column).order_by(func.sum(SyncJobError.occurrence_count).desc()).limit(10).all()
        ]

    rows = query.order_by(func.coalesce(
        SyncJobError.last_seen_at, SyncJobError.created_at,
    ).desc(), SyncJobError.id.desc()).offset(offset).limit(limit).all()
    return {
        "job_id": job_id, "phase": phase_key, "total_error_records": total,
        "total_affected_entities": affected, "latest_failure_timestamp": latest,
        "top_error_categories": grouped(SyncJobError.error_category),
        "top_http_statuses": grouped(SyncJobError.http_status),
        "top_provider_hosts": grouped(SyncJobError.provider),
        "detail_recorded": bool(total),
        "historical_message": None if total else (
            "Detailed information was not recorded for this earlier failure." if phase.failed_count else None
        ),
        "rows": [{
            "occurred_at": row.first_occurred_at or row.created_at,
            "last_seen_at": row.last_seen_at or row.created_at,
            "occurrence_count": row.occurrence_count or 1,
            "provider": row.provider, "phase": row.phase_key,
            "entity_name": row.entity_name, "external_id": row.external_id,
            "checkpoint_offset": row.checkpoint_offset, "attempt": row.attempt,
            "error_category": row.error_category or "item_failure",
            "safe_message": row.error_message,
            "http_status": row.http_status, "retryable": row.retryable,
            "url": row.safe_url,
        } for row in rows],
    }


@router.post("/images/canary")
async def run_image_canary(
    request: ImageCanaryRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    result = await SyncService.sync_images(
        db, limit=request.limit, representative=True, force_refetch=True,
    )
    passed = result["total"] >= 20 and result["errors"] == 0 and result["succeeded"] == result["total"]
    checked_at = datetime.now(UTC)
    stored = {
        "checked_at": checked_at.isoformat(), "passed": passed,
        "total": result["total"], "succeeded": result["succeeded"], "failed": result["errors"],
    }
    _set_setting(db, "sync_images_canary", json.dumps(stored, separators=(",", ":")), "Latest production-safe image downloader canary")
    db.add(WorkspaceAudit(
        actor_id=admin.id, workspace_type="admin", action="sync_images_canary",
        target_type="sync_images", target_id=checked_at.isoformat(), assisted=False,
        safe_metadata={**stored, "failure_categories": result["failure_categories"]},
    ))
    db.commit()
    return {**stored, "failure_categories": result["failure_categories"], "samples": result["samples"]}


@router.post("/jobs/{job_id}/phases/{phase_key}/resume", response_model=SyncJobResponse)
def resume_sync_phase(job_id: str, phase_key: str, db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    job = SyncService.get_job(db, job_id)
    phase = db.query(SyncJobPhase).filter_by(job_id=job_id, phase_key=phase_key).one_or_none()
    if not job or not phase:
        raise HTTPException(404, "Job phase not found")
    if job.status != "completed_with_errors":
        raise HTTPException(409, "A single phase can be resumed only from a partially completed operation")
    if phase.status not in {"failed", "cancelled", "skipped"}:
        raise HTTPException(409, "Only incomplete phases can be resumed")
    failure_ratio = (phase.failed_count / phase.processed_count) if phase.processed_count else 0
    if phase_key == "images" and failure_ratio > 0.8 and not _image_canary_status(db).get("valid"):
        raise HTTPException(409, "Image retry requires a successful recent production canary")
    phase.status = "pending"; phase.finished_at = None; phase.error_category = None; phase.safe_error = None
    if phase_key == "images":
        # A targeted image retry is a fresh measurement over the image queue;
        # durable error rows remain available, but phase counters must not make
        # a successful retry inherit the prior 95% failure ratio.
        phase.processed_count = 0; phase.failed_count = 0; phase.current_offset = 0
        phase.current_entity = None; phase.checkpoint = {}
    job.status = "pending"; job.finished_at = None; job.cancel_requested = False; job.message = f"Phase resume requested: {phase_key}"
    if job.maintenance_requested:
        from app.services.maintenance_mode_service import MaintenanceModeService
        MaintenanceModeService.acquire_sync(db, job=job, actor_id=admin.id, reason=job.operation_label or "Synchronization phase resumed")
    db.add(WorkspaceAudit(actor_id=admin.id, workspace_type="admin", action="full_sync_phase_resumed", target_type="sync_job_phase", target_id=str(phase.id), assisted=False, safe_metadata={"phase": phase_key}))
    db.commit()
    return _to_job_response(job, db)


@router.post("/jobs/{job_id}/phases/{phase_key}/skip", response_model=SyncJobResponse)
def skip_sync_phase(job_id: str, phase_key: str, reason: str = Query(min_length=5, max_length=500), db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    job = SyncService.get_job(db, job_id)
    phase = db.query(SyncJobPhase).filter_by(job_id=job_id, phase_key=phase_key).one_or_none()
    if not job or not phase:
        raise HTTPException(404, "Job phase not found")
    if phase.required or phase.status not in {"failed", "pending", "retrying"}:
        raise HTTPException(409, "This phase cannot be skipped")
    phase.status = "skipped"; phase.finished_at = datetime.now(UTC); phase.safe_error = reason
    db.add(WorkspaceAudit(actor_id=admin.id, workspace_type="admin", action="full_sync_phase_skipped", target_type="sync_job_phase", target_id=str(phase.id), assisted=False, safe_metadata={"phase": phase_key, "reason": reason}))
    db.commit()
    return _to_job_response(job, db)


@router.get("/workers")
def sync_workers(db: Session = Depends(get_db), _admin: User = Depends(get_current_admin_user)):
    return [{"worker_id": row.worker_id, "state": row.state, "last_seen_at": row.last_seen_at, "current_job_id": row.current_job_id, "version": row.version, "enabled": row.enabled} for row in db.query(SyncWorkerHeartbeat).order_by(SyncWorkerHeartbeat.worker_id).all()]


@router.get("/settings", response_model=SyncRuntimeSettings)
def get_sync_runtime_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    _ = current_user
    SyncService.ensure_default_settings(db)
    external_fallback = _get_setting(db, "external_auto_fallback_enabled", "0") == "1"
    image_autofetch = _get_setting(db, "auto_fetch_missing_images_enabled", "0") == "1"
    cache_only_reads = _get_setting(db, "bestiary_cache_only_reads", "1") == "1"
    bestiary_page_size = int(_get_setting(db, "bestiary_search_page_size", "20") or "20")
    full_sync_cooldown = int(_get_setting(db, "sync_full_cooldown_minutes", "30") or "30")
    return SyncRuntimeSettings(
        bestiary_cache_only_reads=cache_only_reads,
        bestiary_allow_external_detail_fallback=external_fallback,
        bestiary_search_page_size=bestiary_page_size,
        sync_cooldown_minutes=full_sync_cooldown,
        external_auto_fallback_enabled=external_fallback,
        auto_fetch_missing_images_enabled=image_autofetch,
        scheduled_sync_enabled=_get_setting(db, "scheduled_sync_enabled", "0") == "1",
        sync_request_timeout_seconds=int(_get_setting(db, "sync_request_timeout_seconds", "30") or "30"),
        sync_retry_count=int(_get_setting(db, "sync_retry_count", "2") or "2"),
        sync_notify_email_enabled=_get_setting(db, "sync_notify_email_enabled", "0") == "1",
    )


@router.put("/settings", response_model=SyncRuntimeSettings)
def update_sync_runtime_settings(
    payload: SyncRuntimeSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    _ = current_user
    SyncService.ensure_default_settings(db)

    if payload.bestiary_cache_only_reads is not None:
        _set_setting(db, "bestiary_cache_only_reads", "1" if payload.bestiary_cache_only_reads else "0")
    if payload.bestiary_allow_external_detail_fallback is not None:
        _set_setting(
            db,
            "external_auto_fallback_enabled",
            "1" if payload.bestiary_allow_external_detail_fallback else "0",
        )
    if payload.bestiary_search_page_size is not None:
        _set_setting(db, "bestiary_search_page_size", str(max(5, min(100, payload.bestiary_search_page_size))))
    if payload.sync_cooldown_minutes is not None:
        _set_setting(db, "sync_full_cooldown_minutes", str(max(1, min(1440, payload.sync_cooldown_minutes))))

    if payload.external_auto_fallback_enabled is not None:
        _set_setting(db, "external_auto_fallback_enabled", "1" if payload.external_auto_fallback_enabled else "0")
    if payload.auto_fetch_missing_images_enabled is not None:
        _set_setting(db, "auto_fetch_missing_images_enabled", "1" if payload.auto_fetch_missing_images_enabled else "0")
    if payload.scheduled_sync_enabled is not None:
        _set_setting(db, "scheduled_sync_enabled", "1" if payload.scheduled_sync_enabled else "0")
    if payload.sync_request_timeout_seconds is not None:
        _set_setting(db, "sync_request_timeout_seconds", str(max(5, min(600, payload.sync_request_timeout_seconds))))
    if payload.sync_retry_count is not None:
        _set_setting(db, "sync_retry_count", str(max(0, min(10, payload.sync_retry_count))))
    if payload.sync_notify_email_enabled is not None:
        _set_setting(db, "sync_notify_email_enabled", "1" if payload.sync_notify_email_enabled else "0")

    # Legacy setting aliases for backward compatibility in public endpoints.
    _set_setting(
        db,
        "bestiary_allow_external_detail_fallback",
        _get_setting(db, "external_auto_fallback_enabled", "0"),
        "Legacy alias of external_auto_fallback_enabled",
    )
    _set_setting(
        db,
        "sync_cooldown_minutes",
        _get_setting(db, "sync_full_cooldown_minutes", "30"),
        "Legacy alias of sync_full_cooldown_minutes",
    )

    db.commit()
    return get_sync_runtime_settings(db=db, current_user=current_user)


# Legacy aliases kept for existing admin panel routes.
@router.post("/sync/{target}")
def legacy_sync_target(
    target: str,
    force: bool = Query(False),
    limit: Optional[int] = Query(None, ge=1),
    batch_size: int = Query(100, ge=10, le=500),
    max_retries: int = Query(3, ge=0, le=10),
    external_timeout_seconds: int = Query(15, ge=5, le=120),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    normalized = _normalize_target(target)
    return _start_job(
        db,
        target=normalized,
        requester=current_user,
        force=force,
        skip_images=False,
        limit=limit,
        batch_size=batch_size,
        max_retries=max_retries,
        external_timeout_seconds=external_timeout_seconds,
    )


@router.post("/manual/{api_name}")
def legacy_manual(
    api_name: str,
    force: bool = Query(False),
    limit: Optional[int] = Query(None, ge=1),
    batch_size: int = Query(100, ge=10, le=500),
    max_retries: int = Query(3, ge=0, le=10),
    external_timeout_seconds: int = Query(15, ge=5, le=120),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    normalized = _normalize_target(api_name)
    if normalized == "full":
        normalized = "creatures"
    return _start_job(
        db,
        target=normalized,
        requester=current_user,
        force=force,
        skip_images=False,
        limit=limit,
        batch_size=batch_size,
        max_retries=max_retries,
        external_timeout_seconds=external_timeout_seconds,
    )


@router.post("/bestiary/start")
def legacy_bestiary_start(
    source: str = Query("creatures"),
    force: bool = Query(False),
    limit: Optional[int] = Query(None, ge=1),
    batch_size: int = Query(100, ge=10, le=500),
    max_retries: int = Query(3, ge=0, le=10),
    external_timeout_seconds: int = Query(15, ge=5, le=120),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    normalized = _normalize_target(source)
    return _start_job(
        db,
        target=normalized,
        requester=current_user,
        force=force,
        skip_images=False,
        limit=limit,
        batch_size=batch_size,
        max_retries=max_retries,
        external_timeout_seconds=external_timeout_seconds,
    )


@router.get("/status")
def legacy_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    _ = current_user
    jobs = SyncService.list_jobs(db, limit=50)
    active = [_to_job_response(job) for job in jobs if job.status in {"pending", "running"}]
    failed = [_to_job_response(job) for job in jobs if job.status == "failed"]
    completed = [_to_job_response(job) for job in jobs if job.status == "completed"]
    cancelled = [_to_job_response(job) for job in jobs if job.status == "cancelled"]
    return {
        "running_sources": sorted(list({job.job_type for job in jobs if job.status == "running"})),
        "active_jobs": active,
        "failed_jobs": failed,
        "completed_jobs": completed,
        "cancelled_jobs": cancelled,
    }
