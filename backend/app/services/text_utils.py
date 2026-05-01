"""Shared text normalization and ranking helpers."""
from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def normalize_search_text(value: str | None) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKD", value)
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    normalized = normalized.lower().strip()
    normalized = _NON_ALNUM_RE.sub(" ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def slugify(value: str | None) -> str:
    return normalize_search_text(value).replace(" ", "-") or "unknown"


def similarity_ratio(left: str | None, right: str | None) -> float:
    return SequenceMatcher(a=normalize_search_text(left), b=normalize_search_text(right)).ratio()