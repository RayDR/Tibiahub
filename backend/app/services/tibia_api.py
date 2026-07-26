"""Live TibiaData integration for character, guild, and world data."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from urllib.parse import quote

import httpx

from app.core.config import settings
from app.services.external_resilience import request_json_with_resilience
from app.services.mock_data import MOCK_CHARACTER, MOCK_GUILD, MOCK_WORLDS

logger = logging.getLogger(__name__)

TIMEOUT = 15.0


class TibiaAPIError(Exception):
    """Custom exception for TibiaData failures."""


async def _get_json(url: str) -> Dict[str, Any]:
    data = await request_json_with_resilience(
        provider="tibiadata",
        url=url,
        headers={"User-Agent": settings.TIBIAWIKI_USER_AGENT},
        timeout_seconds=TIMEOUT,
        retries=2,
        retry_backoff_seconds=0.5,
        circuit_failures=3,
        circuit_cooldown_seconds=30,
    )
    logger.info("tibiadata_request url=%s cache_hit=false fallback=false", url)
    return data


async def get_character_info(character_name: str) -> Optional[Dict[str, Any]]:
    if settings.USE_MOCK_DATA:
        payload = dict(MOCK_CHARACTER)
        payload["name"] = character_name
        return payload

    url = f"{settings.TIBIADATA_BASE_URL}/character/{quote(character_name)}"
    try:
        data = await _get_json(url)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            logger.warning("tibiadata_missing entity=character name=%s", character_name)
            return None
        raise TibiaAPIError(str(exc)) from exc
    except Exception as exc:
        raise TibiaAPIError(str(exc)) from exc

    payload = data.get("character") or {}
    character = payload.get("character") or {}
    if not character:
        return None

    missing_fields = [field for field in ["name", "level", "vocation", "world", "last_login"] if character.get(field) in (None, "")]
    if missing_fields:
        logger.warning("tibiadata_incomplete entity=character name=%s missing=%s", character_name, ",".join(missing_fields))

    guild_data = character.get("guild") or {}
    guild_name = guild_data.get("name") if isinstance(guild_data, dict) else guild_data
    account_information = payload.get("account_information") or {}
    return {
        "name": character.get("name"),
        "level": character.get("level"),
        "vocation": character.get("vocation"),
        "world": character.get("world"),
        "last_login": character.get("last_login"),
        "last_login_at": character.get("last_login"),
        "guild": {
            "name": guild_name,
            "rank": guild_data.get("rank") if isinstance(guild_data, dict) else None,
        } if guild_name else None,
        "residence": character.get("residence"),
        "sex": character.get("sex"),
        "achievement_points": character.get("achievement_points") or account_information.get("achievement_points"),
        "comment": character.get("comment") or "",
        "account_information": account_information,
    }


async def get_worlds() -> list[Dict[str, Any]]:
    if settings.USE_MOCK_DATA:
        return list(MOCK_WORLDS)

    try:
        worlds = (await _get_json(f"{settings.TIBIADATA_BASE_URL}/worlds")).get("worlds") or {}
    except Exception as exc:
        raise TibiaAPIError(str(exc)) from exc

    regular = worlds.get("regular_worlds") or []
    tournament = worlds.get("tournament_worlds") or []
    return [
        {
            "name": world.get("name"),
            "status": world.get("status"),
            "location": world.get("location"),
            "pvp_type": world.get("pvp_type"),
        }
        for world in [*regular, *tournament]
    ]


async def get_guild_info(guild_name: str) -> Optional[Dict[str, Any]]:
    if settings.USE_MOCK_DATA:
        payload = dict(MOCK_GUILD)
        payload["name"] = guild_name
        return payload

    url = f"{settings.TIBIADATA_BASE_URL}/guild/{quote(guild_name)}"
    try:
        guild = (await _get_json(url)).get("guild") or {}
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            logger.warning("tibiadata_missing entity=guild name=%s", guild_name)
            return None
        raise TibiaAPIError(str(exc)) from exc
    except Exception as exc:
        raise TibiaAPIError(str(exc)) from exc

    members = guild.get("members") or []
    missing_fields = [field for field in ["name", "world", "members"] if guild.get(field) in (None, "")]
    if missing_fields:
        logger.warning("tibiadata_incomplete entity=guild name=%s missing=%s", guild_name, ",".join(missing_fields))

    return {
        "name": guild.get("name"),
        "world": guild.get("world"),
        "description": guild.get("description"),
        "founded": guild.get("founded"),
        "members": members,
        "member_count": len(members),
        "logo_url": guild.get("logo_url"),
    }

async def get_active_guild_members(guild_name: str, days_active: int = 10) -> list[dict[str, Any]]:
    """
    Fetch all guild members and filter by last login within X days.
    """
    guild_info = await get_guild_info(guild_name)
    if not guild_info:
        return []

    semaphore = asyncio.Semaphore(10)

    async def enrich_member(member: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        async with semaphore:
            character_name = member.get("name")
            if not character_name:
                return None
            try:
                info = await get_character_info(character_name)
                if not info or not info.get("last_login"):
                    return None
                last_login = datetime.fromisoformat(info["last_login"].replace("Z", "+00:00"))
                cutoff = datetime.now(last_login.tzinfo) - timedelta(days=days_active)
                if last_login < cutoff:
                    return None
                return {
                    "name": info.get("name"),
                    "level": info.get("level"),
                    "vocation": info.get("vocation"),
                    "world": info.get("world") or guild_info.get("world"),
                    "last_login": info.get("last_login"),
                    "guild_rank": member.get("rank") or member.get("title") or member.get("position"),
                }
            except Exception as exc:
                logger.warning("tibiadata_member_check_failed name=%s error=%s", character_name, exc)
                return None

    results = await asyncio.gather(*(enrich_member(member) for member in guild_info.get("members") or []))
    return [member for member in results if member is not None]
