"""Deterministic conversation-language and explicit-fact handling."""

from __future__ import annotations

import re

from app.assistant.schemas import AssistantConversationContext, AssistantLanguage
from app.services.text_utils import normalize_search_text


_SPANISH_MARKERS = {
    "como", "donde", "puedo", "tengo", "acceso", "llegar", "conseguir", "cazar",
    "misiones", "mision", "estoy", "nivel", "semillas",
}


def detect_language(message: str, fallback: AssistantLanguage = "en") -> AssistantLanguage:
    normalized = normalize_search_text(message)
    words = set(normalized.split())
    if words & _SPANISH_MARKERS or re.search(r"[¿¡]", message):
        return "es"
    if words & {"how", "where", "hunt", "access", "already", "get", "reach", "level"}:
        return "en"
    return fallback


def _clean_fact(value: str) -> str:
    return re.split(r"[?.!,;]|\b(?:and|but|y|pero)\b", value, maxsplit=1, flags=re.I)[0].strip(" '\"")[:255]


def _append_unique(values: list[str], value: str) -> None:
    cleaned = _clean_fact(value)
    if cleaned and normalize_search_text(cleaned) not in {normalize_search_text(item) for item in values}:
        values.append(cleaned)


class ConversationContextService:
    ACCESS_PATTERNS = (
        re.compile(r"\b(?:i (?:already )?have|i've got) access to\s+([^?.!,;]+)", re.I),
        re.compile(r"\b(?:ya )?tengo acceso a\s+([^?.!,;]+)", re.I),
    )
    QUEST_PATTERNS = (
        re.compile(r"\b(?:i (?:already )?(?:completed|finished)|i've completed)\s+([^?.!,;]+)", re.I),
        re.compile(r"\b(?:ya )?(?:complete|he completado|termine)\s+([^?.!,;]+)", re.I),
    )
    LOCATION_PATTERNS = (
        re.compile(r"\b(?:i am|i'm|im) (?:currently )?(?:in|at)\s+([^?.!,;]+)", re.I),
        re.compile(r"\b(?:estoy|me encuentro) (?:en|dentro de)\s+([^?.!,;]+)", re.I),
    )
    OWNED_ITEM_PATTERNS = (
        re.compile(r"\b(?:i (?:already )?(?:own|have)|i've got) (?:an? |the )?([^?.!,;]+?)\s+(?:item|in my depot|in my backpack)\b", re.I),
        re.compile(r"\b(?:ya )?tengo (?:el |la |los |las )?([^?.!,;]+?)\s+(?:en mi depot|en mi mochila)\b", re.I),
    )

    @classmethod
    def update(cls, context: AssistantConversationContext | None, message: str) -> AssistantConversationContext:
        value = context.model_copy(deep=True) if context else AssistantConversationContext()
        value.language = detect_language(message, value.language)
        for pattern in cls.ACCESS_PATTERNS:
            if match := pattern.search(message):
                _append_unique(value.known_access_unlocks, match.group(1))
        for pattern in cls.QUEST_PATTERNS:
            if match := pattern.search(message):
                _append_unique(value.completed_quests, match.group(1))
        for pattern in cls.OWNED_ITEM_PATTERNS:
            if match := pattern.search(message):
                _append_unique(value.owned_items, match.group(1))
        for pattern in cls.LOCATION_PATTERNS:
            if match := pattern.search(message):
                value.current_location = _clean_fact(match.group(1)) or value.current_location

        normalized = normalize_search_text(message)
        level_match = re.search(r"\b(?:level|nivel)\s*(\d{1,4})\b", normalized)
        if level_match:
            value.character.level = max(1, min(5000, int(level_match.group(1))))
        vocation_map = {
            "knight": "knight", "elite knight": "elite knight", "caballero": "knight",
            "paladin": "paladin", "royal paladin": "royal paladin",
            "sorcerer": "sorcerer", "master sorcerer": "master sorcerer", "hechicero": "sorcerer",
            "druid": "druid", "elder druid": "elder druid", "druida": "druid",
            "monk": "monk", "exalted monk": "exalted monk", "monje": "monk",
        }
        for candidate in sorted(vocation_map, key=len, reverse=True):
            if re.search(rf"\b{re.escape(candidate)}\b", normalized):
                value.character.vocation = vocation_map[candidate]
                break
        return value

    @staticmethod
    def knows_access(context: AssistantConversationContext, name: str) -> bool:
        target = normalize_search_text(name)
        return any(
            target == normalize_search_text(value)
            or target in normalize_search_text(value)
            or normalize_search_text(value) in target
            for value in context.known_access_unlocks
        )
