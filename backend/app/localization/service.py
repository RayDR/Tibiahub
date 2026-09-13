"""Translation orchestration, locale fallback, term protection, and persistence."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.knowledge.models import KnowledgeLocalization
from app.localization.provider import TranslationProvider, TranslationRequest


_TERM_TOKEN = "[[TH_TERM_{index:04d}]]"


@dataclass(frozen=True, slots=True)
class LocalizedText:
    text: str
    language: str
    status: str
    origin: str
    used_fallback: bool


def normalize_language_tag(value: str | None) -> str | None:
    if not value:
        return None
    parts = value.strip().replace("_", "-").split("-")
    if not parts or not parts[0]:
        return None
    normalized = [parts[0].lower()]
    for part in parts[1:]:
        if len(part) == 2 and part.isalpha():
            normalized.append(part.upper())
        else:
            normalized.append(part)
    return "-".join(normalized)


def language_fallbacks(requested: str | None, *, default: str = "en") -> list[str]:
    requested = normalize_language_tag(requested) or normalize_language_tag(default) or "en"
    values = [requested]
    if "-" in requested:
        values.append(requested.split("-", 1)[0])
    default = normalize_language_tag(default) or "en"
    if default not in values:
        values.append(default)
    return values


def source_text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def protect_terms(text: str, terms: tuple[str, ...]) -> tuple[str, dict[str, str]]:
    protected = text
    replacements: dict[str, str] = {}
    unique_terms = sorted({term.strip() for term in terms if term and term.strip()}, key=len, reverse=True)
    for index, term in enumerate(unique_terms):
        token = _TERM_TOKEN.format(index=index)
        pattern = re.compile(re.escape(term), flags=re.IGNORECASE)
        if not pattern.search(protected):
            continue
        replacements[token] = term
        protected = pattern.sub(token, protected)
    return protected, replacements


def restore_terms(text: str, replacements: dict[str, str]) -> str:
    restored = text
    for token, term in replacements.items():
        restored = restored.replace(token, term)
    return restored


class ContentLocalizationService:
    """Read and human-review operations independent of any translation provider."""

    @staticmethod
    def resolve_text(
        db: Session,
        *,
        resource_type: str,
        resource_key: str,
        field_path: str,
        source_text: str | None,
        source_language: str,
        requested_language: str | None,
        default_language: str = "en",
    ) -> LocalizedText | None:
        if source_text is None:
            return None
        source_language = normalize_language_tag(source_language) or source_language
        requested = normalize_language_tag(requested_language) or normalize_language_tag(default_language) or "en"
        if requested == source_language:
            return LocalizedText(source_text, source_language, "source", "provider", False)

        fallbacks = language_fallbacks(requested, default=default_language)
        rows = (
            db.query(KnowledgeLocalization)
            .filter(
                KnowledgeLocalization.resource_type == resource_type,
                KnowledgeLocalization.resource_key == resource_key,
                KnowledgeLocalization.field_path == field_path,
                KnowledgeLocalization.language.in_(fallbacks),
                KnowledgeLocalization.status.in_(["generated", "reviewed", "approved"]),
            )
            .all()
        )
        by_language = {row.language: row for row in rows}
        for language in fallbacks:
            row = by_language.get(language)
            if row is not None:
                return LocalizedText(
                    row.text,
                    row.language,
                    row.status,
                    row.origin,
                    row.language != requested,
                )
            if language == source_language:
                return LocalizedText(source_text, source_language, "source", "provider", language != requested)
        return LocalizedText(source_text, source_language, "source", "provider", source_language != requested)

    @staticmethod
    def review(
        db: Session,
        localization: KnowledgeLocalization,
        *,
        reviewer_id: int,
        text: str | None = None,
        lock: bool | None = None,
    ) -> KnowledgeLocalization:
        if localization.status == "failed":
            raise ValueError("failed localization cannot be reviewed")
        if text is not None:
            clean = text.strip()
            if not clean:
                raise ValueError("localized text cannot be empty")
            localization.text = clean
            localization.origin = "human"
        localization.status = "reviewed"
        localization.reviewed_by_id = reviewer_id
        localization.reviewed_at = datetime.now(UTC)
        if lock is not None:
            localization.locked = lock
        db.flush()
        return localization

    @staticmethod
    def approve(
        db: Session,
        localization: KnowledgeLocalization,
        *,
        reviewer_id: int,
        text: str | None = None,
    ) -> KnowledgeLocalization:
        ContentLocalizationService.review(
            db,
            localization,
            reviewer_id=reviewer_id,
            text=text,
            lock=True,
        )
        now = datetime.now(UTC)
        localization.status = "approved"
        localization.approved_by_id = reviewer_id
        localization.approved_at = now
        localization.reviewed_by_id = reviewer_id
        localization.reviewed_at = now
        localization.locked = True
        db.flush()
        return localization

    @staticmethod
    def unlock_for_regeneration(
        db: Session,
        localization: KnowledgeLocalization,
    ) -> KnowledgeLocalization:
        localization.locked = False
        localization.approved_by_id = None
        localization.approved_at = None
        if localization.status == "approved":
            localization.status = "reviewed"
        db.flush()
        return localization


class ContentTranslationService:
    def __init__(self, provider: TranslationProvider):
        self.provider = provider

    async def translate_and_store(
        self,
        db: Session,
        *,
        resource_type: str,
        resource_key: str,
        field_path: str,
        source_text: str,
        source_language: str,
        target_language: str,
        entity_uuid: UUID | None = None,
        protected_terms: tuple[str, ...] = (),
        context: str | None = None,
    ) -> KnowledgeLocalization:
        source_language = normalize_language_tag(source_language) or source_language
        target_language = normalize_language_tag(target_language) or target_language
        digest = source_text_hash(source_text)

        existing = (
            db.query(KnowledgeLocalization)
            .filter(
                KnowledgeLocalization.resource_type == resource_type,
                KnowledgeLocalization.resource_key == resource_key,
                KnowledgeLocalization.field_path == field_path,
                KnowledgeLocalization.language == target_language,
            )
            .first()
        )

        if existing and existing.source_text_hash == digest and existing.status not in {"failed", "stale"}:
            return existing

        human_protected = bool(
            existing
            and (
                existing.locked
                or existing.status == "approved"
                or existing.approved_at is not None
            )
        )
        if existing and human_protected:
            existing.status = "stale"
            existing.source_text_hash = digest
            existing.source_language = source_language
            db.flush()
            return existing

        masked_text, replacements = protect_terms(source_text, protected_terms)
        result = await self.provider.translate(
            TranslationRequest(
                text=masked_text,
                source_language=source_language,
                target_language=target_language,
                protected_terms=tuple(replacements),
                context=context,
            )
        )
        translated_text = restore_terms(result.text, replacements)
        detected_source_language = normalize_language_tag(result.source_language) or result.source_language or source_language

        if existing is None:
            existing = KnowledgeLocalization(
                entity_uuid=entity_uuid,
                resource_type=resource_type,
                resource_key=resource_key,
                field_path=field_path,
                language=target_language,
                text=translated_text,
                source_language=detected_source_language,
                source_text_hash=digest,
                origin="machine",
                status="generated",
                provider=result.provider,
                provider_model=result.model,
                provider_metadata=result.metadata,
            )
            db.add(existing)
        else:
            existing.entity_uuid = entity_uuid or existing.entity_uuid
            existing.text = translated_text
            existing.source_language = detected_source_language
            existing.source_text_hash = digest
            existing.origin = "machine"
            existing.status = "generated"
            existing.provider = result.provider
            existing.provider_model = result.model
            existing.provider_metadata = result.metadata
            existing.reviewed_by_id = None
            existing.reviewed_at = None

        db.flush()
        return existing
