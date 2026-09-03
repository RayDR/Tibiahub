"""Stable provider-to-canonical entity identifiers."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import Column, DateTime, ForeignKey, Index, String, UniqueConstraint, Uuid
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base
from app.db.types import JSONBType


class KnowledgeExternalMapping(Base):
    __tablename__ = "knowledge_external_mappings"
    __table_args__ = (
        UniqueConstraint(
            "provider_id",
            "entity_type_id",
            "external_id",
            name="uq_knowledge_external_mapping_identifier",
        ),
        Index("ix_knowledge_external_mappings_entity", "entity_uuid"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    provider_id = Column(
        String(64),
        ForeignKey("knowledge_providers.provider_id", ondelete="CASCADE"),
        nullable=False,
    )
    entity_type_id = Column(
        String(64),
        ForeignKey("knowledge_entity_types.entity_type", ondelete="CASCADE"),
        nullable=False,
    )
    external_id = Column(String(255), nullable=False)
    entity_uuid = Column(
        Uuid(as_uuid=True),
        ForeignKey("knowledge_entities.uuid", ondelete="CASCADE"),
        nullable=False,
    )
    provider_metadata = Column(JSONBType, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    entity = relationship("KnowledgeEntity")
    provider = relationship("KnowledgeProvider")
