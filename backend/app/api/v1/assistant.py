"""Thin public endpoint for the bounded, grounded TibiaHub Assistant."""

from __future__ import annotations

import asyncio
import threading
import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.assistant.entities import FabricatedEntityReferenceError
from app.assistant.openai_provider import OpenAIAssistantProvider
from app.assistant.provider import AssistantProvider, AssistantProviderError
from app.assistant.schemas import AssistantLanguage, AssistantRequest, AssistantResponse, AssistantSuggestion
from app.assistant.service import AssistantService
from app.assistant.suggestions import build_assistant_suggestions
from app.core.config import settings
from app.db.database import get_db


router = APIRouter(prefix="/assistant", tags=["TibiaHub Assistant"])


class _AssistantThrottle:
    """Small per-process limiter for the public V1 endpoint."""

    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, *, limit: int, window_seconds: int) -> int | None:
        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= limit:
                return max(1, int(window_seconds - (now - events[0])))
            events.append(now)
            if len(self._events) > 5000:
                for old_key in list(self._events)[:1000]:
                    if not self._events[old_key] or self._events[old_key][-1] <= cutoff:
                        self._events.pop(old_key, None)
            return None


_throttle = _AssistantThrottle()


def get_assistant_provider() -> AssistantProvider:
    class LazyOpenAIAssistantProvider:
        """Delay key validation/client creation until routing needs the model."""

        async def generate(self, provider_request):
            key = settings.OPENAI_API_KEY.get_secret_value() if settings.OPENAI_API_KEY else ""
            if not key:
                raise HTTPException(status_code=503, detail={"code": "assistant_not_configured"})
            provider = OpenAIAssistantProvider(
                api_key=key,
                model=settings.ASSISTANT_MODEL,
                timeout_seconds=settings.ASSISTANT_TIMEOUT_SECONDS,
                max_output_tokens=settings.ASSISTANT_MAX_OUTPUT_TOKENS,
            )
            return await provider.generate(provider_request)

    return LazyOpenAIAssistantProvider()


@router.get("/suggestions", response_model=list[AssistantSuggestion])
def get_assistant_suggestions(
    language: AssistantLanguage = "en",
    limit: int = Query(8, ge=3, le=12),
    db: Session = Depends(get_db),
) -> list[AssistantSuggestion]:
    """Return bounded prompts made only from canonical local entity names."""
    return build_assistant_suggestions(db, language=language, limit=limit)


@router.post("/", response_model=AssistantResponse)
async def ask_assistant(
    payload: AssistantRequest,
    request: Request,
    db: Session = Depends(get_db),
    provider: AssistantProvider = Depends(get_assistant_provider),
) -> AssistantResponse:
    if not settings.ASSISTANT_ENABLED:
        raise HTTPException(status_code=503, detail={"code": "assistant_disabled"})
    if len(payload.message) > settings.ASSISTANT_MAX_MESSAGE_CHARS:
        raise HTTPException(status_code=422, detail={"code": "assistant_message_too_long", "max_chars": settings.ASSISTANT_MAX_MESSAGE_CHARS})
    if len(payload.history) > settings.ASSISTANT_MAX_HISTORY_MESSAGES:
        raise HTTPException(status_code=422, detail={"code": "assistant_history_too_long", "max_messages": settings.ASSISTANT_MAX_HISTORY_MESSAGES})

    client = request.client.host if request.client else "unknown"
    conversation = str(payload.context.conversation_id) if payload.context else request.headers.get("x-assistant-session", "new")[:128]
    retry_after = _throttle.check(
        f"{client}:{conversation}", limit=settings.ASSISTANT_RATE_LIMIT_REQUESTS,
        window_seconds=settings.ASSISTANT_RATE_LIMIT_WINDOW_SECONDS,
    )
    if retry_after is not None:
        raise HTTPException(status_code=429, headers={"Retry-After": str(retry_after)}, detail={"code": "assistant_rate_limited"})

    service = AssistantService(
        db, provider, max_tool_calls=settings.ASSISTANT_MAX_TOOL_CALLS,
        max_history_messages=settings.ASSISTANT_MAX_HISTORY_MESSAGES,
    )
    try:
        async with asyncio.timeout(settings.ASSISTANT_TIMEOUT_SECONDS):
            return await service.answer(payload)
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail={"code": "assistant_timeout"}) from exc
    except FabricatedEntityReferenceError as exc:
        raise HTTPException(status_code=502, detail={"code": "assistant_grounding_rejected"}) from exc
    except AssistantProviderError as exc:
        raise HTTPException(status_code=502, detail={"code": "assistant_provider_unavailable"}) from exc
