"""
Password Reset endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional
import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta

from app.db.database import get_db
from app.models.user import User
from app.models.user_character import UserCharacter
from app.core import security
from app.api.v1.endpoints.auth import get_current_admin_user

router = APIRouter()

# Email configuration
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_EMAIL = "no-reply@domoforge.com"
SMTP_PASSWORD = "L2SzP79ATZge8ub"


class PasswordResetRequest(BaseModel):
    email: Optional[EmailStr] = None
    character_name: Optional[str] = None


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str


class AdminPasswordResetByEmail(BaseModel):
    user_id: int


def send_reset_email(email: str, username: str, reset_link: str):
    """Send password reset email"""
    try:
        msg = MIMEMultipart('alternative')
        msg['From'] = SMTP_EMAIL
        msg['To'] = email
        msg['Subject'] = 'TibiaHub - Password Reset Request'
        
        html = f"""
        <html>
            <body style="font-family: Arial, sans-serif; padding: 20px; background-color: #0f172a; color: #cbd5e1;">
                <div style="max-width: 600px; margin: 0 auto; background-color: #1e293b; border-radius: 8px; padding: 30px; border: 1px solid #334155;">
                    <h2 style="color: #f59e0b; margin-bottom: 20px;">Password Reset Request</h2>
                    <p>Hello {username},</p>
                    <p>You have requested to reset your password for your TibiaHub account.</p>
                    <p>Click the link below to reset your password:</p>
                    <a href="{reset_link}" style="display: inline-block; margin: 20px 0; padding: 12px 24px; background-color: #f59e0b; color: #0f172a; text-decoration: none; border-radius: 6px; font-weight: bold;">
                        Reset Password
                    </a>
                    <p>Or copy and paste this link into your browser:</p>
                    <p style="color: #94a3b8; word-break: break-all;">{reset_link}</p>
                    <p style="margin-top: 30px; color: #64748b; font-size: 12px;">
                        If you did not request this password reset, please ignore this email.
                        This link will expire in 1 hour.
                    </p>
                    <hr style="border: none; border-top: 1px solid #334155; margin: 20px 0;">
                    <p style="color: #64748b; font-size: 12px;">
                        TibiaHub - Bloodborne Warhowl Command Center
                    </p>
                </div>
            </body>
        </html>
        """
        
        part = MIMEText(html, 'html')
        msg.attach(part)
        
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.send_message(msg)
            
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False


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
    
    # Generate reset token
    token = secrets.token_urlsafe(32)
    user.reset_token = token
    user.reset_token_expires = datetime.utcnow() + timedelta(hours=1)
    db.commit()
    
    # Send email in background
    reset_link = f"https://tibiahub.domoforge.com/reset-password?token={token}"
    background_tasks.add_task(send_reset_email, user.email, user.username, reset_link)
    
    return {"message": "If an account with that information exists, a reset email will be sent"}


@router.post("/reset-password")
def reset_password(
    reset_data: PasswordResetConfirm,
    db: Session = Depends(get_db)
):
    """
    Reset password using token from email
    """
    user = db.query(User).filter(User.reset_token == reset_data.token).first()
    
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    
    # Check if token is expired
    if user.reset_token_expires < datetime.utcnow():
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
    
    # Generate reset token
    token = secrets.token_urlsafe(32)
    user.reset_token = token
    user.reset_token_expires = datetime.utcnow() + timedelta(hours=1)
    db.commit()
    
    # Send email in background
    reset_link = f"https://tibiahub.domoforge.com/reset-password?token={token}"
    background_tasks.add_task(send_reset_email, user.email, user.username, reset_link)
    
    return {"message": f"Password reset email sent to {user.email}"}
