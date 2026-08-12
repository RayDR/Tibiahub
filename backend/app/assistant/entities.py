"""Canonical local entity resolution and per-turn reference validation."""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from urllib.parse import quote

from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session, joinedload

from app.assistant.schemas import AssistantEntityReference
from app.assistant.routing import DirectMatchMode
from app.knowledge.models import KnowledgeEntity, KnowledgeEntityAlias
from app.models import Creature, HuntZone, Loot
from app.models.external_data import Item, TibiaWikiLocation, TibiaWikiNpc, TibiaWikiQuest
from app.services.text_utils import normalize_search_text, slugify


SUPPORTED_ENTITY_TYPES = {"creature", "item", "npc", "quest", "location", "area", "town", "hunt_zone"}
DIRECT_LOOKUP_MAX_RESULTS = 10


class FabricatedEntityReferenceError(ValueError):
    """Raised when provider output references identity not observed in this turn."""


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
        metadata={
            "hitpoints": row.hitpoints,
            "experience": row.experience,
            "difficulty": row.difficulty,
            "is_boss": bool(row.is_boss),
        },
    )


def hunt_zone_reference(row: HuntZone) -> AssistantEntityReference:
    slug = row.slug or slugify(row.name)
    return AssistantEntityReference(
        key=f"hunt_zone:{row.id}", entity_type="hunt_zone", id=str(row.id),
        canonical_name=row.name, slug=slug,
        image_url=f"/api/v1/hunt-zones/{row.id}/map-image",
        detail_route=f"/hunt-zones/{quote(slug, safe='')}",
        metadata={"city": row.city, "min_level": row.min_level or None, "difficulty": row.difficulty},
    )


def item_reference(row: Item) -> AssistantEntityReference:
    slug = row.slug or slugify(row.name)
    return AssistantEntityReference(
        key=f"item:{row.id}", entity_type="item", id=str(row.id),
        knowledge_entity_id=row.knowledge_entity_id, canonical_name=row.name, slug=slug,
        image_url=f"/api/v1/items/{row.id}/image?placeholder=false",
        detail_route=f"/items/{quote(slug, safe='')}",
        metadata={"item_type": row.type, "category": row.category, "level": row.level_required},
    )


def legacy_item_reference(row: Loot) -> AssistantEntityReference:
    normalized = row.normalized_name or normalize_search_text(row.item_name)
    slug = slugify(row.item_name)
    return AssistantEntityReference(
        key=f"item:legacy:{normalized}", entity_type="item", id=normalized,
        canonical_name=row.item_name, slug=slug,
        image_url=f"/api/v1/items/{row.id}/image?placeholder=false",
        detail_route=f"/items/{quote(slug, safe='')}",
        metadata={"rarity": row.rarity},
    )


