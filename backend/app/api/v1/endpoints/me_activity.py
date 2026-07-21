"""Endpoints for authenticated user activity history."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.v1.endpoints.auth import get_current_user
from app.db.database import get_db
from app.models.user import User
from app.models.user_activity import UserActivity

router = APIRouter(prefix="/me", tags=["User Activity"])


class ActivityCreateRequest(BaseModel):
    activity_type: str
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    query: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class ActivityResponse(BaseModel):
    id: int
    activity_type: str
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    query: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None
    created_at: str


def _to_response(entry: UserActivity) -> ActivityResponse:
    return ActivityResponse(
        id=entry.id,
        activity_type=entry.activity_type,
        entity_type=entry.entity_type,
        entity_id=entry.entity_id,
        query=entry.query,
        metadata=entry.meta_payload,
        created_at=entry.created_at.isoformat() if entry.created_at else "",
    )


@router.get("/activity", response_model=list[ActivityResponse])
def get_my_activity(
    limit: int = Query(40, ge=1, le=200),
    activity_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(UserActivity).filter(UserActivity.user_id == current_user.id)
    if activity_type:
        query = query.filter(UserActivity.activity_type == activity_type)
    entries = query.order_by(UserActivity.created_at.desc()).limit(limit).all()
    return [_to_response(entry) for entry in entries]


@router.delete("/activity")
def clear_my_activity(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deleted = db.query(UserActivity).filter(UserActivity.user_id == current_user.id).delete()
    db.commit()
    return {"status": "ok", "deleted": deleted}


@router.post("/activity", response_model=ActivityResponse)
def record_my_activity(
    payload: ActivityCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    entry = UserActivity(
        user_id=current_user.id,
        activity_type=payload.activity_type,
        entity_type=payload.entity_type,
        entity_id=payload.entity_id,
        query=payload.query,
        meta_payload=payload.metadata,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return _to_response(entry)
