"""
Real bestiary source integration using Tibia Fandom MediaWiki APIs.
"""
from __future__ import annotations

import asyncio
import html
import logging
import re
import time
import zlib
from threading import Lock
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import httpx

from app.core.config import settings
from app.services.external_resilience import request_json_with_resilience
from app.services.mock_data import MOCK_CREATURE

logger = logging.getLogger(__name__)

_LINK_RE = re.compile(r"\[\[(?:[^|\]]+\|)?([^\]]+)\]\]")
_HTML_RE = re.compile(r"<[^>]+>")
_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
_DANGLING_COMMENT_RE = re.compile(r"<!--.*$", re.S)
_GALLERY_RE = re.compile(
    r"<gallery\b[^>]*>.*?</gallery\s*>",
    re.I | re.S,
)
_UNCLOSED_GALLERY_RE = re.compile(
    r"<gallery\b[^>]*>.*$",
    re.I | re.S,
)
_TEMPLATE_RE = re.compile(r"\{\{[^{}]*\}\}")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
_SEMANTIC_EMPTY_TEXT = {
    "",
    "?",
    "??",
    "--",
    "unknown",
    "n/a",
    "n.a",
    "none",
}

_LSTH_RE = re.compile(
    r"^\s*\{\{#lsth\s*:\s*([^|{}]+?)\s*\|\s*([^{}]+?)\s*\}\}\s*$",
    re.I | re.S,
)

_MESSAGE_TEMPLATE_RE = re.compile(
    r"\{\{(?:sound|server message)\|([^{}]*?)\}\}",
    re.I | re.S,
)

_WIKI_HEADING_RE = re.compile(
    r"^(={1,6})\s*(.*?)\s*\1\s*$"
)

BESTIARY_CHARM_POINTS = {
    "Harmless": 1,
    "Trivial": 5,
    "Easy": 15,
    "Medium": 25,
    "Hard": 50,
}

CLASSIFICATION_KEYWORDS = {
    "Humanoid": ["human", "humanoid", "orc", "barbarian", "pirate", "minotaur"],
    "Undead": ["undead", "skeleton", "ghoul", "vampire", "lich", "zombie"],
    "Demon": ["demon", "hellspawn"],
    "Dragon": ["dragon", "drake", "wyrm", "wyvern", "hydra"],
    "Elemental": ["elemental", "fire", "ice", "earth", "energy", "stone golem"],
    "Construct": ["construct", "golem", "automaton", "machine"],
}


class BestiarySourceError(Exception):
    """Raised when live bestiary data cannot be retrieved."""


@dataclass
class CacheEntry:
    expires_at: float
    value: Any


_cache: Dict[str, CacheEntry] = {}
_cache_lock = Lock()


def _cache_get(cache_key: str) -> Optional[Any]:
    with _cache_lock:
        entry = _cache.get(cache_key)
    if not entry:
        return None
    if entry.expires_at < time.time():
        with _cache_lock:
            _cache.pop(cache_key, None)
        return None
    return entry.value


def _cache_set(cache_key: str, value: Any, ttl_seconds: int) -> Any:
    with _cache_lock:
        _cache[cache_key] = CacheEntry(expires_at=time.time() + ttl_seconds, value=value)
    return value


