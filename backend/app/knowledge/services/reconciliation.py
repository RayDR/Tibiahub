"""Exact-only, idempotent reconciliation for existing knowledge facts."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from uuid import UUID

from sqlalchemy.orm import Session, selectinload

from app.knowledge.indexing import normalize_name
from app.knowledge.models import (
    KnowledgeDocument,
    KnowledgeEntity,
    KnowledgeExternalMapping,
    KnowledgeRelationship,
    SpatialRoute,
)
from app.knowledge.services.graph import KnowledgeGraphService, RelationshipInput
from app.models import Creature


PLACE_ENTITY_TYPES = frozenset({"area", "location", "town"})


@dataclass(frozen=True, slots=True)
class ExactReferenceReport:
    considered: int = 0
    no_candidate: int = 0
    uniquely_resolvable: int = 0
    ambiguous_candidates: int = 0
    self_references_skipped: int = 0
    resolved: int = 0

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ProvenanceRepairReport:
    relationships_considered: int = 0
    relationships_repairable: int = 0
    relationships_repaired: int = 0
    relationships_unrepairable: int = 0
    spatial_routes_considered: int = 0
    spatial_routes_repairable: int = 0
    spatial_routes_repaired: int = 0

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


def _entity_name_index(
    db: Session,
) -> tuple[dict[tuple[str, str], dict[UUID, KnowledgeEntity]], set[UUID]]:
    index: dict[tuple[str, str], dict[UUID, KnowledgeEntity]] = {}
    entities = (
        db.query(KnowledgeEntity)
        .options(selectinload(KnowledgeEntity.aliases))
        .all()
    )
    for entity in entities:
        for value in (entity.canonical_name, *(alias.alias for alias in entity.aliases)):
            normalized = normalize_name(value)
            if normalized:
                index.setdefault((entity.entity_type, normalized), {})[entity.uuid] = entity
    boss_ids = {
        entity_id
        for (entity_id,) in db.query(Creature.knowledge_entity_id).filter(
            Creature.knowledge_entity_id.isnot(None),
            Creature.is_boss.is_(True),
        )
    }
    return index, boss_ids


def _candidates(
    relationship: KnowledgeRelationship,
    index: dict[tuple[str, str], dict[UUID, KnowledgeEntity]],
    boss_ids: set[UUID],
) -> list[KnowledgeEntity]:
    normalized = relationship.normalized_unresolved_name or normalize_name(
        relationship.unresolved_name or ""
    )
    if not normalized:
        return []
    target_type = relationship.target_entity_type_id or ""
    matches: dict[UUID, KnowledgeEntity] = {}
    candidate_types = PLACE_ENTITY_TYPES if target_type in PLACE_ENTITY_TYPES else {target_type}
    for entity_type in candidate_types:
        matches.update(index.get((entity_type, normalized), {}))
    if target_type == "boss":
        matches.update(
            {
                entity_id: entity
                for entity_id, entity in index.get(("creature", normalized), {}).items()
                if entity_id in boss_ids
            }
        )
    return list(matches.values())


def reconcile_exact_references(db: Session, *, apply: bool) -> ExactReferenceReport:
    """Resolve only current, non-manual facts with one exact local target."""
    index, boss_ids = _entity_name_index(db)
    rows = (
        db.query(KnowledgeRelationship)
        .filter(
            KnowledgeRelationship.is_current.is_(True),
            KnowledgeRelationship.resolution_state.in_(("unresolved", "ambiguous")),
            KnowledgeRelationship.manual_override.is_(False),
        )
        .order_by(KnowledgeRelationship.id)
        .all()
    )
    counts = {
        "considered": len(rows),
        "no_candidate": 0,
        "uniquely_resolvable": 0,
        "ambiguous_candidates": 0,
        "self_references_skipped": 0,
        "resolved": 0,
    }
    for row in rows:
        candidates = _candidates(row, index, boss_ids)
        if not candidates:
            counts["no_candidate"] += 1
            continue
        if len(candidates) > 1:
            counts["ambiguous_candidates"] += 1
            continue
        target = candidates[0]
        if target.uuid == row.source_entity_id:
            counts["self_references_skipped"] += 1
            continue
        counts["uniquely_resolvable"] += 1
        if not apply:
            continue
        document_ref = (
            row.source_document.provider_document_id
            if row.source_document is not None
            else (row.source_context or {}).get("source_document_ref")
        )
        mutation = KnowledgeGraphService.upsert(
            db,
            RelationshipInput(
                source_entity_id=row.source_entity_id,
                source_scope=row.source_scope,
                relationship_type=row.relationship_type_code,
                target_entity_id=target.uuid,
                unresolved_name=row.unresolved_name,
                resolution_state="resolved",
                confidence=row.confidence,
                source_provider_id=row.source_provider_id,
                source_document_ref=document_ref,
                source_job_id=row.source_job_id,
                source_context={
                    **dict(row.source_context or {}),
                    "resolution_policy": "exact_name_or_alias_only",
                    "resolved_from": str(row.id),
                },
            ),
        )
        if row.is_current:
            KnowledgeGraphService.supersede(db, row, mutation.relationship)
        counts["resolved"] += 1
    if apply:
        db.flush()
    return ExactReferenceReport(**counts)


def repair_document_provenance(db: Session, *, apply: bool) -> ProvenanceRepairReport:
    """Attach existing raw documents where provider identity proves the link."""
    document_cache: dict[tuple[str, str], KnowledgeDocument | None] = {}

    def latest_document(provider: str, reference: str) -> KnowledgeDocument | None:
        key = (provider, reference)
        if key not in document_cache:
            document_cache[key] = (
                db.query(KnowledgeDocument)
                .filter_by(provider_id=provider, provider_document_id=reference)
                .order_by(KnowledgeDocument.retrieved_at.desc())
                .first()
            )
        return document_cache[key]

    route_mappings = {
        (mapping.provider_id, mapping.entity_uuid): mapping.external_id
        for mapping in db.query(KnowledgeExternalMapping).filter(
            KnowledgeExternalMapping.entity_type_id == "route"
        )
    }
    relationship_rows = (
        db.query(KnowledgeRelationship)
        .options(selectinload(KnowledgeRelationship.source_entity))
        .filter(KnowledgeRelationship.source_document_id.is_(None))
        .all()
    )
    relationship_counts = {
        "relationships_considered": 0,
        "relationships_repairable": 0,
        "relationships_repaired": 0,
        "relationships_unrepairable": 0,
    }
    for row in relationship_rows:
        reference = (row.source_context or {}).get("source_document_ref")
        if not reference:
            continue
        relationship_counts["relationships_considered"] += 1
        provider = row.source_provider_id or ""
        document = latest_document(provider, str(reference))
        if document is None and row.source_entity.entity_type == "route":
            external_id = route_mappings.get((provider, row.source_entity_id))
            if external_id:
                document = latest_document(provider, f"route:{external_id}")
        if document is None or document.entity_uuid not in (None, row.source_entity_id):
            relationship_counts["relationships_unrepairable"] += 1
            continue
        relationship_counts["relationships_repairable"] += 1
        if apply:
            context = dict(row.source_context or {})
            if reference != document.provider_document_id:
                context.setdefault("source_reference", reference)
                context["source_document_ref"] = document.provider_document_id
                row.source_context = context
            row.source_document_id = document.uuid
            relationship_counts["relationships_repaired"] += 1

    route_counts = {
        "spatial_routes_considered": 0,
        "spatial_routes_repairable": 0,
        "spatial_routes_repaired": 0,
    }
    routes = db.query(SpatialRoute).filter(SpatialRoute.source_document_id.is_(None)).all()
    for route in routes:
        route_counts["spatial_routes_considered"] += 1
        document = latest_document(
            route.source_provider_id or "", f"route:{route.external_id}"
        )
        if document is None or document.entity_uuid not in (None, route.knowledge_entity_id):
            continue
        route_counts["spatial_routes_repairable"] += 1
        if apply:
            route.source_document_id = document.uuid
            route_counts["spatial_routes_repaired"] += 1
    if apply:
        db.flush()
    return ProvenanceRepairReport(**relationship_counts, **route_counts)
