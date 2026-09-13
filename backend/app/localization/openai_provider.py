"""OpenAI Responses API translation provider."""

from __future__ import annotations

import json

import httpx

from app.localization.provider import (
    TranslationProviderError,
    TranslationRequest,
    TranslationResult,
)


class OpenAITranslationProvider:
    endpoint = "https://api.openai.com/v1/responses"

    def __init__(self, *, api_key: str, model: str = "gpt-5-mini", timeout_seconds: int = 45):
        if not api_key:
            raise TranslationProviderError("OPENAI_API_KEY is not configured")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds

    async def translate(self, request: TranslationRequest) -> TranslationResult:
        source_language = request.source_language or "auto"
        context = request.context or "Tibia game knowledge content"
        payload = {
            "model": self.model,
            "store": False,
            "instructions": (
                "Translate TibiaHub knowledge content faithfully. Preserve game proper nouns, item names, "
                "creature names, NPC names, quest names, numbers, URLs, markup, and every token matching "
                "[[TH_TERM_####]] exactly. Do not add commentary, omit facts, or invent information. "
                "Use natural terminology for the target language while keeping Tibia-specific terms stable."
            ),
            "input": (
                f"Source language: {source_language}\n"
                f"Target language: {request.target_language}\n"
                f"Context: {context}\n\n"
                f"Text:\n{request.text}"
            ),
            "max_output_tokens": 4000,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "tibiahub_translation",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "translated_text": {"type": "string"},
                            "detected_source_language": {"type": "string"},
                        },
                        "required": ["translated_text", "detected_source_language"],
                        "additionalProperties": False,
                    },
                }
            },
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    self.endpoint,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
            response.raise_for_status()
            body = response.json()
        except httpx.TimeoutException as exc:
            raise TranslationProviderError("Translation request timed out") from exc
        except httpx.HTTPStatusError as exc:
            raise TranslationProviderError(
                f"Translation request failed with HTTP {exc.response.status_code}"
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise TranslationProviderError("Translation request failed") from exc

        output_text = body.get("output_text")
        if not isinstance(output_text, str):
            fragments: list[str] = []
            for item in body.get("output") or []:
                if not isinstance(item, dict) or item.get("type") != "message":
                    continue
                for content in item.get("content") or []:
                    if isinstance(content, dict) and isinstance(content.get("text"), str):
                        fragments.append(content["text"])
            output_text = "".join(fragments)

        try:
            parsed = json.loads(output_text)
            translated_text = parsed["translated_text"]
            detected = parsed["detected_source_language"]
        except (TypeError, KeyError, ValueError, json.JSONDecodeError) as exc:
            raise TranslationProviderError("Translation provider returned invalid structured output") from exc

        if not isinstance(translated_text, str) or not translated_text.strip():
            raise TranslationProviderError("Translation provider returned empty text")

        return TranslationResult(
            text=translated_text,
            source_language=str(detected or source_language),
            target_language=request.target_language,
            provider="openai",
            model=self.model,
            metadata={"response_id": body.get("id")},
        )
