"""Item identity resolution, canonical normalization, and current Item bridge."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.knowledge.adapters.protocol import KnowledgeNormalizationResult
from app.knowledge.dto import ItemKnowledgeDTO
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
from app.knowledge.services.item_relationships import exact_entity_candidates, link_item_drops
from app.models.external_data import Item
from app.services.entity_metadata_service import EntityMetadataService
from app.services.text_utils import normalize_search_text


class ItemIdentityConflictError(InvalidNormalizationContractError):
    code = "item_identity_conflict"
    safe_message = "The item identity conflicts with an existing canonical record."


@dataclass(frozen=True, slots=True)
class ItemNormalizationApplied:
    status: str
    entity_uuid: UUID
    aliases_created: int
    warnings: int


def _mapped_entity(db: Session, provider_code: str, external_id: str) -> KnowledgeEntity | None:
    mapping = (
        db.query(KnowledgeExternalMapping)
        .filter_by(provider_id=provider_code, entity_type_id="item", external_id=external_id)
        .first()
    )
    return mapping.entity if mapping else None


def _entity_provider_mapping(db: Session, provider_code: str, entity_uuid: UUID) -> KnowledgeExternalMapping | None:
    return (
        db.query(KnowledgeExternalMapping)
        .filter_by(provider_id=provider_code, entity_type_id="item", entity_uuid=entity_uuid)
        .first()
    )


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
        .filter_by(provider_id=provider_code, entity_type_id="item", external_id=external_id)
        .first()
    )
    if existing is not None:
        if existing.entity_uuid != entity.uuid:
            raise ItemIdentityConflictError()
        existing.provider_metadata = dict(metadata)
        return existing
    mapping = KnowledgeExternalMapping(
        provider_id=provider_code,
        entity_type_id="item",
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
            .filter_by(provider_id=provider_code, entity_type_id="item", external_id=external_id)
            .one_or_none()
        )
        if existing is None or existing.entity_uuid != entity.uuid:
            raise ItemIdentityConflictError()
        return existing
    return mapping


def _resolve_or_create_entity(
    db: Session,
    result: KnowledgeNormalizationResult,
    dto: ItemKnowledgeDTO,
) -> tuple[KnowledgeEntity, bool]:
    if not result.provider_code or not result.external_id or result.candidate is None:
        raise InvalidNormalizationContractError()
    mapped = _mapped_entity(db, result.provider_code, result.external_id)
    if mapped is not None:
        return mapped, False

    matches = exact_entity_candidates(db, "item", dto.canonical_name)
    allow_variant = False
    if len(matches) > 1:
        unmapped = [
            match
            for match in matches
            if _entity_provider_mapping(db, result.provider_code, match.uuid) is None
        ]
        if unmapped:
            raise ItemIdentityConflictError()
        allow_variant = True
    if len(matches) == 1:
        provider_mapping = _entity_provider_mapping(db, result.provider_code, matches[0].uuid)
        if provider_mapping is None or provider_mapping.external_id == result.external_id:
            return matches[0], False
        allow_variant = True

    candidate = result.candidate
    entity = KnowledgeEntityService.create(
        db,
        KnowledgeEntityCreate(
            entity_type="item",
            canonical_name=candidate.canonical_name,
            language_neutral_id=candidate.language_neutral_id,
            aliases=list(candidate.aliases),
            status=candidate.status,
            source_priority=candidate.source_priority,
            visibility=candidate.visibility,
            search_weight=candidate.search_weight,
            allow_name_collision=allow_variant,
            slug_suffix=result.external_id if allow_variant else None,
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
    changed = changed or aliases_created > 0
    refresh_search_metadata(entity)
    return changed, aliases_created, warnings


def _bridge_item(db: Session, entity: KnowledgeEntity, dto: ItemKnowledgeDTO) -> tuple[Item, bool]:
    item = db.query(Item).filter(Item.knowledge_entity_id == entity.uuid).first()
    if item is None:
        item = (
            db.query(Item)
            .filter(Item.source_name == "tibiawiki", Item.external_id == dto.external_id)
            .first()
        )
    if item is None and dto.game_item_id is not None:
        item = db.query(Item).filter(Item.item_id == dto.game_item_id).first()
    if item is None:
        legacy = (
            db.query(Item)
            .filter(
                Item.knowledge_entity_id.is_(None),
                Item.normalized_name == normalize_search_text(dto.canonical_name),
            )
            .all()
        )
        if not legacy:
            legacy = [
                candidate
                for candidate in db.query(Item).filter(Item.knowledge_entity_id.is_(None)).all()
                if normalize_search_text(candidate.name) == normalize_search_text(dto.canonical_name)
            ]
        if len(legacy) > 1:
            raise ItemIdentityConflictError()
        item = legacy[0] if legacy else None
    if item is not None and item.knowledge_entity_id not in (None, entity.uuid):
        raise ItemIdentityConflictError()

    created = item is None
    if item is None:
        item = Item(
            name=dto.canonical_name,
            normalized_name=normalize_search_text(dto.canonical_name),
            slug=entity.slug,
            external_id=dto.external_id,
            source_name="tibiawiki",
            knowledge_entity_id=entity.uuid,
            data_version=1,
            protected_fields=[],
        )
        db.add(item)
        db.flush()

    protected = set(item.protected_fields or [])
    canonical_changed = False

    def assign(
        field: str,
        value,
        *,
        supplied: str | None = None,
        clear_if_supplied: bool = False,
    ) -> None:
        nonlocal canonical_changed
        if field in protected:
            return
        if supplied is not None and supplied not in dto.supplied_fields:
            return
        if (
            value in (None, "", [], {})
            and not (clear_if_supplied and supplied is not None)
        ):
            return
        if dto.is_partial and not created and getattr(item, field) not in (None, "", [], {}):
            return
        if getattr(item, field) != value:
            setattr(item, field, value)
            canonical_changed = True

    if item.knowledge_entity_id is None:
        item.knowledge_entity_id = entity.uuid
        canonical_changed = True
    assign("name", dto.canonical_name)
    assign("normalized_name", normalize_search_text(dto.canonical_name))
    assign("slug", entity.slug)
    assign("external_id", dto.external_id)
    assign("source_name", "tibiawiki")
    assign("source_url", dto.source_reference, supplied="source_reference")
    assign("image_url", dto.image_reference, supplied="image_reference")
    assign("item_id", dto.game_item_id, supplied="game_item_id")
    assign("description", dto.description, supplied="description")
    assign("notes", dto.notes, supplied="notes")
    assign("type", dto.item_type, supplied="item_type")
    assign("item_class", dto.item_class, supplied="item_class")
    assign("category", dto.category, supplied="category")
    assign("weight", dto.weight, supplied="weight")
    assign("value", dto.value, supplied="value")
    assign("attack", dto.attack, supplied="attack")
    assign("defense", dto.defense, supplied="defense")
    assign("armor", dto.armor, supplied="armor")
    assign("range", dto.range, supplied="range")
    assign("level_required", dto.level_requirement, supplied="level_requirement")
    assign(
        "vocation_requirements",
        list(dto.vocation_requirements),
        supplied="vocation_requirements",
        clear_if_supplied=True,
    )
    assign(
        "vocation_required",
        ", ".join(dto.vocation_requirements) or None,
        supplied="vocation_requirements",
        clear_if_supplied=True,
    )
    assign("slots", list(dto.slots), supplied="slots", clear_if_supplied=True)
    assign("imbuement_slots", dto.imbuement_slots, supplied="imbuement_slots")
    assign("attributes", dict(dto.attributes), supplied="attributes", clear_if_supplied=True)
    assign("resistances", dict(dto.resistances), supplied="resistances", clear_if_supplied=True)
    assign("bonuses", dict(dto.bonuses), supplied="bonuses", clear_if_supplied=True)
    assign(
        "buy_from",
        [asdict(reference) for reference in dto.buy_from],
        supplied="buy_from",
        clear_if_supplied=True,
    )
    assign(
        "sell_to",
        [asdict(reference) for reference in dto.sell_to],
        supplied="sell_to",
        clear_if_supplied=True,
    )
    assign(
        "rewards_from",
        list(dto.rewards_from),
        supplied="rewards_from",
        clear_if_supplied=True,
    )
    assign(
        "required_for",
        list(dto.required_for),
        supplied="required_for",
        clear_if_supplied=True,
    )
    assign("tradeable", dto.tradeable, supplied="tradeable")
    assign("stackable", dto.stackable, supplied="stackable")

    if not created and canonical_changed:
        item.data_version = max(1, item.data_version or 1) + 1
    item.last_synced_at = datetime.now(UTC)
    EntityMetadataService.update_sync_timestamp(
        db,
        entity_type="item",
        entity_key=item.normalized_name,
        display_name=item.name,
        entity_id=item.id,
    )
    db.flush()
    return item, created or canonical_changed


class ItemKnowledgeNormalizationService:
    @staticmethod
    def apply(db: Session, result: KnowledgeNormalizationResult) -> ItemNormalizationApplied:
        if result.canonical_data is None:
            raise InvalidNormalizationContractError()
        dto = ItemKnowledgeDTO.from_canonical_data(result.canonical_data)
        entity, created = _resolve_or_create_entity(db, result, dto)
        _ensure_mapping(
            db,
            provider_code=result.provider_code or "",
            external_id=result.external_id or "",
            entity=entity,
            metadata=dto.provider_metadata,
        )
        entity_changed, aliases_created, warnings = _update_entity(db, entity, result)
        _item, item_changed = _bridge_item(db, entity, dto)
        _relationships_created, unresolved = link_item_drops(
            db,
            item_entity_uuid=entity.uuid,
            item_name=dto.canonical_name,
            dropped_by=dto.dropped_by,
            provider_id=result.provider_code or "tibiawiki",
            source_document_id=f"item:{dto.external_id}",
        )
        warnings += unresolved
        changed = entity_changed or item_changed
        if changed and not created:
            emit_event(
                db,
                KnowledgeEventType.ENTITY_UPDATED,
                entity_uuid=entity.uuid,
                payload={"source": "tibiawiki_item_normalization"},
            )
        return ItemNormalizationApplied(
            "created" if created else "updated" if changed else "unchanged",
            entity.uuid,
            aliases_created,
            warnings,
        )
