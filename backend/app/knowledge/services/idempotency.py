"""Canonical idempotency hashing for durable knowledge jobs."""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any


def normalize_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): normalize_json(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, list):
        return [normalize_json(item) for item in value]
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Idempotency input cannot contain non-finite numbers")
    if value is None or isinstance(value, (bool, int, float)):
        return value
    raise ValueError("Idempotency input must contain only JSON values")


def canonical_json(value: Any) -> str:
    return json.dumps(normalize_json(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def scope_hash(scope: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(scope).encode("utf-8")).hexdigest()


def knowledge_job_idempotency_key(
    *,
    provider_id: str,
    job_type: str,
    entity_type: str | None,
    scope: dict[str, Any],
    payload: dict[str, Any],
    time_bucket: str | None = None,
) -> str:
    identity = {
        "provider": provider_id,
        "job_type": job_type,
        "entity_type": entity_type,
        "scope": normalize_json(scope),
        "payload": normalize_json(payload),
        "time_bucket": time_bucket.strip() if time_bucket else None,
    }
    return hashlib.sha256(canonical_json(identity).encode("utf-8")).hexdigest()
