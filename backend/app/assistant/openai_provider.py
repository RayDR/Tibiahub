"""OpenAI Responses API adapter with strict tools and structured output."""

from __future__ import annotations

import json
from typing import Any

import httpx

from app.assistant.provider import AssistantProviderError, AssistantProviderFormatError
from app.assistant.schemas import (
    AssistantDraftResponse,
    AssistantProviderRequest,
    AssistantProviderTurn,
    AssistantToolCall,
)


class OpenAIAssistantProvider:
    endpoint = "https://api.openai.com/v1/responses"

    def __init__(self, *, api_key: str, model: str, timeout_seconds: int, max_output_tokens: int = 3000):
        if not api_key:
            raise AssistantProviderError("OPENAI_API_KEY is not configured")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_output_tokens = max(500, min(max_output_tokens, 8000))

    async def generate(self, request: AssistantProviderRequest) -> AssistantProviderTurn:
        payload: dict[str, Any] = {
            "model": self.model,
            "instructions": request.instructions,
            "input": request.input_items,
            "tools": request.tools,
            "tool_choice": "required" if request.require_tool else "auto",
            "parallel_tool_calls": False,
            "max_output_tokens": self.max_output_tokens,
            "store": False,
            "text": {"format": {
                "type": "json_schema", "name": "tibiahub_assistant_response", "strict": True,
                "schema": AssistantDraftResponse.model_json_schema(),
            }},
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    self.endpoint,
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json=payload,
                )
            response.raise_for_status()
            body = response.json()
        except httpx.TimeoutException as exc:
            raise AssistantProviderError("OpenAI assistant request timed out") from exc
        except httpx.HTTPStatusError as exc:
            raise AssistantProviderError(f"OpenAI assistant request failed with HTTP {exc.response.status_code}") from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise AssistantProviderError("OpenAI assistant request failed") from exc

        output = body.get("output")
        if not isinstance(output, list):
            raise AssistantProviderFormatError("OpenAI response did not contain output items")
        calls: list[AssistantToolCall] = []
        for item in output:
            if not isinstance(item, dict) or item.get("type") != "function_call":
                continue
            try:
                arguments = json.loads(item.get("arguments") or "{}")
                calls.append(AssistantToolCall(id=item["call_id"], name=item["name"], arguments=arguments))
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                raise AssistantProviderFormatError("OpenAI returned an invalid function call") from exc
        if calls:
            return AssistantProviderTurn(output_items=output, tool_calls=calls)

        output_text = body.get("output_text")
        if not isinstance(output_text, str):
            fragments: list[str] = []
            for item in output:
                if not isinstance(item, dict) or item.get("type") != "message":
                    continue
                for content in item.get("content") or []:
                    if isinstance(content, dict) and content.get("type") in {"output_text", "text"} and isinstance(content.get("text"), str):
                        fragments.append(content["text"])
            output_text = "".join(fragments)
        try:
            draft = AssistantDraftResponse.model_validate_json(output_text)
        except Exception as exc:
            raise AssistantProviderFormatError("OpenAI returned an invalid structured assistant response") from exc
        return AssistantProviderTurn(output_items=output, draft=draft)
