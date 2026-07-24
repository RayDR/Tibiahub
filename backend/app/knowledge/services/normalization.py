"""Provider-neutral no-op and canonical test-entity normalization boundary."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.knowledge.adapters import KnowledgeNormalizationResult
from app.knowledge.events import KnowledgeEventType, emit_event
from app.knowledge.metadata import refresh_search_metadata
from app.knowledge.models import KnowledgeEntity, KnowledgeEntityAlias
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


class KnowledgeNormalizationService:
    @staticmethod
    def apply(db: Session, result: KnowledgeNormalizationResult) -> AppliedNormalization:
        if result.action == "noop":
            return AppliedNormalization("unchanged", None, 0, len(result.warnings))
        if result.canonical_data is not None and result.provider_code == "tibiawiki":
            from app.knowledge.services.creature_normalization import CreatureKnowledgeNormalizationService

            applied = CreatureKnowledgeNormalizationService.apply(db, result)
            return AppliedNormalization(
                applied.status,
                applied.entity_uuid,
                applied.aliases_created,
                applied.warnings,
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
            return AppliedNormalization("created", entity.uuid, len(candidate.aliases) + 1, len(result.warnings))

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
        refresh_search_metadata(entity)
        if changed:
            emit_event(
                db,
                KnowledgeEventType.ENTITY_UPDATED,
                entity_uuid=entity.uuid,
                payload={"source": "knowledge_normalization"},
            )
        return AppliedNormalization(
            "updated" if changed else "unchanged",
            entity.uuid,
            aliases_created,
            len(result.warnings),
        )