def normalize_name(value: str) -> str:
    lowered = value.strip().lower()
    lowered = html.unescape(lowered)
    lowered = _NON_ALNUM_RE.sub(" ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def creature_id_for_name(name: str) -> int:
    # PostgreSQL INTEGER is signed 32-bit. CRC32 is unsigned and can produce
    # values above 2_147_483_647, so constrain generated compatibility IDs to
    # the positive signed range while preserving deterministic lookups.
    return zlib.crc32(normalize_name(name).encode("utf-8")) & 0x7FFFFFFF


def slugify_name(name: str) -> str:
    return _NON_ALNUM_RE.sub("-", name.strip().lower()).strip("-") or "creature"


def _build_wiki_page_url(title: str) -> str:
    title_path = quote(title.replace(" ", "_"), safe="_()/:-")
    return f"{settings.TIBIAWIKI_BASE_PAGE_URL}/{title_path}"


def _build_sprite_url(asset_name: str) -> str:
    quoted = quote(asset_name.replace(" ", "_"), safe="_.-()")
    return f"{settings.TIBIAWIKI_BASE_PAGE_URL}/Special:FilePath/{quoted}.gif"


def _build_file_reference_url(
    file_reference: str,
) -> str:
    """
    Build Special:FilePath only from an explicit MediaWiki File reference.
    Unlike _build_sprite_url(), this function never invents an extension.
    """
    value = str(file_reference or "").strip()

    if value.casefold().startswith("file:"):
        value = value[5:].strip()

    quoted = quote(
        value.replace(" ", "_"),
        safe="_.-()",
    )

    return (
        f"{settings.TIBIAWIKI_BASE_PAGE_URL}"
        f"/Special:FilePath/{quoted}"
    )



def _is_semantic_empty_text(value: object) -> bool:
    """
    Return True only for canonical/source placeholder text such as
    Unknown, None, ?, N/A, etc. Empty/None values are also semantically empty.
    """
    if value is None:
        return True

    marker = html.unescape(str(value)).strip().casefold()
    marker = marker.rstrip(".").strip()

    return marker in _SEMANTIC_EMPTY_TEXT



def _strip_markup(value: str) -> str:
    text = html.unescape(value or "")

    # Galleries are presentation/media metadata, not semantic prose.
    # Preserve meaningful prose that appears before or after them.
    text = _GALLERY_RE.sub(" ", text)
    text = _UNCLOSED_GALLERY_RE.sub(" ", text)

    # Infobox values are parsed line-by-line. A multiline comment may
    # therefore appear here only as its opening fragment.
    text = _COMMENT_RE.sub("", text)
    text = _DANGLING_COMMENT_RE.sub("", text)

    text = (
        text.replace("<br />", ", ")
        .replace("<br/>", ", ")
        .replace("<br>", ", ")
    )

    text = _LINK_RE.sub(
        lambda match: match.group(1),
        text,
    )

    previous = None
    while previous != text:
        previous = text
        text = _TEMPLATE_RE.sub("", text)

    text = _HTML_RE.sub("", text)
    text = text.replace("'''", "").replace("''", "")
    text = text.replace("&nbsp;", " ")
    text = re.sub(r"\s+", " ", text)

    cleaned = text.strip(" ,")

    marker = cleaned.casefold().strip()
    marker = marker.rstrip(".").strip()

    if marker in _SEMANTIC_EMPTY_TEXT:
        return ""

    return cleaned



def _parse_lsth_transclusion(
    value: Optional[str],
) -> Optional[Dict[str, str]]:
    raw = str(value or "").strip()
    if not raw:
        return None

    match = _LSTH_RE.fullmatch(raw)
    if match is None:
        return None

    page = match.group(1).strip()
    section = match.group(2).strip()

    if not page or not section:
        return None

    return {
        "page": page,
        "section": section,
    }


def _remove_media_wikilinks(value: str) -> str:
    """Remove File:/Image: wikilinks, including links with nested captions."""
    text = value or ""
    output: List[str] = []
    cursor = 0
    length = len(text)

    while cursor < length:
        start = text.find("[[", cursor)

        if start < 0:
            output.append(text[cursor:])
            break

        output.append(text[cursor:start])

        pos = start + 2
        depth = 1

        while pos < length and depth:
            if text.startswith("[[", pos):
                depth += 1
                pos += 2
                continue

            if text.startswith("]]", pos):
                depth -= 1
                pos += 2
                continue

            pos += 1

        if depth != 0:
            # Unbalanced markup: preserve it rather than guessing.
            output.append(text[start:])
            break

        block = text[start:pos]
        inner = block[2:-2]
        target = inner.split("|", 1)[0].strip().casefold()

        if target.startswith("file:") or target.startswith("image:"):
            output.append(" ")
        else:
            output.append(block)

        cursor = pos

    return "".join(output)


def _extract_wiki_section(
    wikitext: str,
    section_title: str,
) -> Optional[str]:
    """Extract one exact heading section without following provider links."""
    lines = (wikitext or "").splitlines()
    wanted = normalize_name(_strip_markup(section_title or ""))

    headings: List[tuple[int, int, str]] = []

    for index, line in enumerate(lines):
        match = _WIKI_HEADING_RE.match(line.strip())
        if match is None:
            continue

        headings.append(
            (
                index,
                len(match.group(1)),
                match.group(2).strip(),
            )
        )

    matches = [
        heading
        for heading in headings
        if normalize_name(_strip_markup(heading[2])) == wanted
    ]

    if len(matches) != 1:
        return None

    start, level, _title = matches[0]
    end = len(lines)

    for next_index, next_level, _next_title in headings:
        if next_index <= start:
            continue

        if next_level <= level:
            end = next_index
            break

    return "\n".join(
        lines[start + 1:end]
    ).strip()


def _strip_strategy_section_markup(value: str) -> str:
    """
    Strip presentation-oriented wikitext from a quest strategy section while
    preserving semantic prose, list items, dialogue and table cell content.
    """
    text = html.unescape(value or "")

    text = _GALLERY_RE.sub(" ", text)
    text = _UNCLOSED_GALLERY_RE.sub(" ", text)
    text = _COMMENT_RE.sub(" ", text)
    text = _DANGLING_COMMENT_RE.sub(" ", text)

    # File/Image links are presentation evidence, not strategy prose.
    text = _remove_media_wikilinks(text)

    # Preserve message/dialogue text before removing the remaining templates.
    previous = None
    while previous != text:
        previous = text

        text = _MESSAGE_TEMPLATE_RE.sub(
            lambda match: match.group(1).strip(),
            text,
        )

    previous = None
    while previous != text:
        previous = text
        text = _TEMPLATE_RE.sub(" ", text)

    text = (
        text.replace("<br />", "\n")
        .replace("<br/>", "\n")
        .replace("<br>", "\n")
    )

    text = _HTML_RE.sub(" ", text)

    output: List[str] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()

        if not line:
            continue

        # MediaWiki table framing.
        if (
            line.startswith("{|")
            or line == "|}"
            or line.startswith("|-")
        ):
            continue

        # Table header metadata is not strategy prose.
        if line.startswith("!"):
            continue

        if line.startswith("|"):
            line = line[1:].strip()

            # Pure style/document metadata cells are presentation-only.
            if line.casefold().startswith("style="):
                continue

        line = line.lstrip("*#;: ").strip()

        if not line:
            continue

        cleaned = _strip_markup(line)

        if not cleaned:
            continue

        marker = cleaned.casefold().strip()

        if marker in {
            "right",
            "left",
            "center",
            "thumb",
        }:
            continue

        if re.fullmatch(r"\\d+px", marker):
            continue

        output.append(cleaned)

    cleaned = " ".join(output)

    # Images used only as status icons can leave an empty "(icon)" shell.
    cleaned = re.sub(
        r"\\(\\s*icon\\s*\\)",
        "",
        cleaned,
        flags=re.I,
    )

    cleaned = re.sub(
        r"\\s+",
        " ",
        cleaned,
    ).strip(" ,")

    return cleaned



def _extract_infobox_param_map(wikitext: str) -> Dict[str, str]:
    params: Dict[str, str] = {}
    for line in wikitext.splitlines():
        match = re.match(r"^\|\s*([^=\n]+?)\s*=\s*(.*)$", line)
        if not match:
            continue
        key = match.group(1).strip().lower()
        if key not in params:
            params[key] = match.group(2).strip()
    return params


def _dedupe_reference_values(
    values: List[str],
) -> List[str]:
    result: List[str] = []
    seen: set[str] = set()

    for raw_value in values:
        item = _strip_markup(raw_value).strip()

        # Removing templates such as Mapper Coords can leave "." or
        # other punctuation-only fragments. They are not locations.
        if not item or not any(
            character.isalnum()
            for character in item
        ):
            continue

        key = re.sub(
            r"\s+",
            " ",
            item,
        ).casefold()

        if key in seen:
            continue

        seen.add(key)
        result.append(item)

    return result


def _extract_links(value: str) -> List[str]:
    links = [
        match.group(1)
        for match in _LINK_RE.finditer(value)
    ]

    if links:
        return _dedupe_reference_values(links)

    cleaned = _strip_markup(value)

    if not cleaned:
        return []

    return _dedupe_reference_values(
        [
            item.strip()
            for item in cleaned.split(",")
        ]
    )


_LOOT_AMOUNT_TOKEN_RE = re.compile(
    r"^\d+(?:\s*-\s*(?:\d+|\?))?\s*[?+]?$"
)


def _is_loot_amount_token(value: str) -> bool:
    return bool(
        _LOOT_AMOUNT_TOKEN_RE.fullmatch(
            (value or "").strip()
        )
    )


def _parse_amount(raw_value: Optional[str]) -> tuple[int, int]:
    if not raw_value:
        return 1, 1

    value = raw_value.strip()

    match = re.match(
        r"^(\d+)\s*-\s*(\d+)",
        value,
    )
    if match:
        return int(match.group(1)), int(match.group(2))

    match = re.match(r"^(\d+)", value)
    if match:
        amount = int(match.group(1))
        return amount, amount

    return 1, 1


def _extract_loot_items(wikitext: str) -> List[Dict[str, Any]]:
    loot_items: List[Dict[str, Any]] = []
    for raw_item in re.findall(r"\{\{Loot Item\|([^{}]+)\}\}", wikitext):
        parts = [part.strip() for part in raw_item.split("|") if part.strip()]
        if not parts:
            continue

        if _is_loot_amount_token(parts[0]):
            amount_raw = parts[0]
            item_name = parts[1] if len(parts) > 1 else "Unknown"
            rarity = parts[2] if len(parts) > 2 else None
        else:
            amount_raw = None
            item_name = parts[0]
            rarity = parts[1] if len(parts) > 1 else None

        min_amount, max_amount = _parse_amount(amount_raw)
        item_name = _strip_markup(item_name)
        rarity_value = _strip_markup(rarity).title() if rarity else None
        item_slug = slugify_name(item_name)
        loot_items.append(
            {
                "id": zlib.crc32(f"loot:{item_slug}".encode("utf-8")) & 0xFFFFFFFF,
                "item_name": item_name,
                "rarity": rarity_value,
                "percentage": None,
                "min_amount": min_amount,
                "max_amount": max_amount,
                "item_value": None,
                "item_type": None,
                "item_image_url": _build_sprite_url(item_name),
                "source_url": _build_wiki_page_url(item_name),
            }
        )
    return loot_items


def _to_int(value: Optional[str]) -> Optional[int]:
    if value in (None, "", "--"):
        return None
    match = re.search(r"-?\d[\d,]*", value)
    if not match:
        return None
    return int(match.group(0).replace(",", ""))


def _to_bool(value: Optional[str]) -> bool:
    return str(value or "").strip().lower() in {"yes", "true", "1"}


def _infer_classification(*, name: str, creature_class: Optional[str], bestiary_class: Optional[str]) -> Optional[str]:
    haystack = " ".join([name or "", creature_class or "", bestiary_class or ""]).lower()
    for label, keywords in CLASSIFICATION_KEYWORDS.items():
        if any(keyword in haystack for keyword in keywords):
            return label
    return None


async def _request_json(
    *,
    url: str,
    params: Optional[Dict[str, Any]],
    cache_key: str,
    ttl_seconds: int,
) -> Dict[str, Any]:
    cached = _cache_get(cache_key)
    if cached is not None:
        logger.info("external_request url=%s cache_hit=true fallback=false", f"{url}?{params}" if params else url)
        return cached

    headers = {"User-Agent": settings.TIBIAWIKI_USER_AGENT, "Accept": "application/json"}
    data = await request_json_with_resilience(
        provider="tibiawiki",
        url=url,
        params=params,
        headers=headers,
        timeout_seconds=20.0,
        retries=2,
        retry_backoff_seconds=0.5,
        circuit_failures=3,
        circuit_cooldown_seconds=45,
    )
    logger.info(
        "external_request url=%s cache_hit=false fallback=false",
        f"{url}?{params}" if params else url,
    )
    return _cache_set(cache_key, data, ttl_seconds)


async def get_category_members(category: str) -> List[str]:
    cache_key = f"category:{category}"
    cached = _cache_get(cache_key)
    if cached is not None:
        logger.info("external_category category=%s cache_hit=true", category)
        return cached

    titles: List[str] = []
    continuation: Optional[str] = None
    while True:
        params: Dict[str, Any] = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": f"Category:{category}",
            "cmlimit": 500,
            "cmtype": "page",
            "format": "json",
        }
        if continuation:
            params["cmcontinue"] = continuation

        data = await _request_json(
            url=settings.TIBIAWIKI_API_URL,
            params=params,
            cache_key=f"{cache_key}:{continuation or 'first'}",
            ttl_seconds=settings.EXTERNAL_API_LIST_CACHE_TTL_SECONDS,
        )
        titles.extend(member["title"] for member in data.get("query", {}).get("categorymembers", []))
        continuation = data.get("continue", {}).get("cmcontinue")
        if not continuation:
            break

    deduped: List[str] = []
    seen = set()
    for title in titles:
        normalized = normalize_name(title)
        if not normalized or normalized in seen or ":" in title or title.startswith("List of"):
            continue
        seen.add(normalized)
        deduped.append(title)

    logger.info("external_category category=%s count=%s cache_hit=false", category, len(deduped))
    return _cache_set(cache_key, deduped, settings.EXTERNAL_API_LIST_CACHE_TTL_SECONDS)


