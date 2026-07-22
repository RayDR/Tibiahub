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
_TEMPLATE_RE = re.compile(r"\{\{[^{}]*\}\}")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")

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
    "Beast": ["beast", "mammal", "animal", "boar", "bear", "wolf", "tiger", "lion"],
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
    return zlib.crc32(normalize_name(name).encode("utf-8")) & 0xFFFFFFFF


def slugify_name(name: str) -> str:
    return _NON_ALNUM_RE.sub("-", name.strip().lower()).strip("-") or "creature"


def _build_wiki_page_url(title: str) -> str:
    title_path = quote(title.replace(" ", "_"), safe="_()/:-")
    return f"{settings.TIBIAWIKI_BASE_PAGE_URL}/{title_path}"


def _build_sprite_url(asset_name: str) -> str:
    quoted = quote(asset_name.replace(" ", "_"), safe="_.-()")
    return f"{settings.TIBIAWIKI_BASE_PAGE_URL}/Special:FilePath/{quoted}.gif"


def _strip_markup(value: str) -> str:
    text = html.unescape(value or "")
    text = _COMMENT_RE.sub("", text)
    text = text.replace("<br />", ", ").replace("<br/>", ", ").replace("<br>", ", ")
    text = _LINK_RE.sub(lambda match: match.group(1), text)
    previous = None
    while previous != text:
        previous = text
        text = _TEMPLATE_RE.sub("", text)
    text = _HTML_RE.sub("", text)
    text = text.replace("'''", "").replace("''", "")
    text = text.replace("&nbsp;", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip(" ,")


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


def _extract_links(value: str) -> List[str]:
    links = [_strip_markup(match.group(1)) for match in _LINK_RE.finditer(value)]
    if links:
        return [item for item in links if item]

    cleaned = _strip_markup(value)
    if not cleaned:
        return []
    return [item.strip() for item in cleaned.split(",") if item.strip()]


def _parse_amount(raw_value: Optional[str]) -> tuple[int, int]:
    if not raw_value:
        return 1, 1
    match = re.match(r"^(\d+)\s*-\s*(\d+)$", raw_value)
    if match:
        return int(match.group(1)), int(match.group(2))
    digits = re.search(r"(\d+)", raw_value)
    if digits:
        amount = int(digits.group(1))
        return amount, amount
    return 1, 1


def _extract_loot_items(wikitext: str) -> List[Dict[str, Any]]:
    loot_items: List[Dict[str, Any]] = []
    for raw_item in re.findall(r"\{\{Loot Item\|([^{}]+)\}\}", wikitext):
        parts = [part.strip() for part in raw_item.split("|") if part.strip()]
        if not parts:
            continue

        if re.match(r"^\d+(?:\s*-\s*\d+)?$", parts[0]):
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


def _build_creature_payload(name: str, wikitext: str) -> Dict[str, Any]:
    params = _extract_infobox_param_map(wikitext)
    display_name = _strip_markup(params.get("name") or name)
    actual_name = _strip_markup(params.get("actualname") or display_name)
    bestiary_level = _strip_markup(params.get("bestiarylevel") or "") or None
    locations = _extract_links(params.get("location", ""))
    loot_items = _extract_loot_items(wikitext)
    missing_fields = [
        field
        for field, value in {
            "image_url": actual_name,
            "experience": params.get("exp"),
            "hitpoints": params.get("hp"),
            "locations": locations,
            "loot": loot_items,
        }.items()
        if not value
    ]

    payload = {
        "id": creature_id_for_name(display_name),
        "slug": slugify_name(display_name),
        "name": display_name,
        "article": _strip_markup(params.get("article") or "") or None,
        "plural": _strip_markup(params.get("plural") or "") or None,
        "hitpoints": _to_int(params.get("hp")) or 0,
        "experience": _to_int(params.get("exp")) or 0,
        "armor": _to_int(params.get("armor")) or 0,
        "speed": _to_int(params.get("speed")) or 0,
        "max_damage": _to_int(params.get("maxdmg")),
        "summon_cost": _to_int(params.get("summon")),
        "convince_cost": _to_int(params.get("convince")),
        "difficulty": bestiary_level,
        "occurrence": _strip_markup(params.get("occurrence") or "") or None,
        "is_boss": _to_bool(params.get("isboss")),
        "loot_value": None,
        "description": _strip_markup(params.get("bestiarytext") or params.get("notes") or "") or None,
        "behavior": _strip_markup(params.get("strategy") or params.get("behaviour") or "") or None,
        "image_url": _build_sprite_url(actual_name) if actual_name else None,
        "loot_items": loot_items,
        "spawn_locations": [],
        "weaknesses": [],
        "resistances": [],
        "locations": locations,
        "related_tasks": [],
        "bestiary_class": _strip_markup(params.get("bestiaryclass") or "") or None,
        "bestiary_level": bestiary_level,
        "charm_points": BESTIARY_CHARM_POINTS.get(bestiary_level),
        "creature_class": _strip_markup(params.get("creatureclass") or "") or None,
        "primary_type": _strip_markup(params.get("primarytype") or "") or None,
        "source_url": _build_wiki_page_url(display_name),
        "data_sources": ["tibiawiki", "tibiadata"],
        "missing_fields": missing_fields,
        "classification": _infer_classification(
            name=display_name,
            creature_class=_strip_markup(params.get("creatureclass") or "") or None,
            bestiary_class=_strip_markup(params.get("bestiaryclass") or "") or None,
        ),
    }
    if missing_fields:
        logger.warning("creature_incomplete name=%s missing=%s", display_name, ",".join(missing_fields))
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
            "tradeable": True,
            "stackable": False,
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