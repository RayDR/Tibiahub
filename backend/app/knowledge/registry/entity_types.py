"""Data-driven registry for canonical entity types."""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.knowledge.models import KnowledgeEntityType


@dataclass(frozen=True, slots=True)
class EntityTypeDefinition:
    entity_type: str
    display_name: str
    metadata: dict[str, object] = field(default_factory=dict)


INITIAL_ENTITY_TYPES = (
    EntityTypeDefinition("creature", "Creature"),
    EntityTypeDefinition("item", "Item"),
    EntityTypeDefinition("quest", "Quest"),
    EntityTypeDefinition("npc", "NPC"),
    EntityTypeDefinition("spell", "Spell"),
    EntityTypeDefinition("achievement", "Achievement"),
    EntityTypeDefinition("imbuement", "Imbuement"),
    EntityTypeDefinition("bestiary", "Bestiary"),
    EntityTypeDefinition("boss", "Boss"),
    EntityTypeDefinition("guild", "Guild"),
    EntityTypeDefinition("character", "Character"),
    EntityTypeDefinition("world", "World"),
    EntityTypeDefinition("hunt_zone", "Hunt Zone"),
    EntityTypeDefinition("access", "Access"),
    EntityTypeDefinition("area", "Area"),
    EntityTypeDefinition("town", "Town"),
    EntityTypeDefinition("location", "Location"),
    EntityTypeDefinition("map_point", "Map Point"),
    EntityTypeDefinition("map_region", "Map Region"),
    EntityTypeDefinition("route", "Route"),
)


class EntityTypeRegistry:
    @staticmethod
    def register(db: Session, definition: EntityTypeDefinition) -> KnowledgeEntityType:
        entity_type = db.get(KnowledgeEntityType, definition.entity_type)
        if entity_type is None:
            entity_type = KnowledgeEntityType(entity_type=definition.entity_type)
            db.add(entity_type)
        entity_type.display_name = definition.display_name
        entity_type.type_metadata = dict(definition.metadata)
        return entity_type

    @classmethod
    def register_initial(cls, db: Session) -> list[KnowledgeEntityType]:
        return [cls.register(db, definition) for definition in INITIAL_ENTITY_TYPES]

    @staticmethod
    def get(db: Session, entity_type: str) -> KnowledgeEntityType | None:
        return db.get(KnowledgeEntityType, entity_type)

    @staticmethod
    def enabled(db: Session) -> list[KnowledgeEntityType]:
        return (
            db.query(KnowledgeEntityType)
            .filter(KnowledgeEntityType.enabled.is_(True))
            .order_by(KnowledgeEntityType.display_name.asc())
            .all()
        )
