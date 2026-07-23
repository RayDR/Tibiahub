"""Language-neutral normalization helpers for canonical lookup metadata."""

from __future__ import annotations

import re
import unicodedata


_NON_ALPHANUMERIC = re.compile(r"[^a-z0-9]+")


def normalize_name(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.strip())
    ascii_value = "".join(character for character in decomposed if not unicodedata.combining(character))
    return " ".join(_NON_ALPHANUMERIC.sub(" ", ascii_value.casefold()).split())


def slugify(value: str) -> str:
    return normalize_name(value).replace(" ", "-")


def search_tokens(*values: str) -> list[str]:
    return sorted({token for value in values for token in normalize_name(value).split() if token})
