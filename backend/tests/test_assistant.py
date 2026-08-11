from __future__ import annotations

import json

import httpx
import pytest

from app.assistant.context import ConversationContextService, detect_language
from app.assistant.entities import AssistantEntityResolver, FabricatedEntityReferenceError, TurnEntityRegistry
from app.assistant.provider import AssistantProviderError, ScriptedAssistantProvider
from app.assistant.schemas import (
    AssistantConversationContext,
    AssistantDraftNotice,
    AssistantDraftResponse,
    AssistantProviderTurn,
    AssistantRequest,
    AssistantToolCall,
)
from app.assistant.service import AssistantService
from app.assistant.tools import MAX_TOOL_RESULT_BYTES, TibiaHubAssistantTools, bound_tool_value
from app.core.config import settings
from app.knowledge.indexing import normalize_name
from app.knowledge.models import KnowledgeEntity, KnowledgeEntityAlias, KnowledgeEntityType
from app.models import Creature, HuntZone, SpawnLocation
from app.models.external_data import Item, TibiaWikiLocation, TibiaWikiNpc, TibiaWikiQuest


def creature_with_zone(db, *, creature_id=101, zone_id=201, name="Werewolf", plural="Werewolves"):
    creature = Creature(
        id=creature_id, name=name, normalized_name=name.lower(), slug=name.lower(), plural=plural,
        hitpoints=1955, experience=1900, is_boss=False, is_hidden=False,
    )
    zone = HuntZone(id=zone_id, name="Grimvale", normalized_name="grimvale", slug="grimvale", min_level=0)
    db.add_all([creature, zone]); db.flush()
    db.add(SpawnLocation(creature_id=creature.id, hunt_zone_id=zone.id, quantity="Unknown")); db.flush()
    return creature, zone


def canonical_entity(db, entity_type: str, name: str, *, alias: str | None = None) -> KnowledgeEntity:
    if db.get(KnowledgeEntityType, entity_type) is None:
        db.add(KnowledgeEntityType(entity_type=entity_type, display_name=entity_type.title(), enabled=True))
        db.flush()
    entity = KnowledgeEntity(
        entity_type=entity_type,
        canonical_name=name,
        slug=name.lower().replace(" ", "-"),
        language_neutral_id=f"{entity_type}:assistant-test:{normalize_name(name)}",
        status="active",
        visibility="public",
    )
    db.add(entity)
    db.flush()
    if alias:
        db.add(KnowledgeEntityAlias(
            entity_uuid=entity.uuid,
            entity_type=entity_type,
            alias=alias,
            normalized_alias=normalize_name(alias),
            language="es",
        ))
        db.flush()
    return entity


def draft(*, text: str, entity_keys: list[str], evidence_keys: list[str], warnings=None) -> AssistantDraftResponse:
    return AssistantDraftResponse(
        language="en", message=text, message_entity_keys=entity_keys,
        message_evidence_keys=evidence_keys, sections=[], entity_card_keys=entity_keys,
        route_keys=[], prerequisites=[], warnings=warnings or [], suggested_followups=[],
    )


def grounded_provider(creature: Creature, zone: HuntZone, *, language="en") -> ScriptedAssistantProvider:
    evidence = "tool:1:creature_hunting_context"
    final = draft(
        text=f"{creature.name} is locally linked to {zone.name}.",
        entity_keys=[f"creature:{creature.id}", f"hunt_zone:{zone.id}"], evidence_keys=[evidence],
    )
    final.language = language
    return ScriptedAssistantProvider([
        AssistantProviderTurn(
            output_items=[{"type": "function_call", "call_id": "call-1", "name": "creature_hunting_context", "arguments": "{}"}],
            tool_calls=[AssistantToolCall(id="call-1", name="creature_hunting_context", arguments={"query": creature.name, "limit": 10})],
        ),
        AssistantProviderTurn(output_items=[], draft=final),
    ])


def test_entity_resolution_uses_local_plural_and_returns_backend_owned_routes(db):
    creature, zone = creature_with_zone(db)
    resolver = AssistantEntityResolver(db)
    result = resolver.resolve("Werewolves", ["creature"], limit=3)
    assert result[0].id == str(creature.id)
    assert result[0].detail_route == "/creatures/werewolf"
    assert result[0].image_url.startswith("/api/v1/creatures/")
    execution = TibiaHubAssistantTools(db, AssistantConversationContext(), "Where can I hunt Werewolves?").execute(
        "creature_hunting_context", {"query": "Werewolves", "limit": 10},
    )
    assert execution.payload["spawns"][0]["hunt_zone_key"] == f"hunt_zone:{zone.id}"
    assert execution.payload["ranking_available"] is False
    assert execution.payload["ranked_spawns"] == []
    assert any("cannot be ranked" in gap for gap in execution.data_gaps)


