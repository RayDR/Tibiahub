"""Translation provider construction from runtime settings."""

from app.core.config import settings
from app.localization.openai_provider import OpenAITranslationProvider
from app.localization.provider import TranslationProvider, TranslationProviderError


def build_translation_provider() -> TranslationProvider:
    if settings.LOCALIZATION_PROVIDER != "openai":
        raise TranslationProviderError("Unsupported localization provider")
    if settings.OPENAI_API_KEY is None:
        raise TranslationProviderError("OPENAI_API_KEY is not configured")
    return OpenAITranslationProvider(
        api_key=settings.OPENAI_API_KEY.get_secret_value(),
        model=settings.LOCALIZATION_MODEL,
        timeout_seconds=settings.LOCALIZATION_TIMEOUT_SECONDS,
    )
