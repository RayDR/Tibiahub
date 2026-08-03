"""Neutral, rate-limited password recovery backed by hashed one-time tokens."""

from datetime import timedelta
import logging
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from sqlalchemy.orm import Session

from app.api.v1.endpoints.auth import get_current_admin_user
from app.core import security
from app.core.password_policy import validate_password
from app.core.config import settings
from app.db.database import get_db
from app.models.user import User
from app.models.user_character import UserCharacter
from app.services.auth_token_service import AuthTokenService, PASSWORD_RESET
from app.services.email_service import EmailService
from app.services.character_ownership_service import normalize_character_name

router = APIRouter()
logger = logging.getLogger(__name__)
NEUTRAL_MESSAGE = "If an account with that information exists, reset instructions will be sent"


class PasswordResetRequest(BaseModel):
    email: EmailStr | None = None
    character_name: str | None = Field(None, min_length=2, max_length=100)
    locale: Literal["en", "es"] = "en"

    @model_validator(mode="after")
    def exactly_one_identifier(self):
        if bool(self.email) == bool((self.character_name or "").strip()):
            raise ValueError("Provide exactly one account identifier")
        return self


class PasswordResetConfirm(BaseModel):
    token: str = Field(..., min_length=32, max_length=256)
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_policy(cls, value: str) -> str:
        return validate_password(value)


class AdminPasswordResetByEmail(BaseModel):
    user_id: int
    locale: Literal["en", "es"] = "en"


class EmailTestRequest(BaseModel):
    email: EmailStr
    locale: Literal["en", "es"] = "en"


def _queue_reset_email(background_tasks: BackgroundTasks, *, user: User, raw_token: str, locale: str) -> None:
    reset_link = f"{settings.RESET_PASSWORD_URL}?token={raw_token}"

    def _send() -> None:
        result = EmailService.send_password_reset_email(
            to_email=user.email,
            username=user.display_name or user.username,
            reset_link=reset_link,
            locale=locale,
        )
        if not result.ok:
            logger.error("password_reset_email_failed user_id=%s", user.id)

    background_tasks.add_task(_send)


def _find_user(db: Session, payload: PasswordResetRequest) -> User | None:
    if payload.email:
        return db.query(User).filter(User.email == str(payload.email).casefold()).first()
    character = db.query(UserCharacter).filter(
        UserCharacter.normalized_name == normalize_character_name(payload.character_name or ""),
        UserCharacter.ownership_status == "verified",
    ).first()
    return character.user if character else None


@router.post("/request-reset")
def request_password_reset(
    payload: PasswordResetRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    subject = str(payload.email or payload.character_name or "").strip()
    requester = request.client.host if request.client else "unknown"
    allowed = AuthTokenService.allow_request(
        db, purpose=PASSWORD_RESET, subject=subject, requester=requester,
    )
    user = _find_user(db, payload) if allowed else None
    if user and user.is_active and user.email:
        raw_token = AuthTokenService.issue(
            db,
            user=user,
            purpose=PASSWORD_RESET,
            ttl=timedelta(minutes=settings.PASSWORD_RESET_TTL_MINUTES),
        )
        _queue_reset_email(background_tasks, user=user, raw_token=raw_token, locale=payload.locale)
    db.commit()
    return {"message": NEUTRAL_MESSAGE}


@router.post("/reset-password")
def reset_password(payload: PasswordResetConfirm, db: Session = Depends(get_db)):
    user = AuthTokenService.consume(db, purpose=PASSWORD_RESET, raw_token=payload.token)
    if user is None:
        db.rollback()
        raise HTTPException(status_code=400, detail="The reset link is invalid or expired")
    user.hashed_password = security.get_password_hash(payload.new_password)
    # Invalidate compatibility tokens as well; they are never accepted here.
    user.reset_token = None
    user.reset_token_expires = None
    db.commit()
    return {"message": "Password reset successfully"}


@router.post("/admin/send-reset-email")
def admin_send_reset_email(
    payload: AdminPasswordResetByEmail,
    background_tasks: BackgroundTasks,
    _admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    user = db.get(User, payload.user_id)
    if not user or not user.email:
        raise HTTPException(status_code=404, detail="Eligible account not found")
    raw_token = AuthTokenService.issue(
        db,
        user=user,
        purpose=PASSWORD_RESET,
        ttl=timedelta(minutes=settings.PASSWORD_RESET_TTL_MINUTES),
    )
    db.commit()
    _queue_reset_email(background_tasks, user=user, raw_token=raw_token, locale=payload.locale)
    return {"message": "Password reset instructions queued"}


@router.post("/test-email")
def send_test_email(payload: EmailTestRequest, _admin: User = Depends(get_current_admin_user)):
    subject, html_body, text_body = EmailService.build_password_reset_content(
        username="Admin Test",
        reset_link=f"{settings.RESET_PASSWORD_URL}?token=test-token-not-valid",
        locale=payload.locale,
    )
    result = EmailService.send_message(EmailService.build_message(
        to_email=payload.email,
        subject=f"[Test] {subject}",
        html_body=html_body,
        text_body=text_body,
    ))
    if not result.ok:
        raise HTTPException(status_code=503, detail=result.detail)
    return {"message": "Test email queued"}
