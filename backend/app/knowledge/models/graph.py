"""Unified, provenance-aware Knowledge Graph relationship models."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, String, Text, Uuid, text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base
from app.db.types import JSONBType


RELATIONSHIP_STATES = ("resolved", "unresolved", "ambiguous", "rejected", "superseded")
RELATIONSHIP_CONFIDENCES = ("verified", "high", "medium", "low", "unknown")


class KnowledgeRelationshipType(Base):
    __tablename__ = "knowledge_relationship_types"

    code = Column(String(64), primary_key=True)
    display_translation_key = Column(String(160), nullable=False, unique=True)
    inverse_code = Column(String(64), ForeignKey("knowledge_relationship_types.code", ondelete="RESTRICT"), nullable=False)
    source_entity_types = Column(JSONBType, nullable=False, default=list)
    target_entity_types = Column(JSONBType, nullable=False, default=list)
    directional = Column(Boolean, nullable=False, default=True)
    symmetric = Column(Boolean, nullable=False, default=False)
    transitive = Column(Boolean, nullable=False, default=False)
    user_visible = Column(Boolean, nullable=False, default=True)
    ai_visible = Column(Boolean, nullable=False, default=True)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    inverse = relationship("KnowledgeRelationshipType", remote_side=[code], uselist=False)


class KnowledgeRelationship(Base):
    __tablename__ = "knowledge_relationships"
    __table_args__ = (
        CheckConstraint("resolution_state IN ('resolved','unresolved','ambiguous','rejected','superseded')", name="ck_knowledge_relationship_state"),
        CheckConstraint("confidence IN ('verified','high','medium','low','unknown')", name="ck_knowledge_relationship_confidence"),
        CheckConstraint("(resolution_state <> 'resolved') OR (target_entity_id IS NOT NULL)", name="ck_knowledge_relationship_resolved_target"),
        CheckConstraint("(resolution_state NOT IN ('unresolved','ambiguous')) OR (unresolved_name IS NOT NULL AND normalized_unresolved_name IS NOT NULL)", name="ck_knowledge_relationship_unresolved_name"),
        CheckConstraint("target_entity_id IS NULL OR source_entity_id <> target_entity_id", name="ck_knowledge_relationship_not_self"),
        CheckConstraint("superseded_by_id IS NULL OR superseded_by_id <> id", name="ck_knowledge_relationship_not_self_superseded"),
        Index("ix_knowledge_relationships_source_current", "source_entity_id", "is_current"),
        Index("ix_knowledge_relationships_target_current", "target_entity_id", "is_current"),
        Index("ix_knowledge_relationships_type_current", "relationship_type_code", "is_current"),
        Index("ix_knowledge_relationships_resolution", "resolution_state", "is_current"),
        Index("ix_knowledge_relationships_provider", "source_provider_id", "is_current"),
        Index("ix_knowledge_relationships_document", "source_document_id"),
        Index("ix_knowledge_relationships_job", "source_job_id"),
        Index(
            "ix_knowledge_relationships_pending_target_lookup",
            "target_entity_type_id",
            "normalized_unresolved_name",
            postgresql_where=text(
                "is_current AND manual_override = false "
                "AND resolution_state IN ('unresolved','ambiguous')"
            ),
            sqlite_where=text(
                "is_current = 1 AND manual_override = 0 "
                "AND resolution_state IN ('unresolved','ambiguous')"
            ),
        ),
        Index(
            "uq_knowledge_relationship_current_provenance",
            "source_entity_id", "source_scope", "relationship_type_code", "target_identity", "provenance_key",
            unique=True, postgresql_where=text("is_current"), sqlite_where=text("is_current = 1"),
        ),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    source_entity_id = Column(Uuid(as_uuid=True), ForeignKey("knowledge_entities.uuid", ondelete="CASCADE"), nullable=False)
    source_scope = Column(String(512), nullable=False, default="entity")
    relationship_type_code = Column(String(64), ForeignKey("knowledge_relationship_types.code", ondelete="RESTRICT"), nullable=False)
    target_entity_id = Column(Uuid(as_uuid=True), ForeignKey("knowledge_entities.uuid", ondelete="SET NULL"), nullable=True)
    target_entity_type_id = Column(String(64), ForeignKey("knowledge_entity_types.entity_type", ondelete="RESTRICT"), nullable=True)
    unresolved_name = Column(String(255), nullable=True)
    normalized_unresolved_name = Column(String(255), nullable=True)
    target_identity = Column(String(600), nullable=False)
    resolution_state = Column(String(32), nullable=False, default="unresolved")
    confidence = Column(String(32), nullable=False, default="unknown")
    source_provider_id = Column(String(64), ForeignKey("knowledge_providers.provider_id", ondelete="SET NULL"), nullable=True)
    source_document_id = Column(Uuid(as_uuid=True), ForeignKey("knowledge_documents.uuid", ondelete="SET NULL"), nullable=True)
    source_job_id = Column(Uuid(as_uuid=True), ForeignKey("knowledge_jobs.id", ondelete="SET NULL"), nullable=True)
    provenance_key = Column(String(255), nullable=False)
    source_context = Column(JSONBType, nullable=False, default=dict)
    manual_override = Column(Boolean, nullable=False, default=False)
    verified_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    valid_from = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    valid_until = Column(DateTime(timezone=True), nullable=True)
    is_current = Column(Boolean, nullable=False, default=True)
    superseded_by_id = Column(Uuid(as_uuid=True), ForeignKey("knowledge_relationships.id", ondelete="SET NULL"), nullable=True)
    rejection_reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    source_entity = relationship("KnowledgeEntity", foreign_keys=[source_entity_id])
    target_entity = relationship("KnowledgeEntity", foreign_keys=[target_entity_id])
    relationship_type = relationship("KnowledgeRelationshipType", foreign_keys=[relationship_type_code])
    source_provider = relationship("KnowledgeProvider")
    source_document = relationship("KnowledgeDocument")
    source_job = relationship("KnowledgeJob")
    verified_by = relationship("User")
    superseded_by = relationship("KnowledgeRelationship", remote_side=[id], foreign_keys=[superseded_by_id])
