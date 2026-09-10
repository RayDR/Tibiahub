"""Public/admin presentation settings for the TibiaHub shell."""
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.v1.endpoints.auth import get_current_admin_user
from app.db.database import get_db
from app.models.settings import SystemSettings

router = APIRouter(tags=["Site Presentation"])
admin_router = APIRouter(tags=["Admin Site Presentation"])


class SitePresentationSettings(BaseModel):
    navbar_show_icons: bool = True
    navbar_alignment: Literal["left", "center", "right"] = "center"
    navbar_show_global_search: bool = True


class UpdateSitePresentationSettings(BaseModel):
    navbar_show_icons: bool | None = None
    navbar_alignment: Literal["left", "center", "right"] | None = None
    navbar_show_global_search: bool | None = None


_DEFAULTS = SitePresentationSettings()
_SETTING_KEYS = {
    "navbar_show_icons": "site_navbar_show_icons",
    "navbar_alignment": "site_navbar_alignment",
    "navbar_show_global_search": "site_navbar_show_global_search",
}


def _read_value(db: Session, key: str, default: str) -> str:
    row = (
        db.query(SystemSettings)
        .filter(SystemSettings.key == key, SystemSettings.is_active.is_(True))
        .first()
    )
    return row.value if row and row.value is not None else default


def _write_value(db: Session, key: str, value: str, description: str) -> None:
    row = db.query(SystemSettings).filter(SystemSettings.key == key).first()
    if row:
        row.value = value
        row.description = description
        row.is_active = True
        return
    db.add(
        SystemSettings(
            key=key,
            value=value,
            description=description,
            is_active=True,
        )
    )


def _load(db: Session) -> SitePresentationSettings:
    alignment = _read_value(
        db,
        _SETTING_KEYS["navbar_alignment"],
        _DEFAULTS.navbar_alignment,
    )
    if alignment not in {"left", "center", "right"}:
        alignment = _DEFAULTS.navbar_alignment

    return SitePresentationSettings(
        navbar_show_icons=(
            _read_value(
                db,
                _SETTING_KEYS["navbar_show_icons"],
                "1" if _DEFAULTS.navbar_show_icons else "0",
            )
            == "1"
        ),
        navbar_alignment=alignment,
        navbar_show_global_search=(
            _read_value(
                db,
                _SETTING_KEYS["navbar_show_global_search"],
                "1" if _DEFAULTS.navbar_show_global_search else "0",
            )
            == "1"
        ),
    )


@router.get("/site-presentation", response_model=SitePresentationSettings)
def get_site_presentation(db: Session = Depends(get_db)) -> SitePresentationSettings:
    """Return non-sensitive shell presentation settings for all visitors."""
    return _load(db)


@admin_router.get("/site-presentation", response_model=SitePresentationSettings)
def get_admin_site_presentation(
    db: Session = Depends(get_db),
    _current_user=Depends(get_current_admin_user),
) -> SitePresentationSettings:
    return _load(db)


@admin_router.put("/site-presentation", response_model=SitePresentationSettings)
def update_admin_site_presentation(
    payload: UpdateSitePresentationSettings,
    db: Session = Depends(get_db),
    _current_user=Depends(get_current_admin_user),
) -> SitePresentationSettings:
    values = payload.model_dump(exclude_none=True)

    if "navbar_show_icons" in values:
        _write_value(
            db,
            _SETTING_KEYS["navbar_show_icons"],
            "1" if values["navbar_show_icons"] else "0",
            "Show TibiaHub brand SVG icons in the primary navigation",
        )
    if "navbar_alignment" in values:
        _write_value(
            db,
            _SETTING_KEYS["navbar_alignment"],
            values["navbar_alignment"],
            "Primary navigation horizontal alignment",
        )
    if "navbar_show_global_search" in values:
        _write_value(
            db,
            _SETTING_KEYS["navbar_show_global_search"],
            "1" if values["navbar_show_global_search"] else "0",
            "Show global Cyclopedia search in the primary navigation",
        )

    db.commit()
    return _load(db)