async def get_page_wikitext(title: str) -> str:
    data = await _request_json(
        url=settings.TIBIAWIKI_API_URL,
        params={"action": "parse", "page": title, "prop": "wikitext", "format": "json"},
        cache_key=f"page:{title}",
        ttl_seconds=settings.EXTERNAL_API_CACHE_TTL_SECONDS,
    )
    parsed = data.get("parse", {})
    wikitext = parsed.get("wikitext", {}).get("*")
    if not wikitext:
        raise BestiarySourceError(f"No wikitext returned for page '{title}'")
    return wikitext


async def get_page_links(title: str) -> List[str]:
    """Return internal page links for a given wiki page title."""
    data = await _request_json(
        url=settings.TIBIAWIKI_API_URL,
        params={"action": "parse", "page": title, "prop": "links", "format": "json"},
        cache_key=f"page-links:{title}",
        ttl_seconds=settings.EXTERNAL_API_CACHE_TTL_SECONDS,
    )
    links = (data.get("parse") or {}).get("links") or []
    names: List[str] = []
    seen: set[str] = set()
    for entry in links:
        link_name = (entry or {}).get("*")
        if not link_name or ":" in link_name:
            continue
        normalized = normalize_name(link_name)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        names.append(link_name)
    return names


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", normalize_name(value)).strip("-")


