"""Small, provenance-aware relationship foundation for creature item drops."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, String, UniqueConstraint, Uuid
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base
from app.db.types import JSONBType


class KnowledgeCreatureItemDrop(Base):
    __tablename__ = "knowledge_creature_item_drops"
    __table_args__ = (
        UniqueConstraint(
            "provider_id",
            "normalized_creature_name",
            "normalized_item_name",
            name="uq_knowledge_creature_item_drop_fact",
        ),
        CheckConstraint(
            "resolution_status IN ('resolved','unresolved','ambiguous')",
            name="ck_knowledge_creature_item_drop_resolution",
        ),
        Index("ix_knowledge_creature_item_drops_creature", "creature_entity_uuid"),
        Index("ix_knowledge_creature_item_drops_item", "item_entity_uuid"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    provider_id = Column(
        String(64),
        ForeignKey("knowledge_providers.provider_id", ondelete="RESTRICT"),
        nullable=False,
    )
    creature_entity_uuid = Column(
        Uuid(as_uuid=True),
        ForeignKey("knowledge_entities.uuid", ondelete="SET NULL"),
        nullable=True,
    )
    item_entity_uuid = Column(
        Uuid(as_uuid=True),
        ForeignKey("knowledge_entities.uuid", ondelete="SET NULL"),
        nullable=True,
    )
    creature_name = Column(String(255), nullable=False)
    item_name = Column(String(255), nullable=False)
    normalized_creature_name = Column(String(255), nullable=False)
    normalized_item_name = Column(String(255), nullable=False)
    resolution_status = Column(String(32), nullable=False, default="unresolved")
    confidence = Column(String(32), nullable=False, default="exact")
    source_document_ids = Column(JSONBType, nullable=False, default=list)
    source_directions = Column(JSONBType, nullable=False, default=list)
    relationship_metadata = Column("metadata", JSONBType, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    creature_entity = relationship("KnowledgeEntity", foreign_keys=[creature_entity_uuid])
    item_entity = relationship("KnowledgeEntity", foreign_keys=[item_entity_uuid])
    provider = relationship("KnowledgeProvider")
