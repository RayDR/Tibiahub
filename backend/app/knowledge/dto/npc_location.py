"""Provider-neutral NPC and named-location transfer objects."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class NamedKnowledgeReference:
    name: str


@dataclass(frozen=True, slots=True)
class NpcTradeReference:
    name: str
    price: int | None = None


@dataclass(frozen=True, slots=True)
class NpcKnowledgeDTO:
    external_id: str
    canonical_name: str
    slug: str
    aliases: tuple[str, ...] = ()
    title: str | None = None
    occupation: str | None = None
    sex: str | None = None
    location_name: str | None = None
    description: str | None = None
    buys: tuple[NpcTradeReference, ...] = ()
    sells: tuple[NpcTradeReference, ...] = ()
    destinations: tuple[NamedKnowledgeReference, ...] = ()
    related_quests: tuple[NamedKnowledgeReference, ...] = ()
    image_reference: str | None = None
    source_reference: str | None = None
    provider_metadata: dict[str, Any] = field(default_factory=dict)
    supplied_fields: frozenset[str] = frozenset()
    is_partial: bool = False

    @property
    def language_neutral_id(self) -> str:
        return f"npc:tibiawiki:{self.external_id}"

    @property
    def sufficient_detail(self) -> bool:
        return bool(self.supplied_fields - {"canonical_name", "slug", "image_reference", "source_reference"})

    def to_canonical_data(self) -> dict[str, Any]:
        value = asdict(self)
        value["supplied_fields"] = sorted(self.supplied_fields)
        return value

    @classmethod
    def from_canonical_data(cls, value: dict[str, Any]) -> "NpcKnowledgeDTO":
        data = dict(value)
        data["aliases"] = tuple(data.get("aliases") or [])
        data["buys"] = tuple(NpcTradeReference(**entry) for entry in data.get("buys") or [])
        data["sells"] = tuple(NpcTradeReference(**entry) for entry in data.get("sells") or [])
        for key in ("destinations", "related_quests"):
            data[key] = tuple(NamedKnowledgeReference(**entry) for entry in data.get(key) or [])
        data["supplied_fields"] = frozenset(data.get("supplied_fields") or [])
        return cls(**data)


@dataclass(frozen=True, slots=True)
class LocationKnowledgeDTO:
    external_id: str
    canonical_name: str
    slug: str
    aliases: tuple[str, ...] = ()
    location_kind: str | None = None
    region: str | None = None
    parent_location: str | None = None
    description: str | None = None
    premium_required: bool | None = None
    minimum_level: int | None = None
    maximum_level: int | None = None
    npcs: tuple[NamedKnowledgeReference, ...] = ()
    creatures: tuple[NamedKnowledgeReference, ...] = ()
    quests: tuple[NamedKnowledgeReference, ...] = ()
    sublocations: tuple[NamedKnowledgeReference, ...] = ()
    access_notes: str | None = None
    image_reference: str | None = None
    source_reference: str | None = None
    provider_metadata: dict[str, Any] = field(default_factory=dict)
    supplied_fields: frozenset[str] = frozenset()
    is_partial: bool = False

    @property
    def language_neutral_id(self) -> str:
        return f"location:tibiawiki:{self.external_id}"

    @property
    def sufficient_detail(self) -> bool:
        return bool(self.supplied_fields - {"canonical_name", "slug", "image_reference", "source_reference"})

    def to_canonical_data(self) -> dict[str, Any]:
        value = asdict(self)
        value["supplied_fields"] = sorted(self.supplied_fields)
        return value

    @classmethod
    def from_canonical_data(cls, value: dict[str, Any]) -> "LocationKnowledgeDTO":
        data = dict(value)
        data["aliases"] = tuple(data.get("aliases") or [])
        for key in ("npcs", "creatures", "quests", "sublocations"):
            data[key] = tuple(NamedKnowledgeReference(**entry) for entry in data.get(key) or [])
        data["supplied_fields"] = frozenset(data.get("supplied_fields") or [])
        return cls(**data)
