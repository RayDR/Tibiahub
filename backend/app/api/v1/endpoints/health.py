from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.external_data import APISync, SyncJob
from app.models.settings import SystemSettings as SettingsModel

router = APIRouter()


@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    now = datetime.utcnow()
    db_status = "ok"

    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"

    active_jobs = db.query(SyncJob).filter(SyncJob.status.in_(["pending", "running"])).count()
    failed_jobs_24h = (
        db.query(SyncJob)
        .filter(SyncJob.status == "failed", SyncJob.created_at >= now.replace(hour=0, minute=0, second=0, microsecond=0))
        .count()
    )

    latest_sync = (
        db.query(APISync)
        .filter(APISync.status == "success")
        .order_by(APISync.completed_at.desc())
        .first()
    )
    configured_version = db.query(SettingsModel).filter(SettingsModel.key == "tibia_latest_update_version").first()
    latest_data_version = configured_version.value if configured_version and configured_version.value else None
    if not latest_data_version and latest_sync and latest_sync.completed_at:
        latest_data_version = latest_sync.completed_at.strftime("Synced %Y-%m-%d")

    status = "ok" if db_status == "ok" else "degraded"
    return {
        "status": status,
        "db": db_status,
        "external_sync": {
            "active_jobs": active_jobs,
            "failed_jobs_today": failed_jobs_24h,
            "latest_data_version": latest_data_version,
            "latest_success_at": latest_sync.completed_at.isoformat() + "Z" if latest_sync and latest_sync.completed_at else None,
        },
        "timestamp": now.isoformat() + "Z",
    }
