"""Public application maintenance status."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.services.maintenance_mode_service import MaintenanceModeService

router = APIRouter()


@router.get("/status")
def maintenance_status(db: Session = Depends(get_db)):
    return MaintenanceModeService.status(db)
