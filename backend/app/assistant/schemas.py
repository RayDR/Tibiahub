"""Public and provider-facing schemas for TibiaHub Assistant V1."""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


AssistantLanguage = Literal["en", "es"]
AssistantEntityType = Literal[
    "creature", "item", "npc", "quest", "location", "area", "town", "hunt_zone"
]


class AssistantPartyMember(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    vocation: str | None = Field(default=None, max_length=50)
    level: int | None = Field(default=None, ge=1, le=5000)


class AssistantCharacterContext(BaseModel):
    vocation: str | None = Field(default=None, max_length=50)
    level: int | None = Field(default=None, ge=1, le=5000)


class AssistantConversationContext(BaseModel):
    """Explicit user facts only; inferred game facts never enter this object."""

    conversation_id: UUID = Field(default_factory=uuid4)
    language: AssistantLanguage = "en"
    known_access_unlocks: list[str] = Field(default_factory=list, max_length=50)
    completed_quests: list[str] = Field(default_factory=list, max_length=100)
    owned_items: list[str] = Field(default_factory=list, max_length=100)
    current_location: str | None = Field(default=None, max_length=255)
    character: AssistantCharacterContext = Field(default_factory=AssistantCharacterContext)
    party_members: list[AssistantPartyMember] = Field(default_factory=list, max_length=20)


class AssistantConversationMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class AssistantRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    history: list[AssistantConversationMessage] = Field(default_factory=list, max_length=24)
    context: AssistantConversationContext | None = None


class AssistantEntityReference(BaseModel):
    key: str
    entity_type: AssistantEntityType
    id: str
    knowledge_entity_id: UUID | None = None
    canonical_name: str
    slug: str
    image_url: str | None = None
    detail_route: str
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class AssistantContentPart(BaseModel):
    kind: Literal["text", "entity"]
    text: str | None = None
    entity_key: str | None = None

    @model_validator(mode="after")
    def validate_payload(self) -> "AssistantContentPart":
        if self.kind == "text" and not self.text:
            raise ValueError("Text content parts require text")
        if self.kind == "entity" and not self.entity_key:
            raise ValueError("Entity content parts require entity_key")
        return self


class AssistantSection(BaseModel):
    kind: Literal["summary", "details", "access", "travel", "hunt", "acquisition", "quest", "warning"]
    title: str
    content: list[AssistantContentPart]
    entity_keys: list[str] = Field(default_factory=list)


class AssistantRouteStep(BaseModel):
    sequence: int = Field(ge=1)
    kind: str
    instruction: str | None = None
    location_name: str | None = None
    x: int | None = None
    y: int | None = None
    z: int | None = None


class AssistantMapReference(BaseModel):
    id: str
    name: str
    image_url: str
    verification_state: str
    confidence: str


class AssistantRouteReference(BaseModel):
    key: str
    id: UUID
    name: str
    slug: str
    start_location: str | None = None
    end_location: str | None = None
    verification_state: str
    confidence: str
    steps: list[AssistantRouteStep] = Field(default_factory=list)
    maps: list[AssistantMapReference] = Field(default_factory=list)


class AssistantPrerequisite(BaseModel):
    status: Literal["required", "satisfied", "unknown"]
    content: list[AssistantContentPart]


class AssistantNotice(BaseModel):
    code: str
    severity: Literal["info", "warning", "error"] = "warning"
    message: str


class AssistantGrounding(BaseModel):
    tool_calls: int = 0
    evidence_keys: list[str] = Field(default_factory=list)
    data_gaps: list[str] = Field(default_factory=list)


class AssistantResponse(BaseModel):
    conversation_id: UUID
    language: AssistantLanguage
    message: list[AssistantContentPart]
    sections: list[AssistantSection] = Field(default_factory=list)
    entities: list[AssistantEntityReference] = Field(default_factory=list)
    entity_cards: list[str] = Field(default_factory=list)
    routes: list[AssistantRouteReference] = Field(default_factory=list)
    prerequisites: list[AssistantPrerequisite] = Field(default_factory=list)
    warnings: list[AssistantNotice] = Field(default_factory=list)
    suggested_followups: list[str] = Field(default_factory=list)
    context: AssistantConversationContext
    grounding: AssistantGrounding = Field(default_factory=AssistantGrounding)


class AssistantDraftSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["summary", "details", "access", "travel", "hunt", "acquisition", "quest", "warning"]
    title: str
    text: str
    entity_keys: list[str]
    evidence_keys: list[str]


class AssistantDraftPrerequisite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["required", "satisfied", "unknown"]
    text: str
    entity_keys: list[str]
    evidence_keys: list[str]


class AssistantDraftNotice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    severity: Literal["info", "warning", "error"]
    message: str


class AssistantDraftResponse(BaseModel):
    """Strict model output. URLs and canonical identity are deliberately absent."""

    model_config = ConfigDict(extra="forbid")

    language: AssistantLanguage
    message: str
    message_entity_keys: list[str]
    message_evidence_keys: list[str]
    sections: list[AssistantDraftSection]
    entity_card_keys: list[str]
    route_keys: list[str]
    prerequisites: list[AssistantDraftPrerequisite]
    warnings: list[AssistantDraftNotice]
    suggested_followups: list[str]


class AssistantToolCall(BaseModel):
    id: str
    name: str
    arguments: dict[str, Any]


class AssistantProviderRequest(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    instructions: str
    input_items: list[dict[str, Any]]
    tools: list[dict[str, Any]]
    require_tool: bool = False


class AssistantProviderTurn(BaseModel):
    output_items: list[dict[str, Any]] = Field(default_factory=list)
    tool_calls: list[AssistantToolCall] = Field(default_factory=list)
    draft: AssistantDraftResponse | None = None
