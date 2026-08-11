"""Bounded model/tool orchestration and backend-owned response materialization."""

from __future__ import annotations

import json
import re
from typing import Iterable

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.assistant.context import ConversationContextService
from app.assistant.entities import FabricatedEntityReferenceError
from app.assistant.provider import AssistantProvider, AssistantProviderFormatError
from app.assistant.schemas import (
    AssistantContentPart,
    AssistantDraftResponse,
    AssistantGrounding,
    AssistantNotice,
    AssistantPrerequisite,
    AssistantProviderRequest,
    AssistantRequest,
    AssistantResponse,
    AssistantSection,
)
from app.assistant.tools import AssistantToolError, TibiaHubAssistantTools


_URL_RE = re.compile(r"(?:https?://|\[[^\]]+\]\([^\)]+\))", re.I)


def _instructions(context_json: str) -> str:
    return f"""You are TibiaHub Assistant, a read-only guide grounded exclusively in tool results from local synchronized PostgreSQL data.

Rules:
- Always use one or more TibiaHub tools before answering. You have no database access other than these tools.
- Never use web search, model memory, or general Tibia knowledge to fill a missing fact.
- Never invent creature locations, drops, access requirements, quest prerequisites, NPC keywords, coordinates, routes, route steps, or hunt statistics.
- If local evidence is missing, say TibiaHub does not currently have enough verified information and include a warning.
- Never infer or complete missing route steps. Preserve verification_state and confidence caveats.
- Answer in the user's language (English or Spanish), while keeping canonical game entity names unchanged.
- Every entity key, route key, and evidence key in final output must have appeared in a tool result during this turn.
- Do not output URLs or Markdown links. The backend owns every entity URL and image URL.
- Use entity keys for every real named creature, item, NPC, quest, location, or hunt zone mentioned in the response.
- Respect explicit user facts in conversation context. If access is already known, do not explain unlocking it unless the user explicitly asks again.
- Keep the answer concise, useful, and factual. Suggested follow-ups must also be answerable from local tools.

Current explicit conversation context:
{context_json}
"""


def _unique(values: Iterable[str]) -> list[str]:
    output: list[str] = []
    for value in values:
        if value not in output:
            output.append(value)
    return output


