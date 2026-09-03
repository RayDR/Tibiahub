"""Canonical, read-only Hunting Zone projections for public consumers."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, selectinload

from app.knowledge.models import (
    KnowledgeEntity,
    KnowledgeEntityAlias,
    KnowledgeExternalMapping,
    KnowledgeRelationship,
)
from app.models import Creature, HuntZone, SpawnLocation
from app.models.external_data import TibiaWikiLocation, TibiaWikiQuest
from app.models.media_asset import MediaAsset
from app.models.quest import Quest
from app.schemas import HuntZoneBase
from app.services.map_presentation_service import zone_spatial_presentations
from app.services.text_utils import normalize_search_text


TRUSTED_CONFIDENCE = frozenset({"verified", "high"})
ZONE_RELATIONSHIP_TYPES = frozenset({
    "has_creature",
    "requires_hunt_quest",
    "requires_access",
    "located_at",
})


def _canonical_slug(zone: HuntZone) -> str:
    return zone.slug or normalize_search_text(zone.name).replace(" ", "-")


def _legacy_placeholder_row(zone: HuntZone) -> bool:
    raw = zone.raw_data if isinstance(zone.raw_data, dict) else {}
    return bool(
        zone.source_provider == "tibiamaps"
        and zone.external_id is None
        and not zone.supplied_fields
        and raw.get("source_provider") == "tibiamaps"
    )


def public_zone_fields(zone: HuntZone) -> dict:
    """Return compatible public fields without promoting legacy defaults to facts."""
    payload = {
        field_name: getattr(zone, field_name, None)
        for field_name in HuntZoneBase.model_fields
    }
    payload["slug"] = _canonical_slug(zone)
    payload["canonical_id"] = zone.knowledge_entity_id
    payload["knowledge_entity_id"] = zone.knowledge_entity_id
    if payload.get("avg_exp_hour") == 0:
        payload["avg_exp_hour"] = None
    if payload.get("avg_profit_hour") == 0:
        payload["avg_profit_hour"] = None
    if payload.get("recommended_level") == 0:
        payload["recommended_level"] = None

    # The historical TibiaMaps recovery populated placeholders, not provider
    # observations. Preserve the rows for SpawnLocation compatibility while
    # exposing their unknown values honestly.
    if _legacy_placeholder_row(zone):
        if payload.get("min_level") == 0:
            payload["min_level"] = None
        for field_name in (
            "knights_recommended",
            "paladins_recommended",
            "sorcerers_recommended",
            "druids_recommended",
            "monks_recommended",
            "requires_quest",
            "requires_premium",
        ):
            if payload.get(field_name) is False:
                payload[field_name] = None
        payload["map_bounds"] = None
        payload["map_image_url"] = None
    return payload


def _trusted(relationship: KnowledgeRelationship) -> bool:
    return bool(
        relationship.resolution_state == "resolved"
        and (
            relationship.confidence in TRUSTED_CONFIDENCE
            or relationship.manual_override
        )
    )


def _unresolved_reference(relationship: KnowledgeRelationship) -> dict:
    return {
        "name": relationship.unresolved_name or (
            relationship.target_entity.canonical_name if relationship.target_entity else "Unknown"
        ),
        "relationship": relationship.relationship_type_code,
        "resolution_state": relationship.resolution_state,
        "confidence": relationship.confidence,
        "source_provider": relationship.source_provider_id,
    }


def _access_names(zone: HuntZone, legacy_quest: Quest | None, location: TibiaWikiLocation | None) -> list[str]:
    names: list[str] = []
    if legacy_quest is not None and legacy_quest.name:
        names.append(legacy_quest.name)
    location_metadata = location.provider_metadata if location and isinstance(location.provider_metadata, dict) else {}
    values = location_metadata.get("access_quest_names") or []
    if isinstance(values, list):
        names.extend(str(value or "").strip() for value in values if str(value or "").strip())
    zone_metadata = zone.provider_metadata if isinstance(zone.provider_metadata, dict) else {}
    canonical = zone_metadata.get("canonical") if isinstance(zone_metadata.get("canonical"), dict) else {}
    values = canonical.get("access_quests") or []
    if isinstance(values, list):
        names.extend(str(value or "").strip() for value in values if str(value or "").strip())
    deduplicated: dict[str, str] = {}
    for name in names:
        normalized = normalize_search_text(name)
        if normalized:
            deduplicated.setdefault(normalized, name)
    return list(deduplicated.values())


class HuntZoneProjectionService:
    """Build bounded list or rich detail projections from one evidence policy."""

    @staticmethod
    def project(
        db: Session,
        zones: Iterable[HuntZone],
        *,
        detail: bool,
        creature_preview_limit: int = 3,
    ) -> list[dict]:
        rows = list(zones)
        if not rows:
            return []
        zone_ids = {zone.id for zone in rows}
        entity_ids = {zone.knowledge_entity_id for zone in rows if zone.knowledge_entity_id}

        entities = {
            entity.uuid: entity
            for entity in db.query(KnowledgeEntity).filter(KnowledgeEntity.uuid.in_(entity_ids)).all()
        } if entity_ids else {}
        aliases_by_entity: dict[UUID, list[str]] = defaultdict(list)
        mappings_by_entity: dict[UUID, list[dict]] = defaultdict(list)
        if entity_ids:
            for alias in db.query(KnowledgeEntityAlias).filter(
                KnowledgeEntityAlias.entity_uuid.in_(entity_ids),
            ).order_by(KnowledgeEntityAlias.alias).all():
                aliases_by_entity[alias.entity_uuid].append(alias.alias)
            for mapping in db.query(KnowledgeExternalMapping).filter(
                KnowledgeExternalMapping.entity_uuid.in_(entity_ids),
            ).order_by(KnowledgeExternalMapping.provider_id, KnowledgeExternalMapping.external_id).all():
                mappings_by_entity[mapping.entity_uuid].append({
                    "provider": mapping.provider_id,
                    "external_id": mapping.external_id,
                })

        outgoing: dict[UUID, list[KnowledgeRelationship]] = defaultdict(list)
        incoming_appearances: dict[UUID, list[KnowledgeRelationship]] = defaultdict(list)
        relationships: list[KnowledgeRelationship] = []
        if entity_ids:
            relationships = db.query(KnowledgeRelationship).options(
                selectinload(KnowledgeRelationship.source_entity),
                selectinload(KnowledgeRelationship.target_entity),
            ).filter(
                KnowledgeRelationship.is_current.is_(True),
                or_(
                    and_(
                        KnowledgeRelationship.source_entity_id.in_(entity_ids),
                        KnowledgeRelationship.relationship_type_code.in_(ZONE_RELATIONSHIP_TYPES),
                    ),
                    and_(
                        KnowledgeRelationship.target_entity_id.in_(entity_ids),
                        KnowledgeRelationship.relationship_type_code == "appears_in",
                    ),
                ),
            ).all()
            for relationship in relationships:
                if relationship.source_entity_id in entity_ids:
                    outgoing[relationship.source_entity_id].append(relationship)
                if (
                    relationship.relationship_type_code == "appears_in"
                    and relationship.target_entity_id in entity_ids
                ):
                    incoming_appearances[relationship.target_entity_id].append(relationship)

        access_entity_ids = {
            relationship.target_entity_id
            for relationship in relationships
            if relationship.relationship_type_code == "requires_access" and _trusted(relationship)
        }
        unlocks_by_access: dict[UUID, list[KnowledgeRelationship]] = defaultdict(list)
        unlock_relationships: list[KnowledgeRelationship] = []
        if access_entity_ids:
            unlock_relationships = db.query(KnowledgeRelationship).options(
                selectinload(KnowledgeRelationship.source_entity),
                selectinload(KnowledgeRelationship.target_entity),
            ).filter(
                KnowledgeRelationship.target_entity_id.in_(access_entity_ids),
                KnowledgeRelationship.relationship_type_code == "unlocks_access",
                KnowledgeRelationship.is_current.is_(True),
            ).all()
            for relationship in unlock_relationships:
                unlocks_by_access[relationship.target_entity_id].append(relationship)

        canonical_creature_ids: set[UUID] = set()
        canonical_quest_ids: set[UUID] = set()
        for zone_entity_id in entity_ids:
            for relationship in [*outgoing[zone_entity_id], *incoming_appearances[zone_entity_id]]:
                if relationship.relationship_type_code == "has_creature" and relationship.target_entity_id:
                    canonical_creature_ids.add(relationship.target_entity_id)
                elif relationship.relationship_type_code == "appears_in":
                    canonical_creature_ids.add(relationship.source_entity_id)
                elif relationship.relationship_type_code == "requires_hunt_quest" and relationship.target_entity_id:
                    canonical_quest_ids.add(relationship.target_entity_id)
        canonical_quest_ids.update(
            relationship.source_entity_id
            for relationship in unlock_relationships
            if relationship.source_entity_id
        )

        spawns = db.query(SpawnLocation).options(
            selectinload(SpawnLocation.creature),
        ).filter(SpawnLocation.hunt_zone_id.in_(zone_ids)).order_by(
            SpawnLocation.hunt_zone_id, SpawnLocation.id,
        ).all()
        spawns_by_zone: dict[int, list[SpawnLocation]] = defaultdict(list)
        for spawn in spawns:
            spawns_by_zone[spawn.hunt_zone_id].append(spawn)
            if spawn.creature and spawn.creature.knowledge_entity_id:
                canonical_creature_ids.add(spawn.creature.knowledge_entity_id)

        creatures_by_entity = {
            creature.knowledge_entity_id: creature
            for creature in db.query(Creature).filter(
                Creature.knowledge_entity_id.in_(canonical_creature_ids),
            ).all()
        } if canonical_creature_ids else {}

        legacy_quest_ids = {zone.quest_id for zone in rows if zone.quest_id}
        legacy_quests = {
            quest.id: quest
            for quest in db.query(Quest).filter(Quest.id.in_(legacy_quest_ids)).all()
        } if legacy_quest_ids else {}

        normalized_zone_names = {
            zone.normalized_name or normalize_search_text(zone.name)
            for zone in rows
        }
        locations_by_name: dict[str, TibiaWikiLocation] = {}
        if normalized_zone_names:
            grouped_locations: dict[str, list[TibiaWikiLocation]] = defaultdict(list)
            for location in db.query(TibiaWikiLocation).filter(
                TibiaWikiLocation.normalized_name.in_(normalized_zone_names),
            ).all():
                grouped_locations[location.normalized_name].append(location)
            locations_by_name = {
                name: matches[0] for name, matches in grouped_locations.items() if len(matches) == 1
            }

        all_access_names: set[str] = set()
        for zone in rows:
            normalized = zone.normalized_name or normalize_search_text(zone.name)
            all_access_names.update(
                normalize_search_text(name)
                for name in _access_names(zone, legacy_quests.get(zone.quest_id), locations_by_name.get(normalized))
            )
        quest_bridges = db.query(TibiaWikiQuest).filter(or_(
            TibiaWikiQuest.knowledge_entity_id.in_(canonical_quest_ids) if canonical_quest_ids else False,
            TibiaWikiQuest.normalized_name.in_(all_access_names) if all_access_names else False,
        )).all() if canonical_quest_ids or all_access_names else []
        quests_by_entity = {
            quest.knowledge_entity_id: quest
            for quest in quest_bridges if quest.knowledge_entity_id
        }
        grouped_quests: dict[str, list[TibiaWikiQuest]] = defaultdict(list)
        for quest in quest_bridges:
            if quest.normalized_name:
                grouped_quests[quest.normalized_name].append(quest)
        quests_by_name = {
            name: matches[0] for name, matches in grouped_quests.items() if len(matches) == 1
        }

        media_ids = {zone.map_asset_id for zone in rows if zone.map_asset_id}
        media_assets = {
            asset.id: asset
            for asset in db.query(MediaAsset).filter(MediaAsset.id.in_(media_ids)).all()
        } if media_ids else {}
        spatial_by_zone = zone_spatial_presentations(db, rows)

        return [HuntZoneProjectionService._project_one(
            zone,
            entities=entities,
            aliases_by_entity=aliases_by_entity,
            mappings_by_entity=mappings_by_entity,
            outgoing=outgoing,
            incoming_appearances=incoming_appearances,
            unlocks_by_access=unlocks_by_access,
            creatures_by_entity=creatures_by_entity,
            spawns=spawns_by_zone[zone.id],
            legacy_quest=legacy_quests.get(zone.quest_id),
            location=locations_by_name.get(zone.normalized_name or normalize_search_text(zone.name)),
            quests_by_entity=quests_by_entity,
            quests_by_name=quests_by_name,
            media_asset=media_assets.get(zone.map_asset_id),
            spatial=spatial_by_zone[zone.id],
            detail=detail,
            creature_preview_limit=creature_preview_limit,
        ) for zone in rows]

    @staticmethod
    def _project_one(
        zone: HuntZone,
        *,
        entities: dict,
        aliases_by_entity: dict,
        mappings_by_entity: dict,
        outgoing: dict,
        incoming_appearances: dict,
        unlocks_by_access: dict,
        creatures_by_entity: dict,
        spawns: list[SpawnLocation],
        legacy_quest: Quest | None,
        location: TibiaWikiLocation | None,
        quests_by_entity: dict,
        quests_by_name: dict,
        media_asset: MediaAsset | None,
        spatial: dict,
        detail: bool,
        creature_preview_limit: int,
    ) -> dict:
        payload = public_zone_fields(zone)
        entity = entities.get(zone.knowledge_entity_id)
        zone_relationships = outgoing.get(zone.knowledge_entity_id, [])
        appearance_relationships = incoming_appearances.get(zone.knowledge_entity_id, [])
        creature_projection, unresolved_creatures, creature_state = HuntZoneProjectionService._creatures(
            zone_relationships,
            appearance_relationships,
            creatures_by_entity,
            spawns,
        )
        access = HuntZoneProjectionService._access(
            zone,
            zone_relationships,
            unlocks_by_access,
            legacy_quest,
            location,
            quests_by_entity,
            quests_by_name,
        )
        resolved_locations, unresolved_locations = HuntZoneProjectionService._locations(zone_relationships)

        if spatial["geometry_status"] == "mapped":
            spatial_state = "resolved_bounds" if spatial.get("bounds") else "resolved_point"
        elif unresolved_locations:
            spatial_state = "unresolved"
        else:
            spatial_state = "knowledge_only"

        raw_experience = None
        represented_creatures = [value for value in creature_projection if value.get("id") is not None]
        if creature_projection and len(represented_creatures) == len(creature_projection):
            values = [value.get("experience") for value in represented_creatures]
            if all(value is not None for value in values):
                raw_experience = sum(values)

        media = HuntZoneProjectionService._media(zone, entity, media_asset)
        raw = zone.raw_data if isinstance(zone.raw_data, dict) else {}
        vocation_recommendations = raw.get("vocation_recommendations")
        payload["vocation_recommendations"] = (
            vocation_recommendations if isinstance(vocation_recommendations, dict) else None
        )
        if payload.get("min_level") is None and location and location.minimum_level is not None:
            payload["min_level"] = location.minimum_level
        if payload.get("max_level") is None and location and location.maximum_level is not None:
            payload["max_level"] = location.maximum_level
        if access["premium_required"] is True:
            payload["requires_premium"] = True
        if access["quest_required"] is True:
            payload["requires_quest"] = True
        payload.update({
            "id": zone.id,
            "identity_state": "canonical" if entity else "legacy_only",
            "spatial_state": spatial_state,
            "creature_state": creature_state,
            "creature_count": len(creature_projection),
            "boss_count": sum(value.get("is_boss") is True for value in creature_projection),
            "creature_preview": creature_projection[:creature_preview_limit],
            "raw_creature_experience": raw_experience,
            "access_required": access["quest_required"],
            "access_quest_count": len(access["quests"]) + len(access["unresolved_quests"]),
            "representative_media": media,
            "spatial": spatial,
            "supplied_fields": list(zone.supplied_fields or []) if zone.supplied_fields is not None else None,
            "missing_fields": HuntZoneProjectionService._missing_fields(zone),
            "data_sources": sorted({value for value in (zone.source_provider, zone.source_name) if value}) or None,
        })
        if access["quests"]:
            primary = access["quests"][0]
            payload["quest_id"] = primary["id"]
            payload["quest_name"] = primary["name"]
            payload["quest_slug"] = primary["slug"]
        elif legacy_quest is not None:
            # Compatibility display bridge: a unique local TibiaWiki quest may
            # supply its public route while canonical access identity remains
            # honestly unresolved in ``access.unresolved_quests``.
            public_quest = quests_by_name.get(normalize_search_text(legacy_quest.name))
            if public_quest is not None:
                payload["quest_id"] = public_quest.id
                payload["quest_name"] = public_quest.name
                payload["quest_slug"] = public_quest.slug
        if not detail:
            return payload

        payload.update({
            "canonical_identity": ({
                "canonical_id": entity.uuid,
                "domain_id": zone.id,
                "aliases": aliases_by_entity.get(entity.uuid, []),
                "provider_mappings": mappings_by_entity.get(entity.uuid, []),
            } if entity else None),
            "creatures": creature_projection,
            "unresolved_creatures": unresolved_creatures,
            "creature_spawns": spawns,
            "access": access,
            "locations": resolved_locations,
            "unresolved_locations": unresolved_locations,
        })
        return payload

    @staticmethod
    def _creatures(
        outgoing: list[KnowledgeRelationship],
        incoming: list[KnowledgeRelationship],
        creatures_by_entity: dict,
        spawns: list[SpawnLocation],
    ) -> tuple[list[dict], list[dict], str]:
        values: dict[str, dict] = {}
        unresolved: list[dict] = []
        canonical_keys: set[str] = set()
        legacy_keys: set[str] = set()

        graph_relationships = [
            relationship for relationship in [*outgoing, *incoming]
            if relationship.relationship_type_code in {"has_creature", "appears_in"}
        ]
        for relationship in graph_relationships:
            creature_entity_id = (
                relationship.target_entity_id
                if relationship.relationship_type_code == "has_creature"
                else relationship.source_entity_id
            )
            creature_entity = (
                relationship.target_entity
                if relationship.relationship_type_code == "has_creature"
                else relationship.source_entity
            )
            if not _trusted(relationship) or creature_entity is None:
                unresolved.append(_unresolved_reference(relationship))
                continue
            creature = creatures_by_entity.get(creature_entity_id)
            key = f"canonical:{creature_entity_id}"
            canonical_keys.add(key)
            existing = values.get(key)
            if existing is None:
                values[key] = {
                    "id": creature.id if creature else None,
                    "canonical_id": creature_entity_id,
                    "name": creature.name if creature else creature_entity.canonical_name,
                    "slug": creature.slug if creature else creature_entity.slug,
                    "is_boss": bool(creature.is_boss) if creature else creature_entity.entity_type == "boss",
                    "hitpoints": creature.hitpoints if creature else None,
                    "experience": creature.experience if creature else None,
                    "difficulty": creature.difficulty if creature else None,
                    "image_url": f"/api/v1/creatures/{creature.id}/image" if creature else None,
                    "quantity": None,
                    "notes": None,
                    "relationship_types": [relationship.relationship_type_code],
                    "sources": ["canonical_graph"],
                    "confidence": relationship.confidence,
                    "source_provider": relationship.source_provider_id,
                }
            else:
                existing["relationship_types"].append(relationship.relationship_type_code)
                if existing.get("source_provider") is None:
                    existing["source_provider"] = relationship.source_provider_id

        for spawn in spawns:
            creature = spawn.creature
            if creature is None:
                continue
            key = (
                f"canonical:{creature.knowledge_entity_id}"
                if creature.knowledge_entity_id else f"legacy:{creature.id}"
            )
            legacy_keys.add(key)
            existing = values.get(key)
            if existing is None:
                existing = {
                    "id": creature.id,
                    "canonical_id": creature.knowledge_entity_id,
                    "name": creature.name,
                    "slug": creature.slug,
                    "is_boss": bool(creature.is_boss),
                    "hitpoints": creature.hitpoints,
                    "experience": creature.experience,
                    "difficulty": creature.difficulty,
                    "image_url": f"/api/v1/creatures/{creature.id}/image",
                    "quantity": spawn.quantity,
                    "notes": spawn.notes,
                    "relationship_types": [],
                    "sources": ["legacy_spawn"],
                    "confidence": None,
                    "source_provider": creature.source_name,
                }
                values[key] = existing
            else:
                existing.update({
                    "id": creature.id,
                    "slug": creature.slug,
                    "is_boss": bool(creature.is_boss),
                    "hitpoints": creature.hitpoints,
                    "experience": creature.experience,
                    "difficulty": creature.difficulty,
                    "image_url": f"/api/v1/creatures/{creature.id}/image",
                    "quantity": spawn.quantity,
                    "notes": spawn.notes,
                })
                if "legacy_spawn" not in existing["sources"]:
                    existing["sources"].append("legacy_spawn")

        for value in values.values():
            value["sources"] = sorted(value["sources"], key=lambda item: item != "canonical_graph")
            value["relationship_types"] = sorted(set(value["relationship_types"]))
        ordered = sorted(values.values(), key=lambda item: (not bool(item["canonical_id"]), item["name"].casefold()))
        if canonical_keys and legacy_keys:
            state = "canonical_and_legacy"
        elif canonical_keys:
            state = "canonical"
        elif legacy_keys:
            state = "legacy_only"
        elif unresolved:
            state = "unresolved"
        else:
            state = "missing"
        return ordered, unresolved, state

    @staticmethod
    def _access(
        zone: HuntZone,
        outgoing: list[KnowledgeRelationship],
        unlocks_by_access: dict,
        legacy_quest: Quest | None,
        location: TibiaWikiLocation | None,
        quests_by_entity: dict,
        quests_by_name: dict,
    ) -> dict:
        quests: dict[str, dict] = {}
        unresolved: list[dict] = []
        evidence_relationships: list[KnowledgeRelationship] = []

        def add_resolved(relationship: KnowledgeRelationship, requirement_type: str) -> None:
            quest_entity = relationship.target_entity if requirement_type == "required_for_access" else relationship.source_entity
            quest_entity_id = relationship.target_entity_id if requirement_type == "required_for_access" else relationship.source_entity_id
            if not _trusted(relationship) or quest_entity is None:
                unresolved.append(_unresolved_reference(relationship))
                return
            bridge = quests_by_entity.get(quest_entity_id)
            key = f"canonical:{quest_entity_id}"
            existing = quests.get(key)
            if existing is None:
                quests[key] = {
                    "id": bridge.id if bridge else None,
                    "canonical_id": quest_entity_id,
                    "name": bridge.name if bridge else quest_entity.canonical_name,
                    "slug": bridge.slug if bridge else quest_entity.slug,
                    "requirement_type": requirement_type,
                    "resolution_state": "resolved",
                    "confidence": relationship.confidence,
                    "source_provider": relationship.source_provider_id,
                    "sources": ["canonical_graph"],
                }
            elif requirement_type == "required_for_access":
                existing["requirement_type"] = requirement_type

        for relationship in outgoing:
            if relationship.relationship_type_code == "requires_hunt_quest":
                evidence_relationships.append(relationship)
                if relationship.resolution_state == "resolved":
                    add_resolved(relationship, "required_for_access")
                else:
                    unresolved.append(_unresolved_reference(relationship))
            elif relationship.relationship_type_code == "requires_access" and _trusted(relationship):
                for unlock in unlocks_by_access.get(relationship.target_entity_id, []):
                    evidence_relationships.append(unlock)
                    if unlock.resolution_state == "resolved":
                        add_resolved(unlock, "unlocks_access")
                    else:
                        unresolved.append(_unresolved_reference(unlock))

        for name in _access_names(zone, legacy_quest, location):
            normalized = normalize_search_text(name)
            bridge = quests_by_name.get(normalized)
            canonical_id = bridge.knowledge_entity_id if bridge else None
            key = f"canonical:{canonical_id}" if canonical_id else f"unresolved:{normalized}"
            if canonical_id and key in quests:
                if "legacy_access" not in quests[key]["sources"]:
                    quests[key]["sources"].append("legacy_access")
                continue
            if bridge and canonical_id:
                quests[key] = {
                    "id": bridge.id,
                    "canonical_id": canonical_id,
                    "name": bridge.name,
                    "slug": bridge.slug,
                    "requirement_type": "required_for_access",
                    "resolution_state": "resolved",
                    "confidence": "high",
                    "source_provider": bridge.source_name,
                    "sources": ["legacy_access"],
                }
            elif not any(normalize_search_text(value["name"]) == normalized for value in unresolved):
                unresolved.append({
                    "name": name,
                    "relationship": "requires_hunt_quest",
                    "resolution_state": "unresolved",
                    "confidence": "high",
                    "source_provider": zone.source_provider,
                })

        quest_values = sorted(quests.values(), key=lambda item: item["name"].casefold())
        for value in quest_values:
            value["sources"] = sorted(set(value["sources"]), key=lambda item: item != "canonical_graph")

        zone_supplied = set(zone.supplied_fields or [])
        quest_required = (
            True if quest_values or unresolved or zone.requires_quest is True
            else False if zone.requires_quest is False and "access_quests" in zone_supplied
            else None
        )
        quest_requires_premium = any(
            (quests_by_entity.get(value["canonical_id"]).premium_required is True)
            for value in quest_values
            if value["canonical_id"] in quests_by_entity
        )
        if zone.requires_premium is True or quest_requires_premium:
            premium_required = True
        elif "premium_required" in zone_supplied and zone.requires_premium is False:
            premium_required = False
        elif location is not None:
            premium_required = location.premium_required
        else:
            premium_required = None

        minimum_level = location.minimum_level if location else None
        maximum_level = location.maximum_level if location else None
        metadata = zone.provider_metadata if isinstance(zone.provider_metadata, dict) else {}
        canonical = metadata.get("canonical") if isinstance(metadata.get("canonical"), dict) else {}
        notes = location.access_notes if location else canonical.get("access_notes")
        restriction = bool(
            (minimum_level is not None and minimum_level > 0)
            or premium_required is True
            or quest_required is True
        )
        evidence = bool(
            minimum_level is not None
            or maximum_level is not None
            or premium_required is not None
            or quest_required is not None
            or notes
        )
        provider = next((value.source_provider_id for value in evidence_relationships if value.source_provider_id), None)
        return {
            "status": "restricted" if restriction else "documented" if evidence else "unknown",
            "minimum_level": minimum_level,
            "maximum_level": maximum_level,
            "premium_required": premium_required,
            "quest_required": quest_required,
            "quests": quest_values,
            "unresolved_quests": unresolved,
            "notes": notes,
            "source_provider": provider or (location.source_name if location else zone.source_provider),
            "source_url": location.source_url if location else zone.source_url,
        }

    @staticmethod
    def _locations(outgoing: list[KnowledgeRelationship]) -> tuple[list[dict], list[dict]]:
        resolved: list[dict] = []
        unresolved: list[dict] = []
        for relationship in outgoing:
            if relationship.relationship_type_code != "located_at":
                continue
            if _trusted(relationship) and relationship.target_entity is not None:
                resolved.append({
                    "canonical_id": relationship.target_entity_id,
                    "name": relationship.target_entity.canonical_name,
                    "entity_type": relationship.target_entity.entity_type,
                    "relationship": "located_at",
                    "resolution_state": "resolved",
                    "confidence": relationship.confidence,
                    "source_provider": relationship.source_provider_id,
                })
            else:
                unresolved.append(_unresolved_reference(relationship))
        return resolved, unresolved

    @staticmethod
    def _media(zone: HuntZone, entity: KnowledgeEntity | None, asset: MediaAsset | None) -> dict:
        if asset is not None and asset.status == "cached":
            return {
                "status": "available",
                "kind": "local_media",
                "url": f"/api/v1/hunt-zones/{zone.id}/map-image?placeholder=false",
                "source_provider": zone.source_provider,
                "source_url": asset.source_url or zone.source_url,
            }
        if entity is not None and entity.media_id is not None:
            return {
                "status": "reference_only",
                "kind": "canonical_knowledge_media",
                "url": None,
                "source_provider": None,
                "source_url": None,
            }
        if zone.map_image_url and "image_reference" in set(zone.supplied_fields or []):
            return {
                "status": "reference_only",
                "kind": "provider_image_reference",
                "url": None,
                "source_provider": zone.source_provider,
                "source_url": zone.map_image_url,
            }
        if zone.map_image_url and not _legacy_placeholder_row(zone):
            return {
                "status": "available",
                "kind": "curated_zone_image",
                "url": zone.map_image_url,
                "source_provider": zone.source_provider,
                "source_url": zone.source_url,
            }
        return {
            "status": "missing",
            "kind": None,
            "url": None,
            "source_provider": None,
            "source_url": None,
        }

    @staticmethod
    def _missing_fields(zone: HuntZone) -> list[str]:
        supplied = set(zone.supplied_fields or [])
        expected = {
            "city",
            "location",
            "vocation_recommendations",
            "creatures",
            "access_notes",
            "access_quests",
            "premium_required",
            "experience",
            "loot",
            "map_references",
            "source_reference",
        }
        return sorted(expected - supplied)
