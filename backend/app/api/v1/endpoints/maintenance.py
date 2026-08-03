from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from datetime import datetime
from sqlalchemy.orm import Session

from app.api.v1.endpoints.auth import get_current_admin_user
from app.db.database import get_db
from app.models.user import User
from app.services.admin_maintenance_service import AdminMaintenanceService, MaintenanceError
from app.services.maintenance_mode_service import MaintenanceModeError, MaintenanceModeService


router = APIRouter()


class MaintenanceExecute(BaseModel):
    confirmation: str = Field(min_length=1, max_length=255)
    reason: str = Field(min_length=5, max_length=1000)


class ManualMaintenanceEnable(BaseModel):
    reason: str = Field(min_length=5, max_length=1000)
    public_message: str = Field(min_length=5, max_length=500)
    planned_end_at: datetime | None = None
    confirmation: str


class MaintenanceDisable(BaseModel):
    reason: str = Field(min_length=5, max_length=1000)
    confirmation: str


class HoldRelease(BaseModel):
    reason: str = Field(min_length=5, max_length=1000)


@router.get("")
def maintenance_mode_admin(db: Session = Depends(get_db), _admin: User = Depends(get_current_admin_user)):
    MaintenanceModeService.reconcile(db); db.commit()
    return MaintenanceModeService.status(db, include_private=True)


@router.get("/holds")
def maintenance_holds(db: Session = Depends(get_db), _admin: User = Depends(get_current_admin_user)):
    return [MaintenanceModeService.serialize(row) for row in MaintenanceModeService.active_holds(db)]


@router.post("/manual/enable")
def enable_manual_maintenance(payload: ManualMaintenanceEnable, db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    try:
        row = MaintenanceModeService.enable_manual(db, actor=admin, **payload.model_dump())
        db.commit(); db.refresh(row)
        return MaintenanceModeService.status(db, include_private=True)
    except MaintenanceModeError as exc:
        db.rollback(); raise HTTPException(409, str(exc)) from exc


@router.post("/manual/disable")
def disable_manual_maintenance(payload: MaintenanceDisable, db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    try:
        MaintenanceModeService.disable_manual(db, actor=admin, **payload.model_dump())
        db.commit()
        return MaintenanceModeService.status(db, include_private=True)
    except MaintenanceModeError as exc:
        db.rollback(); raise HTTPException(409, str(exc)) from exc


@router.post("/holds/{hold_id}/release")
def release_maintenance_hold(hold_id: int, payload: HoldRelease, db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    try:
        row = MaintenanceModeService.release_hold(db, hold_id=hold_id, actor=admin, reason=payload.reason)
        db.commit(); db.refresh(row)
        return MaintenanceModeService.serialize(row)
    except MaintenanceModeError as exc:
        db.rollback(); raise HTTPException(404, str(exc)) from exc


@router.get("/{category}")
def list_maintenance_items(category: str, search: str = "", limit: int = Query(100, ge=1, le=200), db: Session = Depends(get_db), _admin: User = Depends(get_current_admin_user)):
    try:
        return {"items": AdminMaintenanceService.list_items(db, category, search, limit)}
    except MaintenanceError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/{category}/{identity}/preflight")
def maintenance_preflight(category: str, identity: str, db: Session = Depends(get_db), _admin: User = Depends(get_current_admin_user)):
    try:
        return AdminMaintenanceService.preflight(db, category, identity)
    except MaintenanceError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/{category}/{identity}/execute")
def execute_maintenance(category: str, identity: str, payload: MaintenanceExecute, db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    try:
        result = AdminMaintenanceService.execute(db, admin, category, identity, payload.confirmation, payload.reason)
        db.commit()
        return result
    except PermissionError as exc:
        db.rollback()
        raise HTTPException(403, str(exc)) from exc
    except MaintenanceError as exc:
        db.rollback()
        raise HTTPException(409, str(exc)) from exc
