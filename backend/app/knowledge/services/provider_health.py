"""Operational provider health and cooldown state transitions."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.knowledge.models import KnowledgeProvider
from app.knowledge.services.failures import ClassifiedFailure, retry_delay_seconds


def record_provider_attempt(provider: KnowledgeProvider, *, now: datetime | None = None) -> None:
    provider.last_attempted_at = now or datetime.now(UTC)
    if not provider.enabled:
        provider.health = "disabled"


def record_provider_success(provider: KnowledgeProvider, *, now: datetime | None = None) -> None:
    succeeded_at = now or datetime.now(UTC)
    provider.last_attempted_at = succeeded_at
    provider.last_success_at = succeeded_at
    provider.last_sync_at = succeeded_at
    provider.consecutive_failures = 0
    provider.cooldown_until = None
    provider.health = "healthy" if provider.enabled else "disabled"


def record_provider_failure(
    provider: KnowledgeProvider,
    failure: ClassifiedFailure,
    *,
    now: datetime | None = None,
) -> None:
    failed_at = now or datetime.now(UTC)
    provider.last_attempted_at = failed_at
    provider.last_failure_at = failed_at
    provider.consecutive_failures = (provider.consecutive_failures or 0) + 1
    if not provider.enabled:
        provider.health = "disabled"
        provider.cooldown_until = None
        return
    provider.health = "unavailable" if provider.consecutive_failures >= 3 else "degraded"
    if failure.retryable:
        cooldown = retry_delay_seconds(
            provider.consecutive_failures,
            retry_after_seconds=failure.retry_after_seconds,
            base_seconds=15,
            maximum_seconds=900,
        )
        provider.cooldown_until = failed_at + timedelta(seconds=cooldown)
