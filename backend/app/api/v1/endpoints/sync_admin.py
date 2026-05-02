"""Admin endpoints for data synchronization and local metadata curation."""
from typing import Any, List, Optional
import asyncio
from threading import Lock
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db.database import SessionLocal, get_db
from app.models.user import User
from app.api.v1.endpoints.auth import get_current_admin_user
from app.services.external_sync_service import ExternalSyncService
from app.models.external_data import APISync, Item, HuntingPlace, TibiaWikiQuest, SyncJob
from app.models.creature import Creature
from app.services.entity_metadata_service import EntityMetadataService
from datetime import datetime
from app.models.settings import SystemSettings as SettingsModel

router = APIRouter()
_SYNC_JOB_STORE: dict[str, dict[str, Any]] = {}
_SYNC_LOCK = Lock()
_RUNNING_SOURCES: set[str] = set()
SYNC_STEP_TIMEOUT_SECONDS = 60


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

class SyncResponse(BaseModel):
    """Response from sync operations"""
    api: str
    status: str
    source: Optional[str] = None
    created: int = 0
    updated: int = 0
    errors: int = 0
    total: int = 0
    error: Optional[str] = None
    sync_id: int
    message: Optional[str] = None
    conflicts: Optional[List[dict[str, Any]]] = None

class SyncLogResponse(BaseModel):
    """Sync log entry"""
    id: int
    api_name: str
    endpoint: str
    status: str
    source: Optional[str]
    total_items: Optional[int]
    processed_items: int
    error_count: int
    message: Optional[str]
    error_details: Optional[str]
    started_at: datetime
    completed_at: Optional[datetime]

class SyncStats(BaseModel):
    """Sync statistics"""
    creatures: int
    items: int
    hunting_places: int
    quests: int
    sync_logs: int

class DataComparison(BaseModel):
    """Comparison between old and new data"""
    field: str
    old_value: Any
    new_value: Any
    different: bool

class ConflictItem(BaseModel):
    """Item with conflicts"""
    api_name: str
    item_name: str
    conflicts: List[DataComparison]
    action: str = "pending"

class ConflictResolution(BaseModel):
    """Resolution for conflicts"""
    conflicts: List[ConflictItem]
    action: str  # 'skip_all' or 'overwrite_all'


class MetadataFlagRequest(BaseModel):
    entity_type: str
    entity_key: str
    display_name: str
    entity_id: Optional[int] = None
    is_featured: Optional[bool] = None
    is_pinned: Optional[bool] = None
    is_favorite: Optional[bool] = None
    notes: Optional[str] = None


class SyncRuntimeSettings(BaseModel):
    bestiary_cache_only_reads: bool
    bestiary_allow_external_detail_fallback: bool
    bestiary_search_page_size: int
    sync_cooldown_minutes: int


class SyncRuntimeSettingsUpdate(BaseModel):
    bestiary_cache_only_reads: Optional[bool] = None
    bestiary_allow_external_detail_fallback: Optional[bool] = None
    bestiary_search_page_size: Optional[int] = None
    sync_cooldown_minutes: Optional[int] = None


def _normalize_sync_source(api_name: str) -> str:
    api = (api_name or "").strip().lower()
    if api in {"creatures", "creature"}:
        return "creatures"
    if api in {"items", "item"}:
        return "items"
    if api in {"hunting-places", "hunting_places", "zones", "hunt-zones"}:
        return "hunting-places"
    if api in {"quests", "quest"}:
        return "quests"
    if api in {"all", "bestiary"}:
        return "all"
    raise HTTPException(status_code=404, detail=f"Unknown sync api '{api_name}'")


def _set_job(job_id: str, **kwargs: Any) -> None:
    with _SYNC_LOCK:
        entry = _SYNC_JOB_STORE.get(job_id, {})
        entry.update(kwargs)
        _SYNC_JOB_STORE[job_id] = entry


