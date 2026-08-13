"""Append-only current provider observations, distinct from semantic Knowledge."""

from uuid import uuid4

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, Uuid, text
from sqlalchemy.sql import func

from app.db.database import Base
from app.db.types import JSONBType


class KnowledgeProviderObservation(Base):
    """A real provider response observed at a known retrieval time.

    Rows are never synthesized. Reprocessing the same immutable document at a
    newer normalization version produces a new normalized row without fetching.
    """

    __tablename__ = "knowledge_provider_observations"
    __table_args__ = (
        UniqueConstraint(
            "provider_id", "observation_type", "observation_key", "document_uuid",
            "normalization_version", name="uq_knowledge_observation_document_version",
        ),
        Index(
            "uq_knowledge_observation_current",
            "provider_id", "observation_type", "observation_key",
            unique=True,
            postgresql_where=text("is_current"),
            sqlite_where=text("is_current = 1"),
        ),
        Index("ix_knowledge_observation_entity_time", "entity_uuid", "observed_at"),
        Index("ix_knowledge_observation_type_time", "observation_type", "observed_at"),
    )

    uuid = Column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    provider_id = Column(
        String(64), ForeignKey("knowledge_providers.provider_id", ondelete="RESTRICT"), nullable=False,
    )
    observation_type = Column(String(64), nullable=False)
    observation_key = Column(String(512), nullable=False)
    entity_uuid = Column(
        Uuid(as_uuid=True), ForeignKey("knowledge_entities.uuid", ondelete="SET NULL"), nullable=True,
    )
    document_uuid = Column(
        Uuid(as_uuid=True), ForeignKey("knowledge_documents.uuid", ondelete="RESTRICT"), nullable=False,
    )
    normalized_payload = Column(JSONBType, nullable=False)
    supplied_fields = Column(JSONBType, nullable=False, default=list)
    source_url = Column(String(2048), nullable=True)
    normalization_version = Column(Integer, nullable=False, default=1)
    observed_at = Column(DateTime(timezone=True), nullable=False)
    is_current = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
