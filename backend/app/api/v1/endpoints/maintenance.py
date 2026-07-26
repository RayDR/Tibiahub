from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.v1.endpoints.auth import get_current_admin_user
from app.db.database import get_db
from app.models.user import User
from app.services.admin_maintenance_service import AdminMaintenanceService, MaintenanceError


router = APIRouter()


class MaintenanceExecute(BaseModel):
    confirmation: str = Field(min_length=1, max_length=255)
    reason: str = Field(min_length=5, max_length=1000)


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
