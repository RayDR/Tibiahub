"""Creature identity resolution and Cyclopedia bridge."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.knowledge.adapters.protocol import KnowledgeNormalizationResult
from app.knowledge.dto import CreatureKnowledgeDTO
from app.knowledge.events import KnowledgeEventType, emit_event
from app.knowledge.indexing import normalize_name
from app.knowledge.metadata import refresh_search_metadata
from app.knowledge.models import KnowledgeEntity, KnowledgeEntityAlias, KnowledgeExternalMapping
from app.knowledge.schemas import KnowledgeEntityCreate
from app.knowledge.services.entities import (
    DuplicateKnowledgeAliasError,
    DuplicateKnowledgeEntityError,
    KnowledgeEntityService,
)
from app.knowledge.services.failures import InvalidNormalizationContractError
from app.knowledge.services.item_relationships import link_creature_loot
from app.models import Creature, Loot
from app.services.entity_metadata_service import EntityMetadataService
from app.services.text_utils import normalize_search_text


class CreatureIdentityConflictError(InvalidNormalizationContractError):
    code = "creature_identity_conflict"
    safe_message = "The creature identity conflicts with an existing canonical record."


@dataclass(frozen=True, slots=True)
class CreatureNormalizationApplied:
    status: str
    entity_uuid: UUID
    aliases_created: int
    warnings: int


def _mapped_entity(
    db: Session,
    *,
    provider_code: str,
    external_id: str,
) -> tuple[KnowledgeEntity | None, KnowledgeExternalMapping | None]:
    mapping = (
        db.query(KnowledgeExternalMapping)
        .filter_by(provider_id=provider_code, entity_type_id="creature", external_id=external_id)
        .first()
    )
    return (mapping.entity if mapping else None), mapping


def _assert_boss_compatibility(db: Session, entity: KnowledgeEntity, dto: CreatureKnowledgeDTO) -> None:
    creature = (
        db.query(Creature)
        .filter(
            (Creature.knowledge_entity_id == entity.uuid)
            | (Creature.normalized_name == normalize_search_text(dto.canonical_name))
        )
        .first()
    )
    if creature is not None and bool(creature.is_boss) != dto.is_boss:
        raise CreatureIdentityConflictError()


def _ensure_mapping(
    db: Session,
    *,
    provider_code: str,
    external_id: str,
    entity: KnowledgeEntity,
    metadata: dict,
) -> KnowledgeExternalMapping:
    existing = (
        db.query(KnowledgeExternalMapping)
        .filter_by(provider_id=provider_code, entity_type_id="creature", external_id=external_id)
        .first()
    )
    if existing is not None:
        if existing.entity_uuid != entity.uuid:
            raise CreatureIdentityConflictError()
        existing.provider_metadata = dict(metadata)
        return existing
    mapping = KnowledgeExternalMapping(
        provider_id=provider_code,
        entity_type_id="creature",
        external_id=external_id,
        entity_uuid=entity.uuid,
        provider_metadata=dict(metadata),
    )
    try:
        with db.begin_nested():
            db.add(mapping)
            db.flush()
    except IntegrityError:
        existing = (
            db.query(KnowledgeExternalMapping)
            .filter_by(provider_id=provider_code, entity_type_id="creature", external_id=external_id)
            .one_or_none()
        )
        if existing is None or existing.entity_uuid != entity.uuid:
            raise CreatureIdentityConflictError()
        return existing
    return mapping


def _resolve_or_create_entity(
    db: Session,
    result: KnowledgeNormalizationResult,
    dto: CreatureKnowledgeDTO,
) -> tuple[KnowledgeEntity, bool]:
    if not result.provider_code or not result.external_id or result.candidate is None:
        raise InvalidNormalizationContractError()
    entity, _mapping = _mapped_entity(
        db,
        provider_code=result.provider_code,
        external_id=result.external_id,
    )
    if entity is not None:
        _assert_boss_compatibility(db, entity, dto)
        return entity, False

    entity = KnowledgeEntityService.resolve(db, "creature", dto.canonical_name)
    if entity is not None:
        _assert_boss_compatibility(db, entity, dto)
        return entity, False

    candidate = result.candidate
    entity = KnowledgeEntityService.create(
        db,
        KnowledgeEntityCreate(
            entity_type="creature",
            canonical_name=candidate.canonical_name,
            language_neutral_id=candidate.language_neutral_id,
            aliases=list(candidate.aliases),
            status=candidate.status,
            source_priority=candidate.source_priority,
            visibility=candidate.visibility,
            search_weight=candidate.search_weight,
        ),
    )
    return entity, True


def _update_entity(
    db: Session,
    entity: KnowledgeEntity,
    result: KnowledgeNormalizationResult,
) -> tuple[bool, int, int]:
    candidate = result.candidate
    if candidate is None:
        raise InvalidNormalizationContractError()
    changed = False
    warnings = len(result.warnings)
    if candidate.source_priority <= entity.source_priority:
        for field, value in (
            ("canonical_name", candidate.canonical_name),
            ("slug", normalize_search_text(candidate.canonical_name).replace(" ", "-")),
            ("status", candidate.status),
            ("source_priority", candidate.source_priority),
            ("visibility", candidate.visibility),
            ("search_weight", candidate.search_weight),
        ):
            if value not in (None, "") and getattr(entity, field) != value:
                setattr(entity, field, value)
                changed = True
    existing_aliases = {
        alias.normalized_alias
        for alias in db.query(KnowledgeEntityAlias).filter(KnowledgeEntityAlias.entity_uuid == entity.uuid).all()
    }
    aliases_created = 0
    for alias in candidate.aliases:
        normalized = normalize_name(alias)
        if not normalized or normalized in existing_aliases:
            continue
        try:
            KnowledgeEntityService.add_alias(db, entity, alias)
            existing_aliases.add(normalized)
            aliases_created += 1
        except (DuplicateKnowledgeAliasError, DuplicateKnowledgeEntityError):
            warnings += 1
    if aliases_created:
        changed = True
    refresh_search_metadata(entity)
    return changed, aliases_created, warnings


def _bridge_creature(db: Session, entity: KnowledgeEntity, dto: CreatureKnowledgeDTO) -> tuple[Creature, bool]:
    creature = db.query(Creature).filter(Creature.knowledge_entity_id == entity.uuid).first()
    if creature is None:
        creature = (
            db.query(Creature)
            .filter(
                Creature.source_name == "tibiawiki",
                Creature.external_id == dto.external_id,
            )
            .first()
        )
    if creature is None:
        creature = db.query(Creature).filter(Creature.normalized_name == normalize_search_text(dto.canonical_name)).first()
    if creature is not None and creature.knowledge_entity_id not in (None, entity.uuid):
        raise CreatureIdentityConflictError()
    if creature is not None and bool(creature.is_boss) != dto.is_boss:
        raise CreatureIdentityConflictError()

    created = creature is None
    if creature is None:
        creature = Creature(
            knowledge_entity_id=entity.uuid,
            name=dto.canonical_name,
            normalized_name=normalize_search_text(dto.canonical_name),
            slug=dto.slug,
            external_id=dto.external_id,
            source_name="tibiawiki",
            hitpoints=dto.hitpoints or 0,
            experience=dto.experience or 0,
            is_boss=dto.is_boss,
            data_version=1,
            protected_fields=[],
        )
        db.add(creature)
        db.flush()

    protected = set(creature.protected_fields or [])
    canonical_changed = False

    def assign(
        field: str,
        value,
        *,
        provided: str | None = None,
        preserve_existing_on_partial: bool = True,
    ) -> None:
        nonlocal canonical_changed
        if field in protected or value in (None, "", []):
            return
        if provided is not None and provided not in dto.provided_fields:
            return
        if (
            preserve_existing_on_partial
            and dto.is_partial
            and not created
            and getattr(creature, field) not in (None, "", [])
        ):
            return
        if getattr(creature, field) != value:
            setattr(creature, field, value)
            canonical_changed = True

    if creature.knowledge_entity_id is None:
        creature.knowledge_entity_id = entity.uuid
        canonical_changed = True
    assign("name", dto.canonical_name)
    assign("normalized_name", normalize_search_text(dto.canonical_name))
    assign("slug", dto.slug)
    assign(
        "external_id",
        dto.external_id,
        preserve_existing_on_partial=False,
    )
    assign(
        "source_name",
        "tibiawiki",
        preserve_existing_on_partial=False,
    )
    assign("source_url", dto.source_reference, provided="source_reference")
    assign("article", dto.article, provided="article")
    assign("plural", dto.plural, provided="plural")
    assign("hitpoints", dto.hitpoints, provided="hitpoints")
    assign("experience", dto.experience, provided="experience")
    assign("armor", dto.armor, provided="armor")
    assign("speed", dto.speed, provided="speed")
    assign("max_damage", dto.max_damage, provided="max_damage")
    assign("summon_cost", dto.summon_cost, provided="summon_cost")
    assign("convince_cost", dto.convince_cost, provided="convince_cost")
    assign("difficulty", dto.difficulty, provided="difficulty")
    assign("occurrence", dto.occurrence, provided="occurrence")
    assign("is_boss", dto.is_boss, provided="is_boss")
    assign("description", dto.description, provided="description")
    assign("behavior", dto.behavior, provided="behavior")
    assign("bestiary_class", dto.bestiary_class, provided="bestiary_class")
    assign("bestiary_level", dto.bestiary_level, provided="bestiary_level")
    assign("charm_points", dto.charm_points, provided="charm_points")
    assign("classification", dto.classification, provided="classification")
    assign("creature_class", dto.race, provided="race")
    assign("primary_type", dto.primary_type, provided="primary_type")
    if not creature.image_locked:
        assign("image_url", dto.image_reference, provided="image_reference")
    assign("locations", list(dto.locations), provided="locations")
    assign("related_tasks", list(dto.task_references), provided="task_references")

    data_sources = list(creature.data_sources or [])
    if "tibiawiki" not in data_sources:
        data_sources.append("tibiawiki")
        creature.data_sources = data_sources
        canonical_changed = True
    creature.missing_fields = list(dto.provider_metadata.get("missing_fields") or [])

    existing_loot = {loot.normalized_name: loot for loot in creature.loot_items}
    if dto.loot and "loot" not in protected:
        for item in dto.loot:
            normalized = normalize_search_text(item.item_name)
            loot = existing_loot.get(normalized)
            if loot is None:
                loot = Loot(creature_id=creature.id, item_name=item.item_name, normalized_name=normalized)
                db.add(loot)
                existing_loot[normalized] = loot
                canonical_changed = True
            for field, value in (
                ("item_name", item.item_name),
                ("external_id", item.external_id),
                ("rarity", item.rarity),
                ("percentage", item.percentage),
                ("min_amount", item.min_amount),
                ("max_amount", item.max_amount),
                ("item_image_url", item.image_reference),
                ("source_url", item.source_reference),
            ):
                if value not in (None, "") and getattr(loot, field) != value:
                    setattr(loot, field, value)
                    canonical_changed = True

    if not created and canonical_changed:
        creature.data_version = max(1, creature.data_version or 1) + 1
    creature.last_synced_at = datetime.now(UTC)
    EntityMetadataService.update_sync_timestamp(
        db,
        entity_type="creature",
        entity_key=creature.normalized_name,
        display_name=creature.name,
        entity_id=creature.id,
    )
    db.flush()
    return creature, created or canonical_changed


class CreatureKnowledgeNormalizationService:
    @staticmethod
    def apply(db: Session, result: KnowledgeNormalizationResult) -> CreatureNormalizationApplied:
        if result.canonical_data is None:
            raise InvalidNormalizationContractError()
        dto = CreatureKnowledgeDTO.from_canonical_data(result.canonical_data)
        entity, created = _resolve_or_create_entity(db, result, dto)
        _ensure_mapping(
            db,
            provider_code=result.provider_code or "",
            external_id=result.external_id or "",
            entity=entity,
            metadata=dto.provider_metadata,
        )
        entity_changed, aliases_created, warnings = _update_entity(db, entity, result)
        _creature, creature_changed = _bridge_creature(db, entity, dto)
        _relationships_created, unresolved = link_creature_loot(
            db,
            creature_entity_uuid=entity.uuid,
            creature_name=dto.canonical_name,
            loot_references=dto.loot,
            provider_id=result.provider_code or "tibiawiki",
            source_document_id=f"creature:{dto.external_id}",
        )
        warnings += unresolved
        changed = entity_changed or creature_changed
        if changed and not created:
            emit_event(
                db,
                KnowledgeEventType.ENTITY_UPDATED,
                entity_uuid=entity.uuid,
                payload={"source": "tibiawiki_creature_normalization"},
            )
        return CreatureNormalizationApplied(
            "created" if created else "updated" if changed else "unchanged",
            entity.uuid,
            aliases_created,
            warnings,
        )