def test_item_acquisition_uses_normalized_fixture_evidence_and_spanish_alias(db):
    item_entity = canonical_entity(db, "item", "Ice Flower Seeds", alias="Semillas de Flor de Hielo")
    npc_entity = canonical_entity(db, "npc", "Seedkeeper")
    npc = TibiaWikiNpc(
        id=501,
        name="Seedkeeper",
        normalized_name="seedkeeper",
        slug="seedkeeper",
        external_id="501",
        source_name="fixture",
        knowledge_entity_id=npc_entity.uuid,
        buys=[], sells=[], destinations=[], related_quests=[],
        provider_metadata={}, supplied_fields=[], protected_fields=[],
    )
    item = Item(
        id=502,
        name="Ice Flower Seeds",
        normalized_name="ice flower seeds",
        slug="ice-flower-seeds",
        external_id="502",
        source_name="fixture",
        knowledge_entity_id=item_entity.uuid,
        buy_from=[{"name": "Seedkeeper"}],
        sell_to=[], rewards_from=[], required_for=[],
        vocation_requirements=[], slots=[], attributes={}, resistances={}, bonuses={}, protected_fields=[],
    )
    db.add_all([npc, item]); db.flush()

    result = TibiaHubAssistantTools(
        db,
        AssistantConversationContext(language="es"),
        "¿Dónde consigo Semillas de Flor de Hielo?",
    ).execute("item_acquisition_context", {"query": "Semillas de Flor de Hielo", "limit": 10})

    assert result.payload["item_key"] == f"item:{item.id}"
    assert result.payload["buy_from"] == [{"name": "Seedkeeper"}]
    assert {value.canonical_name for value in result.entities} == {"Ice Flower Seeds", "Seedkeeper"}


def test_marapur_access_context_exposes_normalized_quest_evidence(db):
    location_entity = canonical_entity(db, "location", "Marapur", alias="Isla de Marapur")
    quest_entity = canonical_entity(db, "quest", "Within the Tides Quest")
    location = TibiaWikiLocation(
        id=601,
        name="Marapur",
        normalized_name="marapur",
        slug="marapur",
        external_id="reference:marapur",
        source_name="fixture",
        knowledge_entity_id=location_entity.uuid,
        npcs=[], creatures=[], quests=[], sublocations=[],
        provider_metadata={"reference_only": True}, supplied_fields=[], protected_fields=[],
    )
    quest = TibiaWikiQuest(
        id=602,
        name="Within the Tides Quest",
        normalized_name="within the tides quest",
        slug="within-the-tides-quest",
        external_id="98526",
        source_name="fixture",
        knowledge_entity_id=quest_entity.uuid,
        is_group=False,
        access_unlocks=[{
            "name": "Marapur Access",
            "destination_name": "Marapur",
            "description": "Access to Marapur",
        }],
        locations=[{"name": "Marapur"}],
        starting_npcs=[], related_npcs=[], required_items=[], rewarded_items=[],
        required_quests=[], unlocked_quests=[], required_creatures=[], bosses=[],
        parser_metadata={}, protected_fields=[],
    )
    db.add_all([location, quest]); db.flush()

    result = TibiaHubAssistantTools(
        db,
        AssistantConversationContext(language="es"),
        "¿Cómo obtengo acceso a la Isla de Marapur?",
    ).execute("location_access_context", {"query": "Isla de Marapur", "limit": 10})

    assert result.payload["location_key"] == f"location:{location.id}"
    assert result.payload["quest_keys"] == [f"quest:{quest.id}"]
    assert result.payload["access_unlocks"][0]["values"][0]["destination_name"] == "Marapur"
    assert {value.canonical_name for value in result.entities} == {"Marapur", "Within the Tides Quest"}


