from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from app.knowledge.models import KnowledgeDocument, KnowledgeEntity, KnowledgeProvider
from app.models.creature import Creature
from app.models.media_asset import MediaAsset
from app.services import boosted_creatures_service, media_asset_service, tibia_api
from app.services.text_utils import normalize_search_text


@pytest.fixture(autouse=True)
def reset_boosted_cache():
    boosted_creatures_service._reset_boosted_cache_for_tests()
    yield
    boosted_creatures_service._reset_boosted_cache_for_tests()


def _creature(db, name: str, *, is_boss: bool, hidden: bool = False) -> Creature:
    row = Creature(
        name=name,
        normalized_name=normalize_search_text(name),
        slug=normalize_search_text(name).replace(" ", "-"),
        is_boss=is_boss,
        is_hidden=hidden,
        knowledge_entity_id=uuid4(),
    )
    db.add(row)
    db.flush()
    return row


def _asset(db, tmp_path: Path, creature: Creature, *, exists: bool = True) -> MediaAsset:
    path = tmp_path / f"{creature.id}.gif"
    if exists:
        path.write_bytes(b"GIF89a")
    row = MediaAsset(
        asset_key=media_asset_service.build_creature_asset_key(creature),
        status="cached",
        local_path=str(path),
        content_type="image/gif",
        size_bytes=6,
    )
    db.add(row)
    db.flush()
    return row


@pytest.mark.asyncio
async def test_tibiadata_boosted_payload_parsing_uses_v4_contracts(monkeypatch):
    calls: list[str] = []

    async def fake_get_json(url: str):
        calls.append(url)
        if url.endswith("/creatures"):
            return {"creatures": {"boosted": {"name": "Cave Rat", "image_url": "https://static.tibia.com/rat.gif"}}}
        return {"boostable_bosses": {"boosted": {"name": "Ferumbras", "image_url": "https://static.tibia.com/boss.gif"}}}

    monkeypatch.setattr(tibia_api, "_get_json", fake_get_json)
    assert await tibia_api.get_boosted_creature_name() == "Cave Rat"
    assert await tibia_api.get_boosted_boss_name() == "Ferumbras"
    assert calls == [
        f"{tibia_api.settings.TIBIADATA_BASE_URL}/creatures",
        f"{tibia_api.settings.TIBIADATA_BASE_URL}/boostablebosses",
    ]


def test_boosted_projection_resolves_exact_kind_and_verified_local_media_only(
    client, db, tmp_path, monkeypatch,
):
    creature = _creature(db, "Cave Rat", is_boss=False)
    boss = _creature(db, "Ferumbras", is_boss=True)
    _asset(db, tmp_path, creature)
    _asset(db, tmp_path, boss, exists=False)
    observed_before = datetime(2025, 1, 1, tzinfo=UTC)
    provider = KnowledgeProvider(
        provider_id="tibiadata",
        provider_name="TibiaData test provider",
        health="degraded",
        last_success_at=observed_before,
        consecutive_failures=2,
    )
    db.add(provider)
    db.flush()
    knowledge_counts = (
        db.query(KnowledgeEntity).count(),
        db.query(KnowledgeDocument).count(),
    )

    async def creature_name():
        return "Cave Rat"

    async def boss_name():
        return "Ferumbras"

    async def unexpected_download(*_args, **_kwargs):
        raise AssertionError("boosted projection must not download media")

    monkeypatch.setattr(tibia_api, "get_boosted_creature_name", creature_name)
    monkeypatch.setattr(tibia_api, "get_boosted_boss_name", boss_name)
    monkeypatch.setattr(media_asset_service, "cache_media_asset", unexpected_download)

    response = client.get("/api/v1/tibia/boosted")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "available" and payload["source"] == "tibiadata"
    assert payload["observed_at"] is not None
    assert payload["creature"] == {
        "source_name": "Cave Rat",
        "resolution_state": "resolved",
        "id": creature.id,
        "canonical_id": str(creature.knowledge_entity_id),
        "slug": creature.slug,
        "name": creature.name,
        "media": {
            "status": "available",
            "url": f"/api/v1/creatures/{creature.id}/image?placeholder=false",
        },
    }
    assert payload["boss"]["resolution_state"] == "resolved"
    assert payload["boss"]["id"] == boss.id
    assert payload["boss"]["media"] == {"status": "unavailable", "url": None}
    assert "image_url" not in str(payload)
    assert "static.tibia.com" not in str(payload)

    assert (db.query(KnowledgeEntity).count(), db.query(KnowledgeDocument).count()) == knowledge_counts
    assert provider.health == "degraded"
    assert provider.last_success_at == observed_before
    assert provider.consecutive_failures == 2


