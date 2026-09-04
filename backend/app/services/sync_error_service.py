"""Safe, deduplicated persistence for synchronization failures."""
from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from urllib.parse import urlsplit, urlunsplit

import httpx
from sqlalchemy.orm import Session

from app.models.external_data import SyncJobError


SAFE_MESSAGES = {
    "provider_forbidden": "Provider rejected the resource request with HTTP 403.",
    "provider_rate_limited": "Provider rate limited the request.",
    "provider_not_found": "The provider resource was not found.",
    "provider_timeout": "The provider request timed out.",
    "provider_server_error": "The provider returned a server error.",
    "invalid_payload": "The provider record could not be validated safely.",
    "database_constraint": "The record did not satisfy a database constraint.",
    "unsupported_resource": "The resource type or content is unsupported.",
    "unsupported_content_type": "The provider response has an unsupported content type.",
    "unsupported_image_format": "The decoded image format is unsupported.",
    "invalid_image_payload": "The provider response is not a valid safe image.",
    "oversized_resource": "The provider image exceeds the configured safety limit.",
    "unsafe_source": "The image source did not pass the local media safety policy.",
    "resolution_failed": "The provider image reference could not be resolved exactly.",
    "unknown_provider_error": "The provider request failed for an unclassified safe reason.",
    "download_failed": "The resource could not be downloaded safely.",
    "item_failure": "The record could not be synchronized safely.",
    "worker_interrupted": "The worker was interrupted before the phase completed.",
}


def sanitize_url(value: str | None) -> str | None:
    """Keep only HTTPS host and path; discard credentials, query and fragment."""
    if not value:
        return None
    try:
        parsed = urlsplit(value)
    except ValueError:
        return None
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        return None
    port = f":{parsed.port}" if parsed.port and parsed.port != 443 else ""
    return urlunsplit(("https", f"{parsed.hostname.lower()}{port}", parsed.path or "/", "", ""))


def provider_host(value: str | None, fallback: str | None = None) -> str | None:
    safe = sanitize_url(value)
    return urlsplit(safe).hostname if safe else fallback


def classify_exception(exc: Exception) -> tuple[str, int | None, bool, str]:
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status == 403:
            category, retryable = "provider_forbidden", False
        elif status == 404:
            category, retryable = "provider_not_found", False
        elif status == 429:
            category, retryable = "provider_rate_limited", True
        elif 500 <= status < 600:
            category, retryable = "provider_server_error", True
        else:
            category, retryable = "download_failed", False
        return category, status, retryable, SAFE_MESSAGES[category]
    if isinstance(exc, (httpx.TimeoutException, TimeoutError)):
        return "provider_timeout", None, True, SAFE_MESSAGES["provider_timeout"]
    return "item_failure", None, False, SAFE_MESSAGES["item_failure"]


def record_sync_error(
    db: Session,
    *,
    job_id: str,
    phase_key: str,
    entity_type: str,
    external_id: str | None,
    entity_name: str | None,
    category: str,
    message: str | None = None,
    provider: str | None = None,
    source_url: str | None = None,
    http_status: int | None = None,
    retryable: bool | None = None,
    checkpoint_offset: int | None = None,
    attempt: int | None = None,
) -> SyncJobError:
    now = datetime.now(UTC)
    safe_url = sanitize_url(source_url)
    identity = external_id or entity_name or "phase"
    fingerprint = hashlib.sha256(
        "\x1f".join((job_id, phase_key, entity_type, identity, category, str(http_status or ""))).encode("utf-8")
    ).hexdigest()
    row = db.query(SyncJobError).filter(SyncJobError.fingerprint == fingerprint).one_or_none()
    safe_message = (message or SAFE_MESSAGES.get(category) or SAFE_MESSAGES["item_failure"])[:500]
    if row:
        row.last_seen_at = now
        row.occurrence_count = int(row.occurrence_count or 1) + 1
        row.checkpoint_offset = checkpoint_offset
        row.attempt = attempt
        row.error_message = safe_message
        row.safe_url = safe_url
        row.provider = provider_host(safe_url, provider)
        row.retryable = retryable
        return row
    row = SyncJobError(
        job_id=job_id, phase_key=phase_key, entity_type=entity_type,
        external_id=external_id, entity_name=entity_name,
        error_message=safe_message, error_category=category,
        provider=provider_host(safe_url, provider), safe_url=safe_url,
        http_status=http_status, retryable=retryable,
        checkpoint_offset=checkpoint_offset, attempt=attempt,
        occurrence_count=1, first_occurred_at=now, last_seen_at=now,
        fingerprint=fingerprint, retry_count=max(0, int((attempt or 1) - 1)), status="failed",
    )
    db.add(row)
    db.flush()
    return row
