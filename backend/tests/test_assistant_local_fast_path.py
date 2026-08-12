from __future__ import annotations

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import pytest

from app.assistant.provider import ScriptedAssistantProvider
from app.assistant.schemas import (
    AssistantConversationContext,
    AssistantDraftResponse,
    AssistantProviderTurn,
    AssistantRequest,
    AssistantToolCall,
)
from app.assistant.service import AssistantService
from app.db.database import Base
from app.knowledge.models import KnowledgeEntity, KnowledgeEntityAlias, KnowledgeEntityType
from app.models import Creature, HuntZone, Loot
from app.models.external_data import Item, TibiaWikiQuest


class ProviderMustNotRun:
    def __init__(self) -> None:
        self.calls = 0

    async def generate(self, _request):
        self.calls += 1
        raise AssertionError("provider.generate() must not run for a direct local lookup")


def add_item(db: Session, item_id: int, name: str) -> Item:
    item = Item(
        id=item_id,
        name=name,
        normalized_name=name.casefold(),
        slug=name.casefold().replace(" ", "-"),
        external_id=str(item_id),
        source_name="fixture",
    )
    db.add(item)
    db.flush()
    return item


def add_creature(db: Session, creature_id: int, name: str, *, is_boss: bool = False) -> Creature:
    creature = Creature(
        id=creature_id,
        name=name,
        normalized_name=name.casefold(),
        slug=name.casefold().replace(" ", "-"),
        plural=f"{name}s",
        hitpoints=1000,
        experience=1000,
        is_boss=is_boss,
        is_hidden=False,
    )
    db.add(creature)
    db.flush()
    return creature


async def local_answer(db: Session, message: str, *, context=None):
    provider = ProviderMustNotRun()
    response = await AssistantService(db, provider).answer(AssistantRequest(message=message, context=context))
    assert provider.calls == 0
    return response


@pytest.mark.asyncio
async def test_exact_item_lookup_uses_zero_provider_calls(db):
    item = add_item(db, 1001, "White Silk Flower")

    response = await local_answer(db, "white silk flower")

    assert [entity.key for entity in response.entities] == [f"item:{item.id}"]
    assert response.entity_cards == [f"item:{item.id}"]
    assert response.message[0].text == "I found this match for “white silk flower”."
    assert response.grounding.tool_calls == 0
    assert response.grounding.evidence_keys == ["local:entity_lookup"]
    assert response.grounding.data_gaps == []
    assert response.warnings == []


@pytest.mark.asyncio
async def test_partial_item_lookup_is_ranked_and_uses_zero_provider_calls(db):
    exact = add_item(db, 1010, "Silk Flower")
    prefix = add_item(db, 1011, "Silk Flower Garland")
    contains = add_item(db, 1012, "White Silk Flower")

    response = await local_answer(db, "silk flower")

    assert [entity.key for entity in response.entities] == [
        f"item:{exact.id}",
        f"item:{prefix.id}",
        f"item:{contains.id}",
    ]
    assert response.message[0].text == (
        "I found several matches for “silk flower”. Were you looking for one of these?"
    )


@pytest.mark.asyncio
async def test_exact_creature_and_boss_lookups_use_zero_provider_calls(db):
    creature = add_creature(db, 1020, "Werewolf")
    boss = add_creature(db, 1021, "Ferumbras", is_boss=True)

    creature_response = await local_answer(db, "Werewolf")
    boss_response = await local_answer(db, "Ferumbras")

    assert creature_response.entities[0].key == f"creature:{creature.id}"
    assert creature_response.entities[0].metadata["is_boss"] is False
    assert boss_response.entities[0].key == f"creature:{boss.id}"
    assert boss_response.entities[0].entity_type == "creature"
    assert boss_response.entities[0].metadata["is_boss"] is True


@pytest.mark.asyncio
async def test_hunt_zone_lookup_uses_zero_provider_calls(db):
    zone = HuntZone(
        id=1030,
        name="Lion Sanctum",
        normalized_name="lion sanctum",
        slug="lion-sanctum",
        min_level=250,
    )
    db.add(zone)
    db.flush()

    response = await local_answer(db, "Lion Sanctum")

    assert response.entities[0].key == f"hunt_zone:{zone.id}"
    assert response.entities[0].detail_route == "/hunt-zones/lion-sanctum"


