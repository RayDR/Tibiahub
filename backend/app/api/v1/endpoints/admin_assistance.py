"""Focused global-administrator assistance operations."""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.v1.endpoints.auth import get_current_admin_user
from app.db.database import get_db
from app.models.user import User
from app.services.raffle_assistance_service import RaffleAssistanceError, RaffleAssistanceService

router = APIRouter()


class RaffleRescheduleRequest(BaseModel):
    local_scheduled_at: datetime
    timezone_name: str = Field(min_length=1, max_length=64)
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=5, max_length=1000)
    explicit_confirmation: bool
    snapshot_decision: Literal["preserve", "invalidate"] = "preserve"


def _error(exc: RaffleAssistanceError) -> HTTPException:
    status = 404 if exc.code == "raffle_not_found" else 409 if exc.code not in {"invalid_public_code", "invalid_timezone", "nonexistent_local_time", "ambiguous_local_time", "schedule_in_past"} else 422
    return HTTPException(status, detail={"code": exc.code, "message": exc.message})


@router.get("/raffles/lookup")
def lookup_raffle(identifier: str = Query(min_length=1, max_length=500), db: Session = Depends(get_db), _admin: User = Depends(get_current_admin_user)):
    try:
        return RaffleAssistanceService.serialize(db, RaffleAssistanceService.lookup(db, identifier))
    except RaffleAssistanceError as exc:
        raise _error(exc) from exc


@router.patch("/raffles/by-code/{public_code}/schedule")
def reschedule_raffle(public_code: str, payload: RaffleRescheduleRequest, db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    try:
        raffle, audit = RaffleAssistanceService.reschedule(db, public_code=public_code, actor=admin, **payload.model_dump())
        db.commit(); db.refresh(raffle)
        return {"audit_id": audit.id, "raffle": RaffleAssistanceService.serialize(db, raffle)}
    except RaffleAssistanceError as exc:
        db.rollback(); raise _error(exc) from exc
