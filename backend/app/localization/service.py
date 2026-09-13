"""Translation orchestration, locale fallback, term protection, and persistence."""

from __future__ import annotations

import hashlib
import re
from uuid import UUID

from sqlalchemy.orm import Session

from app.knowledge.models import KnowledgeLocalization
from app.localization.provider import TranslationProvider, TranslationRequest


_TERM_TOKEN = "[[TH_TERM_{index:04d}]]"


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

        # An approved translation remains human-owned even after it becomes stale.
        # approved_at is retained when status changes to stale so later retries cannot
        # silently replace the previously approved text.
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

        if existing is None:
            existing = KnowledgeLocalization(
                entity_uuid=entity_uuid,
                resource_type=resource_type,
                resource_key=resource_key,
                field_path=field_path,
                language=target_language,
                text=translated_text,
                source_language=source_language,
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
            existing.source_language = source_language
            existing.source_text_hash = digest
            existing.origin = "machine"
            existing.status = "generated"
            existing.provider = result.provider
            existing.provider_model = result.model
            existing.provider_metadata = result.metadata

        db.flush()
        return existing
