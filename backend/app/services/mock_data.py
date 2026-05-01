"""
Explicit mock data for test and demo modes only.

Production code must not reach this module unless USE_MOCK_DATA is enabled.
"""
from typing import Any, Dict, List


MOCK_CHARACTER: Dict[str, Any] = {
    "name": "Mock Character",
    "level": 100,
    "vocation": "Elder Druid",
    "world": "Antica",
    "last_login": "2026-01-01T00:00:00Z",
    "guild": "Mock Guild",
}

MOCK_GUILD: Dict[str, Any] = {
    "name": "Mock Guild",
    "world": "Antica",
    "description": "Mock guild for non-production testing.",
    "members": [
        {"name": "Mock Vice", "rank": "Vice Leader", "level": 300, "vocation": "Knight"},
        {"name": "Mock Member", "rank": "Member", "level": 200, "vocation": "Sorcerer"},
    ],
    "member_count": 2,
}

MOCK_WORLDS: List[Dict[str, Any]] = [
    {"name": "Antica", "status": "online"},
    {"name": "Secura", "status": "online"},
]

MOCK_CREATURE: Dict[str, Any] = {
    "name": "Mock Creature",
    "article": "a",
    "plural": "mock creatures",
    "hitpoints": 250,
    "experience": 150,
    "armor": 10,
    "speed": 140,
    "max_damage": 55,
    "difficulty": "Easy",
    "occurrence": "Common",
    "is_boss": False,
    "description": "Mock creature for isolated testing only.",
    "behavior": "Mock behavior",
    "image_url": "https://example.invalid/mock.gif",
    "loot_items": [],
    "spawn_locations": [],
    "weaknesses": [],
    "resistances": [],
    "locations": [],
    "related_tasks": [],
    "bestiary_class": None,
    "bestiary_level": None,
    "charm_points": None,
    "creature_class": None,
    "primary_type": None,
    "source_url": "https://example.invalid/mock-creature",
    "data_sources": ["mock"],
    "missing_fields": [],
}