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


def is_non_creature_catalog_title(value: str | None) -> bool:
    return (
        str(value or "")
        .strip()
        .casefold()
        in NON_CREATURE_CATALOG_TITLES
    )
