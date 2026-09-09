from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.services.category_visual_service import daily_category_visuals

router = APIRouter(tags=["Catalog"])


@router.get("/catalog/category-visuals/daily")
def get_daily_category_visuals(response: Response, db: Session = Depends(get_db)):
    """Return one local, validated media visual per product category for the current UTC day."""
    response.headers["Cache-Control"] = "public, max-age=3600, stale-while-revalidate=3600"
    return daily_category_visuals(db)
