"""Password Reset endpoints."""
import hashlib
import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr

from app.api.v1.endpoints.auth import get_current_admin_user
from app.core import security
from app.core.config import settings
from app.db.database import get_db
from app.models.user import User
from app.models.user_character import UserCharacter
from app.services.email_service import EmailService

router = APIRouter()
logger = logging.getLogger(__name__)


class PasswordResetRequest(BaseModel):
    email: Optional[EmailStr] = None
    character_name: Optional[str] = None


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str


class AdminPasswordResetByEmail(BaseModel):
    user_id: int


class EmailTestRequest(BaseModel):
    email: EmailStr


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _store_reset_token(user: User) -> str:
    raw_token = secrets.token_urlsafe(48)
    user.reset_token = _token_hash(raw_token)
    user.reset_token_expires = datetime.now(UTC) + timedelta(hours=1)
    return raw_token


def _queue_reset_email(background_tasks: BackgroundTasks, *, email: str, username: str, raw_token: str) -> None:
    reset_link = f"{settings.RESET_PASSWORD_URL}?token={raw_token}"

    def _send() -> None:
        result = EmailService.send_password_reset_email(
            to_email=email,
            username=username,
            reset_link=reset_link,
        )
        if not result.ok:
            logger.error("password_reset_email_failed username=%s email=%s detail=%s", username, email, result.detail)

    background_tasks.add_task(_send)


@router.post("/request-reset")
async def request_password_reset(
    request: PasswordResetRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Request password reset by email or character name
    Sends an email with reset link
    """
    user = None
    
    if request.email:
        user = db.query(User).filter(User.email == request.email).first()
    elif request.character_name:
        # Find user by character name
        character = db.query(UserCharacter).filter(
            UserCharacter.character_name.ilike(request.character_name)
        ).first()
        
        if character:
            user = db.query(User).filter(User.id == character.user_id).first()
    else:
        raise HTTPException(status_code=400, detail="Provide email or character name")
    
    # Always return success even if user not found (security)
    if not user or not user.email:
        return {"message": "If an account with that information exists, a reset email will be sent"}
    
    token = _store_reset_token(user)
    db.commit()
    
    _queue_reset_email(background_tasks, email=user.email, username=user.username, raw_token=token)
    
    return {"message": "If an account with that information exists, a reset email will be sent"}


@router.post("/reset-password")
def reset_password(
    reset_data: PasswordResetConfirm,
    db: Session = Depends(get_db)
):
    """
    Reset password using token from email
    """
    token_hash = _token_hash(reset_data.token)
    user = db.query(User).filter(User.reset_token == token_hash).first()
    
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    
    # Check if token is expired
    if user.reset_token_expires < datetime.now(UTC):
        raise HTTPException(status_code=400, detail="Reset token has expired")
    
    # Update password
    user.hashed_password = security.get_password_hash(reset_data.new_password)
    user.reset_token = None
    user.reset_token_expires = None
    db.commit()
    
    return {"message": "Password reset successfully"}


@router.post("/admin/send-reset-email")
def admin_send_reset_email(
    request: AdminPasswordResetByEmail,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Admin can send password reset email to any user
    """
    user = db.query(User).filter(User.id == request.user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if not user.email:
        raise HTTPException(status_code=400, detail="User has no email address set")
    
    token = _store_reset_token(user)
    db.commit()
    
    _queue_reset_email(background_tasks, email=user.email, username=user.username, raw_token=token)
    
    return {"message": f"Password reset email sent to {user.email}"}


@router.post("/test-email")
def send_test_email(
    payload: EmailTestRequest,
    current_user: User = Depends(get_current_admin_user),
):
    _ = current_user
    subject, html_body, text_body = EmailService.build_password_reset_content(
        username="Admin Test",
        reset_link=f"{settings.RESET_PASSWORD_URL}?token=test-token",
    )
    result = EmailService.send_message(
        EmailService.build_message(
            to_email=payload.email,
            subject=f"[Test] {subject}",
            html_body=html_body,
            text_body=text_body,
        )
    )
    if not result.ok:
        raise HTTPException(status_code=503, detail=result.detail)
    return {"message": f"Test email sent to {payload.email}"}