def _syncjob_set_status(db: Session, job_id: str, **kwargs: Any) -> None:
    row = db.query(SyncJob).filter(SyncJob.id == job_id).first()
    if not row:
        return
    for key, value in kwargs.items():
        setattr(row, key, value)
    db.add(row)
    db.commit()


def _is_cancel_requested(db: Session, job_id: str) -> bool:
    row = db.query(SyncJob).filter(SyncJob.id == job_id).first()
    return bool(row and row.cancel_requested)


class SyncCancelledError(Exception):
    pass


def _get_running_sources_for_target(target: str) -> list[str]:
    if target == "all":
        return [source for source in ["creatures", "items", "hunting-places", "quests"] if source in _RUNNING_SOURCES]
    return [target] if target in _RUNNING_SOURCES else []


def _execute_sync_job(job_id: str, target: str, mode: str) -> None:
    _set_job(job_id, status="running", started_at=datetime.utcnow().isoformat(), progress=5)
    db = SessionLocal()
    try:
        _syncjob_set_status(db, job_id, status="running", started_at=datetime.utcnow(), progress=5)
        if _is_cancel_requested(db, job_id):
            raise SyncCancelledError("Cancellation requested before execution")

        results: dict[str, Any] = {}
        if target in {"creatures", "all"}:
            results["creatures"] = asyncio.run(
                asyncio.wait_for(ExternalSyncService.sync_creatures(db, mode=mode), timeout=SYNC_STEP_TIMEOUT_SECONDS)
            )
            _set_job(job_id, progress=30)
            _syncjob_set_status(db, job_id, progress=30)
            if _is_cancel_requested(db, job_id):
                raise SyncCancelledError("Cancellation requested")
        if target in {"items", "all"}:
            results["items"] = asyncio.run(
                asyncio.wait_for(ExternalSyncService.sync_items(db), timeout=SYNC_STEP_TIMEOUT_SECONDS)
            )
            _set_job(job_id, progress=55)
            _syncjob_set_status(db, job_id, progress=55)
            if _is_cancel_requested(db, job_id):
                raise SyncCancelledError("Cancellation requested")
        if target in {"hunting-places", "all"}:
            results["hunting_places"] = asyncio.run(
                asyncio.wait_for(ExternalSyncService.sync_hunting_places(db), timeout=SYNC_STEP_TIMEOUT_SECONDS)
            )
            _set_job(job_id, progress=80)
            _syncjob_set_status(db, job_id, progress=80)
            if _is_cancel_requested(db, job_id):
                raise SyncCancelledError("Cancellation requested")
        if target in {"quests", "all"}:
            results["quests"] = asyncio.run(
                asyncio.wait_for(ExternalSyncService.sync_quests(db), timeout=SYNC_STEP_TIMEOUT_SECONDS)
            )

        if _is_cancel_requested(db, job_id):
            raise SyncCancelledError("Cancellation requested")

        _set_job(job_id, status="completed", finished_at=datetime.utcnow().isoformat(), results=results, progress=100)
        _syncjob_set_status(db, job_id, status="completed", finished_at=datetime.utcnow(), progress=100, error=None)
    except SyncCancelledError as exc:
        _set_job(job_id, status="cancelled", finished_at=datetime.utcnow().isoformat(), error=str(exc))
        _syncjob_set_status(db, job_id, status="cancelled", finished_at=datetime.utcnow(), error=str(exc))
    except asyncio.TimeoutError:
        message = f"Sync step timeout after {SYNC_STEP_TIMEOUT_SECONDS}s"
        _set_job(job_id, status="failed", finished_at=datetime.utcnow().isoformat(), error=message)
        _syncjob_set_status(db, job_id, status="failed", finished_at=datetime.utcnow(), error=message)
    except Exception as exc:
        _set_job(job_id, status="failed", finished_at=datetime.utcnow().isoformat(), error=str(exc))
        _syncjob_set_status(db, job_id, status="failed", finished_at=datetime.utcnow(), error=str(exc))
    finally:
        with _SYNC_LOCK:
            if target == "all":
                _RUNNING_SOURCES.discard("creatures")
                _RUNNING_SOURCES.discard("items")
                _RUNNING_SOURCES.discard("hunting-places")
                _RUNNING_SOURCES.discard("quests")
            else:
                _RUNNING_SOURCES.discard(target)
        db.close()


