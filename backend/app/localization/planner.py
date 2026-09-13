"""Plan translation jobs from provider-neutral canonical normalization data."""

from __future__ import annotations

from collections.abc import Iterator
from uuid import UUID

from sqlalchemy.orm import Session

from app.knowledge.adapters.protocol import KnowledgeNormalizationResult
from app.localization.queue import LocalizationQueueService


_TEXT_FIELDS: dict[str, tuple[str, ...]] = {
    "creature": ("description", "behavior", "strategy", "notes"),
    "item": ("description", "notes"),
    "quest": ("description", "summary"),
    "npc": ("title", "occupation", "location_text", "description"),
    "location": ("description", "access_notes"),
    "area": ("description", "access_notes"),
    "town": ("description", "access_notes"),
    "hunt_zone": ("description", "access_notes", "vocation_text"),
}
_REFERENCE_KEYS = {
    "canonical_name",
    "name",
    "item_name",
    "location_name",
    "destination_name",
    "parent_location",
    "city",
    "region",
}


def _source_language(data: dict) -> str:
    direct = data.get("language")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    metadata = data.get("provider_metadata")
    if isinstance(metadata, dict):
        value = metadata.get("language") or metadata.get("source_language")
        if isinstance(value, str) and value.strip():
            return value.strip()
    # Providers may add language metadata later. "auto" lets the translation
    # provider detect Portuguese/English without making the sync guess.
    return "auto"


def _collect_reference_terms(value, *, key: str | None = None) -> set[str]:
    terms: set[str] = set()
    if isinstance(value, dict):
        for child_key, child_value in value.items():
            if child_key in _REFERENCE_KEYS and isinstance(child_value, str) and child_value.strip():
                terms.add(child_value.strip())
            terms.update(_collect_reference_terms(child_value, key=child_key))
    elif isinstance(value, list):
        for child in value:
            terms.update(_collect_reference_terms(child, key=key))
    return terms


def _iter_translatable_fields(entity_type: str, data: dict) -> Iterator[tuple[str, str]]:
    for field_path in _TEXT_FIELDS.get(entity_type, ()):
        value = data.get(field_path)
        if isinstance(value, str) and value.strip():
            yield field_path, value.strip()

    if entity_type == "quest":
        for index, mission in enumerate(data.get("missions") or []):
            if not isinstance(mission, dict):
                continue
            identity = mission.get("external_id") or mission.get("sequence") or index
            description = mission.get("description")
            if isinstance(description, str) and description.strip():
                yield f"missions.{identity}.description", description.strip()
            for objective_index, objective in enumerate(mission.get("objectives") or []):
                if isinstance(objective, str) and objective.strip():
                    yield f"missions.{identity}.objectives.{objective_index}", objective.strip()


class LocalizationPlanningService:
    @staticmethod
    def plan_normalization(
        db: Session,
        *,
        result: KnowledgeNormalizationResult,
        entity_uuid: UUID | None,
        applied_status: str,
    ) -> int:
        if applied_status not in {"created", "updated"}:
            return 0
        candidate = result.candidate
        data = result.canonical_data
        if candidate is None or not isinstance(data, dict):
            return 0
        entity_type = candidate.entity_type
        fields = dict(_iter_translatable_fields(entity_type, data))
        if not fields:
            return 0

        protected = _collect_reference_terms(data)
        protected.add(candidate.canonical_name)
        protected.update(alias for alias in candidate.aliases if alias)
        resource_key = str(entity_uuid or result.external_id or candidate.language_neutral_id)
        return LocalizationQueueService.enqueue_targets(
            db,
            resource_type=entity_type,
            resource_key=resource_key,
            fields=fields,
            source_language=_source_language(data),
            entity_uuid=entity_uuid,
            protected_terms=tuple(sorted(protected, key=len, reverse=True)),
            context=f"Tibia {entity_type} knowledge: {candidate.canonical_name}",
        )
