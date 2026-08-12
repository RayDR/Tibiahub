"""Cheap deterministic routing decisions made before any model invocation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from app.services.text_utils import normalize_search_text


DirectMatchMode = Literal["exact", "prefix", "contains"]
StructuredIntent = Literal["item_acquisition", "creature_hunting", "quest_requirements", "access"]


@dataclass(frozen=True)
class QueryQuality:
    normalized: str
    direct_match_mode: DirectMatchMode | None
    reject_without_lookup: bool = False


@dataclass(frozen=True)
class StructuredQuery:
    intent: StructuredIntent
    target: str


_STRUCTURED_PATTERNS: tuple[tuple[StructuredIntent, re.Pattern[str]], ...] = (
    ("item_acquisition", re.compile(r"^(?:loot|drops?|drop de|loot de)\s+(.+)$")),
    ("item_acquisition", re.compile(r"^(.+?)\s+drops?$")),
    ("creature_hunting", re.compile(r"^(?:hunt|spawns?|spawn de|donde hunt)\s+(.+)$")),
    ("creature_hunting", re.compile(r"^(.+?)\s+hunt$")),
    ("quest_requirements", re.compile(r"^(?:requirements?|requirements for|requisitos?|req)(?:\s+(?:for|de))?\s+(.+)$")),
    ("access", re.compile(r"^(?:access|acceso)(?:\s+(?:to|a|de))?\s+(.+)$")),
)


def assess_query_quality(message: str) -> QueryQuality:
    normalized = normalize_search_text(message)
    meaningful = normalized.replace(" ", "")
    if not meaningful:
        return QueryQuality(normalized="", direct_match_mode=None, reject_without_lookup=True)
    if len(meaningful) > 1 and len(set(meaningful)) == 1:
        return QueryQuality(normalized=normalized, direct_match_mode=None, reject_without_lookup=True)
    if len(meaningful) <= 2:
        return QueryQuality(normalized=normalized, direct_match_mode="exact")
    if len(meaningful) == 3:
        return QueryQuality(normalized=normalized, direct_match_mode="prefix")
    return QueryQuality(normalized=normalized, direct_match_mode="contains")


def parse_structured_query(message: str) -> StructuredQuery | None:
    normalized = normalize_search_text(message)
    for intent, pattern in _STRUCTURED_PATTERNS:
        match = pattern.fullmatch(normalized)
        if match:
            target = match.group(1).strip()
            if len(target.replace(" ", "")) >= 3:
                return StructuredQuery(intent=intent, target=target)
    return None
