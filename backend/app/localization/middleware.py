"""Public localization projection middleware.

This layer is intentionally read-only: it overlays already-persisted translations
onto JSON knowledge responses. It never calls a translation provider and it
fails open to canonical/source content if localization cannot be projected.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable

from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings
from app.db.database import SessionLocal
from app.localization.projection import apply_localizations_to_payload, requested_language


logger = logging.getLogger("app.localization.public")

_PATH_RESOURCE_TYPES: tuple[tuple[str, str], ...] = (
    ("/api/v1/creatures/", "creature"),
    ("/api/v1/items/", "item"),
    ("/api/v1/quests/", "quest"),
    ("/api/v1/npcs/", "npc"),
    ("/api/v1/locations/", "location"),
    ("/api/v1/hunt-zones/", "hunt_zone"),
)


def _resource_type(path: str) -> str | None:
    normalized = path if path.endswith("/") else f"{path}/"
    for prefix, resource_type in _PATH_RESOURCE_TYPES:
        if normalized.startswith(prefix):
            return resource_type
    return None


def _project_payload(resource_type: str, payload: dict, language: str) -> tuple[dict, int, tuple[str, ...]]:
    with SessionLocal() as db:
        localized, projection = apply_localizations_to_payload(
            db,
            resource_type=resource_type,
            payload=payload,
            requested=language,
        )
        return localized, len(projection.localized_fields), projection.applied_languages


def _vary_accept_language(headers: dict[str, str]) -> None:
    current = headers.get("vary", "")
    values = [value.strip() for value in current.split(",") if value.strip()]
    if not any(value.lower() == "accept-language" for value in values):
        values.append("Accept-Language")
    headers["vary"] = ", ".join(values)


class PublicLocalizationMiddleware(BaseHTTPMiddleware):
    """Overlay persisted localized fields for public detail JSON responses."""

    async def dispatch(self, request: Request, call_next: Callable):
        response = await call_next(request)
        if (
            not settings.LOCALIZATION_ENABLED
            or request.method != "GET"
            or response.status_code != 200
        ):
            return response

        resource_type = _resource_type(request.url.path)
        content_type = response.headers.get("content-type", "")
        if resource_type is None or "application/json" not in content_type.lower():
            return response

        chunks: list[bytes] = []
        async for chunk in response.body_iterator:
            chunks.append(chunk if isinstance(chunk, bytes) else str(chunk).encode("utf-8"))
        original_body = b"".join(chunks)
        headers = dict(response.headers)
        headers.pop("content-length", None)
        _vary_accept_language(headers)

        try:
            payload = json.loads(original_body)
            # Lists/search results intentionally remain language-neutral. Detail
            # payloads carry the prose fields and stable resource identity.
            if not isinstance(payload, dict):
                return Response(
                    content=original_body,
                    status_code=response.status_code,
                    headers=headers,
                    background=response.background,
                )

            language = requested_language(request, request.query_params.get("lang"))
            localized, field_count, applied_languages = await run_in_threadpool(
                _project_payload,
                resource_type,
                payload,
                language,
            )
            headers["X-Content-Language-Requested"] = language
            headers["X-Localized-Fields"] = str(field_count)
            if applied_languages:
                headers["X-Content-Language-Applied"] = ",".join(applied_languages)
            body = json.dumps(localized, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            return Response(
                content=body,
                status_code=response.status_code,
                headers=headers,
                background=response.background,
            )
        except Exception:
            logger.exception(
                "public_localization_projection_failed path=%s resource_type=%s",
                request.url.path,
                resource_type,
            )
            return Response(
                content=original_body,
                status_code=response.status_code,
                headers=headers,
                background=response.background,
            )
