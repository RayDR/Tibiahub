from types import SimpleNamespace

from app.api.v1.npcs_locations import _npc_matches_category


def npc(*, title=None, occupation=None, buys=None, sells=None, quests=None, travel=None):
    return SimpleNamespace(
        title=title,
        occupation=occupation,
        buys=buys or [],
        sells=sells or [],
        related_quests=quests or [],
        destinations=travel or [],
    )


def test_semantic_categories_match_directory_presentation():
    artist = npc(occupation="Artist")
    assert _npc_matches_category(artist, "service")
    assert not _npc_matches_category(artist, "information")

    spy = npc(occupation="Spy")
    assert _npc_matches_category(spy, "information")
    assert not _npc_matches_category(spy, "service")

    trader = npc(occupation="Merchant", sells=[{"name": "Rope"}])
    assert _npc_matches_category(trader, "trade")
    assert not _npc_matches_category(trader, "service")

    ferryman = npc(occupation="Ferryman", travel=[{"name": "Thais"}])
    assert _npc_matches_category(ferryman, "travel")
    assert not _npc_matches_category(ferryman, "service")

    quest_giver = npc(occupation="Adventurer", quests=[{"name": "Explorer Society Quest"}])
    assert _npc_matches_category(quest_giver, "quests")
    assert not _npc_matches_category(quest_giver, "service")


def test_legacy_category_aliases_remain_available():
    trader = npc(
        occupation="Merchant",
        buys=[{"name": "Rope"}],
        sells=[{"name": "Shovel"}],
    )
    assert _npc_matches_category(trader, "buys")
    assert _npc_matches_category(trader, "sells")

    unclassified = npc()
    assert _npc_matches_category(unclassified, "other")
