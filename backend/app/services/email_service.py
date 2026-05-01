"""SMTP email service with explicit configuration and logging."""
from __future__ import annotations

import logging
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class EmailSendResult:
    ok: bool
    detail: str


class EmailService:
    @staticmethod
    def verify_configuration() -> EmailSendResult:
        if not settings.smtp_configured:
            detail = "SMTP is not configured. Set SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, and optional SMTP_FROM."
            logger.warning("email_not_configured detail=%s", detail)
            return EmailSendResult(ok=False, detail=detail)
        return EmailSendResult(ok=True, detail="SMTP is configured")

    @staticmethod
    def build_message(*, to_email: str, subject: str, html_body: str, text_body: str) -> EmailMessage:
        message = EmailMessage()
        message["From"] = settings.smtp_from_address
        message["To"] = to_email
        message["Subject"] = subject
        message.set_content(text_body)
        message.add_alternative(html_body, subtype="html")
        return message

    @staticmethod
    def send_message(message: EmailMessage) -> EmailSendResult:
        config_check = EmailService.verify_configuration()
        if not config_check.ok:
            return config_check

        try:
            smtp_cls = smtplib.SMTP_SSL if settings.SMTP_USE_SSL else smtplib.SMTP
            with smtp_cls(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as client:
                client.ehlo()
                if settings.SMTP_USE_TLS and not settings.SMTP_USE_SSL:
                    client.starttls()
                    client.ehlo()
                client.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                client.send_message(message)
            logger.info("email_sent to=%s subject=%s", message["To"], message["Subject"])
            return EmailSendResult(ok=True, detail="Email sent")
        except Exception as exc:
            logger.exception("email_send_failed to=%s subject=%s error=%s", message["To"], message["Subject"], exc)
            return EmailSendResult(ok=False, detail=str(exc))

    @staticmethod
    def build_password_reset_content(*, username: str, reset_link: str) -> tuple[str, str, str]:
        subject = "TibiaHub - Password Reset Request"
        text_body = (
            f"Hello {username},\n\n"
            "We received a request to reset your TibiaHub password.\n"
            f"Open this link to continue: {reset_link}\n\n"
            "This link expires in 1 hour. If you did not request this change, you can ignore this email."
        )
        html_body = f"""
        <html>
          <body style=\"font-family: Arial, sans-serif; background: #0f172a; color: #cbd5e1; padding: 24px;\">
            <div style=\"max-width: 640px; margin: 0 auto; background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 32px;\">
              <h2 style=\"color: #f59e0b; margin-top: 0;\">Password Reset Request</h2>
              <p>Hello {username},</p>
              <p>We received a request to reset your TibiaHub password.</p>
              <p>
                <a href=\"{reset_link}\" style=\"display: inline-block; padding: 12px 18px; border-radius: 8px; background: #f59e0b; color: #0f172a; text-decoration: none; font-weight: bold;\">Reset password</a>
              </p>
              <p>If the button does not open, copy this URL:</p>
              <p style=\"word-break: break-word; color: #f8fafc;\">{reset_link}</p>
              <p style=\"font-size: 12px; color: #94a3b8; margin-top: 32px;\">This link expires in 1 hour. If you did not request this change, you can ignore this email.</p>
            </div>
          </body>
        </html>
        """
        return subject, html_body, text_body

    @staticmethod
    def send_password_reset_email(*, to_email: str, username: str, reset_link: str) -> EmailSendResult:
        subject, html_body, text_body = EmailService.build_password_reset_content(
            username=username,
            reset_link=reset_link,
        )
        return EmailService.send_message(
            EmailService.build_message(
                to_email=to_email,
                subject=subject,
                html_body=html_body,
                text_body=text_body,
            )
        )