"""Plan translation jobs from provider-neutral canonical normalization data."""

from __future__ import annotations

from collections.abc import Iterator
from uuid import UUID

from sqlalchemy.orm import Session

from app.knowledge.adapters.protocol import KnowledgeNormalizationResult
from app.localization.queue import LocalizationQueueService


# (canonical source field, public localization field path). Keeping these
# separate lets provider DTOs remain provider-neutral while the stored
# localization targets the shape actually rendered by TibiaHub.
_TEXT_FIELDS: dict[str, tuple[tuple[str, str], ...]] = {
    "creature": (
        ("description", "description"),
        ("behavior", "behavior"),
        ("strategy", "strategy"),
        ("notes", "notes"),
    ),
    "item": (("description", "description"), ("notes", "notes")),
    "quest": (("description", "description"), ("summary", "summary")),
    "npc": (("title", "title"), ("occupation", "occupation"), ("description", "description")),
    "location": (("description", "description"), ("access_notes", "access_notes")),
    "area": (("description", "description"), ("access_notes", "access_notes")),
    "town": (("description", "description"), ("access_notes", "access_notes")),
    # Hunt Zone access notes are exposed inside the public `access` object.
    # `vocation_text` is intentionally omitted until it has a public prose
    # surface; translating invisible canonical metadata only burns tokens.
    "hunt_zone": (("description", "description"), ("access_notes", "access.notes")),
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
    for source_field, public_field_path in _TEXT_FIELDS.get(entity_type, ()):
        value = data.get(source_field)
        if isinstance(value, str) and value.strip():
            yield public_field_path, value.strip()

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
        # Areas and towns are persisted/read through the public Location family,
        # so their localized prose must use the same resource namespace.
        resource_type = "location" if entity_type in {"location", "area", "town"} else entity_type
        return LocalizationQueueService.enqueue_targets(
            db,
            resource_type=resource_type,
            resource_key=resource_key,
            fields=fields,
            source_language=_source_language(data),
            entity_uuid=entity_uuid,
            protected_terms=tuple(sorted(protected, key=len, reverse=True)),
            context=f"Tibia {entity_type} knowledge: {candidate.canonical_name}",
        )
