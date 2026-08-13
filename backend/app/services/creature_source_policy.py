"""Source-level policy for TibiaWiki creature catalog records."""

from __future__ import annotations


NON_CREATURE_CATALOG_TITLES = frozenset(
    {
        "bestiary/classes",
        "creatures",
        "creatures immune to all damage types",
        "rookgaard creatures",
        "sounds",
        "unreachable creatures",
    }
)

NON_CREATURE_CATALOG_PREFIXES = (
    "list of creatures",
)


def is_non_creature_catalog_title(value: str | None) -> bool:
    normalized = str(value or "").strip().casefold()

    return (
        normalized in NON_CREATURE_CATALOG_TITLES
        or normalized.startswith(NON_CREATURE_CATALOG_PREFIXES)
    )
