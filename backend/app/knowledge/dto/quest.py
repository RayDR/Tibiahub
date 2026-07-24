"""Provider-neutral Quest and Mission knowledge DTOs."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class QuestNamedReference:
    name: str
    external_id: str | None = None


@dataclass(frozen=True, slots=True)
class QuestItemReference:
    name: str
    amount: int = 1
    external_id: str | None = None
    note: str | None = None


@dataclass(frozen=True, slots=True)
class QuestAccessReference:
    name: str
    description: str | None = None
    destination_name: str | None = None
    required_quests: tuple[str, ...] = ()
    required_items: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class QuestMissionDTO:
    external_id: str | None
    title: str
    sequence: int
    description: str | None = None
    objectives: tuple[str, ...] = ()
    required_items: tuple[QuestItemReference, ...] = ()
    rewarded_items: tuple[QuestItemReference, ...] = ()
    related_npcs: tuple[QuestNamedReference, ...] = ()
    related_creatures: tuple[QuestNamedReference, ...] = ()
    locations: tuple[QuestNamedReference, ...] = ()
    supplied_fields: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class QuestKnowledgeDTO:
    external_id: str
    canonical_name: str
    slug: str
    aliases: tuple[str, ...] = ()
    quest_type: str | None = None
    category: str | None = None
    difficulty: str | None = None
    estimated_duration: str | None = None
    minimum_level: int | None = None
    maximum_level: int | None = None
    experience_reward: int | None = None
    premium_required: bool | None = None
    repeatable: bool | None = None
    solo_possible: bool | None = None
    description: str | None = None
    summary: str | None = None
    group_name: str | None = None
    parent_page: str | None = None
    is_group: bool = False
    starting_npcs: tuple[QuestNamedReference, ...] = ()
    related_npcs: tuple[QuestNamedReference, ...] = ()
    required_items: tuple[QuestItemReference, ...] = ()
    rewarded_items: tuple[QuestItemReference, ...] = ()
    required_quests: tuple[QuestNamedReference, ...] = ()
    unlocked_quests: tuple[QuestNamedReference, ...] = ()
    required_creatures: tuple[QuestNamedReference, ...] = ()
    bosses: tuple[QuestNamedReference, ...] = ()
    locations: tuple[QuestNamedReference, ...] = ()
    access_unlocks: tuple[QuestAccessReference, ...] = ()
    missions: tuple[QuestMissionDTO, ...] = ()
    image_reference: str | None = None
    source_reference: str | None = None
    provider_metadata: dict[str, Any] = field(default_factory=dict)
    supplied_fields: frozenset[str] = frozenset()
    is_partial: bool = False

    @property
    def language_neutral_id(self) -> str:
        return f"quest:tibiawiki:{self.external_id}"

    @property
    def sufficient_detail(self) -> bool:
        identity = {
            "canonical_name", "slug", "source_reference", "image_reference",
            "group_name", "parent_page", "is_group",
        }
        return bool(self.supplied_fields - identity)

    def to_canonical_data(self) -> dict[str, Any]:
        value = asdict(self)
        value["supplied_fields"] = sorted(self.supplied_fields)
        for mission in value["missions"]:
            mission["supplied_fields"] = sorted(mission["supplied_fields"])
        return value

    @classmethod
    def from_canonical_data(cls, value: dict[str, Any]) -> "QuestKnowledgeDTO":
        data = dict(value)
        data["aliases"] = tuple(data.get("aliases") or [])
        for key in ("starting_npcs", "related_npcs", "required_quests", "unlocked_quests", "required_creatures", "bosses", "locations"):
            data[key] = _named(data.get(key))
        data["required_items"] = _items(data.get("required_items"))
        data["rewarded_items"] = _items(data.get("rewarded_items"))
        data["access_unlocks"] = tuple(
            QuestAccessReference(
                **{
                    **entry,
                    "required_quests": tuple(entry.get("required_quests") or []),
                    "required_items": tuple(entry.get("required_items") or []),
                }
            )
            for entry in data.get("access_unlocks") or []
        )
        data["missions"] = tuple(
            QuestMissionDTO(
                **{
                    **entry,
                    "objectives": tuple(entry.get("objectives") or []),
                    "required_items": _items(entry.get("required_items")),
                    "rewarded_items": _items(entry.get("rewarded_items")),
                    "related_npcs": _named(entry.get("related_npcs")),
                    "related_creatures": _named(entry.get("related_creatures")),
                    "locations": _named(entry.get("locations")),
                    "supplied_fields": frozenset(entry.get("supplied_fields") or []),
                }
            )
            for entry in data.get("missions") or []
        )
        data["supplied_fields"] = frozenset(data.get("supplied_fields") or [])
        return cls(**data)


def _named(value: Any) -> tuple[QuestNamedReference, ...]:
    return tuple(QuestNamedReference(**entry) for entry in value or [])


def _items(value: Any) -> tuple[QuestItemReference, ...]:
    return tuple(QuestItemReference(**entry) for entry in value or [])