def test_issavi_travel_context_uses_local_npc_destination_fixture(db):
    location_entity = canonical_entity(db, "location", "Issavi")
    npc_entity = canonical_entity(db, "npc", "Local Ferryman")
    location = TibiaWikiLocation(
        id=701,
        name="Issavi", normalized_name="issavi", slug="issavi", external_id="701",
        source_name="fixture", knowledge_entity_id=location_entity.uuid,
        npcs=[], creatures=[], quests=[], sublocations=[], provider_metadata={}, supplied_fields=[], protected_fields=[],
    )
    npc = TibiaWikiNpc(
        id=702,
        name="Local Ferryman", normalized_name="local ferryman", slug="local-ferryman",
        external_id="702", source_name="fixture", knowledge_entity_id=npc_entity.uuid,
        location_name="Fixture Harbor", destinations=[{"name": "Issavi", "keyword": "issavi"}],
        buys=[], sells=[], related_quests=[], provider_metadata={}, supplied_fields=[], protected_fields=[],
    )
    db.add_all([location, npc]); db.flush()

    result = TibiaHubAssistantTools(
        db, AssistantConversationContext(language="es"), "¿Cómo llego a Issavi?",
    ).execute("npc_travel_context", {"origin": None, "destination": "Issavi", "limit": 10})

    assert result.payload["options"][0]["npc_key"] == f"npc:{npc.id}"
    assert {value.canonical_name for value in result.entities} == {"Issavi", "Local Ferryman"}


def test_spawn_ranking_requires_comparable_normalized_quantities(db):
    creature = Creature(
        id=801, name="Scorpion", normalized_name="scorpion", slug="scorpion", plural="Scorpions",
        hitpoints=45, experience=45, is_boss=False, is_hidden=False,
    )
    sparse = HuntZone(id=802, name="Sparse Cave", normalized_name="sparse cave", slug="sparse-cave", min_level=0)
    dense = HuntZone(id=803, name="Dense Cave", normalized_name="dense cave", slug="dense-cave", min_level=0)
    db.add_all([creature, sparse, dense]); db.flush()
    db.add_all([
        SpawnLocation(creature_id=creature.id, hunt_zone_id=sparse.id, quantity="Few"),
        SpawnLocation(creature_id=creature.id, hunt_zone_id=dense.id, quantity="Many"),
    ]); db.flush()

    result = TibiaHubAssistantTools(
        db, AssistantConversationContext(), "Where can I hunt more Scorpions?",
    ).execute("creature_hunting_context", {"query": "Scorpions", "limit": 10})

    assert result.payload["ranking_available"] is True
    assert result.payload["ranking_complete"] is True
    assert result.payload["ranking_basis"] == "density"
    assert result.payload["ranked_spawns"][0]["hunt_zone_key"] == f"hunt_zone:{dense.id}"
    assert not any("cannot be ranked" in gap for gap in result.data_gaps)


def test_fabricated_entity_reference_is_rejected():
    with pytest.raises(FabricatedEntityReferenceError):
        TurnEntityRegistry().require(["creature:does-not-exist"])


@pytest.mark.asyncio
async def test_service_rejects_model_fabricated_entity_key(db):
    creature, _zone = creature_with_zone(db)
    provider = ScriptedAssistantProvider([
        AssistantProviderTurn(
            output_items=[{"type": "function_call", "call_id": "resolve", "name": "resolve_entities", "arguments": "{}"}],
            tool_calls=[AssistantToolCall(id="resolve", name="resolve_entities", arguments={"mentions": [creature.name], "entity_types": ["creature"]})],
        ),
        AssistantProviderTurn(output_items=[], draft=draft(
            text="Fake Dragon Cave is nearby.", entity_keys=["location:fabricated"],
            evidence_keys=["tool:1:resolve_entities"],
        )),
    ])
    with pytest.raises(FabricatedEntityReferenceError):
        await AssistantService(db, provider).answer(AssistantRequest(message="Where is it?"))


def test_tool_results_are_bounded():
    value = bound_tool_value({"items": ["x" * 5000 for _ in range(200)], "extra": "y" * 5000})
    assert len(value["items"]) <= 20
    assert max(map(len, value["items"])) <= 2000
    assert len(json.dumps(value).encode()) <= MAX_TOOL_RESULT_BYTES


def test_conversation_context_updates_explicit_facts_and_language():
    value = ConversationContextService.update(
        None,
        "Ya tengo acceso a Yalahar. Estoy en Edron y soy knight nivel 250.",
    )
    assert value.language == "es"
    assert value.known_access_unlocks == ["Yalahar"]
    assert value.current_location == "Edron"
    assert value.character.vocation == "knight"
    assert value.character.level == 250
    assert detect_language("Where can I hunt Scorpions?") == "en"


