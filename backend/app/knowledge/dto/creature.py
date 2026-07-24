"""Provider-neutral Creature knowledge DTO."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.knowledge.indexing import normalize_name
from app.services.text_utils import slugify


@dataclass(frozen=True, slots=True)
class CreatureLootReference:
    item_name: str
    external_id: str | None = None
    rarity: str | None = None
    percentage: float | None = None
    min_amount: int | None = None
    max_amount: int | None = None
    image_reference: str | None = None
    source_reference: str | None = None


@dataclass(frozen=True, slots=True)
class CreatureKnowledgeDTO:
    external_id: str
    canonical_name: str
    slug: str
    aliases: tuple[str, ...] = ()
    article: str | None = None
    plural: str | None = None
    hitpoints: int | None = None
    experience: int | None = None
    speed: int | None = None
    armor: int | None = None
    max_damage: int | None = None
    summon_cost: int | None = None
    convince_cost: int | None = None
    race: str | None = None
    bestiary_class: str | None = None
    bestiary_level: str | None = None
    occurrence: str | None = None
    difficulty: str | None = None
    classification: str | None = None
    primary_type: str | None = None
    charm_points: int | None = None
    kills_to_unlock: int | None = None
    elements: dict[str, int | float | str] = field(default_factory=dict)
    immunities: tuple[str, ...] = ()
    abilities: tuple[str, ...] = ()
    behavior: str | None = None
    description: str | None = None
    loot: tuple[CreatureLootReference, ...] = ()
    locations: tuple[str, ...] = ()
    task_references: tuple[str, ...] = ()
    image_reference: str | None = None
    source_reference: str | None = None
    is_boss: bool = False
    provider_metadata: dict[str, Any] = field(default_factory=dict)
    provided_fields: frozenset[str] = frozenset()
    is_partial: bool = False

    @property
    def language_neutral_id(self) -> str:
        return f"creature:tibiawiki:{self.external_id}"

    @property
    def sufficient_detail(self) -> bool:
        return {"hitpoints", "experience"}.issubset(self.provided_fields)

    def to_canonical_data(self) -> dict[str, Any]:
        value = asdict(self)
        value["provided_fields"] = sorted(self.provided_fields)
        return value

    @classmethod
    def from_canonical_data(cls, value: dict[str, Any]) -> "CreatureKnowledgeDTO":
        data = dict(value)
        data["aliases"] = tuple(data.get("aliases") or [])
        data["immunities"] = tuple(data.get("immunities") or [])
        data["abilities"] = tuple(data.get("abilities") or [])
        data["locations"] = tuple(data.get("locations") or [])
        data["task_references"] = tuple(data.get("task_references") or [])
        data["provided_fields"] = frozenset(data.get("provided_fields") or [])
        data["loot"] = tuple(CreatureLootReference(**item) for item in data.get("loot") or [])
        return cls(**data)

    @classmethod
    def from_tibiawiki_payload(
        cls,
        payload: dict[str, Any],
        *,
        external_id: str,
        page_title: str,
    ) -> "CreatureKnowledgeDTO":
        missing = set(payload.get("missing_fields") or [])
        field_map = {
            "hitpoints": "hitpoints",
            "experience": "experience",
            "armor": "armor",
            "speed": "speed",
            "max_damage": "max_damage",
            "summon_cost": "summon_cost",
            "convince_cost": "convince_cost",
            "difficulty": "difficulty",
            "occurrence": "occurrence",
            "description": "description",
            "behavior": "behavior",
            "bestiary_class": "bestiary_class",
            "bestiary_level": "bestiary_level",
            "charm_points": "charm_points",
            "classification": "classification",
            "creature_class": "race",
            "primary_type": "primary_type",
            "is_boss": "is_boss",
            "image_url": "image_reference",
            "source_url": "source_reference",
            "locations": "locations",
            "related_tasks": "task_references",
            "loot_items": "loot",
            "article": "article",
            "plural": "plural",
        }
        provided = {
            target
            for source, target in field_map.items()
            if source in payload and source not in missing and payload.get(source) not in (None, "", [])
        }
        canonical_name = str(payload.get("name") or page_title).strip()
        aliases = () if normalize_name(page_title) == normalize_name(canonical_name) else (page_title.strip(),)
        loot = tuple(
            CreatureLootReference(
                item_name=str(item.get("item_name") or "").strip(),
                external_id=str(item["id"]) if item.get("id") is not None else None,
                rarity=item.get("rarity"),
                percentage=item.get("percentage"),
                min_amount=item.get("min_amount"),
                max_amount=item.get("max_amount"),
                image_reference=item.get("item_image_url"),
                source_reference=item.get("source_url"),
            )
            for item in payload.get("loot_items") or []
            if str(item.get("item_name") or "").strip()
        )
        return cls(
            external_id=external_id,
            canonical_name=canonical_name,
            slug=str(payload.get("slug") or slugify(canonical_name)),
            aliases=aliases,
            article=payload.get("article"),
            plural=payload.get("plural"),
            hitpoints=payload.get("hitpoints") if "hitpoints" in provided else None,
            experience=payload.get("experience") if "experience" in provided else None,
            speed=payload.get("speed") if "speed" in provided else None,
            armor=payload.get("armor") if "armor" in provided else None,
            max_damage=payload.get("max_damage") if "max_damage" in provided else None,
            summon_cost=payload.get("summon_cost") if "summon_cost" in provided else None,
            convince_cost=payload.get("convince_cost") if "convince_cost" in provided else None,
            race=payload.get("creature_class"),
            bestiary_class=payload.get("bestiary_class"),
            bestiary_level=payload.get("bestiary_level"),
            occurrence=payload.get("occurrence"),
            difficulty=payload.get("difficulty"),
            classification=payload.get("classification"),
            primary_type=payload.get("primary_type"),
            charm_points=payload.get("charm_points"),
            behavior=payload.get("behavior"),
            description=payload.get("description"),
            loot=loot,
            locations=tuple(str(item) for item in payload.get("locations") or []),
            task_references=tuple(str(item) for item in payload.get("related_tasks") or []),
            image_reference=payload.get("image_url"),
            source_reference=payload.get("source_url"),
            is_boss=bool(payload.get("is_boss")),
            provider_metadata={"page_title": page_title, "missing_fields": sorted(missing)},
            provided_fields=frozenset(provided),
            is_partial=bool(missing),
        )
