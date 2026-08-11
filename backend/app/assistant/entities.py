"""Canonical local entity resolution and per-turn reference validation."""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from urllib.parse import quote

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.assistant.schemas import AssistantEntityReference
from app.knowledge.models import KnowledgeEntity, KnowledgeEntityAlias
from app.models import Creature, HuntZone, Loot
from app.models.external_data import Item, TibiaWikiLocation, TibiaWikiNpc, TibiaWikiQuest
from app.services.text_utils import normalize_search_text, slugify


SUPPORTED_ENTITY_TYPES = {"creature", "item", "npc", "quest", "location", "area", "town", "hunt_zone"}


class FabricatedEntityReferenceError(ValueError):
    """Raised when provider output references identity not observed in this turn."""


def _selected_route(tab: str, kind: str, name: str) -> str:
    selected = f"{kind}:{quote(name, safe='')}"
    return f"/cyclopedia?tab={tab}&selected={quote(selected, safe='')}"


def _rank(query: str, name: str, aliases: tuple[str, ...] = ()) -> tuple[int, float, str]:
    needle = normalize_search_text(query)
    values = [normalize_search_text(name), *(normalize_search_text(value) for value in aliases)]
    if needle in values:
        return (0, -1.0, name.casefold())
    if any(value.startswith(needle) for value in values):
        return (1, -1.0, name.casefold())
    if any(needle in value for value in values):
        return (2, -1.0, name.casefold())
    score = max((SequenceMatcher(a=needle, b=value).ratio() for value in values), default=0.0)
    return (3, -score, name.casefold())


def creature_reference(row: Creature) -> AssistantEntityReference:
    slug = row.slug or slugify(row.name)
    return AssistantEntityReference(
        key=f"creature:{row.id}", entity_type="creature", id=str(row.id),
        knowledge_entity_id=row.knowledge_entity_id, canonical_name=row.name, slug=slug,
        image_url=f"/api/v1/creatures/{row.id}/image?placeholder=false",
        detail_route=f"/creatures/{quote(slug, safe='')}",
        metadata={"hitpoints": row.hitpoints, "experience": row.experience, "difficulty": row.difficulty},
    )


def hunt_zone_reference(row: HuntZone) -> AssistantEntityReference:
    slug = row.slug or slugify(row.name)
    return AssistantEntityReference(
        key=f"hunt_zone:{row.id}", entity_type="hunt_zone", id=str(row.id),
        canonical_name=row.name, slug=slug,
        image_url=f"/api/v1/hunt-zones/{row.id}/map-image",
        detail_route=_selected_route("zones", "zone", row.name),
        metadata={"city": row.city, "min_level": row.min_level or None, "difficulty": row.difficulty},
    )


def item_reference(row: Item) -> AssistantEntityReference:
    slug = row.slug or slugify(row.name)
    return AssistantEntityReference(
        key=f"item:{row.id}", entity_type="item", id=str(row.id),
        knowledge_entity_id=row.knowledge_entity_id, canonical_name=row.name, slug=slug,
        image_url=f"/api/v1/items/{row.id}/image?placeholder=false",
        detail_route=_selected_route("items", "item", row.name),
        metadata={"item_type": row.type, "category": row.category, "level": row.level_required},
    )


def legacy_item_reference(row: Loot) -> AssistantEntityReference:
    normalized = row.normalized_name or normalize_search_text(row.item_name)
    slug = slugify(row.item_name)
    return AssistantEntityReference(
        key=f"item:legacy:{normalized}", entity_type="item", id=normalized,
        canonical_name=row.item_name, slug=slug,
        image_url=f"/api/v1/items/{row.id}/image?placeholder=false",
        detail_route=_selected_route("items", "item", row.item_name),
        metadata={"rarity": row.rarity},
    )


def quest_reference(row: TibiaWikiQuest) -> AssistantEntityReference:
    slug = row.slug or slugify(row.name)
    return AssistantEntityReference(
        key=f"quest:{row.id}", entity_type="quest", id=str(row.id),
        knowledge_entity_id=row.knowledge_entity_id, canonical_name=row.name, slug=slug,
        image_url=None, detail_route=f"/quests/{row.id}",
        metadata={"min_level": row.min_level, "premium": row.premium_required, "difficulty": row.difficulty},
    )