def _extract_string_list(value: Optional[str]) -> List[str]:
    if not value:
        return []
    cleaned = _strip_markup(value)
    if not cleaned:
        return []
    parts = [item.strip() for item in re.split(r"[,;]", cleaned) if item.strip()]
    return parts


def _extract_requirement_lines(wikitext: str) -> List[str]:
    found: List[str] = []
    in_section = False
    for line in wikitext.splitlines():
        section_match = re.match(r"^==+\s*(.+?)\s*==+\s*$", line.strip())
        if section_match:
            section_name = normalize_name(section_match.group(1))
            in_section = section_name in {"requirements", "requirement", "missions", "mission"}
            continue
        if not in_section:
            continue
        raw = line.strip().lstrip("*#")
        if not raw:
            continue
        parsed = _strip_markup(raw)
        if parsed:
            found.append(parsed)
        if len(found) >= 20:
            break
    return found


async def get_quest_page_summary(title: str) -> Dict[str, Any]:
    """Extract lightweight quest metadata from page wikitext."""
    wikitext = await get_page_wikitext(title)
    params = _extract_infobox_param_map(wikitext)
    display_name = _strip_markup(params.get("name") or title)
    source_url = _build_wiki_page_url(display_name)

    rewards = _extract_string_list(params.get("reward") or params.get("rewards") or params.get("treasure"))
    requirements = _extract_string_list(params.get("requirements") or params.get("requirement"))
    if not requirements:
        requirements = _extract_requirement_lines(wikitext)

    npc = _strip_markup(params.get("npc") or params.get("questgiver") or "") or None
    location = _strip_markup(params.get("location") or params.get("startinglocation") or "") or None

    return {
        "name": display_name,
        "slug": _slugify(display_name),
        "description": _strip_markup(params.get("description") or params.get("summary") or "") or None,
        "min_level": _to_int(params.get("level") or params.get("minlevel")),
        "max_level": _to_int(params.get("maxlevel")),
        "npc": npc,
        "location": location,
        "requirements": requirements,
        "rewards": rewards,
        "source_url": source_url,
    }


