"""Provider-neutral no-op and canonical test-entity normalization boundary."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy.orm import Session

from app.knowledge.adapters import KnowledgeNormalizationResult
from app.knowledge.events import KnowledgeEventType, emit_event
from app.knowledge.metadata import refresh_search_metadata
from app.knowledge.models import KnowledgeEntity, KnowledgeEntityAlias, KnowledgeExternalMapping
from app.knowledge.schemas import KnowledgeEntityCreate
from app.knowledge.services.entities import (
    DuplicateKnowledgeAliasError,
    DuplicateKnowledgeEntityError,
    KnowledgeEntityService,
)


@dataclass(frozen=True, slots=True)
class AppliedNormalization:
    status: str
    entity_uuid: UUID | None
    aliases_created: int
    warnings: int
    metrics: dict[str, int] = field(default_factory=dict)


class KnowledgeNormalizationService:
    @staticmethod
    def apply(db: Session, result: KnowledgeNormalizationResult) -> AppliedNormalization:
        if result.action == "noop":
            return AppliedNormalization("unchanged", None, 0, len(result.warnings))
        if (
            result.canonical_data is not None
            and result.provider_code == "tibiamaps"
            and result.candidate is not None
            and result.candidate.entity_type in {"map_point", "map_region"}
        ):
            from app.knowledge.dto import MapPointDTO, MapRegionDTO
            from app.knowledge.models import SpatialMapPoint, SpatialMapRegion
            from app.knowledge.services.spatial import persist_map_point, persist_map_region

            data = {
                key: value for key, value in result.canonical_data.items()
                if key not in {"upstream_commit", "version", "supplied_fields", "data_version"}
            }
            model = SpatialMapPoint if result.candidate.entity_type == "map_point" else SpatialMapRegion
            existing = db.query(model).filter_by(
                source_provider_id=result.provider_code,
                external_id=result.external_id,
                is_current=True,
            ).first()
            row = (
                persist_map_point(db, MapPointDTO(**data), provider=result.provider_code)
                if result.candidate.entity_type == "map_point"
                else persist_map_region(db, MapRegionDTO(**data), provider=result.provider_code)
            )
            status = "created" if existing is None else "unchanged" if existing.id == row.id else "updated"
            return AppliedNormalization(status, row.knowledge_entity_id, int(existing is None), len(result.warnings))
        if result.canonical_data is not None and result.provider_code == "tibiawiki":
            if result.candidate is not None and result.candidate.entity_type == "creature":
                from app.knowledge.services.creature_normalization import CreatureKnowledgeNormalizationService

                applied = CreatureKnowledgeNormalizationService.apply(db, result)
            elif result.candidate is not None and result.candidate.entity_type == "item":
                from app.knowledge.services.item_normalization import ItemKnowledgeNormalizationService

                applied = ItemKnowledgeNormalizationService.apply(db, result)
            elif result.candidate is not None and result.candidate.entity_type == "quest":
                from app.knowledge.services.quest_normalization import QuestKnowledgeNormalizationService

                applied = QuestKnowledgeNormalizationService.apply(db, result)
            elif result.candidate is not None and result.candidate.entity_type in {"npc", "location", "area", "town"}:
                from app.knowledge.services.npc_location_normalization import NpcLocationKnowledgeNormalizationService

                applied = NpcLocationKnowledgeNormalizationService.apply(db, result)
            elif result.candidate is not None and result.candidate.entity_type == "route":
                from app.knowledge.dto import RouteDTO, RouteStepDTO
                from app.knowledge.models import SpatialRoute
                from app.knowledge.services.spatial import persist_route

                data = dict(result.canonical_data)
                data["steps"] = tuple(RouteStepDTO(**step) for step in data.get("steps") or [])
                existing = db.query(SpatialRoute).filter_by(
                    source_provider_id=result.provider_code,
                    external_id=result.external_id,
                    is_current=True,
                ).first()
                route = persist_route(db, RouteDTO(**data), provider=result.provider_code)
                status = "created" if existing is None else "unchanged" if existing.id == route.id else "updated"
                return AppliedNormalization(status, route.knowledge_entity_id, 0, len(result.warnings), {"route_steps": route.step_count})
            elif result.candidate is not None and result.candidate.entity_type == "hunt_zone":
                from app.knowledge.services.hunt_zone_normalization import HuntZoneKnowledgeNormalizationService

                applied = HuntZoneKnowledgeNormalizationService.apply(db, result)
            else:
                raise ValueError("TibiaWiki normalization requires a supported canonical entity type")
            return AppliedNormalization(
                applied.status,
                applied.entity_uuid,
                applied.aliases_created,
                applied.warnings,
                getattr(applied, "metrics", {}),
            )
        candidate = result.candidate
        if candidate is None:
            raise ValueError("Upsert normalization requires a canonical candidate")
        entity = (
            db.query(KnowledgeEntity)
            .filter(
                KnowledgeEntity.entity_type == candidate.entity_type,
                KnowledgeEntity.language_neutral_id == candidate.language_neutral_id,
            )
            .first()
        )
        if entity is None and candidate.identity_strategy == "exact_unique_or_create":
            from app.knowledge.indexing import normalize_name

            normalized = normalize_name(candidate.canonical_name)
            exact = db.query(KnowledgeEntity).filter(
                KnowledgeEntity.entity_type == candidate.entity_type,
            ).all()
            matches = [row for row in exact if normalize_name(row.canonical_name) == normalized]
            alias_matches = db.query(KnowledgeEntity).join(KnowledgeEntityAlias).filter(
                KnowledgeEntity.entity_type == candidate.entity_type,
                KnowledgeEntityAlias.normalized_alias == normalized,
            ).all()
            matches = list({row.uuid: row for row in [*matches, *alias_matches]}.values())
            if len(matches) == 1:
                entity = matches[0]
        created = entity is None
        if entity is None:
            entity = KnowledgeEntityService.create(
                db,
                KnowledgeEntityCreate(
                    entity_type=candidate.entity_type,
                    canonical_name=candidate.canonical_name,
                    language_neutral_id=candidate.language_neutral_id,
                    aliases=list(candidate.aliases),
                    status=candidate.status,
                    source_priority=candidate.source_priority,
                    visibility=candidate.visibility,
                    search_weight=candidate.search_weight,
                ),
            )
        changed = False
        for field, value in (
            ("canonical_name", candidate.canonical_name),
            ("status", candidate.status),
            ("source_priority", candidate.source_priority),
            ("visibility", candidate.visibility),
            ("search_weight", candidate.search_weight),
        ):
            if getattr(entity, field) != value:
                setattr(entity, field, value)
                changed = True
        aliases_created = 0
        existing_aliases = {
            alias.normalized_alias
            for alias in db.query(KnowledgeEntityAlias).filter(KnowledgeEntityAlias.entity_uuid == entity.uuid).all()
        }
        from app.knowledge.indexing import normalize_name

        for alias in candidate.aliases:
            if normalize_name(alias) in existing_aliases:
                continue
            try:
                KnowledgeEntityService.add_alias(db, entity, alias)
                aliases_created += 1
            except (DuplicateKnowledgeAliasError, DuplicateKnowledgeEntityError):
                continue
        if aliases_created:
            changed = True
        if result.provider_code and result.external_id:
            mapping = db.query(KnowledgeExternalMapping).filter_by(
                provider_id=result.provider_code,
                entity_type_id=candidate.entity_type,
                external_id=result.external_id,
            ).first()
            if mapping is None:
                mapping = KnowledgeExternalMapping(
                    provider_id=result.provider_code,
                    entity_type_id=candidate.entity_type,
                    external_id=result.external_id,
                    entity_uuid=entity.uuid,
                    provider_metadata=dict(result.canonical_data or {}),
                )
                db.add(mapping)
                changed = True
            elif mapping.entity_uuid != entity.uuid:
                raise ValueError("Provider identity conflicts with an existing canonical entity")
            elif mapping.provider_metadata != dict(result.canonical_data or {}):
                mapping.provider_metadata = dict(result.canonical_data or {})
                changed = True
        refresh_search_metadata(entity)
        if changed:
            emit_event(
                db,
                KnowledgeEventType.ENTITY_UPDATED,
                entity_uuid=entity.uuid,
                payload={"source": "knowledge_normalization"},
            )
        return AppliedNormalization(
            "created" if created else "updated" if changed else "unchanged",
            entity.uuid,
            len(candidate.aliases) + 1 if created else aliases_created,
            len(result.warnings),
        )
