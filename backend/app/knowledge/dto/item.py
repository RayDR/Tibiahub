"""Provider-neutral Item knowledge DTO."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ItemNpcReference:
    name: str
    price: int | float | None = None
    location: str | None = None
    currency: str | None = None
    qualifier: str | None = None


@dataclass(frozen=True, slots=True)
class ItemCreatureReference:
    name: str
    external_id: str | None = None


@dataclass(frozen=True, slots=True)
class ItemKnowledgeDTO:
    external_id: str
    canonical_name: str
    slug: str
    aliases: tuple[str, ...] = ()
    game_item_id: int | None = None
    item_class: str | None = None
    item_type: str | None = None
    category: str | None = None
    weight: float | None = None
    value: int | None = None
    level_requirement: int | None = None
    vocation_requirements: tuple[str, ...] = ()
    attack: int | None = None
    defense: int | None = None
    armor: int | None = None
    range: int | None = None
    slots: tuple[str, ...] = ()
    imbuement_slots: int | None = None
    attributes: dict[str, int | float | str] = field(default_factory=dict)
    resistances: dict[str, int | float | str] = field(default_factory=dict)
    bonuses: dict[str, int | float | str] = field(default_factory=dict)
    description: str | None = None
    notes: str | None = None
    buy_from: tuple[ItemNpcReference, ...] = ()
    sell_to: tuple[ItemNpcReference, ...] = ()
    dropped_by: tuple[ItemCreatureReference, ...] = ()
    rewards_from: tuple[str, ...] = ()
    required_for: tuple[str, ...] = ()
    tradeable: bool | None = None
    stackable: bool | None = None
    image_reference: str | None = None
    source_reference: str | None = None
    provider_metadata: dict[str, Any] = field(default_factory=dict)
    supplied_fields: frozenset[str] = frozenset()
    is_partial: bool = False

    @property
    def language_neutral_id(self) -> str:
        return f"item:tibiawiki:{self.external_id}"

    @property
    def sufficient_detail(self) -> bool:
        return bool(
            self.supplied_fields
            - {"canonical_name", "slug", "image_reference", "source_reference"}
        )

    def to_canonical_data(self) -> dict[str, Any]:
        value = asdict(self)
        value["supplied_fields"] = sorted(self.supplied_fields)
        return value

    @classmethod
    def from_canonical_data(cls, value: dict[str, Any]) -> "ItemKnowledgeDTO":
        data = dict(value)
        for key in ("aliases", "vocation_requirements", "slots", "rewards_from", "required_for"):
            data[key] = tuple(data.get(key) or [])
        data["buy_from"] = tuple(ItemNpcReference(**item) for item in data.get("buy_from") or [])
        data["sell_to"] = tuple(ItemNpcReference(**item) for item in data.get("sell_to") or [])
        data["dropped_by"] = tuple(ItemCreatureReference(**item) for item in data.get("dropped_by") or [])
        data["supplied_fields"] = frozenset(data.get("supplied_fields") or [])
        return cls(**data)