async def get_tibiamaps_markers(limit: int = 2000) -> List[Dict[str, Any]]:
    """Fetch marker metadata from tibiamaps/tibia-map-data (public JSON)."""
    data = await _request_json(
        url="https://tibiamaps.github.io/tibia-map-data/markers.json",
        params=None,
        cache_key="tibiamaps:markers",
        ttl_seconds=settings.EXTERNAL_API_LIST_CACHE_TTL_SECONDS,
    )
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)][:limit]


async def get_tibiamaps_bounds() -> Dict[str, Any]:
    """Fetch world bounds metadata from tibiamaps/tibia-map-data."""
    data = await _request_json(
        url="https://tibiamaps.github.io/tibia-map-data/bounds.json",
        params=None,
        cache_key="tibiamaps:bounds",
        ttl_seconds=settings.EXTERNAL_API_LIST_CACHE_TTL_SECONDS,
    )
    return data if isinstance(data, dict) else {}


def _build_creature_payload(
    name: str,
    wikitext: str,
    *,
    image_reference: str | None = None,
) -> Dict[str, Any]:
    params = _extract_infobox_param_map(wikitext)

    def optional_text(value: Optional[str]) -> Optional[str]:
        cleaned = _strip_markup(value or "")
        if not cleaned:
            return None
        if cleaned.strip().lower() in {
            "?",
            "??",
            "--",
            "unknown",
            "unknown.",
            "n/a",
            "n.a.",
            "none",
        }:
            return None
        return cleaned

    display_name = _strip_markup(params.get("name") or name)
    actual_name = _strip_markup(params.get("actualname") or display_name)

    hitpoints = _to_int(params.get("hp"))
    experience = _to_int(params.get("exp"))
    armor = _to_int(params.get("armor"))
    speed = _to_int(params.get("speed"))
    max_damage = _to_int(params.get("maxdmg"))
    summon_cost = _to_int(params.get("summon"))
    convince_cost = _to_int(params.get("convince"))

    bestiary_class = optional_text(params.get("bestiaryclass"))
    bestiary_level = optional_text(params.get("bestiarylevel"))
    creature_class = optional_text(params.get("creatureclass"))
    primary_type = optional_text(params.get("primarytype"))

    raw_bestiary_text = params.get("bestiarytext")
    raw_notes = params.get("notes")
    raw_behavior = (
        params.get("behaviour")
        if "behaviour" in params
        else params.get("behavior")
    )
    raw_strategy = params.get("strategy")
    raw_location = params.get("location")

    bestiary_text = optional_text(raw_bestiary_text)
    notes = optional_text(raw_notes)

    # TibiaWiki uses these as two distinct semantics:
    # - behaviour: what the creature itself does
    # - strategy: advice for the player fighting it
    behavior = optional_text(raw_behavior)

    strategy_transclusion = _parse_lsth_transclusion(
        raw_strategy
    )

    strategy = (
        None
        if strategy_transclusion is not None
        else optional_text(raw_strategy)
    )

    # Keep description backward-compatible for pages that have no bestiary
    # text while preserving notes separately when both exist.
    description = bestiary_text or notes

    locations = _extract_links(raw_location or "")
    loot_items = _extract_loot_items(wikitext)

    # Source absence, blank source fields, and explicit semantic-empty source
    # values are three distinct contracts.
    #
    #   absent:
    #       no provider evidence -> preserve canonical
    #
    #   present but blank:
    #       provider currently supplies no value -> clear only a canonical
    #       semantic placeholder, never useful canonical prose
    #
    #   present with Unknown/None/?/N/A or markup that sanitizes empty:
    #       explicit semantic-empty evidence -> stale canonical may be cleared
    #
    # This prevents an empty "| behaviour =" from erasing useful historical
    # knowledge while still removing legacy canonical values such as
    # "Unknown." and "None.".
    source_clear_fields: set[str] = set()
    source_blank_fields: set[str] = set()

    bestiary_text_supplied = (
        "bestiarytext" in params
    )
    notes_supplied = (
        "notes" in params
    )
    behavior_supplied = (
        "behaviour" in params
        or "behavior" in params
    )
    strategy_supplied = (
        "strategy" in params
    )
    location_supplied = (
        "location" in params
    )

    def classify_empty_source(
        field: str,
        *,
        supplied: bool,
        raw_values: tuple[object, ...],
        parsed_value: object,
    ) -> None:
        if not supplied:
            return

        if parsed_value not in (None, "", [], ()):
            return

        supplied_raw = [
            value
            for value in raw_values
            if value is not None
        ]

        has_nonblank_raw = any(
            bool(str(value).strip())
            for value in supplied_raw
        )

        if has_nonblank_raw:
            source_clear_fields.add(field)
        else:
            source_blank_fields.add(field)

    classify_empty_source(
        "behavior",
        supplied=behavior_supplied,
        raw_values=(raw_behavior,),
        parsed_value=behavior,
    )

    if strategy_transclusion is None:
        classify_empty_source(
            "strategy",
            supplied=strategy_supplied,
            raw_values=(raw_strategy,),
            parsed_value=strategy,
        )

    classify_empty_source(
        "description",
        supplied=(
            bestiary_text_supplied
            or notes_supplied
        ),
        raw_values=(
            raw_bestiary_text,
            raw_notes,
        ),
        parsed_value=description,
    )

    classify_empty_source(
        "notes",
        supplied=notes_supplied,
        raw_values=(raw_notes,),
        parsed_value=notes,
    )

    classify_empty_source(
        "locations",
        supplied=location_supplied,
        raw_values=(raw_location,),
        parsed_value=locations,
    )

    source_unknown_fields = [
        field
        for field, value in {
            "hitpoints": hitpoints,
            "experience": experience,
            "armor": armor,
            "speed": speed,
            "max_damage": max_damage,
        }.items()
        if value is None
    ]

    # Media identity is evidence-driven when MediaWiki supplied an exact
    # File reference. The historical name-derived URL remains a compatibility
    # fallback only; it is explicitly labelled as synthetic provenance.
    exact_image_reference = (
        str(image_reference).strip()
        if image_reference
        else None
    )

    if exact_image_reference:
        image_url = _build_file_reference_url(
            exact_image_reference
        )
        image_evidence = "page_images_exact"
    elif actual_name:
        image_url = _build_sprite_url(
            actual_name
        )
        image_evidence = "synthetic_name_fallback"
    else:
        image_url = None
        image_evidence = "none"

    missing_fields = [
        field
        for field, value in {
            "image_url": image_url,
            "experience": experience,
            "hitpoints": hitpoints,
            "locations": locations,
            "loot": loot_items,
        }.items()
        if value in (None, "", [], {})
    ]

    payload = {
        "id": creature_id_for_name(display_name),
        "slug": slugify_name(display_name),
        "name": display_name,
        "article": optional_text(params.get("article")),
        "plural": optional_text(params.get("plural")),
        "hitpoints": hitpoints,
        "experience": experience,
        "armor": armor,
        "speed": speed,
        "max_damage": max_damage,
        "summon_cost": summon_cost,
        "convince_cost": convince_cost,
        "difficulty": bestiary_level,
        "occurrence": optional_text(params.get("occurrence")),
        "is_boss": _to_bool(params.get("isboss")),
        "loot_value": None,
        "description": description,
        "behavior": behavior,
        "strategy": strategy,
        "notes": notes,
        "image_url": image_url,
        "image_file_reference": exact_image_reference,
        "image_evidence": image_evidence,
        "loot_items": loot_items,
        "spawn_locations": [],
        "weaknesses": [],
        "resistances": [],
        "locations": locations,
        "related_tasks": [],
        "bestiary_class": bestiary_class,
        "bestiary_level": bestiary_level,
        "charm_points": BESTIARY_CHARM_POINTS.get(bestiary_level),
        "creature_class": creature_class,
        "primary_type": primary_type,
        "source_url": _build_wiki_page_url(display_name),
        "data_sources": ["tibiawiki", "tibiadata"],
        "missing_fields": missing_fields,
        "source_unknown_fields": source_unknown_fields,
        "source_clear_fields": sorted(source_clear_fields),
        "source_blank_fields": sorted(source_blank_fields),
        "strategy_transclusion": strategy_transclusion,
        "classification": _infer_classification(
            name=display_name,
            creature_class=creature_class,
            bestiary_class=bestiary_class,
        ),
    }

    if missing_fields:
        logger.warning(
            "creature_incomplete name=%s missing=%s",
            display_name,
            ",".join(missing_fields),
        )

    return payload

