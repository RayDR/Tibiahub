"""Provider-neutral Knowledge Graph mutations, traversal, and consolidation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.knowledge.indexing import normalize_name
from app.knowledge.models import KnowledgeDocument, KnowledgeEntity, KnowledgeRelationship
from app.knowledge.models.graph import RELATIONSHIP_CONFIDENCES, RELATIONSHIP_STATES
from app.knowledge.registry.relationship_types import RelationshipTypeRegistry


CONFIDENCE_RANK = {"unknown": 0, "low": 1, "medium": 2, "high": 3, "verified": 4}


@dataclass(frozen=True, slots=True)
class RelationshipInput:
    source_entity_id: UUID
    relationship_type: str
    target_entity_id: UUID | None = None
    target_entity_type: str | None = None
    unresolved_name: str | None = None
    resolution_state: str = "resolved"
    confidence: str = "high"
    source_provider_id: str | None = None
    source_document_ref: str | None = None
    source_job_id: UUID | None = None
    source_scope: str = "entity"
    source_context: dict = field(default_factory=dict)
    manual_override: bool = False
    verified_by_id: int | None = None


@dataclass(frozen=True, slots=True)
class RelationshipMutation:
    relationship: KnowledgeRelationship
    created: bool
    changed: bool


@dataclass(frozen=True, slots=True)
class ConsolidatedRelationship:
    relationship_id: UUID
    source_entity_id: UUID
    source_name: str
    source_type: str
    relationship_type: str
    display_translation_key: str
    target_entity_id: UUID | None
    target_name: str
    target_type: str
    target_slug: str | None
    resolution_state: str
    confidence: str
    contributing_providers: tuple[str, ...]
    manual_verified: bool
    freshness: datetime
    source_scope: str
    provenance_count: int


class KnowledgeGraphService:
    @staticmethod
    def _type(db: Session, code: str):
        row = RelationshipTypeRegistry.get(db, code)
        if row is None:
            RelationshipTypeRegistry.register_initial(db)
            row = RelationshipTypeRegistry.get(db, code)
        if row is None:
            raise ValueError("Unsupported relationship type")
        return row

    @staticmethod
    def _document(db: Session, provider_id: str | None, reference: str | None) -> KnowledgeDocument | None:
        if not provider_id or not reference:
            return None
        return db.query(KnowledgeDocument).filter_by(
            provider_id=provider_id, provider_document_id=reference,
        ).order_by(KnowledgeDocument.retrieved_at.desc()).first()

    @classmethod
    def upsert(cls, db: Session, value: RelationshipInput) -> RelationshipMutation:
        if value.resolution_state not in RELATIONSHIP_STATES or value.confidence not in RELATIONSHIP_CONFIDENCES:
            raise ValueError("Invalid relationship state or confidence")
        source = db.get(KnowledgeEntity, value.source_entity_id)
        if source is None:
            raise ValueError("Relationship source entity does not exist")
        target = db.get(KnowledgeEntity, value.target_entity_id) if value.target_entity_id else None
        target_type = target.entity_type if target else value.target_entity_type
        if not target_type:
            raise ValueError("Relationship target entity type is required")
        cls._type(db, value.relationship_type)
        RelationshipTypeRegistry.validate(db, value.relationship_type, source.entity_type, target_type)
        if target and target.uuid == source.uuid:
            raise ValueError("Self relationships are not supported")
        if value.resolution_state == "resolved" and target is None:
            raise ValueError("Resolved relationships require an existing target")
        unresolved_name = (value.unresolved_name or "").strip() or None
        if value.resolution_state in {"unresolved", "ambiguous"} and unresolved_name is None:
            raise ValueError("Unresolved relationships require a name")
        normalized = normalize_name(unresolved_name or "") or None
        target_identity = f"entity:{target.uuid}" if target else f"name:{target_type}:{normalized}"
        provenance = (
            f"manual:{value.verified_by_id or 'system'}"
            if value.manual_override else f"provider:{value.source_provider_id or 'local'}"
        )
        # Resolve document provenance before adding a partially populated row.
        # Queries trigger SQLAlchemy autoflush, and the graph constraints require
        # unresolved names and states to be assigned atomically.
        document = cls._document(db, value.source_provider_id, value.source_document_ref)
        row = db.query(KnowledgeRelationship).filter_by(
            source_entity_id=source.uuid,
            source_scope=value.source_scope,
            relationship_type_code=value.relationship_type,
            target_identity=target_identity,
            provenance_key=provenance,
            is_current=True,
        ).first()
        created = row is None
        if row is None:
            row = KnowledgeRelationship(
                source_entity_id=source.uuid,
                source_scope=value.source_scope,
                relationship_type_code=value.relationship_type,
                target_identity=target_identity,
                provenance_key=provenance,
            )
            db.add(row)
        document_job_id = None
        if document is not None and not value.source_job_id:
            raw_job_id = (document.document_metadata or {}).get("knowledge_job_id")
            try:
                document_job_id = UUID(str(raw_job_id)) if raw_job_id else None
            except (TypeError, ValueError):
                document_job_id = None
        context = dict(value.source_context)
        if value.source_document_ref:
            context.setdefault("source_document_ref", value.source_document_ref)
        changed = created
        assignments = {
            "target_entity_id": target.uuid if target else None,
            "target_entity_type_id": target_type,
            "unresolved_name": None if target else unresolved_name,
            "normalized_unresolved_name": None if target else normalized,
            "resolution_state": value.resolution_state,
            "confidence": value.confidence,
            "source_provider_id": value.source_provider_id,
            "source_document_id": document.uuid if document else None,
            "source_job_id": value.source_job_id or document_job_id,
            "source_context": context,
            "manual_override": value.manual_override,
            "verified_by_id": value.verified_by_id,
            "verified_at": datetime.now(UTC) if value.confidence == "verified" else row.verified_at,
        }
        for field_name, field_value in assignments.items():
            if getattr(row, field_name) != field_value:
                setattr(row, field_name, field_value)
                changed = True
        db.flush()

        # A successful exact resolution supersedes the same provider's prior
        # exact name/alias facts without affecting manual or other-provider
        # provenance. Callers that already know a target often omit
        # ``unresolved_name``; include the target's canonical names so those
        # resolved upserts still retire the stale name-keyed fact.
        if target:
            resolved_names = {
                normalized_name
                for candidate_name in (
                    unresolved_name,
                    target.canonical_name,
                    *(alias.alias for alias in target.aliases),
                )
                if (normalized_name := normalize_name(candidate_name or ""))
            }
            candidates = db.query(KnowledgeRelationship).filter_by(
                source_entity_id=source.uuid,
                source_scope=value.source_scope,
                relationship_type_code=value.relationship_type,
                provenance_key=provenance,
                is_current=True,
            ).filter(
                KnowledgeRelationship.resolution_state.in_(("unresolved", "ambiguous")),
                KnowledgeRelationship.normalized_unresolved_name.in_(resolved_names),
            ).all() if resolved_names else []
            for old in candidates:
                if old.id != row.id and not old.manual_override:
                    cls.supersede(db, old, row)
        return RelationshipMutation(row, created, changed)

    @classmethod
    def batch_upsert(cls, db: Session, values: list[RelationshipInput]) -> list[RelationshipMutation]:
        return [cls.upsert(db, value) for value in values]

    @staticmethod
    def supersede(db: Session, old: KnowledgeRelationship, replacement: KnowledgeRelationship | None = None) -> None:
        if not old.is_current:
            return
        old.is_current = False
        old.resolution_state = "superseded"
        old.valid_until = datetime.now(UTC)
        old.superseded_by_id = replacement.id if replacement else None
        db.flush()

    @classmethod
    def resolve_reference(
        cls, db: Session, relationship: KnowledgeRelationship, target_entity_id: UUID,
        *, admin_id: int, reason: str,
    ) -> KnowledgeRelationship:
        if relationship.resolution_state not in {"unresolved", "ambiguous"} or not relationship.is_current:
            raise ValueError("Only current unresolved or ambiguous references can be resolved")
        target = db.get(KnowledgeEntity, target_entity_id)
        if target is None:
            raise ValueError("Resolution target does not exist")
        result = cls.upsert(db, RelationshipInput(
            source_entity_id=relationship.source_entity_id,
            source_scope=relationship.source_scope,
            relationship_type=relationship.relationship_type_code,
            target_entity_id=target.uuid,
            unresolved_name=relationship.unresolved_name,
            resolution_state="resolved",
            confidence="verified",
            source_context={"reason": reason, "resolved_from": str(relationship.id)},
            manual_override=True,
            verified_by_id=admin_id,
        ))
        cls.supersede(db, relationship, result.relationship)
        return result.relationship

    @staticmethod
    def reject(db: Session, relationship: KnowledgeRelationship, *, admin_id: int, reason: str) -> None:
        if not relationship.is_current:
            raise ValueError("Relationship is not current")
        relationship.resolution_state = "rejected"
        relationship.rejection_reason = reason
        relationship.manual_override = True
        relationship.verified_by_id = admin_id
        relationship.verified_at = datetime.now(UTC)
        relationship.valid_until = datetime.now(UTC)
        relationship.is_current = False
        db.flush()

    @staticmethod
    def verify(db: Session, relationship: KnowledgeRelationship, *, admin_id: int, reason: str) -> None:
        if not relationship.is_current or relationship.resolution_state != "resolved":
            raise ValueError("Only current resolved relationships can be verified")
        relationship.manual_override = True
        relationship.confidence = "verified"
        relationship.verified_by_id = admin_id
        relationship.verified_at = datetime.now(UTC)
        relationship.source_context = {**dict(relationship.source_context or {}), "verification_reason": reason}
        db.flush()

    @classmethod
    def reconcile_provider(
        cls, db: Session, *, source_entity_id: UUID, source_scope: str,
        provider_id: str, relationship_types: set[str], current_ids: set[UUID],
    ) -> int:
        rows = db.query(KnowledgeRelationship).filter(
            KnowledgeRelationship.source_entity_id == source_entity_id,
            KnowledgeRelationship.source_scope == source_scope,
            KnowledgeRelationship.source_provider_id == provider_id,
            KnowledgeRelationship.relationship_type_code.in_(relationship_types),
            KnowledgeRelationship.is_current.is_(True),
            KnowledgeRelationship.manual_override.is_(False),
        ).all()
        superseded = 0
        for row in rows:
            if row.id not in current_ids:
                cls.supersede(db, row)
                superseded += 1
        return superseded

    @staticmethod
    def _consolidate(rows: list[tuple[KnowledgeRelationship, str]]) -> list[ConsolidatedRelationship]:
        groups: dict[tuple, list[tuple[KnowledgeRelationship, str]]] = {}
        for row, exposed_type in rows:
            logical = (row.source_scope, exposed_type, row.target_identity)
            groups.setdefault(logical, []).append((row, exposed_type))
        output: list[ConsolidatedRelationship] = []
        for entries in groups.values():
            entries.sort(key=lambda pair: (
                int(pair[0].manual_override), CONFIDENCE_RANK.get(pair[0].confidence, 0), pair[0].updated_at or pair[0].created_at,
            ), reverse=True)
            row, exposed_type = entries[0]
            target_name = row.target_entity.canonical_name if row.target_entity else row.unresolved_name or ""
            output.append(ConsolidatedRelationship(
                relationship_id=row.id,
                source_entity_id=row.source_entity_id,
                source_name=row.source_entity.canonical_name,
                source_type=row.source_entity.entity_type,
                relationship_type=exposed_type,
                display_translation_key=f"knowledgeGraph.relationships.{exposed_type}",
                target_entity_id=row.target_entity_id,
                target_name=target_name,
                target_type=row.target_entity.entity_type if row.target_entity else row.target_entity_type_id or "unknown",
                target_slug=row.target_entity.slug if row.target_entity else None,
                resolution_state=row.resolution_state,
                confidence=row.confidence,
                contributing_providers=tuple(sorted({entry.source_provider_id for entry, _ in entries if entry.source_provider_id})),
                manual_verified=any(entry.manual_override and entry.confidence == "verified" for entry, _ in entries),
                freshness=max((entry.updated_at or entry.created_at) for entry, _ in entries),
                source_scope=row.source_scope,
                provenance_count=len(entries),
            ))
        return sorted(output, key=lambda value: (value.relationship_type, value.target_name.lower()))

    @classmethod
    def outgoing(cls, db: Session, entity_id: UUID, *, relationship_type: str | None = None) -> list[ConsolidatedRelationship]:
        query = db.query(KnowledgeRelationship).filter_by(source_entity_id=entity_id, is_current=True)
        if relationship_type:
            query = query.filter_by(relationship_type_code=relationship_type)
        return cls._consolidate([(row, row.relationship_type_code) for row in query.all()])

    @classmethod
    def incoming(cls, db: Session, entity_id: UUID, *, relationship_type: str | None = None) -> list[ConsolidatedRelationship]:
        perspective = db.get(KnowledgeEntity, entity_id)
        if perspective is None:
            return []
        groups: dict[tuple[str, str, UUID], list[tuple[KnowledgeRelationship, str]]] = {}
        for row in db.query(KnowledgeRelationship).filter_by(target_entity_id=entity_id, is_current=True).all():
            inverse = cls._type(db, row.relationship_type_code).inverse_code
            if relationship_type is None or inverse == relationship_type:
                groups.setdefault((row.source_scope, inverse, row.source_entity_id), []).append((row, inverse))
        output: list[ConsolidatedRelationship] = []
        for entries in groups.values():
            entries.sort(key=lambda pair: (
                int(pair[0].manual_override), CONFIDENCE_RANK.get(pair[0].confidence, 0), pair[0].updated_at or pair[0].created_at,
            ), reverse=True)
            row, inverse = entries[0]
            source = row.source_entity
            output.append(ConsolidatedRelationship(
                relationship_id=row.id, source_entity_id=perspective.uuid,
                source_name=perspective.canonical_name, source_type=perspective.entity_type,
                relationship_type=inverse, display_translation_key=f"knowledgeGraph.relationships.{inverse}",
                target_entity_id=source.uuid, target_name=source.canonical_name,
                target_type=source.entity_type, target_slug=source.slug,
                resolution_state=row.resolution_state, confidence=row.confidence,
                contributing_providers=tuple(sorted({entry.source_provider_id for entry, _ in entries if entry.source_provider_id})),
                manual_verified=any(entry.manual_override and entry.confidence == "verified" for entry, _ in entries),
                freshness=max((entry.updated_at or entry.created_at) for entry, _ in entries),
                source_scope=row.source_scope, provenance_count=len(entries),
            ))
        return sorted(output, key=lambda value: (value.relationship_type, value.target_name.lower()))

    @classmethod
    def depth_one(cls, db: Session, entity_id: UUID, *, relationship_type: str | None = None):
        return cls.outgoing(db, entity_id, relationship_type=relationship_type), cls.incoming(db, entity_id, relationship_type=relationship_type)

    @staticmethod
    def verify_consistency(db: Session) -> dict[str, int | list[str]]:
        rows = db.query(KnowledgeRelationship).all()
        errors = RelationshipTypeRegistry.verify_integrity(db)
        counts = {
            "relationships": len(rows), "invalid_type_combinations": 0, "orphan_relationships": 0,
            "resolved_without_target": 0, "unresolved_without_name": 0, "duplicate_current_facts": 0,
            "supersession_cycles": 0, "missing_source_documents": 0,
        }
        seen: set[tuple] = set()
        for row in rows:
            if row.source_entity is None:
                counts["orphan_relationships"] += 1
                continue
            try:
                RelationshipTypeRegistry.validate(db, row.relationship_type_code, row.source_entity.entity_type, row.target_entity_type_id or "")
            except (ValueError, AttributeError):
                counts["invalid_type_combinations"] += 1
            counts["resolved_without_target"] += int(row.resolution_state == "resolved" and row.target_entity is None)
            counts["unresolved_without_name"] += int(row.resolution_state in {"unresolved", "ambiguous"} and not row.unresolved_name)
            identity = (row.source_entity_id, row.source_scope, row.relationship_type_code, row.target_identity, row.provenance_key)
            if row.is_current:
                if identity in seen:
                    counts["duplicate_current_facts"] += 1
                seen.add(identity)
            ref = (row.source_context or {}).get("source_document_ref")
            counts["missing_source_documents"] += int(bool(ref and row.source_document_id is None))
        by_id = {row.id: row for row in rows}
        for row in rows:
            visited: set[UUID] = set()
            cursor = row
            while cursor.superseded_by_id and cursor.superseded_by_id in by_id:
                if cursor.id in visited:
                    counts["supersession_cycles"] += 1
                    break
                visited.add(cursor.id)
                cursor = by_id[cursor.superseded_by_id]
        return {**counts, "registry_errors": errors}
