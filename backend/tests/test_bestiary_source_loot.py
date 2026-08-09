from app.services.bestiary_source import (
    _extract_loot_items,
    _infer_classification,
)


def test_loot_amount_annotations_preserve_real_item_names():
    raw = """
    {{Loot Table|
    {{Loot Item|0-98?|Gold Coin}}
    {{Loot Item|1+|Small Enchanted Sapphire|rare}}
    {{Loot Item|1-29+|Platinum Coin|semi-rare}}
    {{Loot Item|Demon Horn|rare}}
    }}
    """

    items = _extract_loot_items(raw)

    assert [item["item_name"] for item in items] == [
        "Gold Coin",
        "Small Enchanted Sapphire",
        "Platinum Coin",
        "Demon Horn",
    ]

    assert (
        items[0]["min_amount"],
        items[0]["max_amount"],
    ) == (0, 98)

    assert (
        items[1]["min_amount"],
        items[1]["max_amount"],
    ) == (1, 1)

    assert (
        items[2]["min_amount"],
        items[2]["max_amount"],
    ) == (1, 29)

    assert items[1]["rarity"] == "Rare"
    assert items[2]["rarity"] == "Semi-Rare"



def test_legacy_beast_is_not_synthesized():
    assert (
        _infer_classification(
            name="Dire Wolf",
            creature_class=None,
            bestiary_class=None,
        )
        is None
    )

    assert (
        _infer_classification(
            name="Demon",
            creature_class=None,
            bestiary_class=None,
        )
        == "Demon"
    )
