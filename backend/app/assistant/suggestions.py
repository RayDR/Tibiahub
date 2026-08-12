"""Deterministic, local-only starter suggestions for the public Assistant."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.assistant.schemas import AssistantLanguage, AssistantSuggestion
from app.models.creature import Creature
from app.models.external_data import Item, TibiaWikiQuest
from app.models.hunt_zone import HuntZone
from app.services.entity_metadata_service import EntityMetadataService
from app.services.text_utils import normalize_search_text


ENTITY_TYPES = ("creature", "item", "quest", "hunt_zone")
MODEL_BY_TYPE = {
    "creature": Creature,
    "item": Item,
    "quest": TibiaWikiQuest,
    "hunt_zone": HuntZone,
}
FALLBACK_NAMES = {
    "creature": "Werewolves",
    "item": "Ice Flower Seeds",
    "quest": "The Inquisition Quest",
    "hunt_zone": "Roshamuul",
}


def _prompt(entity_type: str, name: str, language: AssistantLanguage) -> str:
    templates = {
        "en": {
            "creature": "Where can I hunt {name}?",
            "item": "How can I get {name}?",
            "quest": "What do I need to start {name}?",
            "hunt_zone": "How do I get to {name}?",
        },
        "es": {
            "creature": "¿Dónde puedo cazar {name}?",
            "item": "¿Cómo puedo conseguir {name}?",
            "quest": "¿Qué necesito para comenzar {name}?",
            "hunt_zone": "¿Cómo llego a {name}?",
        },
    }
    return templates[language][entity_type].format(name=name)


def build_assistant_suggestions(
    db: Session,
    *,
    language: AssistantLanguage,
    limit: int,
) -> list[AssistantSuggestion]:
    """Interleave real popularity by entity type, then fill gaps predictably."""
    popular: dict[str, list[str]] = {entity_type: [] for entity_type in ENTITY_TYPES}
    for entity_type in ENTITY_TYPES:
        metadata_rows = EntityMetadataService.get_popular(db, entity_type=entity_type, limit=3)
        entity_ids = [row.entity_id for row in metadata_rows if row.entity_id is not None]
        model = MODEL_BY_TYPE[entity_type]
        canonical_rows = db.query(model).filter(model.id.in_(entity_ids)).all() if entity_ids else []
        canonical_by_id = {row.id: row for row in canonical_rows}
        for metadata in metadata_rows:
            row = canonical_by_id.get(metadata.entity_id)
            if row is None or not getattr(row, "name", None):
                continue
            if entity_type == "quest" and bool(getattr(row, "is_group", False)):
                continue
            name = str(row.name).strip() or None
            if name and name not in popular[entity_type]:
                popular[entity_type].append(name)

    suggestions: list[AssistantSuggestion] = []
    for rank in range(3):
        for entity_type in ENTITY_TYPES:
            names = popular[entity_type]
            if rank >= len(names):
                continue
            name = names[rank]
            suggestions.append(AssistantSuggestion(
                id=f"popular:{entity_type}:{normalize_search_text(name)}",
                text=_prompt(entity_type, name, language),
                entity_type=entity_type,
                entity_name=name,
                source="popular",
            ))
            if len(suggestions) == limit:
                return suggestions

    for entity_type in ENTITY_TYPES:
        name = FALLBACK_NAMES[entity_type]
        if any(row.entity_type == entity_type and row.entity_name == name for row in suggestions):
            continue
        suggestions.append(AssistantSuggestion(
            id=f"fallback:{entity_type}:{normalize_search_text(name)}",
            text=_prompt(entity_type, name, language),
            entity_type=entity_type,
            entity_name=name,
            source="fallback",
        ))
        if len(suggestions) == limit:
            break
    return suggestions
