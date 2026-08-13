"""Provider-neutral Hunting Place transfer objects."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class HuntVocationRecommendation:
    """One provider-supplied vocation recommendation; absent values stay unknown."""

    level: int | None = None
    skill: int | None = None
    defense: int | None = None


@dataclass(frozen=True, slots=True)
class HuntZoneKnowledgeDTO:
    external_id: str
    canonical_name: str
    slug: str
    aliases: tuple[str, ...] = ()
    city: str | None = None
    location: str | None = None
    implemented: str | None = None
    vocation_text: str | None = None
    vocation_recommendations: dict[str, HuntVocationRecommendation] = field(default_factory=dict)
    premium_required: bool | None = None
    access_notes: str | None = None
    access_quests: tuple[str, ...] = ()
    creatures: tuple[str, ...] = ()
    experience: str | None = None
    experience_rating: int | None = None
    loot: str | None = None
    loot_rating: int | None = None
    best_loot: tuple[str, ...] = ()
    map_references: tuple[str, ...] = ()
    description: str | None = None
    image_reference: str | None = None
    source_reference: str | None = None
    provider_metadata: dict[str, Any] = field(default_factory=dict)
    supplied_fields: frozenset[str] = frozenset()
    is_partial: bool = False

    @property
    def language_neutral_id(self) -> str:
        return f"hunt-zone:tibiawiki:{self.external_id}"

    @property
    def minimum_recommended_level(self) -> int | None:
        values = [value.level for value in self.vocation_recommendations.values() if value.level is not None]
        return min(values) if values else None

    @property
    def sufficient_detail(self) -> bool:
        identity = {"canonical_name", "slug", "image_reference", "source_reference"}
        return bool(self.supplied_fields - identity)

    def to_canonical_data(self) -> dict[str, Any]:
        value = asdict(self)
        for field_name in ("aliases", "access_quests", "creatures", "best_loot", "map_references"):
            value[field_name] = list(value[field_name])
        value["supplied_fields"] = sorted(self.supplied_fields)
        return value

    @classmethod
    def from_canonical_data(cls, value: dict[str, Any]) -> "HuntZoneKnowledgeDTO":
        data = dict(value)
        data["aliases"] = tuple(data.get("aliases") or [])
        data["vocation_recommendations"] = {
            name: HuntVocationRecommendation(**recommendation)
            for name, recommendation in (data.get("vocation_recommendations") or {}).items()
        }
        for field_name in ("access_quests", "creatures", "best_loot", "map_references"):
            data[field_name] = tuple(data.get(field_name) or [])
        data["supplied_fields"] = frozenset(data.get("supplied_fields") or [])
        return cls(**data)
