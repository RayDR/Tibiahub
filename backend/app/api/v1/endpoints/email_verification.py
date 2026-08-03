"""Email verification using hashed, expiring, single-use tokens."""

from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.v1.endpoints.auth import get_current_active_user, get_current_admin_user
from app.core.config import settings
from app.db.database import get_db
from app.models.user import User
from app.services.auth_token_service import AuthTokenService, EMAIL_VERIFICATION
from app.services.email_outbox_service import EmailOutboxService

router = APIRouter()


class VerificationRequest(BaseModel):
    locale: Literal["en", "es"] = "en"


class VerificationConfirm(BaseModel):
    token: str = Field(..., min_length=32, max_length=256)


class AdminVerificationRequest(BaseModel):
    user_id: int
    locale: Literal["en", "es"] = "en"


def queue_verification_email(db: Session, *, user: User, raw_token: str, locale: str) -> None:
    EmailOutboxService.enqueue_verification(db, user=user, raw_token=raw_token, locale=locale)


@router.post("/request")
def request_verification(
    payload: VerificationRequest,
    request: Request,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    if user.email and user.email_verified_at is None:
        requester = request.client.host if request.client else "unknown"
        if AuthTokenService.allow_request(
            db, purpose=EMAIL_VERIFICATION, subject=user.email, requester=requester,
        ):
            raw_token = AuthTokenService.issue(
                db,
                user=user,
                purpose=EMAIL_VERIFICATION,
                ttl=timedelta(hours=settings.EMAIL_VERIFICATION_TTL_HOURS),
            )
            queue_verification_email(db, user=user, raw_token=raw_token, locale=payload.locale)
    db.commit()
    return {"message": "If verification is needed, instructions will be sent"}


@router.post("/confirm")
def confirm_verification(payload: VerificationConfirm, db: Session = Depends(get_db)):
    user = AuthTokenService.consume(db, purpose=EMAIL_VERIFICATION, raw_token=payload.token)
    if user is None:
        db.rollback()
        raise HTTPException(status_code=400, detail="The verification link is invalid or expired")
    from datetime import UTC, datetime
    user.email_verified_at = user.email_verified_at or datetime.now(UTC)
    db.commit()
    return {"message": "Email verified"}


@router.post("/admin/resend")
def admin_resend_verification(
    payload: AdminVerificationRequest,
    _admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    user = db.get(User, payload.user_id)
    if user is None or not user.email:
        raise HTTPException(status_code=404, detail="Eligible account not found")
    if user.email_verified_at is not None:
        return {"message": "Email is already verified"}
    raw_token = AuthTokenService.issue(
        db, user=user, purpose=EMAIL_VERIFICATION,
        ttl=timedelta(hours=settings.EMAIL_VERIFICATION_TTL_HOURS),
    )
    queue_verification_email(db, user=user, raw_token=raw_token, locale=payload.locale)
    db.commit()
    return {"message": "Email verification queued"}
