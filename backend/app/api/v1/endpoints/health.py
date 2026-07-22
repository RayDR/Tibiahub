from datetime import datetime

from fastapi import APIRouter, Depends, Response, status as http_status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.external_data import APISync, SyncJob
from app.models.settings import SystemSettings as SettingsModel
from app.models.media_asset import MediaAsset

router = APIRouter()


@router.get("/healthz")
def healthz():
    return {"status": "ok"}


@router.get("/ready")
def readiness_check(response: Response, db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        response.status_code = http_status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "not_ready", "db": "error"}
    return {"status": "ready", "db": "ok"}


@router.get("/health")
def health_check(response: Response, db: Session = Depends(get_db)):
    now = datetime.utcnow()
    db_status = "ok"

    try:
        db.execute(text("SELECT 1"))
    except Exception:
        response.status_code = http_status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "degraded",
            "db": "error",
            "external_sync": {
                "active_jobs": None,
                "failed_jobs_today": None,
                "latest_data_version": None,
                "latest_success_at": None,
            },
            "timestamp": now.isoformat() + "Z",
        }

    active_jobs = db.query(SyncJob).filter(SyncJob.status.in_(["pending", "running"])).count()
    failed_jobs_24h = (
        db.query(SyncJob)
        .filter(SyncJob.status == "failed", SyncJob.created_at >= now.replace(hour=0, minute=0, second=0, microsecond=0))
        .count()
    )

    latest_sync = (
        db.query(SyncJob)
        .filter(SyncJob.status == "completed")
        .order_by(SyncJob.finished_at.desc())
        .first()
    )
    if not latest_sync:
        latest_sync = (
            db.query(APISync)
            .filter(APISync.status == "success")
            .order_by(APISync.completed_at.desc())
            .first()
        )
    configured_version = db.query(SettingsModel).filter(SettingsModel.key == "tibia_latest_update_version").first()
    latest_data_version = configured_version.value if configured_version and configured_version.value else None
    latest_success_at = None
    if latest_sync and getattr(latest_sync, "finished_at", None):
        latest_success_at = latest_sync.finished_at
    elif latest_sync and getattr(latest_sync, "completed_at", None):
        latest_success_at = latest_sync.completed_at
    if not latest_data_version and latest_success_at:
        latest_data_version = latest_success_at.strftime("Synced %Y-%m-%d")

    status = "ok" if db_status == "ok" else "degraded"
    return {
        "status": status,
        "db": db_status,
        "external_sync": {
            "active_jobs": active_jobs,
            "failed_jobs_today": failed_jobs_24h,
            "latest_data_version": latest_data_version,
            "latest_success_at": latest_success_at.isoformat() + "Z" if latest_success_at else None,
        },
        "timestamp": now.isoformat() + "Z",
    }


@router.get("/system/version")
def system_version(db: Session = Depends(get_db)):
    """
    Lightweight endpoint for frontend cache invalidation.
    Returns timestamps the frontend can compare against its stored cache version.
    """
    latest_sync = (
        db.query(SyncJob)
        .filter(SyncJob.status == "completed")
        .order_by(SyncJob.finished_at.desc())
        .first()
    )
    latest_media = (
        db.query(MediaAsset)
        .filter(MediaAsset.status == "cached")
        .order_by(MediaAsset.updated_at.desc())
        .first()
    )
    latest_sync_at = None
    if latest_sync and getattr(latest_sync, "finished_at", None):
        latest_sync_at = latest_sync.finished_at.isoformat() + "Z"
    latest_media_sync_at = None
    if latest_media and getattr(latest_media, "updated_at", None):
        latest_media_sync_at = latest_media.updated_at.isoformat() + "Z"
    candidates = [value for value in (latest_sync_at, latest_media_sync_at) if value]
    data_version = max(candidates) if candidates else None
    return {
        "data_version": data_version,
        "latest_sync_at": latest_sync_at,
        "latest_media_sync_at": latest_media_sync_at,
    }
