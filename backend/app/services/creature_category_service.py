"""Canonical Cyclopedia creature category resolution."""

from __future__ import annotations

from sqlalchemy import and_, case, func, or_

from app.models import Creature


CANONICAL_CREATURE_CATEGORIES: tuple[str, ...] = (
    "Amphibic",
    "Aquatic",
    "Bird",
    "Construct",
    "Demon",
    "Dragon",
    "Elemental",
    "Extra Dimensional",
    "Fey",
    "Giant",
    "Human",
    "Humanoid",
    "Inkborn",
    "Lycanthrope",
    "Magical",
    "Mammal",
    "Plant",
    "Reptile",
    "Slime",
    "Undead",
    "Vermin",
)


LEGACY_CREATURE_CLASS_CATEGORY_MAP: dict[str, str] = {
    "amphibians": "Amphibic",
    "demons": "Demon",
    "elementals": "Elemental",
    "human": "Human",
    "humans": "Human",
    "humanoids": "Humanoid",
    "inkborn": "Inkborn",
    "lizards": "Reptile",
    "lycanthropes": "Lycanthrope",
    "mammals": "Mammal",
    "reptiles": "Reptile",
    "serpents": "Reptile",
    "the undead": "Undead",
    "undead": "Undead",
}


_CANONICAL_BY_KEY = {
    category.casefold(): category
    for category in CANONICAL_CREATURE_CATEGORIES
}


def _normalized(value: str | None) -> str:
    return (value or "").strip().casefold()


def canonicalize_creature_category(
    value: str | None,
) -> str | None:
    return _CANONICAL_BY_KEY.get(_normalized(value))


def resolve_creature_category(
    *,
    bestiary_class: str | None,
    creature_class: str | None,
    classification: str | None,
) -> str | None:
    """Resolve one creature to the canonical Cyclopedia taxonomy.

    Precedence:
    1. Explicit Tibia bestiary class.
    2. Safe legacy creature-class mapping.
    3. Existing classification only when it is already canonical.

    Ambiguous broad legacy groups are intentionally left uncategorized.
    """

    bestiary = canonicalize_creature_category(
        bestiary_class
    )
    if bestiary is not None:
        return bestiary

    legacy = LEGACY_CREATURE_CLASS_CATEGORY_MAP.get(
        _normalized(creature_class)
    )
    if legacy is not None:
        return legacy

    return canonicalize_creature_category(
        classification
    )


def creature_category_expression():
    """SQL expression matching resolve_creature_category precedence."""

    bestiary_trimmed = func.trim(
        Creature.bestiary_class
    )
    bestiary_normalized = func.lower(
        bestiary_trimmed
    )
    creature_class_normalized = func.lower(
        func.trim(Creature.creature_class)
    )
    classification_normalized = func.lower(
        func.trim(Creature.classification)
    )

    bestiary_missing = or_(
        Creature.bestiary_class.is_(None),
        bestiary_trimmed == "",
    )

    choices = []

    for category in CANONICAL_CREATURE_CATEGORIES:
        choices.append(
            (
                bestiary_normalized == category.lower(),
                category,
            )
        )

    for legacy_class, category in (
        LEGACY_CREATURE_CLASS_CATEGORY_MAP.items()
    ):
        choices.append(
            (
                and_(
                    bestiary_missing,
                    creature_class_normalized
                    == legacy_class,
                ),
                category,
            )
        )

    for category in CANONICAL_CREATURE_CATEGORIES:
        choices.append(
            (
                and_(
                    bestiary_missing,
                    classification_normalized
                    == category.lower(),
                ),
                category,
            )
        )

    return case(*choices, else_=None)
