"""Apply stored localizations to public API payloads without provider calls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import Request, Response
from sqlalchemy.orm import Session

from app.core.config import settings
from app.knowledge.models import KnowledgeLocalization
from app.localization.service import language_fallbacks, normalize_language_tag


@dataclass(frozen=True, slots=True)
class LocalizationProjection:
    requested_language: str
    source_language: str
    localized_fields: tuple[str, ...]
    applied_languages: tuple[str, ...]

    @property
    def used_localization(self) -> bool:
        return bool(self.localized_fields)


def requested_language(request: Request, explicit: str | None = None) -> str:
    """Resolve `lang` first, then the highest-priority Accept-Language tag."""
    normalized = normalize_language_tag(explicit)
    if normalized:
        return normalized
    header = request.headers.get("accept-language", "")
    candidates: list[tuple[float, int, str]] = []
    for index, raw in enumerate(header.split(",")):
        value = raw.strip()
        if not value:
            continue
        parts = [part.strip() for part in value.split(";") if part.strip()]
        tag = normalize_language_tag(parts[0])
        if not tag or tag == "*":
            continue
        quality = 1.0
        for parameter in parts[1:]:
            if parameter.startswith("q="):
                try:
                    quality = float(parameter[2:])
                except ValueError:
                    quality = 0.0
        if quality > 0:
            candidates.append((quality, -index, tag))
    if candidates:
        candidates.sort(reverse=True)
        return candidates[0][2]
    return normalize_language_tag(settings.LOCALIZATION_DEFAULT_LANGUAGE) or "en"


def source_language_for_row(row: Any) -> str:
    """Use provider metadata when present; otherwise use configured canonical default."""
    for attribute in ("provider_metadata", "parser_metadata", "raw_data"):
        metadata = getattr(row, attribute, None)
        if not isinstance(metadata, dict):
            continue
        value = metadata.get("language") or metadata.get("source_language")
        normalized = normalize_language_tag(value if isinstance(value, str) else None)
        if normalized:
            return normalized
    return normalize_language_tag(settings.LOCALIZATION_DEFAULT_LANGUAGE) or "en"


def resource_key_for_row(row: Any) -> str:
    entity_uuid = getattr(row, "knowledge_entity_id", None)
    if entity_uuid is not None:
        return str(entity_uuid)
    external_id = getattr(row, "external_id", None)
    if external_id not in (None, ""):
        return str(external_id)
    return str(getattr(row, "id"))


def resource_key_for_payload(payload: dict[str, Any]) -> str | None:
    """Resolve the same stable key used by sync/backfill from a public payload."""
    for key in ("canonical_id", "knowledge_entity_id", "external_id", "id"):
        value = payload.get(key)
        if value not in (None, ""):
            return str(value)
    return None


def source_language_for_payload(payload: dict[str, Any]) -> str:
    for key in ("source_language", "language"):
        value = payload.get(key)
        normalized = normalize_language_tag(value if isinstance(value, str) else None)
        if normalized:
            return normalized
    for key in ("provider_metadata", "parser_metadata", "raw_data"):
        metadata = payload.get(key)
        if not isinstance(metadata, dict):
            continue
        value = metadata.get("language") or metadata.get("source_language")
        normalized = normalize_language_tag(value if isinstance(value, str) else None)
        if normalized:
            return normalized
    return normalize_language_tag(settings.LOCALIZATION_DEFAULT_LANGUAGE) or "en"


def _mission_matches(mission: dict[str, Any], identity: str) -> bool:
    return str(mission.get("external_id") or "") == identity or str(mission.get("sequence") or "") == identity


def _apply_field_path(payload: dict[str, Any], field_path: str, text: str) -> bool:
    if "." not in field_path:
        if field_path not in payload:
            return False
        payload[field_path] = text
        return True

    parts = field_path.split(".")
    if len(parts) >= 3 and parts[0] == "missions":
        missions = payload.get("missions")
        if not isinstance(missions, list):
            return False
        mission = next(
            (candidate for candidate in missions if isinstance(candidate, dict) and _mission_matches(candidate, parts[1])),
            None,
        )
        if mission is None:
            return False
        if parts[2] == "description" and len(parts) == 3:
            mission["description"] = text
            return True
        if parts[2] == "objectives" and len(parts) == 4:
            objectives = mission.get("objectives")
            if not isinstance(objectives, list):
                return False
            try:
                index = int(parts[3])
            except ValueError:
                return False
            if not 0 <= index < len(objectives):
                return False
            objectives[index] = text
            return True

    current: Any = payload
    for part in parts[:-1]:
        if not isinstance(current, dict) or part not in current:
            return False
        current = current[part]
    if not isinstance(current, dict) or parts[-1] not in current:
        return False
    current[parts[-1]] = text
    return True


def _select_localizations(
    db: Session,
    *,
    resource_type: str,
    resource_key: str,
    requested: str,
    source_language: str,
) -> dict[str, KnowledgeLocalization]:
    fallbacks = language_fallbacks(requested, default=source_language)
    rows = (
        db.query(KnowledgeLocalization)
        .filter(
            KnowledgeLocalization.resource_type == resource_type,
            KnowledgeLocalization.resource_key == resource_key,
            KnowledgeLocalization.language.in_(fallbacks),
            KnowledgeLocalization.status.in_(["generated", "reviewed", "approved"]),
        )
        .all()
    )
    rank = {language: index for index, language in enumerate(fallbacks)}
    selected: dict[str, KnowledgeLocalization] = {}
    for localization in rows:
        current = selected.get(localization.field_path)
        if current is None or rank.get(localization.language, 999) < rank.get(current.language, 999):
            selected[localization.field_path] = localization
    return selected


def apply_localizations(
    db: Session,
    *,
    row: Any,
    resource_type: str,
    payload: dict[str, Any],
    requested: str,
) -> tuple[dict[str, Any], LocalizationProjection]:
    """Overlay current localized fields on an already-built response payload."""
    requested = normalize_language_tag(requested) or settings.LOCALIZATION_DEFAULT_LANGUAGE
    source_language = source_language_for_row(row)
    if not settings.LOCALIZATION_ENABLED or requested == source_language:
        return payload, LocalizationProjection(requested, source_language, (), ())

    selected = _select_localizations(
        db,
        resource_type=resource_type,
        resource_key=resource_key_for_row(row),
        requested=requested,
        source_language=source_language,
    )
    localized_fields: list[str] = []
    languages: list[str] = []
    for field_path, localization in selected.items():
        if _apply_field_path(payload, field_path, localization.text):
            localized_fields.append(field_path)
            if localization.language not in languages:
                languages.append(localization.language)

    return payload, LocalizationProjection(
        requested_language=requested,
        source_language=source_language,
        localized_fields=tuple(sorted(localized_fields)),
        applied_languages=tuple(languages),
    )


def apply_localizations_to_payload(
    db: Session,
    *,
    resource_type: str,
    payload: dict[str, Any],
    requested: str,
) -> tuple[dict[str, Any], LocalizationProjection]:
    """Overlay translations using only stable identity present in a public payload."""
    requested = normalize_language_tag(requested) or settings.LOCALIZATION_DEFAULT_LANGUAGE
    source_language = source_language_for_payload(payload)
    resource_key = resource_key_for_payload(payload)
    if not settings.LOCALIZATION_ENABLED or resource_key is None or requested == source_language:
        return payload, LocalizationProjection(requested, source_language, (), ())

    selected = _select_localizations(
        db,
        resource_type=resource_type,
        resource_key=resource_key,
        requested=requested,
        source_language=source_language,
    )
    localized_fields: list[str] = []
    languages: list[str] = []
    for field_path, localization in selected.items():
        if _apply_field_path(payload, field_path, localization.text):
            localized_fields.append(field_path)
            if localization.language not in languages:
                languages.append(localization.language)
    return payload, LocalizationProjection(
        requested_language=requested,
        source_language=source_language,
        localized_fields=tuple(sorted(localized_fields)),
        applied_languages=tuple(languages),
    )


def set_localization_headers(response: Response, projection: LocalizationProjection) -> None:
    response.headers["X-Content-Language-Requested"] = projection.requested_language
    response.headers["X-Content-Language-Source"] = projection.source_language
    response.headers["X-Localized-Fields"] = str(len(projection.localized_fields))
    if projection.applied_languages:
        response.headers["X-Content-Language-Applied"] = ",".join(projection.applied_languages)
