"""Provider-neutral translation contract for TibiaHub content."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


class TranslationProviderError(RuntimeError):
    """Safe provider error that callers may log without leaking credentials."""


@dataclass(frozen=True, slots=True)
class TranslationRequest:
    text: str
    target_language: str
    source_language: str | None = None
    protected_terms: tuple[str, ...] = ()
    context: str | None = None


@dataclass(frozen=True, slots=True)
class TranslationResult:
    text: str
    source_language: str
    target_language: str
    provider: str
    model: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)


class TranslationProvider(Protocol):
    async def translate(self, request: TranslationRequest) -> TranslationResult:
        """Translate one content field without mutating application state."""
        ...