@pytest.mark.asyncio
async def test_action_query_reaches_the_existing_provider_tool_flow(db):
    creature = add_creature(db, 1040, "Werewolf")
    evidence = "tool:1:resolve_entities"
    final = AssistantDraftResponse(
        language="en",
        message="Werewolf is a matching creature.",
        message_entity_keys=[f"creature:{creature.id}"],
        message_evidence_keys=[evidence],
        sections=[],
        entity_card_keys=[f"creature:{creature.id}"],
        route_keys=[],
        prerequisites=[],
        warnings=[],
        suggested_followups=[],
    )
    provider = ScriptedAssistantProvider([
        AssistantProviderTurn(
            output_items=[{"type": "function_call", "call_id": "resolve", "name": "resolve_entities", "arguments": "{}"}],
            tool_calls=[AssistantToolCall(
                id="resolve",
                name="resolve_entities",
                arguments={"mentions": ["Werewolf"], "entity_types": ["creature"]},
            )],
        ),
        AssistantProviderTurn(draft=final),
    ])

    response = await AssistantService(db, provider).answer(
        AssistantRequest(message="Where can I hunt Werewolves?")
    )

    assert len(provider.requests) == 2
    assert response.grounding.tool_calls == 1


@pytest.mark.asyncio
async def test_direct_lookup_is_bounded_to_ten_results(db):
    for index in range(15):
        add_item(db, 1100 + index, f"Silk Flower {index:02d}")

    response = await local_answer(db, "silk flower")

    assert len(response.entities) == 10
    assert len(response.entity_cards) == 10
    assert [entity.canonical_name for entity in response.entities] == [
        f"Silk Flower {index:02d}" for index in range(10)
    ]


@pytest.mark.asyncio
async def test_canonical_and_legacy_item_rows_are_deduplicated(db):
    add_item(db, 1200, "White Silk Flower")
    source_creature = add_creature(db, 1201, "Fixture Creature")
    db.add(Loot(
        id=1202,
        creature_id=source_creature.id,
        item_name="White Silk Flower",
        normalized_name="white silk flower",
    ))
    db.flush()

    response = await local_answer(db, "white silk flower")

    assert len(response.entities) == 1
    assert response.entities[0].key == "item:1200"


@pytest.mark.asyncio
async def test_local_copy_is_deterministic_in_english_and_spanish(db):
    add_item(db, 1300, "Gold Coin")
    spanish_context = AssistantConversationContext(language="es")

    english = await local_answer(db, "Gold Coin")
    spanish = await local_answer(db, "Gold Coin", context=spanish_context)

    assert english.message[0].text == "I found this match for “Gold Coin”."
    assert spanish.message[0].text == "Encontré esta coincidencia para «Gold Coin»."
    assert spanish.language == "es"
    assert spanish.conversation_id == spanish_context.conversation_id


@pytest.mark.asyncio
async def test_known_local_alias_resolves_canonical_entity_without_provider(db):
    db.add(KnowledgeEntityType(entity_type="item", display_name="Item", enabled=True))
    db.flush()
    canonical = KnowledgeEntity(
        entity_type="item",
        canonical_name="White Silk Flower",
        slug="white-silk-flower",
        language_neutral_id="item:white-silk-flower",
        status="active",
        visibility="public",
    )
    db.add(canonical)
    db.flush()
    db.add(KnowledgeEntityAlias(
        entity_uuid=canonical.uuid,
        entity_type="item",
        alias="Flor de Seda Blanca",
        normalized_alias="flor de seda blanca",
        language="es",
    ))
    item = add_item(db, 1350, "White Silk Flower")
    item.knowledge_entity_id = canonical.uuid
    db.flush()

    response = await local_answer(
        db,
        "Flor de Seda Blanca",
        context=AssistantConversationContext(language="es"),
    )

    assert response.entities[0].key == f"item:{item.id}"
    assert response.entities[0].canonical_name == "White Silk Flower"
    assert response.message[0].text == "Encontré esta coincidencia para «Flor de Seda Blanca»."


@pytest.mark.asyncio
async def test_local_lookup_preserves_database_state_and_releases_its_transaction():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    try:
        add_item(session, 1400, "Golden Mug")
        session.commit()
        assert not session.in_transaction()

        response = await local_answer(session, "Golden Mug")

        assert response.entities[0].canonical_name == "Golden Mug"
        assert not session.in_transaction()
        assert session.scalar(select(Item).where(Item.id == 1400)).name == "Golden Mug"
        assert not session.new and not session.dirty and not session.deleted
    finally:
        session.close()
        engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("message", ["aa", "...", "????", "   "])
async def test_junk_guard_uses_zero_provider_and_skips_entity_resolution(db, monkeypatch, message):
    from app.assistant.entities import AssistantEntityResolver

    def forbidden_lookup(*_args, **_kwargs):
        raise AssertionError("obvious junk must not perform entity resolution")

    monkeypatch.setattr(AssistantEntityResolver, "resolve_direct", forbidden_lookup)
    response = await local_answer(db, message)

    assert response.grounding.evidence_keys == ["local:junk_guard"]
    assert response.entity_cards == []
    assert "little more" in response.message[0].text


