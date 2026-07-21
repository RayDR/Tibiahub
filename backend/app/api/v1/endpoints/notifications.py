from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.v1.endpoints.auth import get_current_active_user, get_current_admin_user
from app.core.config import settings
from app.db.database import get_db
from app.models.raffle import InternalNotification, RaffleSchedulerState
from app.models.user import User
from app.services.notification_service import NotificationService
from app.services.raffle_scheduler_service import RaffleSchedulerService

router = APIRouter(prefix="/notifications", tags=["Notifications"])


class NotificationResponse(BaseModel):
    id: int
    guild_name: str | None
    raffle_id: int | None
    notification_type: str
    title_key: str
    message_key: str
    interpolation: dict
    deep_link: str | None
    is_read: bool
    created_at: datetime
    read_at: datetime | None

    class Config:
        from_attributes = True


@router.get("", response_model=list[NotificationResponse])
def list_notifications(limit: int = 30, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    limit = max(1, min(limit, 100))
    return db.query(InternalNotification).filter(InternalNotification.recipient_user_id == current_user.id).order_by(InternalNotification.created_at.desc()).limit(limit).all()


@router.get("/unread-count")
def unread_count(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    count = db.query(func.count(InternalNotification.id)).filter(
        InternalNotification.recipient_user_id == current_user.id, InternalNotification.is_read.is_(False)
    ).scalar() or 0
    return {"unread_count": count}


@router.post("/{notification_id}/read", response_model=NotificationResponse)
def mark_read(notification_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    notification = db.query(InternalNotification).filter(
        InternalNotification.id == notification_id, InternalNotification.recipient_user_id == current_user.id
    ).first()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    NotificationService.mark_read(notification)
    db.commit()
    db.refresh(notification)
    return notification


@router.post("/read-all")
def mark_all_read(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    now = datetime.now(UTC)
    updated = db.query(InternalNotification).filter(
        InternalNotification.recipient_user_id == current_user.id, InternalNotification.is_read.is_(False)
    ).update({InternalNotification.is_read: True, InternalNotification.read_at: now}, synchronize_session=False)
    db.commit()
    return {"updated": updated}


@router.get("/scheduler-health")
def scheduler_health(db: Session = Depends(get_db), _current_user: User = Depends(get_current_admin_user)):
    due_count, expired_count = RaffleSchedulerService().counts(db)
    state = db.get(RaffleSchedulerState, settings.RAFFLE_SCHEDULER_WORKER_ID)
    return {
        "enabled": settings.RAFFLE_SCHEDULER_ENABLED,
        "worker_id": settings.RAFFLE_SCHEDULER_WORKER_ID,
        "heartbeat_at": state.heartbeat_at if state else None,
        "last_poll_at": state.last_poll_at if state else None,
        "last_success_at": state.last_success_at if state else None,
        "last_failure_at": state.last_failure_at if state else None,
        "last_failure_code": state.last_failure_code if state else None,
        "due_job_count": due_count,
        "expired_lease_count": expired_count,
    }