def quest_reference(row: TibiaWikiQuest) -> AssistantEntityReference:
    slug = row.slug or slugify(row.name)
    return AssistantEntityReference(
        key=f"quest:{row.id}", entity_type="quest", id=str(row.id),
        knowledge_entity_id=row.knowledge_entity_id, canonical_name=row.name, slug=slug,
        image_url=None, detail_route=f"/quests/{quote(slug, safe='')}",
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
        "item": f"/items/{quote(row.slug, safe='')}",
        "hunt_zone": f"/hunt-zones/{quote(row.slug, safe='')}",
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

    def resolve_direct(
        self,
        query: str,
        *,
        entity_types: list[str] | None = None,
        match_mode: DirectMatchMode = "contains",
        limit: int = DIRECT_LOOKUP_MAX_RESULTS,
    ) -> list[AssistantEntityReference]:
        """Resolve an entire catalog phrase with bounded SQL and no fuzzy scan.

        This intentionally accepts only exact, prefix, or substring matches
        against normalized canonical names and known local aliases. It is the
        pre-provider cost guard; broader fuzzy resolution remains available to
        model-invoked tools through ``resolve``.
        """
        normalized = normalize_search_text(query)
        if not normalized:
            return []
        allowed = set(entity_types or SUPPORTED_ENTITY_TYPES) & SUPPORTED_ENTITY_TYPES
        result_limit = max(1, min(limit, DIRECT_LOOKUP_MAX_RESULTS))
        per_source_limit = DIRECT_LOOKUP_MAX_RESULTS * 2
        candidates: dict[tuple[str, str], ResolvedEntity] = {}

        def add(reference: AssistantEntityReference, aliases: tuple[str, ...] = ()) -> None:
            score = _rank(query, reference.canonical_name, aliases)
            maximum_rank = {"exact": 0, "prefix": 1, "contains": 2}[match_mode]
            if score[0] > maximum_rank:
                return
            # Canonical and legacy item rows with the same public identity are
            # one card. Type remains part of the identity so names shared by,
            # for example, an NPC and a location are both retained.
            identity = (reference.entity_type, normalize_search_text(reference.canonical_name))
            scored = ResolvedEntity(reference, score)
            current = candidates.get(identity)
            if current is None or scored.score < current.score:
                candidates[identity] = scored

        def matching(column):
            if match_mode == "exact":
                return column == normalized
            if match_mode == "prefix":
                return column.startswith(normalized, autoescape=True)
            return column.contains(normalized, autoescape=True)

        def canonical_match(normalized_column, name_column):
            return or_(matching(normalized_column), matching(func.lower(name_column)))

        def canonical_order(normalized_column, name_column, id_column, *aliases):
            values = (func.coalesce(normalized_column, func.lower(name_column)), *aliases)
            return (
                case(
                    (or_(*(value == normalized for value in values)), 0),
                    (or_(*(value.startswith(normalized, autoescape=True) for value in values)), 1),
                    else_=2,
                ),
                func.lower(name_column),
                id_column,
            )

        if "creature" in allowed:
            normalized_plural = func.lower(Creature.plural)
            creature_rows = self.db.query(Creature).filter(
                Creature.is_hidden.is_(False),
                or_(canonical_match(Creature.normalized_name, Creature.name), matching(normalized_plural)),
            ).order_by(*canonical_order(
                Creature.normalized_name, Creature.name, Creature.id, normalized_plural,
            )).limit(per_source_limit).all()
            for row in creature_rows:
                add(creature_reference(row), tuple(value for value in (row.plural,) if value))

        if "hunt_zone" in allowed:
            for row in self.db.query(HuntZone).filter(
                canonical_match(HuntZone.normalized_name, HuntZone.name),
            ).order_by(*canonical_order(
                HuntZone.normalized_name, HuntZone.name, HuntZone.id,
            )).limit(per_source_limit).all():
                add(hunt_zone_reference(row))

        if "item" in allowed:
            for row in self.db.query(Item).filter(
                canonical_match(Item.normalized_name, Item.name),
            ).order_by(*canonical_order(
                Item.normalized_name, Item.name, Item.id,
            )).limit(per_source_limit).all():
                add(item_reference(row))
            for row in self.db.query(Loot).filter(
                canonical_match(Loot.normalized_name, Loot.item_name),
            ).order_by(*canonical_order(
                Loot.normalized_name, Loot.item_name, Loot.id,
            )).limit(per_source_limit).all():
                add(legacy_item_reference(row))

        if "quest" in allowed:
            for row in self.db.query(TibiaWikiQuest).filter(
                TibiaWikiQuest.is_group.is_(False),
                canonical_match(TibiaWikiQuest.normalized_name, TibiaWikiQuest.name),
            ).order_by(*canonical_order(
                TibiaWikiQuest.normalized_name, TibiaWikiQuest.name, TibiaWikiQuest.id,
            )).limit(per_source_limit).all():
                add(quest_reference(row))

        if "npc" in allowed:
            for row in self.db.query(TibiaWikiNpc).filter(
                canonical_match(TibiaWikiNpc.normalized_name, TibiaWikiNpc.name),
            ).order_by(*canonical_order(
                TibiaWikiNpc.normalized_name, TibiaWikiNpc.name, TibiaWikiNpc.id,
            )).limit(per_source_limit).all():
                add(npc_reference(row))

        if allowed & {"location", "area", "town"}:
            for row in self.db.query(TibiaWikiLocation).options(
                joinedload(TibiaWikiLocation.knowledge_entity),
            ).filter(
                canonical_match(TibiaWikiLocation.normalized_name, TibiaWikiLocation.name),
            ).order_by(*canonical_order(
                TibiaWikiLocation.normalized_name, TibiaWikiLocation.name, TibiaWikiLocation.id,
            )).limit(per_source_limit).all():
                reference = location_reference(row)
                if reference.entity_type in allowed or "location" in allowed:
                    add(reference)

        alias_rows = self.db.query(KnowledgeEntityAlias).join(
            KnowledgeEntityAlias.entity,
        ).options(joinedload(KnowledgeEntityAlias.entity)).filter(
            matching(KnowledgeEntityAlias.normalized_alias),
            KnowledgeEntityAlias.entity_type.in_(allowed),
            KnowledgeEntity.status == "active",
            KnowledgeEntity.visibility == "public",
        ).order_by(
            case(
                (KnowledgeEntityAlias.normalized_alias == normalized, 0),
                (KnowledgeEntityAlias.normalized_alias.startswith(normalized, autoescape=True), 1),
                else_=2,
            ),
            KnowledgeEntityAlias.normalized_alias,
            KnowledgeEntityAlias.uuid,
        ).limit(per_source_limit).all()
        alias_entity_ids: dict[str, list] = {}
        for alias in alias_rows:
            alias_entity_ids.setdefault(alias.entity_type, []).append(alias.entity_uuid)
        alias_bridges: dict[tuple[str, object], AssistantEntityReference] = {}
        bridge_models = {
            "creature": Creature,
            "item": Item,
            "quest": TibiaWikiQuest,
            "npc": TibiaWikiNpc,
            "location": TibiaWikiLocation,
            "area": TibiaWikiLocation,
            "town": TibiaWikiLocation,
        }
        for entity_type, entity_ids in alias_entity_ids.items():
            model = bridge_models.get(entity_type)
            if model is None:
                continue
            bridge_query = self.db.query(model).filter(model.knowledge_entity_id.in_(entity_ids))
            if model is TibiaWikiLocation:
                bridge_query = bridge_query.options(joinedload(TibiaWikiLocation.knowledge_entity))
            for row in bridge_query.limit(per_source_limit).all():
                reference = {
                    "creature": creature_reference,
                    "item": item_reference,
                    "quest": quest_reference,
                    "npc": npc_reference,
                    "location": location_reference,
                    "area": location_reference,
                    "town": location_reference,
                }[entity_type](row)
                alias_bridges[(entity_type, row.knowledge_entity_id)] = reference
        for alias in alias_rows:
            reference = alias_bridges.get((alias.entity_type, alias.entity_uuid)) or generic_reference(alias.entity)
            if reference:
                add(reference, (alias.alias,))

        ranked = sorted(
            candidates.values(),
            key=lambda value: (
                value.score[0],
                value.reference.canonical_name.casefold(),
                value.reference.entity_type,
                value.reference.key,
            ),
        )
        return [value.reference for value in ranked[:result_limit]]

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