def test_known_access_suppresses_unlock_guidance(db):
    db.add(KnowledgeEntityType(entity_type="location", display_name="Location", enabled=True)); db.flush()
    entity = KnowledgeEntity(
        entity_type="location", canonical_name="Yalahar", slug="yalahar",
        language_neutral_id="location:yalahar", status="active", visibility="public",
    )
    db.add(entity); db.flush()
    location = TibiaWikiLocation(
        id=301, name="Yalahar", normalized_name="yalahar", slug="yalahar", external_id="301",
        source_name="test", knowledge_entity_id=entity.uuid, access_notes="Complete a long access quest.",
        npcs=[], creatures=[], quests=[], sublocations=[], provider_metadata=[], supplied_fields=[], protected_fields=[],
    )
    db.add(location); db.flush()
    context = AssistantConversationContext(known_access_unlocks=["Yalahar"])
    result = TibiaHubAssistantTools(
        db, context, "I already have access to Yalahar. How do I reach the Grim Reapers there?",
    ).execute("location_access_context", {"query": "Yalahar", "limit": 10})
    assert result.payload["already_known_access"] is True
    assert result.payload["access_guidance_suppressed"] is True
    assert result.payload["access_notes"] is None
    assert result.payload["quest_keys"] == []


@pytest.mark.asyncio
async def test_service_materializes_only_turn_entities_and_no_provider_download(db, monkeypatch):
    creature, zone = creature_with_zone(db)
    provider = grounded_provider(creature, zone)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("assistant domain tools must not perform provider HTTP requests")

    monkeypatch.setattr(httpx.Client, "request", forbidden)
    result = await AssistantService(db, provider).answer(AssistantRequest(message="Where can I hunt Werewolves?"))
    assert {entity.key for entity in result.entities} == {f"creature:{creature.id}", f"hunt_zone:{zone.id}"}
    assert result.message[0].kind == "entity"
    assert result.grounding.tool_calls == 1


@pytest.mark.asyncio
async def test_tool_failure_can_be_reported_without_fabricated_facts(db):
    warning = AssistantDraftNotice(code="tool_failure", severity="warning", message="Local evidence could not be loaded.")
    provider = ScriptedAssistantProvider([
        AssistantProviderTurn(
            output_items=[{"type": "function_call", "call_id": "bad", "name": "not_a_tool", "arguments": "{}"}],
            tool_calls=[AssistantToolCall(id="bad", name="not_a_tool", arguments={})],
        ),
        AssistantProviderTurn(output_items=[], draft=draft(text="TibiaHub could not verify this answer.", entity_keys=[], evidence_keys=["tool_error:1"], warnings=[warning])),
    ])
    result = await AssistantService(db, provider).answer(AssistantRequest(message="Help me"))
    assert result.warnings[0].code == "tool_failure"
    assert result.entities == []


def test_disabled_assistant_behavior(client, monkeypatch):
    monkeypatch.setattr(settings, "ASSISTANT_ENABLED", False)
    response = client.post("/api/v1/assistant/", json={"message": "Where can I hunt Werewolves?"})
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "assistant_disabled"


class FailingProvider:
    async def generate(self, _request):
        raise AssistantProviderError("provider unavailable")


def test_provider_failure_is_safe(client, monkeypatch):
    from main import app
    from app.api.v1.assistant import get_assistant_provider

    monkeypatch.setattr(settings, "ASSISTANT_ENABLED", True)
    app.dependency_overrides[get_assistant_provider] = lambda: FailingProvider()
    try:
        response = client.post("/api/v1/assistant/", json={"message": "Where can I hunt Werewolves?"})
    finally:
        app.dependency_overrides.pop(get_assistant_provider, None)
    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "assistant_provider_unavailable"


@pytest.mark.asyncio
async def test_spanish_request_preserves_canonical_entity_names(db):
    creature, zone = creature_with_zone(db, name="Scorpion", plural="Scorpions")
    provider = grounded_provider(creature, zone, language="es")
    result = await AssistantService(db, provider).answer(AssistantRequest(message="¿Dónde puedo cazar más Scorpions?"))
    assert result.language == "es"
    assert result.context.language == "es"
    assert any(entity.canonical_name == "Scorpion" for entity in result.entities)
    hunting = TibiaHubAssistantTools(
        db, result.context, "¿Dónde puedo cazar más Scorpions?",
    ).execute("creature_hunting_context", {"query": "Scorpions", "limit": 10})
    assert hunting.payload["ranking_available"] is False
    assert hunting.payload["ranked_spawns"] == []
    assert any("cannot be ranked" in gap for gap in hunting.data_gaps)
