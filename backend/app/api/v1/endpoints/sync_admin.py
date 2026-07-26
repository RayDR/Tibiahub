"""Admin sync endpoints backed by centralized SyncService."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.v1.endpoints.auth import get_current_admin_user
from app.db.database import get_db
from app.models.creature import Creature
from app.models.external_data import SyncJob
from app.models.hunt_zone import HuntZone
from app.models.loot import Loot
from app.models.settings import SystemSettings as SettingsModel
from app.models.quest import Quest
from app.models.user import User
from app.services.sync_service import SyncService

router = APIRouter()


class SyncJobResponse(BaseModel):
    job_id: str
    job_type: str
    status: str
    progress_current: int
    progress_total: int
    progress_percent: int
    current_step: Optional[str] = None
    message: Optional[str] = None
    cancel_requested: bool
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    created_at: Optional[str] = None
    error: Optional[str] = None
    summary: Optional[dict[str, Any]] = None
    checkpoint: Optional[dict[str, Any]] = None
    current_entity_type: Optional[str] = None
    current_offset: int = 0
    processed_count: int = 0
    failed_count: int = 0
    last_successful_external_id: Optional[str] = None


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


def _to_job_response(job) -> SyncJobResponse:
    # Keep legacy status names expected by frontend polling logic.
    status_map = {
        "completed": "success",
        "failed": "error",
    }
    return SyncJobResponse(
        job_id=job.id,
        job_type=job.job_type,
        status=status_map.get(job.status, job.status),
        progress_current=job.progress_current or 0,
        progress_total=job.progress_total or 0,
        progress_percent=job.progress_percent or job.progress or 0,
        current_step=job.current_step,
        message=job.message,
        cancel_requested=bool(job.cancel_requested),
        started_at=job.started_at.isoformat() if job.started_at else None,
        finished_at=job.finished_at.isoformat() if job.finished_at else None,
        created_at=job.created_at.isoformat() if job.created_at else None,
        error=job.error_message or job.error,
        summary=job.result_summary,
        checkpoint=job.checkpoint,
        current_entity_type=job.current_entity_type,
        current_offset=job.current_offset or 0,
        processed_count=job.processed_count or 0,
        failed_count=job.failed_count or 0,
        last_successful_external_id=job.last_successful_external_id,
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
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    SyncService.queue_job(job.id, force=force, skip_images=skip_images, limit=limit)
    return {
        "status": "queued",
        "job_id": job.id,
        "target": target,
        "queued_at": datetime.now(UTC).isoformat(),
    }


@router.post("/full")
def start_full_sync(
    force: bool = Query(False),
    skip_images: bool = Query(False),
    limit: Optional[int] = Query(None, ge=1),
    batch_size: int = Query(100, ge=10, le=500),
    max_retries: int = Query(3, ge=0, le=10),
    external_timeout_seconds: int = Query(15, ge=5, le=120),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    return _start_job(
        db,
        target="full",
        requester=current_user,
        force=force,
        skip_images=skip_images,
        limit=limit,
        batch_size=batch_size,
        max_retries=max_retries,
        external_timeout_seconds=external_timeout_seconds,
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
    return [_to_job_response(job) for job in jobs]


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
    return _to_job_response(job)


@router.post("/jobs/{job_id}/cancel")
def cancel_sync_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    _ = current_user
    job = SyncService.request_cancel(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _to_job_response(job)


@router.post("/jobs/{job_id}/resume", response_model=SyncJobResponse)
def resume_sync_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    _ = current_user
    try:
        job = SyncService.resume_job(db, job_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _to_job_response(job)


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
