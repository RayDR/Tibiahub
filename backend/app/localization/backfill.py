"""Safe, paginated translation backfill for existing canonical content."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.knowledge.models import KnowledgeEntity
from app.localization.queue import LocalizationQueueService
from app.models.creature import Creature
from app.models.external_data import Item, TibiaWikiLocation, TibiaWikiNpc, TibiaWikiQuest
from app.models.hunt_zone import HuntZone


SUPPORTED_BACKFILL_TYPES = ("creature", "item", "quest", "npc", "location", "hunt_zone")


@dataclass(frozen=True)
class LocalizationBackfillResult:
    resource_type: str
    scanned: int
    queued: int
    next_cursor: int | None
    exhausted: bool


def _resource_key(row) -> str:
    entity_uuid = getattr(row, "knowledge_entity_id", None)
    if entity_uuid is not None:
        return str(entity_uuid)
    external_id = getattr(row, "external_id", None)
    if external_id not in (None, ""):
        return str(external_id)
    return str(row.id)


def _canonical_name(row) -> str:
    return str(getattr(row, "name", "") or "").strip()


def _entity_terms(db: Session, row) -> tuple[str, ...]:
    terms: set[str] = set()
    name = _canonical_name(row)
    if name:
        terms.add(name)
    entity_uuid = getattr(row, "knowledge_entity_id", None)
    if entity_uuid is not None:
        entity = db.get(KnowledgeEntity, entity_uuid)
        if entity is not None:
            if entity.canonical_name:
                terms.add(entity.canonical_name)
            terms.update(alias.alias for alias in entity.aliases if alias.alias)
    return tuple(sorted(terms, key=len, reverse=True))


def _fields_for(row, resource_type: str) -> dict[str, str | None]:
    if resource_type == "creature":
        return {
            "description": row.description,
            "behavior": row.behavior,
            "strategy": row.strategy,
            "notes": row.notes,
        }
    if resource_type == "item":
        return {"description": row.description, "notes": row.notes}
    if resource_type == "quest":
        fields: dict[str, str | None] = {
            "description": row.description,
            "summary": row.summary,
        }
        for mission in row.missions:
            identity = mission.external_id or mission.sequence
            fields[f"missions.{identity}.description"] = mission.description
            for index, objective in enumerate(mission.objectives or []):
                if isinstance(objective, str):
                    fields[f"missions.{identity}.objectives.{index}"] = objective
        return fields
    if resource_type == "npc":
        return {
            "title": row.title,
            "occupation": row.occupation,
            "description": row.description,
        }
    if resource_type == "location":
        return {"description": row.description, "access_notes": row.access_notes}
    if resource_type == "hunt_zone":
        return {"description": row.description, "tips": row.tips}
    raise ValueError("unsupported localization backfill resource type")


class LocalizationBackfillService:
    MODELS = {
        "creature": Creature,
        "item": Item,
        "quest": TibiaWikiQuest,
        "npc": TibiaWikiNpc,
        "location": TibiaWikiLocation,
        "hunt_zone": HuntZone,
    }

    @classmethod
    def backfill(
        cls,
        db: Session,
        *,
        resource_type: str,
        after_id: int = 0,
        limit: int = 100,
        source_language: str = "en",
        target_languages: tuple[str, ...] | None = None,
    ) -> LocalizationBackfillResult:
        model = cls.MODELS.get(resource_type)
        if model is None:
            raise ValueError("unsupported localization backfill resource type")
        limit = max(1, min(limit, 500))
        rows = (
            db.query(model)
            .filter(model.id > after_id)
            .order_by(model.id.asc())
            .limit(limit + 1)
            .all()
        )
        selected = rows[:limit]
        has_more = len(rows) > limit
        queued = 0
        for row in selected:
            fields = _fields_for(row, resource_type)
            if not any(isinstance(value, str) and value.strip() for value in fields.values()):
                continue
            queued += LocalizationQueueService.enqueue_targets(
                db,
                resource_type=resource_type,
                resource_key=_resource_key(row),
                fields=fields,
                source_language=source_language,
                entity_uuid=getattr(row, "knowledge_entity_id", None),
                protected_terms=_entity_terms(db, row),
                context=f"Tibia {resource_type} knowledge: {_canonical_name(row)}",
                target_languages=target_languages,
                force=True,
            )
        next_cursor = selected[-1].id if selected and has_more else None
        return LocalizationBackfillResult(
            resource_type=resource_type,
            scanned=len(selected),
            queued=queued,
            next_cursor=next_cursor,
            exhausted=not has_more,
        )
