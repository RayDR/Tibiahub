"""Model-provider boundary for the assistant orchestration service."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from app.assistant.schemas import AssistantProviderRequest, AssistantProviderTurn


class AssistantProviderError(RuntimeError):
    pass


class AssistantProviderFormatError(AssistantProviderError):
    pass


class AssistantProvider(Protocol):
    async def generate(self, request: AssistantProviderRequest) -> AssistantProviderTurn: ...


class ScriptedAssistantProvider:
    """Deterministic provider for tests and the unpaid smoke path."""

    def __init__(self, turns: Iterable[AssistantProviderTurn]):
        self.turns = list(turns)
        self.requests: list[AssistantProviderRequest] = []

    async def generate(self, request: AssistantProviderRequest) -> AssistantProviderTurn:
        self.requests.append(request)
        if not self.turns:
            raise AssistantProviderError("Fake provider has no remaining scripted turn")
        return self.turns.pop(0)
