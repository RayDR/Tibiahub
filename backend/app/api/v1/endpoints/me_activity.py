"""Endpoints for authenticated character-scoped activity history."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.v1.endpoints.auth import get_current_user
from app.db.database import get_db
from app.models.user import User
from app.models.user_activity import UserActivity
from app.models.user_character import UserCharacter

router = APIRouter(prefix="/me", tags=["User Activity"])

HUNT_SEARCH_ACTIVITY_TYPE = "hunt_search"
HUNT_SEARCH_TTL = timedelta(days=7)


class ActivityCreateRequest(BaseModel):
    activity_type: str
    character_id: Optional[int] = None
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    query: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class ActivityResponse(BaseModel):
    id: int
    character_id: Optional[int] = None
    activity_type: str
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    query: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None
    created_at: str


def _verified_character(db: Session, user_id: int, character_id: int) -> UserCharacter:
    character = (
        db.query(UserCharacter)
        .filter(
            UserCharacter.id == character_id,
            UserCharacter.user_id == user_id,
            UserCharacter.ownership_status == "verified",
        )
        .first()
    )
    if character is None:
        raise HTTPException(status_code=404, detail="Verified character not found")
    return character


def _to_response(entry: UserActivity) -> ActivityResponse:
    return ActivityResponse(
        id=entry.id,
        character_id=entry.character_id,
        activity_type=entry.activity_type,
        entity_type=entry.entity_type,
        entity_id=entry.entity_id,
        query=entry.query,
        metadata=entry.meta_payload,
        created_at=entry.created_at.isoformat() if entry.created_at else "",
    )


def _prune_expired_hunt_searches(db: Session, user_id: int) -> int:
    """Delete planner snapshots after their seven-day restore window."""
    cutoff = datetime.now(timezone.utc) - HUNT_SEARCH_TTL
    return (
        db.query(UserActivity)
        .filter(
            UserActivity.user_id == user_id,
            UserActivity.activity_type == HUNT_SEARCH_ACTIVITY_TYPE,
            UserActivity.created_at < cutoff,
        )
        .delete(synchronize_session=False)
    )


def _replace_hunt_search_for_scope(
    db: Session,
    *,
    user_id: int,
    character_id: Optional[int],
) -> int:
    """Keep one authoritative planner snapshot per account/character scope."""
    query = db.query(UserActivity).filter(
        UserActivity.user_id == user_id,
        UserActivity.activity_type == HUNT_SEARCH_ACTIVITY_TYPE,
    )
    if character_id is None:
        query = query.filter(UserActivity.character_id.is_(None))
    else:
        query = query.filter(UserActivity.character_id == character_id)
    return query.delete(synchronize_session=False)


@router.get("/activity", response_model=list[ActivityResponse])
def get_my_activity(
    limit: int = Query(40, ge=1, le=200),
    activity_type: Optional[str] = Query(None),
    character_id: Optional[int] = Query(None, ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if _prune_expired_hunt_searches(db, current_user.id):
        db.commit()

    query = db.query(UserActivity).filter(UserActivity.user_id == current_user.id)
    if character_id is not None:
        character = _verified_character(db, current_user.id, character_id)
        query = query.filter(UserActivity.character_id == character.id)
    if activity_type:
        query = query.filter(UserActivity.activity_type == activity_type)
    entries = query.order_by(UserActivity.created_at.desc()).limit(limit).all()
    return [_to_response(entry) for entry in entries]


@router.delete("/activity")
def clear_my_activity(
    character_id: Optional[int] = Query(None, ge=1),
    activity_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(UserActivity).filter(UserActivity.user_id == current_user.id)
    if character_id is not None:
        character = _verified_character(db, current_user.id, character_id)
        query = query.filter(UserActivity.character_id == character.id)
    if activity_type:
        query = query.filter(UserActivity.activity_type == activity_type)
    deleted = query.delete(synchronize_session=False)
    db.commit()
    return {"status": "ok", "deleted": deleted}


@router.post("/activity", response_model=ActivityResponse)
def record_my_activity(
    payload: ActivityCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    character_id = None
    if payload.character_id is not None:
        character = _verified_character(db, current_user.id, payload.character_id)
        character_id = character.id

    _prune_expired_hunt_searches(db, current_user.id)
    if payload.activity_type == HUNT_SEARCH_ACTIVITY_TYPE:
        _replace_hunt_search_for_scope(
            db,
            user_id=current_user.id,
            character_id=character_id,
        )

    entry = UserActivity(
        user_id=current_user.id,
        character_id=character_id,
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
