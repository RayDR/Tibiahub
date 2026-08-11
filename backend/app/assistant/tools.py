"""Bounded, read-only TibiaHub domain tools exposed to the model."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.assistant.context import ConversationContextService
from app.assistant.entities import (
    AssistantEntityResolver,
    TurnEntityRegistry,
    creature_reference,
    hunt_zone_reference,
    item_reference,
    legacy_item_reference,
    location_reference,
    npc_reference,
    quest_reference,
)
from app.assistant.schemas import (
    AssistantConversationContext,
    AssistantEntityReference,
    AssistantMapReference,
    AssistantRouteReference,
    AssistantRouteStep,
)
from app.knowledge.models import KnowledgeRelationship, SpatialRoute
from app.knowledge.services import KnowledgeGraphService
from app.models import Creature, HuntZone, Loot, SpawnLocation
from app.models.external_data import Item, TibiaWikiLocation, TibiaWikiNpc, TibiaWikiQuest
from app.services.text_utils import normalize_search_text


MAX_TOOL_ITEMS = 20
MAX_TOOL_STRING_CHARS = 2000
MAX_TOOL_RESULT_BYTES = 32_000
SPAWN_DENSITY_LEVELS = {"few": 1, "some": 2, "many": 3, "plenty": 4}


class AssistantToolError(ValueError):
    pass


@dataclass
class ToolExecution:
    name: str
    evidence_key: str
    payload: dict[str, Any]
    entities: list[AssistantEntityReference] = field(default_factory=list)
    routes: list[AssistantRouteReference] = field(default_factory=list)
    data_gaps: list[str] = field(default_factory=list)

    def provider_payload(self) -> dict[str, Any]:
        value = {
            "evidence_key": self.evidence_key,
            **self.payload,
            "entities": [entity.model_dump(mode="json") for entity in self.entities],
            "routes": [route.model_dump(mode="json") for route in self.routes],
            "data_gaps": self.data_gaps,
        }
        return bound_tool_value(value)


def bound_tool_value(value: Any, depth: int = 0) -> Any:
    """Defensively cap provider context even if a synchronized record is unexpectedly large."""
    if depth > 8:
        return None
    if isinstance(value, str):
        return value[:MAX_TOOL_STRING_CHARS]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, dict):
        bounded = {str(key)[:100]: bound_tool_value(item, depth + 1) for key, item in list(value.items())[:MAX_TOOL_ITEMS]}
        while len(json.dumps(bounded, ensure_ascii=False, default=str).encode("utf-8")) > MAX_TOOL_RESULT_BYTES and bounded:
            bounded.pop(next(reversed(bounded)))
        return bounded
    if isinstance(value, (list, tuple, set)):
        bounded = [bound_tool_value(item, depth + 1) for item in list(value)[:MAX_TOOL_ITEMS]]
        while len(json.dumps(bounded, ensure_ascii=False, default=str).encode("utf-8")) > MAX_TOOL_RESULT_BYTES and bounded:
            bounded.pop()
        return bounded
    return str(value)[:MAX_TOOL_STRING_CHARS]


def _named(values: Any, limit: int = MAX_TOOL_ITEMS) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for value in list(values or [])[:limit]:
        if isinstance(value, dict):
            output.append({str(key): item for key, item in value.items() if key in {"name", "amount", "note", "description", "destination_name"}})
        elif isinstance(value, str):
            output.append({"name": value})
    return output


def _spawn_quantity(value: str | None) -> dict[str, Any] | None:
    normalized = normalize_search_text(value)
    if not normalized or normalized == "unknown":
        return None
    if normalized.isdigit() and int(normalized) > 0:
        return {"kind": "count", "value": int(normalized), "label": str(value)}
    if normalized in SPAWN_DENSITY_LEVELS:
        return {"kind": "density", "value": SPAWN_DENSITY_LEVELS[normalized], "label": str(value)}
    return None


def _relationship_values(db: Session, entity_id: UUID, limit: int = MAX_TOOL_ITEMS) -> list[dict[str, Any]]:
    values = [*KnowledgeGraphService.outgoing(db, entity_id), *KnowledgeGraphService.incoming(db, entity_id)]
    return [{
        "relationship_type": value.relationship_type,
        "target_name": value.target_name,
        "target_type": value.target_type,
        "target_slug": value.target_slug,
        "resolution_state": value.resolution_state,
        "confidence": value.confidence,
        "manual_verified": value.manual_verified,
    } for value in values[:limit]]


def _route_reference(row: SpatialRoute) -> AssistantRouteReference:
    maps: list[AssistantMapReference] = []
    for index, source in enumerate(list((row.source_metadata or {}).get("map_images") or [])[:10]):
        # Route ingestion may retain provider URLs as provenance. Assistant runtime
        # returns only already-local media endpoints and never causes a download.
        if not isinstance(source, str) or not source.startswith(("/api/", "/media/")):
            continue
        maps.append(AssistantMapReference(
            id=f"{row.id}:{index}", name=f"{row.name} map {index + 1}", image_url=source,
            verification_state=row.verification_state, confidence=row.confidence,
        ))
    return AssistantRouteReference(
        key=f"route:{row.id}", id=row.id, name=row.name, slug=row.slug,
        start_location=row.start_location.canonical_name if row.start_location else row.unresolved_start_name,
        end_location=row.end_location.canonical_name if row.end_location else row.unresolved_end_name,
        verification_state=row.verification_state, confidence=row.confidence,
        steps=[AssistantRouteStep(
            sequence=step.sequence, kind=step.step_kind, instruction=step.instruction,
            location_name=step.location_entity.canonical_name if step.location_entity else step.unresolved_location_name,
            x=step.tibia_x, y=step.tibia_y, z=step.tibia_z,
        ) for step in list(row.steps or [])[:50]],
        maps=maps,
    )


class TibiaHubAssistantTools:
    def __init__(self, db: Session, context: AssistantConversationContext, user_message: str):
        self.db = db
        self.context = context
        self.user_message = user_message
        self.resolver = AssistantEntityResolver(db)
        self.entities = TurnEntityRegistry()
        self.routes: dict[str, AssistantRouteReference] = {}
        self.evidence_keys: list[str] = []
        self.data_gaps: list[str] = []
        self.call_count = 0

    def _related_references(
        self,
        values: list[dict[str, Any]],
        entity_types: list[str],
        *,
        limit: int = MAX_TOOL_ITEMS,
    ) -> list[AssistantEntityReference]:
        references: list[AssistantEntityReference] = []
        for value in values:
            name = str(value.get("target_name") or value.get("name") or "").strip()
            if not name:
                continue
            reference = self.resolver.resolve_one(name, entity_types)
            if reference and reference.key not in {item.key for item in references}:
                references.append(reference)
            if len(references) >= limit:
                break
        return references

    @staticmethod
    def definitions() -> list[dict[str, Any]]:
        nullable_types = {"type": ["array", "null"], "items": {"type": "string"}}
        return [
            {
                "type": "function", "name": "resolve_entities", "strict": True,
                "description": "Resolve one or more user mentions to real local TibiaHub entities before referring to them.",
                "parameters": {"type": "object", "properties": {
                    "mentions": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 10},
                    "entity_types": nullable_types,
                }, "required": ["mentions", "entity_types"], "additionalProperties": False},
            },
            *[
                {
                    "type": "function", "name": name, "strict": True, "description": description,
                    "parameters": {"type": "object", "properties": {
                        "query": {"type": "string"},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 20},
                    }, "required": ["query", "limit"], "additionalProperties": False},
                }
                for name, description in (
                    ("creature_hunting_context", "Get local creature spawn and hunt-zone evidence."),
                    ("item_acquisition_context", "Get local item drops, NPC offers, rewards, and use evidence."),
                    ("location_access_context", "Get local location access, quest, relationship, and known-access context."),
                    ("quest_context", "Get local quest requirements, missions, access unlocks, and relationships."),
                )
            ],
            {
                "type": "function", "name": "route_context", "strict": True,
                "description": "Get verified or confidence-labelled local spatial routes and exact stored steps. Never infer missing steps.",
                "parameters": {"type": "object", "properties": {
                    "origin": {"type": ["string", "null"]}, "destination": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 10},
                }, "required": ["origin", "destination", "limit"], "additionalProperties": False},
            },
            {
                "type": "function", "name": "npc_travel_context", "strict": True,
                "description": "Find local NPC destination records for travel between named places.",
                "parameters": {"type": "object", "properties": {
                    "origin": {"type": ["string", "null"]}, "destination": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 20},
                }, "required": ["origin", "destination", "limit"], "additionalProperties": False},
            },
        ]

    def execute(self, name: str, arguments: dict[str, Any]) -> ToolExecution:
        handler = getattr(self, f"_tool_{name}", None)
        if handler is None:
            raise AssistantToolError(f"Unknown assistant tool: {name}")
        self.call_count += 1
        evidence_key = f"tool:{self.call_count}:{name}"
        execution: ToolExecution = handler(evidence_key=evidence_key, **arguments)
        self.evidence_keys.append(evidence_key)
        self.entities.add(*execution.entities)
        for route in execution.routes:
            self.routes[route.key] = route
        self.data_gaps.extend(gap for gap in execution.data_gaps if gap not in self.data_gaps)
        return execution

    def _tool_resolve_entities(self, mentions: list[str], entity_types: list[str] | None, *, evidence_key: str) -> ToolExecution:
        if not isinstance(mentions, list) or not 1 <= len(mentions) <= 10:
            raise AssistantToolError("mentions must contain between 1 and 10 values")
        results: list[dict[str, Any]] = []
        entities: list[AssistantEntityReference] = []
        for mention in mentions:
            matches = self.resolver.resolve(str(mention), entity_types, limit=5)
            entities.extend(matches)
            results.append({"mention": str(mention)[:255], "match_keys": [value.key for value in matches]})
        gaps = [f"No local entity resolved for: {row['mention']}" for row in results if not row["match_keys"]]
        return ToolExecution("resolve_entities", evidence_key, {"matches": results}, entities, data_gaps=gaps)

    def _tool_creature_hunting_context(self, query: str, limit: int, *, evidence_key: str) -> ToolExecution:
        reference = self.resolver.resolve_one(query, ["creature"])
        if reference is None:
            return ToolExecution("creature_hunting_context", evidence_key, {"query": query, "found": False}, data_gaps=[f"No local creature matched {query}."])
        creature = self.db.get(Creature, int(reference.id))
        if creature is None:
            return ToolExecution("creature_hunting_context", evidence_key, {"query": query, "found": False}, data_gaps=[f"Creature record for {query} is unavailable."])
        spawns = self.db.query(SpawnLocation).options(joinedload(SpawnLocation.hunt_zone)).filter(SpawnLocation.creature_id == creature.id).limit(min(limit, 20)).all()
        zone_refs = [hunt_zone_reference(spawn.hunt_zone) for spawn in spawns if spawn.hunt_zone]
        normalized_quantities = [
            (spawn, zone, _spawn_quantity(spawn.quantity))
            for spawn, zone in zip(spawns, zone_refs)
        ]
        comparable = [value for value in normalized_quantities if value[2] is not None]
        quantity_kinds = {value[2]["kind"] for value in comparable}
        ranking_available = len(comparable) >= 2 and len(quantity_kinds) == 1
        ranked_spawns = sorted(
            comparable,
            key=lambda value: (-value[2]["value"], value[1].canonical_name.casefold()),
        ) if ranking_available else []
        gaps = []
        if not spawns:
            gaps.append(f"TibiaHub has no synchronized hunt-zone links for {creature.name}.")
        if spawns and not ranking_available:
            gaps.append(f"Spawn quantities for {creature.name} are not verified, so zones cannot be ranked by abundance.")
        return ToolExecution("creature_hunting_context", evidence_key, {
            "found": True, "creature_key": reference.key,
            "spawns": [
                {
                    "hunt_zone_key": zone.key,
                    "quantity": spawn.quantity,
                    "normalized_quantity": quantity,
                    "notes": spawn.notes,
                }
                for spawn, zone, quantity in normalized_quantities
            ],
            "ranking_available": ranking_available,
            "ranking_complete": ranking_available and len(comparable) == len(spawns),
            "ranking_basis": next(iter(quantity_kinds)) if ranking_available else None,
            "ranked_spawns": [
                {
                    "hunt_zone_key": zone.key,
                    "normalized_quantity": quantity,
                }
                for _spawn, zone, quantity in ranked_spawns
            ],
            "known_location_names": list(creature.locations or [])[:20],
        }, [reference, *zone_refs], data_gaps=gaps)

    def _tool_item_acquisition_context(self, query: str, limit: int, *, evidence_key: str) -> ToolExecution:
        reference = self.resolver.resolve_one(query, ["item"])
        if reference is None:
            return ToolExecution("item_acquisition_context", evidence_key, {"query": query, "found": False}, data_gaps=[f"No local item matched {query}."])
        entities = [reference]
        payload: dict[str, Any] = {"found": True, "item_key": reference.key, "drops": [], "buy_from": [], "rewards_from": [], "required_for": []}
        if reference.key.startswith("item:legacy:"):
            rows = self.db.query(Loot).options(joinedload(Loot.creature).joinedload(Creature.spawn_locations).joinedload(SpawnLocation.hunt_zone)).filter(Loot.normalized_name == reference.id).limit(min(limit, 20)).all()
            for row in rows:
                if row.creature:
                    creature_ref = creature_reference(row.creature)
                    entities.append(creature_ref)
                    zones = [hunt_zone_reference(spawn.hunt_zone) for spawn in row.creature.spawn_locations[:10] if spawn.hunt_zone]
                    entities.extend(zones)
                    payload["drops"].append({"creature_key": creature_ref.key, "rarity": row.rarity, "chance": row.percentage, "hunt_zone_keys": [zone.key for zone in zones]})
        else:
            item = self.db.get(Item, int(reference.id))
            if item:
                buy_from = _named(item.buy_from, limit)
                payload.update({
                    "buy_from": buy_from, "rewards_from": list(item.rewards_from or [])[:limit],
                    "required_for": list(item.required_for or [])[:limit], "description": item.description, "notes": item.notes,
                })
                entities.extend(self._related_references(buy_from, ["npc"], limit=limit))
                if item.knowledge_entity_id:
                    relationships = [
                        *KnowledgeGraphService.incoming(self.db, item.knowledge_entity_id, relationship_type="dropped_by"),
                        *KnowledgeGraphService.outgoing(self.db, item.knowledge_entity_id, relationship_type="dropped_by"),
                    ][:limit]
                    for relation in relationships:
                        creature = self.db.query(Creature).filter(Creature.knowledge_entity_id == relation.target_entity_id).first() if relation.target_entity_id else None
                        creature_ref = creature_reference(creature) if creature else None
                        if creature_ref:
                            entities.append(creature_ref)
                        payload["drops"].append({
                            "creature_key": creature_ref.key if creature_ref else None, "creature_name": relation.target_name,
                            "resolution_state": relation.resolution_state, "confidence": relation.confidence,
                        })
        gaps = [] if any(payload[key] for key in ("drops", "buy_from", "rewards_from")) else [f"TibiaHub has the item {reference.canonical_name}, but no verified acquisition source."]
        return ToolExecution("item_acquisition_context", evidence_key, payload, entities, data_gaps=gaps)

    def _tool_location_access_context(self, query: str, limit: int, *, evidence_key: str) -> ToolExecution:
        reference = self.resolver.resolve_one(query, ["location", "area", "town"])
        known = ConversationContextService.knows_access(self.context, query)
        if reference is None:
            return ToolExecution("location_access_context", evidence_key, {"query": query, "found": False, "already_known_access": known}, data_gaps=[f"No local location matched {query}."])
        location = self.db.get(TibiaWikiLocation, int(reference.id))
        if location is None:
            return ToolExecution("location_access_context", evidence_key, {"query": query, "found": False, "already_known_access": known}, data_gaps=[f"Location record for {query} is unavailable."])
        known = known or ConversationContextService.knows_access(self.context, location.name)
        entities = [reference]
        quest_rows: list[TibiaWikiQuest] = []
        access_evidence: list[dict[str, Any]] = []
        target = normalize_search_text(location.name)
        for quest in self.db.query(TibiaWikiQuest).order_by(TibiaWikiQuest.id).limit(500).all():
            matching_access = [
                value
                for value in list(quest.access_unlocks or [])
                if isinstance(value, dict)
                and normalize_search_text(value.get("destination_name") or value.get("name") or "")
                in {target, f"{target} access"}
            ]
            matching_locations = [
                value
                for value in list(quest.locations or [])
                if isinstance(value, dict)
                and normalize_search_text(value.get("name") or "") == target
            ]
            if matching_access or matching_locations:
                quest_rows.append(quest)
                access_evidence.append({
                    "quest_id": quest.id,
                    "access_unlocks": _named(matching_access, limit),
                })
                if len(quest_rows) >= limit:
                    break
        quest_refs = [quest_reference(row) for row in quest_rows]
        entities.extend(quest_refs)
        suppress = known and not any(marker in normalize_search_text(self.user_message) for marker in ("access again", "unlock again", "acceso otra vez"))
        relationships = _relationship_values(self.db, location.knowledge_entity_id, limit)
        relation_refs: list[AssistantEntityReference] = []
        for relationship in relationships:
            target_type = relationship.get("target_type")
            allowed = [target_type] if target_type in {"creature", "item", "npc", "quest", "location", "area", "town", "hunt_zone"} else ["quest", "npc", "location", "area", "town"]
            relation_refs.extend(self._related_references([relationship], allowed, limit=1))
        entities.extend(relation_refs[:limit])
        payload = {
            "found": True, "location_key": reference.key, "already_known_access": known,
            "access_guidance_suppressed": suppress,
            "premium_required": location.premium_required, "minimum_level": location.minimum_level,
            "access_notes": None if suppress else location.access_notes,
            "quest_keys": [] if suppress else [value.key for value in quest_refs],
            "access_unlocks": [] if suppress else [
                {
                    "quest_key": quest_ref.key,
                    "values": evidence["access_unlocks"],
                }
                for quest_ref, evidence in zip(quest_refs, access_evidence)
            ],
            "relationships": relationships,
        }
        gaps = []
        if not suppress and not location.access_notes and not quest_rows:
            gaps.append(f"TibiaHub has no verified access instructions for {location.name}.")
        return ToolExecution("location_access_context", evidence_key, payload, entities, data_gaps=gaps)

    def _tool_quest_context(self, query: str, limit: int, *, evidence_key: str) -> ToolExecution:
        reference = self.resolver.resolve_one(query, ["quest"])
        if reference is None:
            return ToolExecution("quest_context", evidence_key, {"query": query, "found": False}, data_gaps=[f"No local quest matched {query}."])
        quest = self.db.get(TibiaWikiQuest, int(reference.id))
        if quest is None:
            return ToolExecution("quest_context", evidence_key, {"query": query, "found": False}, data_gaps=[f"Quest record for {query} is unavailable."])
        required_items = _named(quest.required_items, limit)
        required_quests = _named(quest.required_quests, limit)
        starting_npcs = _named(quest.starting_npcs, limit)
        locations = _named(quest.locations, limit)
        missions = [{
            "sequence": mission.sequence, "title": mission.title, "description": mission.description,
            "objectives": list(mission.objectives or [])[:limit], "required_items": _named(mission.required_items, limit),
            "related_npcs": _named(mission.related_npcs, limit), "locations": _named(mission.locations, limit),
        } for mission in list(quest.missions or [])[:limit]]
        relationships = _relationship_values(self.db, quest.knowledge_entity_id, limit) if quest.knowledge_entity_id else []
        entities = [reference]
        entities.extend(self._related_references(required_items, ["item"], limit=limit))
        entities.extend(self._related_references(required_quests, ["quest"], limit=limit))
        entities.extend(self._related_references(starting_npcs, ["npc"], limit=limit))
        entities.extend(self._related_references(locations, ["location", "area", "town"], limit=limit))
        for mission in missions:
            entities.extend(self._related_references(mission["required_items"], ["item"], limit=limit))
            entities.extend(self._related_references(mission["related_npcs"], ["npc"], limit=limit))
            entities.extend(self._related_references(mission["locations"], ["location", "area", "town"], limit=limit))
        for relationship in relationships:
            target_type = relationship.get("target_type")
            allowed = [target_type] if target_type in {"creature", "item", "npc", "quest", "location", "area", "town", "hunt_zone"} else ["creature", "item", "npc", "quest", "location"]
            entities.extend(self._related_references([relationship], allowed, limit=1))
        entities = list({value.key: value for value in entities}.values())[:MAX_TOOL_ITEMS]
        payload = {
            "found": True, "quest_key": reference.key, "summary": quest.summary, "description": quest.description,
            "requirements": list(quest.requirements or [])[:limit], "required_items": required_items,
            "required_quests": required_quests, "starting_npcs": starting_npcs,
            "locations": locations, "access_unlocks": _named(quest.access_unlocks, limit),
            "missions": missions, "relationships": relationships,
        }
        gaps = [] if any(payload[key] for key in ("requirements", "missions", "access_unlocks", "description", "summary")) else [f"TibiaHub has only identity metadata for {quest.name}; verified quest instructions are absent."]
        return ToolExecution("quest_context", evidence_key, payload, entities, data_gaps=gaps)

    def _tool_route_context(self, origin: str | None, destination: str, limit: int, *, evidence_key: str) -> ToolExecution:
        destination_ref = self.resolver.resolve_one(destination, ["location", "area", "town"])
        origin_ref = self.resolver.resolve_one(origin, ["location", "area", "town"]) if origin else None
        query = self.db.query(SpatialRoute).filter(SpatialRoute.is_current.is_(True), SpatialRoute.verification_state != "rejected")
        clauses = [SpatialRoute.unresolved_end_name.ilike(f"%{destination}%"), SpatialRoute.name.ilike(f"%{destination}%")]
        if destination_ref and destination_ref.knowledge_entity_id:
            clauses.append(SpatialRoute.end_location_entity_id == destination_ref.knowledge_entity_id)
        query = query.filter(or_(*clauses))
        if origin:
            origin_clauses = [SpatialRoute.unresolved_start_name.ilike(f"%{origin}%"), SpatialRoute.name.ilike(f"%{origin}%")]
            if origin_ref and origin_ref.knowledge_entity_id:
                origin_clauses.append(SpatialRoute.start_location_entity_id == origin_ref.knowledge_entity_id)
            query = query.filter(or_(*origin_clauses))
        rows = query.order_by(SpatialRoute.verification_state.desc(), SpatialRoute.confidence.desc(), SpatialRoute.name).limit(min(limit, 10)).all()
        routes = [_route_reference(row) for row in rows]
        entities = [value for value in (origin_ref, destination_ref) if value]
        gaps = []
        if not rows:
            gaps.append(f"TibiaHub has no non-rejected spatial route to {destination}.")
        elif any(not route.steps for route in routes):
            gaps.append("One or more local routes have no stored steps; missing directions were not inferred.")
        if rows and all(not route.maps for route in routes):
            gaps.append("No locally cached map image is available for these routes.")
        return ToolExecution("route_context", evidence_key, {
            "origin_key": origin_ref.key if origin_ref else None,
            "destination_key": destination_ref.key if destination_ref else None,
            "route_keys": [route.key for route in routes],
        }, entities, routes, gaps)

    def _tool_npc_travel_context(self, origin: str | None, destination: str, limit: int, *, evidence_key: str) -> ToolExecution:
        target = normalize_search_text(destination)
        origin_value = normalize_search_text(origin) if origin else ""
        matches: list[tuple[TibiaWikiNpc, dict[str, Any]]] = []
        for npc in self.db.query(TibiaWikiNpc).order_by(TibiaWikiNpc.id).limit(500).all():
            if origin_value and origin_value not in normalize_search_text(npc.location_name):
                continue
            for destination_value in list(npc.destinations or [])[:50]:
                if not isinstance(destination_value, dict):
                    continue
                label = destination_value.get("destination") or destination_value.get("name") or destination_value.get("location") or ""
                if target and target in normalize_search_text(str(label)):
                    matches.append((npc, destination_value))
                    break
            if len(matches) >= limit:
                break
        npc_refs = [npc_reference(npc) for npc, _ in matches]
        destination_ref = self.resolver.resolve_one(destination, ["location", "area", "town"])
        entities = [*npc_refs, *([destination_ref] if destination_ref else [])]
        gaps = [] if matches else [f"TibiaHub has no synchronized NPC destination to {destination}."]
        return ToolExecution("npc_travel_context", evidence_key, {
            "origin": origin, "destination": destination,
            "options": [{"npc_key": reference.key, "npc_location": npc.location_name, "destination_record": value} for (npc, value), reference in zip(matches, npc_refs)],
        }, entities, data_gaps=gaps)