class AssistantService:
    def __init__(self, db: Session, provider: AssistantProvider, *, max_tool_calls: int = 8, max_history_messages: int = 12):
        self.db = db
        self.provider = provider
        self.max_tool_calls = max(1, min(max_tool_calls, 20))
        self.max_history_messages = max(0, min(max_history_messages, 24))

    async def answer(self, request: AssistantRequest) -> AssistantResponse:
        context = ConversationContextService.update(request.context, request.message)
        tools = TibiaHubAssistantTools(self.db, context, request.message)
        history = request.history[-self.max_history_messages:]
        input_items = [
            {"role": item.role, "content": item.content}
            for item in history
        ]
        input_items.append({"role": "user", "content": request.message})
        instructions = _instructions(json.dumps(context.model_dump(mode="json"), ensure_ascii=False))
        total_calls = 0
        first_turn = True

        while True:
            turn = await self.provider.generate(AssistantProviderRequest(
                instructions=instructions,
                input_items=input_items,
                tools=tools.definitions(),
                require_tool=first_turn,
            ))
            first_turn = False
            input_items.extend(turn.output_items)
            if turn.tool_calls:
                for call in turn.tool_calls:
                    total_calls += 1
                    if total_calls > self.max_tool_calls:
                        raise AssistantProviderFormatError("Assistant exceeded the configured tool-call limit")
                    try:
                        execution = tools.execute(call.name, call.arguments)
                        output = execution.provider_payload()
                    except SQLAlchemyError:
                        self.db.rollback()
                        evidence_key = f"tool_error:{total_calls}"
                        tools.evidence_keys.append(evidence_key)
                        tools.data_gaps.append("The requested local evidence could not be loaded.")
                        output = {"evidence_key": evidence_key, "error": "local_database_unavailable", "message": "The local TibiaHub query failed.", "data_gaps": ["The requested local evidence could not be loaded."]}
                    except (AssistantToolError, TypeError, ValueError) as exc:
                        evidence_key = f"tool_error:{total_calls}"
                        tools.evidence_keys.append(evidence_key)
                        tools.data_gaps.append("The requested local tool could not be completed.")
                        output = {"evidence_key": evidence_key, "error": "tool_request_invalid", "message": str(exc)[:500], "data_gaps": ["The requested local tool could not be completed."]}
                    input_items.append({
                        "type": "function_call_output", "call_id": call.id,
                        "output": json.dumps(output, ensure_ascii=False, default=str),
                    })
                continue
            if turn.draft is None:
                raise AssistantProviderFormatError("Assistant provider returned neither tools nor a final response")
            if total_calls == 0:
                raise AssistantProviderFormatError("Assistant provider attempted an ungrounded response without local tools")
            return self._materialize(turn.draft, context, tools, total_calls)

    @staticmethod
    def _assert_no_urls(*texts: str) -> None:
        if any(_URL_RE.search(text or "") for text in texts):
            raise FabricatedEntityReferenceError("Model-authored URLs are not permitted")

    @staticmethod
    def _parts(text: str, entity_keys: list[str], tools: TibiaHubAssistantTools) -> list[AssistantContentPart]:
        references = tools.entities.require(_unique(entity_keys))
        if not references:
            return [AssistantContentPart(kind="text", text=text)]
        patterns = sorted(((reference.canonical_name, reference.key) for reference in references), key=lambda item: len(item[0]), reverse=True)
        combined = re.compile("(" + "|".join(re.escape(name) for name, _ in patterns) + ")", re.I)
        by_name = {name.casefold(): key for name, key in patterns}
        parts: list[AssistantContentPart] = []
        cursor = 0
        for match in combined.finditer(text):
            if match.start() > cursor:
                parts.append(AssistantContentPart(kind="text", text=text[cursor:match.start()]))
            key = by_name.get(match.group(0).casefold())
            if key:
                parts.append(AssistantContentPart(kind="entity", entity_key=key))
            else:
                parts.append(AssistantContentPart(kind="text", text=match.group(0)))
            cursor = match.end()
        if cursor < len(text):
            parts.append(AssistantContentPart(kind="text", text=text[cursor:]))
        return parts or [AssistantContentPart(kind="text", text=text)]

    @staticmethod
    def _require_evidence(keys: list[str], tools: TibiaHubAssistantTools) -> None:
        unknown = [key for key in keys if key not in tools.evidence_keys]
        if unknown:
            raise FabricatedEntityReferenceError(f"Unvalidated assistant evidence reference: {unknown[0]}")

    def _materialize(
        self,
        draft: AssistantDraftResponse,
        context,
        tools: TibiaHubAssistantTools,
        total_calls: int,
    ) -> AssistantResponse:
        all_texts = [draft.message, *(section.title for section in draft.sections), *(section.text for section in draft.sections),
                     *(item.text for item in draft.prerequisites), *(warning.message for warning in draft.warnings), *draft.suggested_followups]
        self._assert_no_urls(*all_texts)
        if not draft.message_evidence_keys:
            raise FabricatedEntityReferenceError("Assistant response has no local evidence reference")
        self._require_evidence(draft.message_evidence_keys, tools)
        tools.entities.require(draft.message_entity_keys)
        sections: list[AssistantSection] = []
        for section in draft.sections[:10]:
            self._require_evidence(section.evidence_keys, tools)
            tools.entities.require(section.entity_keys)
            sections.append(AssistantSection(
                kind=section.kind, title=section.title[:200],
                content=self._parts(section.text[:4000], section.entity_keys, tools),
                entity_keys=_unique(section.entity_keys),
            ))
        prerequisites: list[AssistantPrerequisite] = []
        for item in draft.prerequisites[:20]:
            self._require_evidence(item.evidence_keys, tools)
            tools.entities.require(item.entity_keys)
            prerequisites.append(AssistantPrerequisite(
                status=item.status, content=self._parts(item.text[:2000], item.entity_keys, tools),
            ))
        card_keys = _unique(draft.entity_card_keys)[:20]
        tools.entities.require(card_keys)
        route_keys = _unique(draft.route_keys)[:10]
        unknown_routes = [key for key in route_keys if key not in tools.routes]
        if unknown_routes:
            raise FabricatedEntityReferenceError(f"Unvalidated assistant route reference: {unknown_routes[0]}")

        referenced_keys = _unique([
            *draft.message_entity_keys, *card_keys,
            *(key for section in draft.sections for key in section.entity_keys),
            *(key for item in draft.prerequisites for key in item.entity_keys),
        ])
        warnings = [AssistantNotice(code=value.code[:100], severity=value.severity, message=value.message[:1000]) for value in draft.warnings[:10]]
        if context.language == "es" and tools.data_gaps:
            localized_gap = "TibiaHub no tiene suficiente información local verificada para responder esta parte con precisión."
            if localized_gap not in {warning.message for warning in warnings}:
                warnings.append(AssistantNotice(code="local_data_gap", severity="warning", message=localized_gap))
        else:
            for gap in tools.data_gaps[:10]:
                if gap not in {warning.message for warning in warnings}:
                    warnings.append(AssistantNotice(code="local_data_gap", severity="warning", message=gap[:1000]))
        evidence = _unique([
            *draft.message_evidence_keys,
            *(key for section in draft.sections for key in section.evidence_keys),
            *(key for item in draft.prerequisites for key in item.evidence_keys),
        ])
        return AssistantResponse(
            conversation_id=context.conversation_id,
            language=context.language,
            message=self._parts(draft.message[:4000], draft.message_entity_keys, tools),
            sections=sections,
            entities=tools.entities.require(referenced_keys),
            entity_cards=card_keys,
            routes=[tools.routes[key] for key in route_keys],
            prerequisites=prerequisites,
            warnings=warnings[:15],
            suggested_followups=[value[:300] for value in draft.suggested_followups[:5]],
            context=context,
            grounding=AssistantGrounding(tool_calls=total_calls, evidence_keys=evidence, data_gaps=tools.data_gaps[:10]),
        )
