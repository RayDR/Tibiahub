#!/usr/bin/env python3
"""Unpaid assistant endpoint smoke test using SQLite and a scripted provider."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
SMOKE_TMP = tempfile.TemporaryDirectory(prefix="tibiahub-assistant-smoke-")
SMOKE_DATABASE_URL = f"sqlite:///{Path(SMOKE_TMP.name) / 'assistant.sqlite3'}"
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = SMOKE_DATABASE_URL

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.api.v1.assistant import get_assistant_provider  # noqa: E402
from app.assistant.provider import ScriptedAssistantProvider  # noqa: E402
from app.assistant.schemas import AssistantDraftResponse, AssistantProviderTurn, AssistantToolCall  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.db.database import Base, get_db  # noqa: E402
import app.models  # noqa: E402,F401
from app.models import Creature, HuntZone, SpawnLocation  # noqa: E402
from main import app  # noqa: E402


def main() -> int:
    engine = create_engine(SMOKE_DATABASE_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    creature = Creature(
        id=9001, name="Werewolf", normalized_name="werewolf", slug="werewolf", plural="Werewolves",
        hitpoints=1955, experience=1900, is_boss=False, is_hidden=False,
    )
    zone = HuntZone(id=9002, name="Grimvale", normalized_name="grimvale", slug="grimvale", min_level=0)
    session.add_all([creature, zone]); session.flush()
    session.add(SpawnLocation(creature_id=creature.id, hunt_zone_id=zone.id, quantity="Unknown")); session.commit()

    provider = ScriptedAssistantProvider([
        AssistantProviderTurn(
            output_items=[{"type": "function_call", "call_id": "smoke-1", "name": "creature_hunting_context", "arguments": "{}"}],
            tool_calls=[AssistantToolCall(id="smoke-1", name="creature_hunting_context", arguments={"query": "Werewolves", "limit": 10})],
        ),
        AssistantProviderTurn(output_items=[], draft=AssistantDraftResponse(
            language="en", message="Werewolf is locally linked to Grimvale.",
            message_entity_keys=["creature:9001", "hunt_zone:9002"],
            message_evidence_keys=["tool:1:creature_hunting_context"], sections=[],
            entity_card_keys=["creature:9001", "hunt_zone:9002"], route_keys=[], prerequisites=[],
            warnings=[], suggested_followups=[],
        )),
    ])

    def override_db():
        yield session

    previous_enabled = settings.ASSISTANT_ENABLED
    settings.ASSISTANT_ENABLED = True
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_assistant_provider] = lambda: provider
    try:
        with TestClient(app) as client:
            response = client.post("/api/v1/assistant/", json={"message": "Where can I hunt Werewolves?"})
        response.raise_for_status()
        body = response.json()
        assert body["grounding"]["tool_calls"] == 1
        assert {item["canonical_name"] for item in body["entities"]} == {"Werewolf", "Grimvale"}
        print("assistant smoke: ok (fake provider, no paid model request)")
        return 0
    finally:
        settings.ASSISTANT_ENABLED = previous_enabled
        app.dependency_overrides.clear()
        session.close()
        engine.dispose()
        SMOKE_TMP.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
