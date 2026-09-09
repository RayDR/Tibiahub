from datetime import UTC, datetime

from app.services.category_visual_service import _daily_pick, daily_category_visuals


def test_daily_pick_is_stable_per_day_and_category():
    values = [f"/media/{index}.gif" for index in range(15)]
    day = "2026-09-09"

    assert _daily_pick(values, "items", day) == _daily_pick(values, "items", day)
    assert _daily_pick(values, "quests", day) == _daily_pick(values, "quests", day)
    assert _daily_pick([], "items", day) is None


def test_daily_category_visuals_has_complete_contract_on_empty_database(db):
    result = daily_category_visuals(db, now=datetime(2026, 9, 9, 12, tzinfo=UTC))

    assert result["visual_day"] == "2026-09-09"
    assert set(result) == {
        "visual_day",
        "creatures",
        "bosses",
        "items",
        "quests",
        "zones",
        "npcs",
    }
    assert all(result[key] is None for key in ("creatures", "bosses", "items", "quests", "zones", "npcs"))


def test_daily_category_visual_endpoint_is_public(client):
    response = client.get("/api/v1/catalog/category-visuals/daily")

    assert response.status_code == 200
    payload = response.json()
    assert payload["visual_day"]
    assert "items" in payload and "quests" in payload and "npcs" in payload
    assert "public" in response.headers["cache-control"]