def npc_reference(row: TibiaWikiNpc) -> AssistantEntityReference:
    return AssistantEntityReference(
        key=f"npc:{row.id}", entity_type="npc", id=str(row.id),
        knowledge_entity_id=row.knowledge_entity_id, canonical_name=row.name, slug=row.slug,
        image_url=None, detail_route=f"/npcs/{quote(row.slug, safe='')}",
        metadata={"occupation": row.occupation, "location": row.location_name},
    )


def location_reference(row: TibiaWikiLocation) -> AssistantEntityReference:
    entity_type = row.knowledge_entity.entity_type if row.knowledge_entity else "location"
    if entity_type not in {"location", "area", "town"}:
        entity_type = "location"
    return AssistantEntityReference(
        key=f"{entity_type}:{row.id}", entity_type=entity_type, id=str(row.id),
        knowledge_entity_id=row.knowledge_entity_id, canonical_name=row.name, slug=row.slug,
        image_url=None, detail_route=f"/locations/{quote(row.slug, safe='')}",
        metadata={"kind": row.location_kind, "region": row.region, "premium": row.premium_required},
    )


def generic_reference(row: KnowledgeEntity) -> AssistantEntityReference | None:
    if row.entity_type not in SUPPORTED_ENTITY_TYPES:
        return None
    route = {
        "creature": f"/creatures/{quote(row.slug, safe='')}",
        "quest": f"/quests/{quote(row.slug, safe='')}",
        "npc": f"/npcs/{quote(row.slug, safe='')}",
        "location": f"/locations/{quote(row.slug, safe='')}",
        "area": f"/locations/{quote(row.slug, safe='')}",
        "town": f"/locations/{quote(row.slug, safe='')}",
        "item": _selected_route("items", "item", row.canonical_name),
        "hunt_zone": _selected_route("zones", "zone", row.canonical_name),
    }[row.entity_type]
    return AssistantEntityReference(
        key=f"knowledge:{row.uuid}", entity_type=row.entity_type, id=str(row.uuid),
        knowledge_entity_id=row.uuid, canonical_name=row.canonical_name, slug=row.slug,
        image_url=None, detail_route=route,
    )


def domain_reference(db: Session, row: KnowledgeEntity) -> AssistantEntityReference | None:
    """Prefer the concrete local bridge so tool handlers receive usable IDs."""
    if row.entity_type == "creature":
        value = db.query(Creature).filter(Creature.knowledge_entity_id == row.uuid).first()
        return creature_reference(value) if value else generic_reference(row)
    if row.entity_type == "item":
        value = db.query(Item).filter(Item.knowledge_entity_id == row.uuid).first()
        return item_reference(value) if value else generic_reference(row)
    if row.entity_type == "quest":
        value = db.query(TibiaWikiQuest).filter(TibiaWikiQuest.knowledge_entity_id == row.uuid).first()
        return quest_reference(value) if value else generic_reference(row)
    if row.entity_type == "npc":
        value = db.query(TibiaWikiNpc).filter(TibiaWikiNpc.knowledge_entity_id == row.uuid).first()
        return npc_reference(value) if value else generic_reference(row)
    if row.entity_type in {"location", "area", "town"}:
        value = db.query(TibiaWikiLocation).filter(TibiaWikiLocation.knowledge_entity_id == row.uuid).first()
        return location_reference(value) if value else generic_reference(row)
    return generic_reference(row)


@dataclass(frozen=True)
class ResolvedEntity:
    reference: AssistantEntityReference
    score: tuple[int, float, str]


