"""SMTP email service with explicit configuration and logging."""
from __future__ import annotations

import logging
import smtplib
from html import escape
from hashlib import sha256
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
        if settings.APP_ENV == "test":
            return EmailSendResult(ok=True, detail="Email delivery disabled in tests")
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
            recipient_hash = sha256(str(message["To"]).casefold().encode("utf-8")).hexdigest()[:12]
            logger.info("email_sent recipient_hash=%s", recipient_hash)
            return EmailSendResult(ok=True, detail="Email sent")
        except Exception as exc:
            recipient_hash = sha256(str(message["To"]).casefold().encode("utf-8")).hexdigest()[:12]
            logger.error("email_send_failed recipient_hash=%s error_type=%s", recipient_hash, type(exc).__name__)
            return EmailSendResult(ok=False, detail="Email delivery failed")

    @staticmethod
    def build_password_reset_content(*, username: str, reset_link: str, locale: str = "en") -> tuple[str, str, str]:
        safe_link = escape(reset_link, quote=True)
        spanish = locale.casefold().startswith("es")
        subject = "TibiaHub - Recuperación de contraseña" if spanish else "TibiaHub - Password recovery"
        greeting = f"Hola {username}" if spanish else f"Hello {username}"
        instruction = "Recibimos una solicitud para restablecer tu contraseña de TibiaHub." if spanish else "We received a request to reset your TibiaHub password."
        action = "Restablecer contraseña" if spanish else "Reset password"
        expiry = "Este enlace vence pronto. Si no solicitaste el cambio, puedes ignorar este correo." if spanish else "This link expires soon. If you did not request this change, you can ignore this email."
        copy_help = "Si el botón no se abre, copia esta URL:" if spanish else "If the button does not open, copy this URL:"
        text_body = (
            f"{greeting},\n\n"
            f"{instruction}\n"
            f"Open this link to continue: {reset_link}\n\n"
            f"{expiry}"
        )
        html_body = f"""
        <html>
          <body style=\"font-family: Arial, sans-serif; background: #0f172a; color: #cbd5e1; padding: 24px;\">
            <div style=\"max-width: 640px; margin: 0 auto; background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 32px;\">
              <h2 style=\"color: #f59e0b; margin-top: 0;\">{subject}</h2>
              <p>{escape(greeting)},</p>
              <p>{instruction}</p>
              <p>
                <a href=\"{safe_link}\" style=\"display: inline-block; padding: 12px 18px; border-radius: 8px; background: #f59e0b; color: #0f172a; text-decoration: none; font-weight: bold;\">{action}</a>
              </p>
              <p>{copy_help}</p>
              <p style=\"word-break: break-word; color: #f8fafc;\">{safe_link}</p>
              <p style=\"font-size: 12px; color: #94a3b8; margin-top: 32px;\">{expiry}</p>
            </div>
          </body>
        </html>
        """
        return subject, html_body, text_body

    @staticmethod
    def send_password_reset_email(*, to_email: str, username: str, reset_link: str, locale: str = "en") -> EmailSendResult:
        subject, html_body, text_body = EmailService.build_password_reset_content(
            username=username,
            reset_link=reset_link, locale=locale,
        )
        return EmailService.send_message(
            EmailService.build_message(
                to_email=to_email,
                subject=subject,
                html_body=html_body,
                text_body=text_body,
            )
        )

    @staticmethod
    def build_verification_content(*, username: str, verification_link: str, locale: str = "en") -> tuple[str, str, str]:
        spanish = locale.casefold().startswith("es")
        safe_link = escape(verification_link, quote=True)
        subject = "TibiaHub - Verifica tu correo" if spanish else "TibiaHub - Verify your email"
        greeting = f"Hola {username}" if spanish else f"Hello {username}"
        instruction = "Confirma que esta dirección de correo te pertenece." if spanish else "Confirm that this email address belongs to you."
        action = "Verificar correo" if spanish else "Verify email"
        expiry = "El enlace vence pronto y solo puede usarse una vez." if spanish else "The link expires soon and can only be used once."
        text = f"{greeting}\n\n{instruction}\n{verification_link}\n\n{expiry}"
        html = f"<main><h1>{subject}</h1><p>{escape(greeting)}</p><p>{instruction}</p><p><a href=\"{safe_link}\">{action}</a></p><p>{expiry}</p></main>"
        return subject, html, text

    @staticmethod
    def send_verification_email(*, to_email: str, username: str, verification_link: str, locale: str = "en") -> EmailSendResult:
        subject, html_body, text_body = EmailService.build_verification_content(
            username=username, verification_link=verification_link, locale=locale,
        )
        return EmailService.send_message(EmailService.build_message(
            to_email=to_email, subject=subject, html_body=html_body, text_body=text_body,
        ))
