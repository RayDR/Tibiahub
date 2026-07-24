"""Central, data-backed Knowledge Graph relationship-type registry."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.knowledge.models.graph import KnowledgeRelationshipType


@dataclass(frozen=True, slots=True)
class RelationshipTypeDefinition:
    code: str
    inverse_code: str
    sources: tuple[str, ...]
    targets: tuple[str, ...]
    directional: bool = True
    symmetric: bool = False
    transitive: bool = False
    user_visible: bool = True
    ai_visible: bool = True

    @property
    def display_translation_key(self) -> str:
        return f"knowledgeGraph.relationships.{self.code}"


def _pair(code: str, inverse: str, sources: tuple[str, ...], targets: tuple[str, ...]):
    return (
        RelationshipTypeDefinition(code, inverse, sources, targets),
        RelationshipTypeDefinition(inverse, code, targets, sources),
    )


INITIAL_RELATIONSHIP_TYPES = tuple(definition for pair in (
    _pair("drops", "dropped_by", ("creature",), ("item",)),
    _pair("requires_item", "required_by_quest", ("quest",), ("item",)),
    _pair("rewards_item", "rewarded_by_quest", ("quest",), ("item",)),
    _pair("requires_quest", "prerequisite_for", ("quest",), ("quest",)),
    _pair("unlocks_access", "unlocked_by_quest", ("quest",), ("access",)),
    _pair("involves_creature", "involved_in_quest", ("quest",), ("creature",)),
    _pair("involves_boss", "boss_in_quest", ("quest",), ("creature", "boss")),
    _pair("starts_at_npc", "starts_quest", ("quest",), ("npc",)),
    _pair("references_npc", "referenced_by_quest", ("quest",), ("npc",)),
    _pair("occurs_at_location", "hosts_quest", ("quest",), ("area", "town", "location")),
    _pair("mission_requires_item", "required_by_mission", ("quest",), ("item",)),
    _pair("mission_rewards_item", "rewarded_by_mission", ("quest",), ("item",)),
    _pair("mission_involves_creature", "involved_in_mission", ("quest",), ("creature",)),
    _pair("mission_references_npc", "referenced_by_mission", ("quest",), ("npc",)),
    _pair("mission_occurs_at_location", "hosts_mission", ("quest",), ("area", "town", "location")),
    _pair("located_at", "hosts_npc", ("npc",), ("area", "town", "location")),
    _pair("contained_in", "contains", ("area", "location"), ("area", "town")),
    _pair("leads_to", "destination_of_access", ("access",), ("area", "town", "location")),
) for definition in pair)


class RelationshipTypeRegistry:
    @staticmethod
    def register_initial(db: Session) -> list[KnowledgeRelationshipType]:
        rows: dict[str, KnowledgeRelationshipType] = {}
        for definition in INITIAL_RELATIONSHIP_TYPES:
            row = db.get(KnowledgeRelationshipType, definition.code)
            if row is None:
                row = KnowledgeRelationshipType(code=definition.code, inverse_code=definition.code)
                db.add(row)
            row.display_translation_key = definition.display_translation_key
            row.source_entity_types = list(definition.sources)
            row.target_entity_types = list(definition.targets)
            row.directional = definition.directional
            row.symmetric = definition.symmetric
            row.transitive = definition.transitive
            row.user_visible = definition.user_visible
            row.ai_visible = definition.ai_visible
            row.active = True
            rows[definition.code] = row
        db.flush()
        for definition in INITIAL_RELATIONSHIP_TYPES:
            rows[definition.code].inverse_code = definition.inverse_code
        db.flush()
        return list(rows.values())

    @staticmethod
    def get(db: Session, code: str) -> KnowledgeRelationshipType | None:
        return db.get(KnowledgeRelationshipType, code)

    @staticmethod
    def inverse(db: Session, code: str) -> str:
        definition = db.get(KnowledgeRelationshipType, code)
        if definition is None or not definition.active:
            raise ValueError("Unsupported relationship type")
        return definition.inverse_code

    @staticmethod
    def validate(db: Session, code: str, source_type: str, target_type: str) -> KnowledgeRelationshipType:
        definition = db.get(KnowledgeRelationshipType, code)
        if definition is None or not definition.active:
            raise ValueError("Unsupported relationship type")
        if source_type not in (definition.source_entity_types or []):
            raise ValueError("Invalid source entity type for relationship")
        if target_type not in (definition.target_entity_types or []):
            raise ValueError("Invalid target entity type for relationship")
        if definition.symmetric and definition.inverse_code != definition.code:
            raise ValueError("Symmetric relationship types must be their own inverse")
        return definition

    @staticmethod
    def verify_integrity(db: Session) -> list[str]:
        errors: list[str] = []
        for row in db.query(KnowledgeRelationshipType).filter_by(active=True).all():
            inverse = db.get(KnowledgeRelationshipType, row.inverse_code)
            if inverse is None or inverse.inverse_code != row.code:
                errors.append(f"broken_inverse:{row.code}")
            if row.symmetric and row.inverse_code != row.code:
                errors.append(f"invalid_symmetric_inverse:{row.code}")
        return errors
