"""
Normalized external API access for TibiaHub.

These helpers never fall back to silent demo data in production. If mock mode is
explicitly enabled, the response is marked as mock so tests can assert on it.
"""
from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any, Dict, Optional

from app.core.config import settings
from app.services.bestiary_source import BestiarySourceError, get_creature_detail_by_name, list_creature_summaries, list_hunting_places, list_items, list_quests
from app.services.mock_data import MOCK_CREATURE


class APISource(str, Enum):
    TIBIAWIKI = "tibiawiki"
    TIBIADATA = "tibiadata"
    MOCK = "mock"


class ExternalAPIError(Exception):
    """Raised when an external API call fails."""


class APIResponse:
    def __init__(self, *, data: Optional[Any], source: APISource, error: Optional[str] = None, is_mock: bool = False):
        self.data = data
        self.source = source
        self.error = error
        self.is_mock = is_mock
        self.timestamp = datetime.now(UTC)

    def success(self) -> bool:
        return self.data is not None and self.error is None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "data": self.data,
            "source": self.source.value,
            "error": self.error,
            "is_mock": self.is_mock,
            "timestamp": self.timestamp.isoformat(),
        }


async def get_creatures(expand: bool = False) -> APIResponse:
    if settings.USE_MOCK_DATA:
        return APIResponse(data=[dict(MOCK_CREATURE)], source=APISource.MOCK, is_mock=True)

    try:
        summaries = await list_creature_summaries(skip=0, limit=500)
        if not expand:
            return APIResponse(data=summaries, source=APISource.TIBIAWIKI)
        detailed = [await get_creature_detail_by_name(item["name"]) for item in summaries]
        return APIResponse(data=detailed, source=APISource.TIBIAWIKI)
    except BestiarySourceError as exc:
        return APIResponse(data=None, source=APISource.TIBIAWIKI, error=str(exc))


async def get_items(expand: bool = False) -> APIResponse:
    try:
        return APIResponse(data=await list_items(200 if expand else 100), source=APISource.TIBIAWIKI)
    except BestiarySourceError as exc:
        return APIResponse(data=None, source=APISource.TIBIAWIKI, error=str(exc))


async def get_hunting_places(expand: bool = False) -> APIResponse:
    try:
        return APIResponse(data=await list_hunting_places(200 if expand else 100), source=APISource.TIBIAWIKI)
    except BestiarySourceError as exc:
        return APIResponse(data=None, source=APISource.TIBIAWIKI, error=str(exc))


async def get_quests(expand: bool = False) -> APIResponse:
    try:
        return APIResponse(data=await list_quests(200 if expand else 100), source=APISource.TIBIAWIKI)
    except BestiarySourceError as exc:
        return APIResponse(data=None, source=APISource.TIBIAWIKI, error=str(exc))
