"""Simple timeout/retry/circuit-breaker helpers for external providers."""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from threading import Lock
from typing import Any

import httpx


@dataclass
class ProviderState:
    failures: int = 0
    open_until: float = 0.0


_STATE_LOCK = Lock()
_PROVIDER_STATE: dict[str, ProviderState] = {}


def _state(provider: str) -> ProviderState:
    with _STATE_LOCK:
        if provider not in _PROVIDER_STATE:
            _PROVIDER_STATE[provider] = ProviderState()
        return _PROVIDER_STATE[provider]


def _is_open(provider: str) -> bool:
    state = _state(provider)
    return state.open_until > time.time()


def _record_success(provider: str) -> None:
    state = _state(provider)
    state.failures = 0
    state.open_until = 0.0


def _record_failure(provider: str, threshold: int, cooldown_seconds: int) -> None:
    state = _state(provider)
    state.failures += 1
    if state.failures >= threshold:
        state.open_until = time.time() + cooldown_seconds


async def request_json_with_resilience(
    *,
    provider: str,
    url: str,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout_seconds: float = 15.0,
    retries: int = 2,
    retry_backoff_seconds: float = 0.4,
    circuit_failures: int = 3,
    circuit_cooldown_seconds: int = 30,
) -> dict[str, Any]:
    if _is_open(provider):
        raise RuntimeError(f"{provider} circuit is open")

    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout_seconds, headers=headers) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                _record_success(provider)
                return response.json()
        except Exception as exc:
            last_error = exc
            _record_failure(provider, threshold=circuit_failures, cooldown_seconds=circuit_cooldown_seconds)
            if attempt < retries:
                await asyncio.sleep(retry_backoff_seconds * (attempt + 1))

    raise RuntimeError(f"{provider} request failed: {last_error}")