class AssistantEntityResolver:
    """Resolve canonical identity without network access or metadata writes."""

    def __init__(self, db: Session):
        self.db = db

    def resolve(self, query: str, entity_types: list[str] | None = None, limit: int = 8) -> list[AssistantEntityReference]:
        normalized = normalize_search_text(query)
        if not normalized:
            return []
        allowed = set(entity_types or SUPPORTED_ENTITY_TYPES) & SUPPORTED_ENTITY_TYPES
        candidates: dict[str, ResolvedEntity] = {}

        def add(reference: AssistantEntityReference, aliases: tuple[str, ...] = ()) -> None:
            scored = ResolvedEntity(reference, _rank(query, reference.canonical_name, aliases))
            current = candidates.get(reference.key)
            if current is None or scored.score < current.score:
                candidates[reference.key] = scored

        if "creature" in allowed:
            rows = self.db.query(Creature).filter(
                Creature.is_hidden.is_(False),
                or_(Creature.normalized_name.contains(normalized), Creature.name.ilike(f"%{query}%"), Creature.plural.ilike(f"%{query}%")),
            ).limit(40).all()
            if not rows:
                rows = self.db.query(Creature).filter(Creature.is_hidden.is_(False)).limit(300).all()
            for row in rows:
                add(creature_reference(row), tuple(value for value in (row.plural,) if value))

        if "hunt_zone" in allowed:
            for row in self.db.query(HuntZone).filter(or_(HuntZone.normalized_name.contains(normalized), HuntZone.name.ilike(f"%{query}%"))).limit(40).all():
                add(hunt_zone_reference(row))

        if "item" in allowed:
            for row in self.db.query(Item).filter(or_(Item.normalized_name.contains(normalized), Item.name.ilike(f"%{query}%"))).limit(40).all():
                add(item_reference(row))
            legacy = self.db.query(Loot).filter(or_(Loot.normalized_name.contains(normalized), Loot.item_name.ilike(f"%{query}%"))).limit(80).all()
            for row in legacy:
                add(legacy_item_reference(row))

        if "quest" in allowed:
            for row in self.db.query(TibiaWikiQuest).filter(or_(TibiaWikiQuest.normalized_name.contains(normalized), TibiaWikiQuest.name.ilike(f"%{query}%"))).limit(40).all():
                add(quest_reference(row))

        if "npc" in allowed:
            for row in self.db.query(TibiaWikiNpc).filter(or_(TibiaWikiNpc.normalized_name.contains(normalized), TibiaWikiNpc.name.ilike(f"%{query}%"))).limit(40).all():
                add(npc_reference(row))

        location_types = allowed & {"location", "area", "town"}
        if location_types:
            rows = self.db.query(TibiaWikiLocation).filter(or_(TibiaWikiLocation.normalized_name.contains(normalized), TibiaWikiLocation.name.ilike(f"%{query}%"))).limit(40).all()
            for row in rows:
                reference = location_reference(row)
                if reference.entity_type in location_types or "location" in location_types:
                    add(reference)

        aliases = self.db.query(KnowledgeEntityAlias).filter(
            KnowledgeEntityAlias.normalized_alias.contains(normalized),
            KnowledgeEntityAlias.entity_type.in_(allowed),
        ).limit(40).all()
        for alias in aliases:
            reference = domain_reference(self.db, alias.entity)
            if reference:
                add(reference, (alias.alias,))

        ranked = sorted(
            (
                value for value in candidates.values()
                if value.score[0] < 3 or value.score[1] <= -0.72
            ),
            key=lambda value: value.score,
        )
        return [value.reference for value in ranked[: max(1, min(limit, 20))]]

    def resolve_one(self, query: str, entity_types: list[str]) -> AssistantEntityReference | None:
        values = self.resolve(query, entity_types, limit=1)
        return values[0] if values else None


class TurnEntityRegistry:
    def __init__(self) -> None:
        self.entities: dict[str, AssistantEntityReference] = {}

    def add(self, *references: AssistantEntityReference) -> None:
        for reference in references:
            self.entities[reference.key] = reference

    def require(self, keys: list[str]) -> list[AssistantEntityReference]:
        missing = [key for key in keys if key not in self.entities]
        if missing:
            raise FabricatedEntityReferenceError(f"Unvalidated assistant entity reference: {missing[0]}")
        return [self.entities[key] for key in keys]