async def get_creature_detail_by_name(name: str) -> Dict[str, Any]:
    if settings.USE_MOCK_DATA:
        mock_payload = dict(MOCK_CREATURE)
        mock_payload.update({"id": creature_id_for_name(name), "slug": slugify_name(name), "name": name})
        return mock_payload

    return _build_creature_payload(name, await get_page_wikitext(name))


async def get_creature_name_by_id(creature_id: int) -> Optional[str]:
    names = await get_category_members("Creatures")
    for name in names:
        if creature_id_for_name(name) == creature_id:
            return name
    return None


async def get_creature_detail_by_id(creature_id: int) -> Dict[str, Any]:
    creature_name = await get_creature_name_by_id(creature_id)
    if not creature_name:
        raise BestiarySourceError(f"Creature id '{creature_id}' not found")
    return await get_creature_detail_by_name(creature_name)


async def list_creature_summaries(
    *,
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    difficulty: Optional[str] = None,
    sort_by: str = "name",
    sort_order: str = "asc",
) -> List[Dict[str, Any]]:
    names = await get_category_members("Creatures")
    filtered = names
    if search:
        normalized_search = normalize_name(search)
        filtered = [name for name in filtered if normalized_search in normalize_name(name)]

    if difficulty:
        detailed = await asyncio.gather(*(get_creature_detail_by_name(name) for name in filtered))
        filtered_payload = [item for item in detailed if (item.get("difficulty") or "").lower() == difficulty.lower()]
    else:
        page_names = filtered[skip: skip + limit]
        filtered_payload = await asyncio.gather(*(get_creature_detail_by_name(name) for name in page_names))

    reverse = sort_order.lower() == "desc"
    if sort_by == "experience":
        filtered_payload.sort(key=lambda item: (item.get("experience") or 0, item.get("name") or ""), reverse=reverse)
    elif sort_by == "hitpoints":
        filtered_payload.sort(key=lambda item: (item.get("hitpoints") or 0, item.get("name") or ""), reverse=reverse)
    elif sort_by == "difficulty":
        rank = {"Harmless": 0, "Trivial": 1, "Easy": 2, "Medium": 3, "Hard": 4}
        filtered_payload.sort(key=lambda item: (rank.get(item.get("difficulty") or "", -1), item.get("name") or ""), reverse=reverse)
    else:
        filtered_payload.sort(key=lambda item: item.get("name") or "", reverse=reverse)

    if difficulty:
        filtered_payload = filtered_payload[skip: skip + limit]

    return [
        {
            "id": item["id"],
            "slug": item["slug"],
            "name": item["name"],
            "hitpoints": item["hitpoints"],
            "experience": item["experience"],
            "difficulty": item.get("difficulty"),
            "image_url": item.get("image_url"),
        }
        for item in filtered_payload
    ]