@pytest.mark.asyncio
async def test_structured_item_acquisition_uses_zero_provider_calls(db):
    creature = add_creature(db, 1500, "Cult Scholar")
    add_item(db, 1502, "White Silk Flower")
    db.add(Loot(
        id=1501,
        creature_id=creature.id,
        item_name="White Silk Flower",
        normalized_name="white silk flower",
        rarity="Rare",
    ))
    db.flush()

    response = await local_answer(db, "loot white silk flower")

    assert response.grounding.evidence_keys == ["local:structured_lookup:item_acquisition"]
    assert response.grounding.tool_calls == 0
    assert f"creature:{creature.id}" in response.entity_cards


@pytest.mark.asyncio
async def test_structured_creature_hunt_uses_zero_provider_calls(db):
    creature = add_creature(db, 1510, "Werewolf")
    zone = HuntZone(
        id=1511,
        name="Grimvale",
        normalized_name="grimvale",
        slug="grimvale",
        min_level=0,
    )
    db.add(zone)
    db.flush()
    from app.models import SpawnLocation
    db.add(SpawnLocation(creature_id=creature.id, hunt_zone_id=zone.id, quantity="Many"))
    db.flush()

    response = await local_answer(db, "hunt werewolf")

    assert response.grounding.evidence_keys == ["local:structured_lookup:creature_hunting"]
    assert response.entity_cards == [f"hunt_zone:{zone.id}"]


@pytest.mark.asyncio
async def test_structured_quest_requirements_use_zero_provider_calls(db):
    quest = TibiaWikiQuest(
        id=1520,
        name="The Inquisition Quest",
        normalized_name="the inquisition quest",
        slug="the-inquisition-quest",
        external_id="1520",
        source_name="fixture",
        is_group=False,
        requirements=[{"description": "Level 100"}],
        required_items=[{"name": "Holy Icon"}],
        required_quests=[],
        starting_npcs=[],
        related_npcs=[],
        rewarded_items=[],
        unlocked_quests=[],
        required_creatures=[],
        bosses=[],
        locations=[],
        access_unlocks=[],
        parser_metadata={},
        protected_fields=[],
    )
    db.add(quest)
    db.flush()

    response = await local_answer(db, "requisitos The Inquisition Quest")

    assert response.language == "es"
    assert response.grounding.evidence_keys == ["local:structured_lookup:quest_requirements"]
    assert "Level 100" in response.message[0].text


@pytest.mark.asyncio
async def test_structured_hunt_zone_access_uses_zero_provider_when_requirement_is_known(db):
    zone = HuntZone(
        id=1525,
        name="Grimvale",
        normalized_name="grimvale",
        slug="grimvale",
        min_level=0,
        requires_premium=True,
    )
    db.add(zone)
    db.flush()

    response = await local_answer(
        db,
        "acceso Grimvale",
        context=AssistantConversationContext(language="es"),
    )

    assert response.grounding.evidence_keys == ["local:structured_lookup:access"]
    assert response.entity_cards == [f"hunt_zone:{zone.id}"]
    assert "Premium Account" in response.message[0].text


@pytest.mark.asyncio
async def test_comparison_and_contextual_questions_still_reach_provider(db):
    add_creature(db, 1530, "Werewolf")
    add_creature(db, 1531, "Werebear")

    class CountingProvider:
        def __init__(self):
            self.calls = 0

        async def generate(self, _request):
            self.calls += 1
            raise RuntimeError("provider path reached")

    for message in (
        "Compare Werewolf and Werebear",
        "I am in Edron, how do I reach Grimvale?",
    ):
        provider = CountingProvider()
        with pytest.raises(RuntimeError, match="provider path reached"):
            await AssistantService(db, provider).answer(AssistantRequest(message=message))
        assert provider.calls == 1


def test_local_endpoint_does_not_require_an_openai_key(client, db, monkeypatch):
    from app.core.config import settings

    add_creature(db, 1540, "Ferumbras", is_boss=True)
    monkeypatch.setattr(settings, "ASSISTANT_ENABLED", True)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", None)

    response = client.post(
        "/api/v1/assistant/",
        json={"message": "Ferumbras"},
        headers={"X-Assistant-Session": "local-no-key"},
    )

    assert response.status_code == 200
    assert response.json()["grounding"]["tool_calls"] == 0


def test_provider_route_still_requires_configuration(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "ASSISTANT_ENABLED", True)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", None)
    response = client.post(
        "/api/v1/assistant/",
        json={"message": "Compare Werewolf and Werebear"},
        headers={"X-Assistant-Session": "provider-needs-key"},
    )
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "assistant_not_configured"