def _start_sync_job(background_tasks: BackgroundTasks, target: str, mode: str) -> dict[str, Any]:
    with _SYNC_LOCK:
        already_running = _get_running_sources_for_target(target)
        if already_running:
            raise HTTPException(status_code=409, detail=f"Sync already running for: {', '.join(already_running)}")

        if target == "all":
            _RUNNING_SOURCES.update({"creatures", "items", "hunting-places", "quests"})
        else:
            _RUNNING_SOURCES.add(target)

        job_id = uuid4().hex
        _SYNC_JOB_STORE[job_id] = {
            "job_id": job_id,
            "target": target,
            "mode": mode,
            "status": "pending",
            "progress": 0,
            "created_at": datetime.utcnow().isoformat(),
        }

        db = SessionLocal()
        try:
            db.add(
                SyncJob(
                    id=job_id,
                    job_type=target,
                    status="pending",
                    progress=0,
                    cancel_requested=False,
                )
            )
            db.commit()
        finally:
            db.close()

    background_tasks.add_task(_execute_sync_job, job_id, target, mode)
    return _SYNC_JOB_STORE[job_id]

# ============ SYNC ENDPOINTS ============

@router.post("/sync/creatures", response_model=SyncResponse)
async def sync_creatures(
    mode: str = Query("compare", description="Sync mode: 'auto' or 'compare'"),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    Sync creatures from TibiaWiki API
    Runs in background, returns sync ID to track progress
    Mode: 'auto' (overwrite without asking) or 'compare' (check conflicts first)
    """
    _ = (current_user, db)
    if background_tasks is None:
        raise HTTPException(status_code=500, detail="Background runner unavailable")
    if mode == "compare":
        conflicts = await ExternalSyncService.check_creature_conflicts(db)
        if conflicts:
            return SyncResponse(api="creatures", status="conflicts_found", sync_id=0, message=f"Found {len(conflicts)} conflicts. Resolve them first.", conflicts=conflicts)
    job = _start_sync_job(background_tasks, target="creatures", mode=mode)
    return SyncResponse(api="creatures", status="queued", sync_id=0, message=f"Sync started. job_id={job['job_id']}")

@router.post("/sync/items", response_model=SyncResponse)
async def sync_items(
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    Sync items from TibiaWiki API
    Runs in background
    """
    _ = (current_user, db)
    if background_tasks is None:
        raise HTTPException(status_code=500, detail="Background runner unavailable")
    job = _start_sync_job(background_tasks, target="items", mode="auto")
    return SyncResponse(api="items", status="queued", sync_id=0, message=f"Sync started. job_id={job['job_id']}")

@router.post("/sync/hunting-places", response_model=SyncResponse)
async def sync_hunting_places(
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    Sync hunting places from TibiaWiki API
    Runs in background
    """
    _ = (current_user, db)
    if background_tasks is None:
        raise HTTPException(status_code=500, detail="Background runner unavailable")
    job = _start_sync_job(background_tasks, target="hunting-places", mode="auto")
    return SyncResponse(api="hunting_places", status="queued", sync_id=0, message=f"Sync started. job_id={job['job_id']}")

@router.post("/sync/quests", response_model=SyncResponse)
async def sync_quests(
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    Sync quests from TibiaWiki API
    Runs in background
    """
    _ = (current_user, db)
    if background_tasks is None:
        raise HTTPException(status_code=500, detail="Background runner unavailable")
    job = _start_sync_job(background_tasks, target="quests", mode="auto")
    return SyncResponse(api="quests", status="queued", sync_id=0, message=f"Sync started. job_id={job['job_id']}")

@router.post("/sync/all", response_model=dict)
async def sync_all(
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    Sync all external APIs in background
    Returns status for each sync
    """
    _ = (current_user, db)
    if background_tasks is None:
        raise HTTPException(status_code=500, detail="Background runner unavailable")
    job = _start_sync_job(background_tasks, target="all", mode="auto")
    return {
        "status": "queued",
        "apis": ["creatures", "items", "hunting_places", "quests"],
        "job_id": job["job_id"],
    }


@router.get("/settings", response_model=SyncRuntimeSettings)
def get_sync_runtime_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    _ = current_user
    return SyncRuntimeSettings(
        bestiary_cache_only_reads=_get_setting(db, "bestiary_cache_only_reads", "1") == "1",
        bestiary_allow_external_detail_fallback=_get_setting(db, "bestiary_allow_external_detail_fallback", "0") == "1",
        bestiary_search_page_size=int(_get_setting(db, "bestiary_search_page_size", "20") or "20"),
        sync_cooldown_minutes=int(_get_setting(db, "sync_cooldown_minutes", "30") or "30"),
    )


@router.put("/settings", response_model=SyncRuntimeSettings)
def update_sync_runtime_settings(
    payload: SyncRuntimeSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    _ = current_user
    if payload.bestiary_cache_only_reads is not None:
        _set_setting(
            db,
            "bestiary_cache_only_reads",
            "1" if payload.bestiary_cache_only_reads else "0",
            "When enabled, creatures GET endpoints use local DB cache only",
        )
    if payload.bestiary_allow_external_detail_fallback is not None:
        _set_setting(
            db,
            "bestiary_allow_external_detail_fallback",
            "1" if payload.bestiary_allow_external_detail_fallback else "0",
            "Allow on-demand external fallback for missing creature details",
        )
    if payload.bestiary_search_page_size is not None:
        page_size = max(10, min(100, payload.bestiary_search_page_size))
        _set_setting(
            db,
            "bestiary_search_page_size",
            str(page_size),
            "Default bestiary page size used by frontend/admin",
        )
    if payload.sync_cooldown_minutes is not None:
        cooldown = max(1, min(1440, payload.sync_cooldown_minutes))
        _set_setting(
            db,
            "sync_cooldown_minutes",
            str(cooldown),
            "Minimum interval in minutes between manual sync runs",
        )
    db.commit()
    return get_sync_runtime_settings(db=db, current_user=current_user)


@router.post("/manual/{api_name}", response_model=SyncResponse)
async def run_manual_sync(
    api_name: str,
    mode: str = Query("compare", description="Sync mode: 'auto' or 'compare'"),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    _ = (current_user, db)
    if background_tasks is None:
        raise HTTPException(status_code=500, detail="Background runner unavailable")

    target = _normalize_sync_source(api_name)
    if target == "all":
        target = "creatures"

    if target == "creatures" and mode == "compare":
        conflicts = await ExternalSyncService.check_creature_conflicts(db)
        if conflicts:
            return SyncResponse(api="creatures", status="conflicts_found", sync_id=0, message=f"Found {len(conflicts)} conflicts. Resolve them first.", conflicts=conflicts)

    job = _start_sync_job(background_tasks, target=target, mode=mode)
    return SyncResponse(
        api=target,
        status="queued",
        source=None,
        created=0,
        updated=0,
        errors=0,
        total=0,
        sync_id=0,
        message=f"Sync started. job_id={job['job_id']}",
    )


@router.post("/bestiary/start")
def start_bestiary_sync(
    source: str = Query("creatures", description="creatures|items|hunting-places|quests|all"),
    mode: str = Query("auto", description="Sync mode: auto|compare"),
    background_tasks: BackgroundTasks = None,
    current_user: User = Depends(get_current_admin_user),
):
    _ = current_user
    if background_tasks is None:
        raise HTTPException(status_code=500, detail="Background runner unavailable")
    target = _normalize_sync_source(source)
    return _start_sync_job(background_tasks, target=target, mode=mode)


@router.get("/jobs/{job_id}")
def get_sync_job(job_id: str, current_user: User = Depends(get_current_admin_user)):
    _ = current_user
    job = _SYNC_JOB_STORE.get(job_id)
    if job:
        return job

    db = SessionLocal()
    try:
        row = db.query(SyncJob).filter(SyncJob.id == job_id).first()
        if not row:
            raise HTTPException(status_code=404, detail="Job not found")
        return {
            "job_id": row.id,
            "target": row.job_type,
            "status": row.status,
            "progress": row.progress,
            "error": row.error,
            "cancel_requested": row.cancel_requested,
            "started_at": row.started_at.isoformat() if row.started_at else None,
            "finished_at": row.finished_at.isoformat() if row.finished_at else None,
        }
    finally:
        db.close()


@router.post("/jobs/{job_id}/cancel")
def cancel_sync_job(job_id: str, current_user: User = Depends(get_current_admin_user)):
    _ = current_user
    with _SYNC_LOCK:
        entry = _SYNC_JOB_STORE.get(job_id)
        if entry:
            if entry.get("status") in {"completed", "failed", "cancelled"}:
                return {"job_id": job_id, "status": entry.get("status"), "message": "Job already finished"}
            entry["cancel_requested"] = True
            _SYNC_JOB_STORE[job_id] = entry

    db = SessionLocal()
    try:
        row = db.query(SyncJob).filter(SyncJob.id == job_id).first()
        if not row:
            raise HTTPException(status_code=404, detail="Job not found")
        if row.status in {"completed", "failed", "cancelled"}:
            return {"job_id": job_id, "status": row.status, "message": "Job already finished"}
        row.cancel_requested = True
        if row.status == "pending":
            row.status = "cancelled"
            row.finished_at = datetime.utcnow()
        db.add(row)
        db.commit()
        return {
            "job_id": row.id,
            "status": row.status,
            "cancel_requested": row.cancel_requested,
        }
    finally:
        db.close()


    


@router.get("/status")
def get_sync_status(current_user: User = Depends(get_current_admin_user)):
    _ = current_user
    with _SYNC_LOCK:
        running_sources = sorted(_RUNNING_SOURCES)
        queued_or_running = [
            job for job in _SYNC_JOB_STORE.values()
            if job.get("status") in {"pending", "running"}
        ]
        failed_jobs = [job for job in _SYNC_JOB_STORE.values() if job.get("status") == "failed"]
        cancelled_jobs = [job for job in _SYNC_JOB_STORE.values() if job.get("status") == "cancelled"]
        completed_jobs = [job for job in _SYNC_JOB_STORE.values() if job.get("status") == "completed"]
    return {
        "running_sources": running_sources,
        "active_jobs": queued_or_running,
        "failed_jobs": failed_jobs,
        "cancelled_jobs": cancelled_jobs,
        "completed_jobs": completed_jobs,
    }

# ============ LOGS ENDPOINTS ============

@router.get("/sync/logs", response_model=List[SyncLogResponse])
def get_sync_logs(
    api_name: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    Get synchronization logs
    Filter by API name if provided
    """
    logs = ExternalSyncService.get_sync_logs(db, api_name=api_name, limit=limit)
    
    return [
        SyncLogResponse(
            id=log.id,
            api_name=log.api_name,
            endpoint=log.endpoint,
            status=log.status,
            source=log.source,
            total_items=log.total_items,
            processed_items=log.processed_items,
            error_count=log.error_count,
            message=log.message,
            error_details=log.error_details,
            started_at=log.started_at,
            completed_at=log.completed_at
        )
        for log in logs
    ]

@router.get("/sync/logs/{sync_id}", response_model=SyncLogResponse)
def get_sync_log(
    sync_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    Get specific sync log details
    """
    log = db.query(APISync).filter(APISync.id == sync_id).first()
    
    if not log:
        raise HTTPException(status_code=404, detail="Sync log not found")
    
    return SyncLogResponse(
        id=log.id,
        api_name=log.api_name,
        endpoint=log.endpoint,
        status=log.status,
        source=log.source,
        total_items=log.total_items,
        processed_items=log.processed_items,
        error_count=log.error_count,
        message=log.message,
        error_details=log.error_details,
        started_at=log.started_at,
        completed_at=log.completed_at
    )

@router.get("/sync/logs/{sync_id}/progress")
def get_sync_progress(
    sync_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    Get current progress of a sync operation
    """
    log = db.query(APISync).filter(APISync.id == sync_id).first()
    
    if not log:
        raise HTTPException(status_code=404, detail="Sync log not found")
    
    percentage = 0
    if log.total_items and log.total_items > 0:
        percentage = int((log.processed_items / log.total_items) * 100)
    
    return {
        "sync_id": log.id,
        "api": log.api_name,
        "status": log.status,
        "total": log.total_items,
        "processed": log.processed_items,
        "percentage": percentage,
        "errors": log.error_count,
        "message": log.message
    }

# ============ STATISTICS ENDPOINTS ============

@router.get("/sync/stats", response_model=SyncStats)
def get_sync_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    Get statistics about synced data
    """
    stats = ExternalSyncService.get_sync_stats(db)
    return SyncStats(**stats)

@router.get("/data/creatures", response_model=dict)
def get_creatures_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Get creature statistics"""
    total = db.query(Creature).count()
    by_level = db.query(Creature.level).filter(Creature.level != None).all()
    
    return {
        "total": total,
        "levels": [level[0] for level in by_level]
    }

@router.get("/data/items", response_model=dict)
def get_items_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Get item statistics"""
    total = db.query(Item).count()
    by_type = {}
    
    items = db.query(Item.type).all()
    for item_type in items:
        if item_type[0]:
            by_type[item_type[0]] = by_type.get(item_type[0], 0) + 1
    
    return {
        "total": total,
        "by_type": by_type
    }

# ============ CONFLICT RESOLUTION ENDPOINTS ============

@router.post("/resolve-conflicts")
async def resolve_conflicts(
    resolution: ConflictResolution,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    Resolve conflicts by applying the chosen action
    Actions: 'skip_all' (keep existing) or 'overwrite_all' (use new data)
    """
    try:
        result = await ExternalSyncService.resolve_conflicts(
            db, 
            resolution.conflicts, 
            resolution.action
        )
        return {
            "status": "success",
            "message": f"Applied {resolution.action} to {len(resolution.conflicts)} items",
            "applied": result.get("applied", 0),
            "skipped": result.get("skipped", 0)
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/metadata/flags")
def set_entity_metadata_flags(
    payload: MetadataFlagRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    _ = current_user
    record = EntityMetadataService.set_flags(
        db,
        entity_type=payload.entity_type,
        entity_key=payload.entity_key,
        display_name=payload.display_name,
        entity_id=payload.entity_id,
        is_featured=payload.is_featured,
        is_pinned=payload.is_pinned,
        is_favorite=payload.is_favorite,
        notes=payload.notes,
    )
    db.commit()
    db.refresh(record)
    return {
        "status": "success",
        "id": record.id,
        "entity_type": record.entity_type,
        "entity_key": record.entity_key,
        "display_name": record.display_name,
        "entity_id": record.entity_id,
        "is_featured": record.is_featured,
        "is_pinned": record.is_pinned,
        "is_favorite": record.is_favorite,
        "search_count": record.search_count,
        "notes": record.notes,
    }
