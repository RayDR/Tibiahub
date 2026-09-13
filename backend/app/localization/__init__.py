"""TibiaHub content localization services."""

from app.localization.provider import (
    TranslationProvider,
    TranslationProviderError,
    TranslationRequest,
    TranslationResult,
)
from app.localization.service import (
    ContentLocalizationService,
    ContentTranslationService,
    LocalizedText,
    language_fallbacks,
    normalize_language_tag,
    protect_terms,
    restore_terms,
    source_text_hash,
)

__all__ = [
    "TranslationProvider",
    "TranslationProviderError",
    "TranslationRequest",
    "TranslationResult",
    "ContentLocalizationService",
    "ContentTranslationService",
    "LocalizedText",
    "language_fallbacks",
    "normalize_language_tag",
    "protect_terms",
    "restore_terms",
    "source_text_hash",
]
