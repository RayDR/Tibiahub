"""Built-in provider capabilities, independent from import workers."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ProviderDefinition:
    provider_id: str
    provider_name: str
    priority: int
    version: str | None = None
    rate_limit: dict[str, int] = field(default_factory=dict)
    supports_entities: tuple[str, ...] = ()
    supports_media: bool = False
    supports_search: bool = False
    enabled: bool = True


INITIAL_PROVIDERS = (
    ProviderDefinition(
        provider_id="tibiadata",
        provider_name="TibiaData",
        priority=10,
        version="v4",
        rate_limit={"requests": 30, "window_seconds": 60},
        supports_entities=("creature", "guild", "character", "world", "spell", "boss"),
        supports_search=True,
    ),
    ProviderDefinition(
        provider_id="tibiawiki",
        provider_name="TibiaWiki",
        priority=20,
        version="mediawiki-v1",
        rate_limit={"requests": 12, "window_seconds": 60},
        supports_entities=("creature", "item", "quest", "npc", "location", "area", "town"),
        supports_media=True,
        supports_search=True,
        enabled=False,
    ),
    ProviderDefinition(
        provider_id="tibiamaps",
        provider_name="TibiaMaps",
        priority=20,
        version="1",
        rate_limit={"requests": 30, "window_seconds": 60},
        supports_entities=("area", "town", "hunt_zone", "access"),
        supports_media=True,
        supports_search=False,
    ),
)
