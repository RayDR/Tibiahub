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
    # (advertised entity, executable adapter root, classification/reason).
    # Derived entity types intentionally share a root parser; staged capabilities
    # must still name the executable staged adapter and explain that boundary.
    entity_execution: tuple[tuple[str, str, str], ...] = ()
    provider_roles: tuple[str, ...] = ()
    observation_capabilities: tuple[str, ...] = ()
    observation_execution: tuple[tuple[str, str, str], ...] = ()
    spatial_capabilities: tuple[str, ...] = ()
    spatial_execution: tuple[tuple[str, str, str], ...] = ()
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
        provider_roles=("current_facts", "live_observations", "historical_snapshot_upstream"),
        supports_entities=("guild", "character", "world", "creature", "spell"),
        entity_execution=(
            ("character", "character", "direct detail adapter"),
            ("guild", "guild", "direct detail adapter"),
            ("world", "world", "catalog adapter"),
            ("creature", "creature", "catalog and detail adapters; exact canonical merge only"),
            ("spell", "spell", "catalog and detail adapters; exact canonical merge only"),
        ),
        observation_capabilities=(
            "character", "guild", "guild_catalog", "world", "highscores",
            "killstatistics", "houses", "creature", "spell", "boosted_bosses",
        ),
        observation_execution=(
            ("character", "character", "detail and stored-document replay"),
            ("guild", "guild", "detail and stored-document replay"),
            ("guild_catalog", "guild", "world-scoped current guild list"),
            ("world", "world", "catalog/detail and stored-document replay"),
            ("highscores", "world", "world/category/vocation/page scoped current observation"),
            ("killstatistics", "world", "world-scoped current observation"),
            ("houses", "town", "world/town-scoped current observation"),
            ("creature", "creature", "catalog/detail and stored-document replay"),
            ("spell", "spell", "catalog/detail and stored-document replay"),
            ("boosted_bosses", "boss", "boostablebosses current observation; no general boss catalog exists"),
        ),
        supports_search=False,
    ),
    ProviderDefinition(
        provider_id="tibiawiki",
        provider_name="TibiaWiki",
        priority=20,
        version="mediawiki-v1",
        rate_limit={"requests": 12, "window_seconds": 60},
        provider_roles=("semantic_knowledge",),
        supports_entities=("creature", "boss", "item", "quest", "mission", "access", "npc", "location", "area", "town", "hunt_zone", "route"),
        entity_execution=(
            ("creature", "creature", "direct catalog/detail adapter"),
            ("boss", "creature", "boss is classified by the creature adapter"),
            ("item", "item", "direct catalog/detail adapter"),
            ("quest", "quest", "direct catalog/detail adapter"),
            ("mission", "quest", "mission is normalized from its parent quest document"),
            ("access", "quest", "access is normalized from its parent quest document"),
            ("npc", "npc", "direct catalog/detail adapter"),
            ("location", "location", "direct catalog/detail adapter"),
            ("area", "location", "area is classified by the location adapter"),
            ("town", "location", "town is classified by the location adapter"),
            ("hunt_zone", "hunt_zone", "direct catalog/detail adapter"),
            ("route", "route", "direct catalog/detail adapter"),
        ),
        supports_media=True,
        supports_search=False,
        enabled=False,
    ),
    ProviderDefinition(
        provider_id="tibiamaps",
        provider_name="TibiaMaps",
        priority=20,
        version="1",
        rate_limit={"requests": 30, "window_seconds": 60},
        provider_roles=("spatial_authority",),
        supports_entities=("map_point", "map_region"),
        entity_execution=(
            ("map_point", "map_point", "staged import adapter; acquisition belongs to map sync"),
            ("map_region", "map_region", "staged import adapter; acquisition belongs to map sync"),
        ),
        spatial_capabilities=("dataset", "floors", "markers", "coordinates", "pathfinding", "map_version"),
        spatial_execution=(
            ("dataset", "world_map_import", "versioned local dataset importer"),
            ("floors", "world_map_import", "all 16 map layers validated and hashed"),
            ("markers", "world_map_import", "raw marker rows retained locally"),
            ("coordinates", "map_point", "typed staged adapter plus exact-only dataset resolver"),
            ("pathfinding", "world_map_import", "all 16 pathfinding layers validated and hashed"),
            ("map_version", "world_map_import", "immutable upstream commit and manifest"),
        ),
        supports_media=True,
        supports_search=False,
    ),
)
