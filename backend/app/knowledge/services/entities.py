"""Canonical entity and alias lifecycle logic."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.knowledge.events import KnowledgeEventType, emit_event
from app.knowledge.indexing import normalize_name, slugify
from app.knowledge.metadata import refresh_search_metadata
from app.knowledge.models import KnowledgeEntity, KnowledgeEntityAlias, KnowledgeEntityType
from app.knowledge.schemas import KnowledgeEntityCreate


class UnknownEntityTypeError(ValueError):
    pass


class DuplicateKnowledgeEntityError(ValueError):
    pass


class DuplicateKnowledgeAliasError(ValueError):
    pass


class KnowledgeEntityService:
    @staticmethod
    def resolve(db: Session, entity_type: str, name_or_alias: str) -> KnowledgeEntity | None:
        normalized = normalize_name(name_or_alias)
        alias = (
            db.query(KnowledgeEntityAlias)
            .filter(
                KnowledgeEntityAlias.entity_type == entity_type,
                KnowledgeEntityAlias.normalized_alias == normalized,
            )
            .first()
        )
        return alias.entity if alias else None

    @classmethod
    def create(cls, db: Session, command: KnowledgeEntityCreate) -> KnowledgeEntity:
        entity_type = db.get(KnowledgeEntityType, command.entity_type)
        if entity_type is None or not entity_type.enabled:
            raise UnknownEntityTypeError(f"Unknown or disabled entity type: {command.entity_type}")
        name_owner = cls.resolve(db, command.entity_type, command.canonical_name)
        if name_owner is not None and not command.allow_name_collision:
            raise DuplicateKnowledgeEntityError("A canonical entity already owns this name or alias")
        if (
            db.query(KnowledgeEntity)
            .filter(
                KnowledgeEntity.entity_type == command.entity_type,
                KnowledgeEntity.language_neutral_id == command.language_neutral_id,
            )
            .first()
            is not None
        ):
            raise DuplicateKnowledgeEntityError("The language-neutral identifier is already registered")

        entity = KnowledgeEntity(
            entity_type=command.entity_type,
            canonical_name=command.canonical_name.strip(),
            slug=(
                f"{slugify(command.canonical_name)}-{command.slug_suffix}"
                if command.allow_name_collision and command.slug_suffix
                else slugify(command.canonical_name)
            ),
            language_neutral_id=command.language_neutral_id,
            status=command.status,
            source_priority=command.source_priority,
            visibility=command.visibility,
            search_weight=command.search_weight,
        )
        db.add(entity)
        db.flush()
        if name_owner is None:
            cls.add_alias(db, entity, command.canonical_name)
        for alias in command.aliases:
            cls.add_alias(db, entity, alias)
        refresh_search_metadata(entity)
        emit_event(
            db,
            KnowledgeEventType.ENTITY_CREATED,
            entity_uuid=entity.uuid,
            payload={"entity_type": entity.entity_type},
        )
        return entity

    @staticmethod
    def add_alias(
        db: Session,
        entity: KnowledgeEntity,
        alias: str,
        *,
        language: str | None = None,
    ) -> KnowledgeEntityAlias:
        display_alias = alias.strip()
        normalized = normalize_name(display_alias)
        if not normalized:
            raise ValueError("Knowledge aliases cannot be empty")
        existing = (
            db.query(KnowledgeEntityAlias)
            .filter(
                KnowledgeEntityAlias.entity_type == entity.entity_type,
                KnowledgeEntityAlias.normalized_alias == normalized,
            )
            .first()
        )
        if existing is not None:
            if existing.entity_uuid == entity.uuid:
                raise DuplicateKnowledgeAliasError("This alias is already registered for the entity")
            raise DuplicateKnowledgeEntityError("This alias already resolves to another canonical entity")
        record = KnowledgeEntityAlias(
            entity=entity,
            entity_type=entity.entity_type,
            alias=display_alias,
            normalized_alias=normalized,
            language=language,
        )
        db.add(record)
        db.flush()
        refresh_search_metadata(entity)
        return record

    @staticmethod
    def update_name(db: Session, entity: KnowledgeEntity, canonical_name: str) -> KnowledgeEntity:
        name = canonical_name.strip()
        if not name:
            raise ValueError("Canonical name cannot be empty")
        entity.canonical_name = name
        entity.slug = slugify(name)
        refresh_search_metadata(entity)
        emit_event(
            db,
            KnowledgeEventType.ENTITY_UPDATED,
            entity_uuid=entity.uuid,
            payload={"fields": ["canonical_name", "slug"]},
        )
        return entity

    @staticmethod
    def record_merge(db: Session, target: KnowledgeEntity, merged_entity_uuid: UUID) -> None:
        emit_event(
            db,
            KnowledgeEventType.KNOWLEDGE_MERGED,
            entity_uuid=target.uuid,
            payload={"merged_entity_uuid": str(merged_entity_uuid)},
        )
