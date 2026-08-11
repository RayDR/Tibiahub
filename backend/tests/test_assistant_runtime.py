from __future__ import annotations

import asyncio
import json

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.assistant.provider import AssistantProvider
from app.assistant.schemas import (
    AssistantDraftResponse,
    AssistantProviderRequest,
    AssistantProviderTurn,
    AssistantRequest,
    AssistantToolCall,
)
from app.assistant.service import AssistantService
from app.assistant.tools import TibiaHubAssistantTools
from app.core.config import Settings, settings
from app.db.database import Base
from app.models import Creature, HuntZone, SpawnLocation


def _runtime_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    db = factory()
    db.add_all([
        Creature(
            id=9101,
            name="Werewolf",
            normalized_name="werewolf",
            slug="werewolf",
            plural="Werewolves",
            hitpoints=1955,
            experience=1900,
            is_boss=False,
            is_hidden=False,
        ),
        HuntZone(
            id=9102,
            name="Grimvale",
            normalized_name="grimvale",
            slug="grimvale",
            min_level=0,
        ),
    ])
    db.flush()
    db.add(SpawnLocation(creature_id=9101, hunt_zone_id=9102, quantity="Unknown"))
    db.commit()
    return engine, db


def _tool_turn(call_id: str) -> AssistantProviderTurn:
    return AssistantProviderTurn(
        output_items=[{
            "type": "function_call",
            "call_id": call_id,
            "name": "creature_hunting_context",
            "arguments": "{}",
        }],
        tool_calls=[AssistantToolCall(
            id=call_id,
            name="creature_hunting_context",
            arguments={"query": "Werewolves", "limit": 10},
        )],
    )


def _final_turn(evidence_keys: list[str]) -> AssistantProviderTurn:
    return AssistantProviderTurn(
        output_items=[],
        draft=AssistantDraftResponse(
            language="en",
            message="Werewolf is locally linked to Grimvale.",
            message_entity_keys=["creature:9101", "hunt_zone:9102"],
            message_evidence_keys=evidence_keys,
            sections=[],
            entity_card_keys=["creature:9101", "hunt_zone:9102"],
            route_keys=[],
            prerequisites=[],
            warnings=[],
            suggested_followups=[],
        ),
    )


class ObservingTwoToolProvider(AssistantProvider):
    def __init__(self, db, active_connections: dict[str, int]):
        self.db = db
        self.active_connections = active_connections
        self.turn = 0
        self.materialized_outputs: list[dict] = []

    async def generate(self, request: AssistantProviderRequest) -> AssistantProviderTurn:
        self.turn += 1
        if self.turn == 1:
            return _tool_turn("first")

        assert self.db.in_transaction() is False
        assert self.active_connections["active"] == 0
        output = json.loads(request.input_items[-1]["output"])
        assert output["entities"][0]["canonical_name"] == "Werewolf"
        assert output["spawns"][0]["hunt_zone_key"] == "hunt_zone:9102"
        self.materialized_outputs.append(output)

        if self.turn == 2:
            return _tool_turn("second")
        return _final_turn([
            "tool:1:creature_hunting_context",
            "tool:2:creature_hunting_context",
        ])


@pytest.mark.asyncio
async def test_read_connection_is_checked_in_between_provider_turns_and_session_is_reusable():
    engine, db = _runtime_session()
    pool_state = {"active": 0, "checkouts": 0, "checkins": 0}

    def checked_out(*_args):
        pool_state["active"] += 1
        pool_state["checkouts"] += 1

    def checked_in(*_args):
        pool_state["active"] -= 1
        pool_state["checkins"] += 1

    event.listen(engine, "checkout", checked_out)
    event.listen(engine, "checkin", checked_in)
    provider = ObservingTwoToolProvider(db, pool_state)
    try:
        before = db.query(Creature).count()
        db.rollback()
        pool_state.update(active=0, checkouts=0, checkins=0)

        result = await AssistantService(db, provider).answer(
            AssistantRequest(message="Where can I hunt Werewolves?"),
        )

        assert provider.turn == 3
        assert len(provider.materialized_outputs) == 2
        assert pool_state["active"] == 0
        assert pool_state["checkouts"] == 2
        assert pool_state["checkins"] == 2
        assert db.in_transaction() is False
        assert result.grounding.tool_calls == 2
        assert db.query(Creature).count() == before
        db.rollback()
    finally:
        db.close()
        engine.dispose()


class RecoveringProvider(AssistantProvider):
    def __init__(self, db):
        self.db = db
        self.turn = 0

    async def generate(self, _request: AssistantProviderRequest) -> AssistantProviderTurn:
        self.turn += 1
        if self.turn == 1:
            return _tool_turn("failing")
        assert self.db.in_transaction() is False
        if self.turn == 2:
            return _tool_turn("recovered")
        return _final_turn(["tool:2:creature_hunting_context"])


@pytest.mark.asyncio
async def test_database_failure_rolls_back_and_later_tool_reuses_same_session(monkeypatch):
    engine, db = _runtime_session()
    provider = RecoveringProvider(db)
    original_execute = TibiaHubAssistantTools.execute
    attempts = 0

    def fail_once(self, name, arguments):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            original_execute(self, name, arguments)
            self.db.execute(text("SELECT * FROM assistant_table_that_does_not_exist"))
        return original_execute(self, name, arguments)

    monkeypatch.setattr(TibiaHubAssistantTools, "execute", fail_once)
    try:
        result = await AssistantService(db, provider).answer(
            AssistantRequest(message="Where can I hunt Werewolves?"),
        )
        assert provider.turn == 3
        assert result.grounding.tool_calls == 2
        assert any("could not be loaded" in gap for gap in result.grounding.data_gaps)
        assert db.in_transaction() is False
    finally:
        db.close()
        engine.dispose()


def test_backend_assistant_timeout_default_is_sixty_seconds():
    assert Settings().ASSISTANT_TIMEOUT_SECONDS == 60


class SlowProvider(AssistantProvider):
    async def generate(self, _request: AssistantProviderRequest) -> AssistantProviderTurn:
        await asyncio.sleep(0.1)
        raise AssertionError("endpoint timeout should cancel the provider turn")


def test_endpoint_returns_controlled_504_on_orchestration_timeout(client, monkeypatch):
    from app.api.v1.assistant import get_assistant_provider
    from main import app

    monkeypatch.setattr(settings, "ASSISTANT_ENABLED", True)
    monkeypatch.setattr(settings, "ASSISTANT_TIMEOUT_SECONDS", 0.01)
    app.dependency_overrides[get_assistant_provider] = lambda: SlowProvider()
    try:
        response = client.post(
            "/api/v1/assistant/",
            json={"message": "Where can I hunt Werewolves?"},
            headers={"X-Assistant-Session": "timeout-regression"},
        )
    finally:
        app.dependency_overrides.pop(get_assistant_provider, None)

    assert response.status_code == 504
    assert response.json()["detail"]["code"] == "assistant_timeout"
