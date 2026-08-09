from app.models import Creature
from app.models.settings import SystemSettings


def creature(
    name: str,
    *,
    bestiary_class=None,
    creature_class=None,
    classification=None,
    is_boss=False,
    is_hidden=False,
):
    return Creature(
        name=name,
        normalized_name=name.lower(),
        slug=name.lower().replace(" ", "-"),
        hitpoints=100,
        experience=100,
        bestiary_class=bestiary_class,
        creature_class=creature_class,
        classification=classification,
        is_boss=is_boss,
        is_hidden=is_hidden,
    )


def test_category_counts_use_effective_taxonomy_and_visible_non_boss_total(
    client,
    db,
):
    db.add_all(
        [
            creature(
                "Explicit Mammal",
                bestiary_class="Mammal",
            ),
            creature(
                "Legacy Mammal",
                creature_class="Mammals",
                classification="Beast",
            ),
            creature(
                "Unresolved Invertebrate",
                creature_class="Invertebrates",
                classification="Beast",
            ),
            creature(
                "Hidden Demon",
                bestiary_class="Demon",
                is_hidden=True,
            ),
            creature(
                "Boss Dragon",
                bestiary_class="Dragon",
                is_boss=True,
            ),
        ]
    )
    db.flush()

    response = client.get(
        "/api/v1/creatures/category-counts"
    )

    assert response.status_code == 200

    payload = response.json()

    # All includes unresolved visible non-boss records.
    assert payload["all"] == 3

    # Both explicit and safe legacy mapping resolve to Mammal.
    assert payload["mammal"] == 2

    # Hidden/boss records are excluded.
    assert payload["demon"] == 0
    assert payload["dragon"] == 0

    # Legacy synthetic taxonomy must never leak publicly.
    assert "beast" not in payload

    # Unresolved records are intentionally not guessed.
    categorized = sum(
        value
        for key, value in payload.items()
        if key != "all"
    )
    assert payload["all"] - categorized == 1


def test_category_images_hide_legacy_and_unknown_keys(
    client,
    db,
):
    db.add_all(
        [
            SystemSettings(
                key="cyclopedia_category_image_mammal",
                value="/api/v1/creatures/category-images/file/mammal.gif",
                is_active=True,
            ),
            SystemSettings(
                key="cyclopedia_category_image_extra_dimensional",
                value="/api/v1/creatures/category-images/file/extra.gif",
                is_active=True,
            ),
            SystemSettings(
                key="cyclopedia_category_image_beast",
                value="/legacy/beast.gif",
                is_active=True,
            ),
            SystemSettings(
                key="cyclopedia_category_image_not_real",
                value="/legacy/not-real.gif",
                is_active=True,
            ),
        ]
    )
    db.flush()

    response = client.get(
        "/api/v1/creatures/category-images"
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload == {
        "mammal": (
            "/api/v1/creatures/category-images/file/"
            "mammal.gif"
        ),
        "extra_dimensional": (
            "/api/v1/creatures/category-images/file/"
            "extra.gif"
        ),
    }