async def list_items(limit: int = 200) -> List[Dict[str, Any]]:
    return [
        {
            "name": name,
            "item_id": None,
            "description": None,
            "type": None,
            "weight": None,
            "value": None,
            "attack": None,
            "defense": None,
            "armor": None,
            "levelrequired": None,
            "vocationrequired": None,
            "tradeable": None,
            "stackable": None,
            "image_url": _build_sprite_url(name),
            "source_url": _build_wiki_page_url(name),
        }
        for name in (await get_category_members("Items"))[:limit]
    ]


async def list_hunting_places(limit: int = 200) -> List[Dict[str, Any]]:
    return [
        {
            "name": name,
            "description": None,
            "location": None,
            "min_level": None,
            "max_level": None,
            "creatures": [],
            "source_url": _build_wiki_page_url(name),
        }
        for name in (await get_category_members("Hunting Places"))[:limit]
    ]


async def list_quests(limit: int = 200) -> List[Dict[str, Any]]:
    return [
        {
            "name": name,
            "description": None,
            "min_level": None,
            "max_level": None,
            "experience_reward": None,
            "treasure": [],
            "location": None,
            "npc": None,
            "source_url": _build_wiki_page_url(name),
        }
        for name in (await get_category_members("Quests"))[:limit]
    ]
