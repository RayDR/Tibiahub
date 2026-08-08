from app.services.creature_category_service import (
    CANONICAL_CREATURE_CATEGORIES,
    canonicalize_creature_category,
    resolve_creature_category,
)


def test_canonical_taxonomy_uses_real_bestiary_classes():
    assert len(CANONICAL_CREATURE_CATEGORIES) == 21
    assert "Aquatic" in CANONICAL_CREATURE_CATEGORIES
    assert "Extra Dimensional" in CANONICAL_CREATURE_CATEGORIES
    assert "Inkborn" in CANONICAL_CREATURE_CATEGORIES
    assert "Plant" in CANONICAL_CREATURE_CATEGORIES
    assert "Reptile" in CANONICAL_CREATURE_CATEGORIES
    assert "Slime" in CANONICAL_CREATURE_CATEGORIES
    assert "Vermin" in CANONICAL_CREATURE_CATEGORIES
    assert "Beast" not in CANONICAL_CREATURE_CATEGORIES


def test_bestiary_class_has_highest_precedence():
    assert (
        resolve_creature_category(
            bestiary_class="Aquatic",
            creature_class="Invertebrates",
            classification="Beast",
        )
        == "Aquatic"
    )


def test_safe_legacy_creature_classes_are_mapped():
    assert (
        resolve_creature_category(
            bestiary_class=None,
            creature_class="Mammals",
            classification="Beast",
        )
        == "Mammal"
    )

    assert (
        resolve_creature_category(
            bestiary_class=None,
            creature_class="Amphibians",
            classification=None,
        )
        == "Amphibic"
    )

    assert (
        resolve_creature_category(
            bestiary_class=None,
            creature_class="The Undead",
            classification=None,
        )
        == "Undead"
    )


def test_ambiguous_invertebrates_are_not_guessed():
    assert (
        resolve_creature_category(
            bestiary_class=None,
            creature_class="Invertebrates",
            classification=None,
        )
        is None
    )


def test_existing_canonical_classification_is_last_fallback():
    assert (
        resolve_creature_category(
            bestiary_class=None,
            creature_class="Special",
            classification="Dragon",
        )
        == "Dragon"
    )


def test_legacy_beast_classification_is_not_canonical():
    assert (
        resolve_creature_category(
            bestiary_class=None,
            creature_class=None,
            classification="Beast",
        )
        is None
    )

    assert canonicalize_creature_category("Beast") is None


def test_category_matching_is_case_and_whitespace_tolerant():
    assert (
        canonicalize_creature_category(
            "  extra dimensional "
        )
        == "Extra Dimensional"
    )