def test_exact_resolution_rejects_wrong_kind_hidden_unknown_and_ambiguity(db):
    _creature(db, "Wrong Creature Kind", is_boss=True)
    _creature(db, "Wrong Boss Kind", is_boss=False)
    _creature(db, "Hidden Creature", is_boss=False, hidden=True)
    _creature(db, "Duplicate Boss", is_boss=True)
    _creature(db, "Duplicate Boss", is_boss=True)

    cases = [
        ("Wrong Creature Kind", False),
        ("Wrong Boss Kind", True),
        ("Hidden Creature", False),
        ("Unknown Current Name", False),
        ("Duplicate Boss", True),
    ]
    for source_name, is_boss in cases:
        payload = boosted_creatures_service._resolve_local(db, source_name, is_boss=is_boss)
        assert payload["source_name"] == source_name
        assert payload["resolution_state"] == "unresolved"
        assert payload["id"] is None and payload["canonical_id"] is None
        assert payload["slug"] is None and payload["name"] is None
        assert payload["media"] == {"status": "unavailable", "url": None}


@pytest.mark.parametrize(
    ("creature_fails", "boss_fails", "expected_status"),
    [(False, True, "partial"), (True, False, "partial"), (True, True, "unavailable")],
)
def test_upstream_failures_are_independent(
    client, monkeypatch, creature_fails, boss_fails, expected_status,
):
    async def creature_name():
        if creature_fails:
            raise RuntimeError("private provider failure")
        return "Current Creature"

    async def boss_name():
        if boss_fails:
            raise RuntimeError("private provider failure")
        return "Current Boss"

    monkeypatch.setattr(tibia_api, "get_boosted_creature_name", creature_name)
    monkeypatch.setattr(tibia_api, "get_boosted_boss_name", boss_name)
    payload = client.get("/api/v1/tibia/boosted").json()
    assert payload["status"] == expected_status
    if creature_fails:
        assert payload["creature"]["resolution_state"] == "unavailable"
    else:
        assert payload["creature"]["source_name"] == "Current Creature"
    if boss_fails:
        assert payload["boss"]["resolution_state"] == "unavailable"
    else:
        assert payload["boss"]["source_name"] == "Current Boss"
    assert "private provider failure" not in str(payload)


def test_success_cache_ttl_refetches_and_never_serves_expired_data_after_failure(
    client, monkeypatch,
):
    clock = {"now": 100.0}
    calls = {"creature": 0, "boss": 0}
    fail = {"value": False}

    async def creature_name():
        calls["creature"] += 1
        if fail["value"]:
            raise RuntimeError("expired")
        return "Cached Creature"

    async def boss_name():
        calls["boss"] += 1
        if fail["value"]:
            raise RuntimeError("expired")
        return "Cached Boss"

    monkeypatch.setattr(boosted_creatures_service.time, "monotonic", lambda: clock["now"])
    monkeypatch.setattr(tibia_api, "get_boosted_creature_name", creature_name)
    monkeypatch.setattr(tibia_api, "get_boosted_boss_name", boss_name)

    first = client.get("/api/v1/tibia/boosted").json()
    clock["now"] = 399.0
    second = client.get("/api/v1/tibia/boosted").json()
    assert calls == {"creature": 1, "boss": 1}
    assert second["observed_at"] == first["observed_at"]

    clock["now"] = 400.0
    client.get("/api/v1/tibia/boosted")
    assert calls == {"creature": 2, "boss": 2}

    fail["value"] = True
    clock["now"] = 700.0
    expired_failure = client.get("/api/v1/tibia/boosted").json()
    assert calls == {"creature": 3, "boss": 3}
    assert expired_failure["status"] == "unavailable"
    assert expired_failure["observed_at"] is None
    assert expired_failure["creature"]["source_name"] is None
    assert expired_failure["boss"]["source_name"] is None
