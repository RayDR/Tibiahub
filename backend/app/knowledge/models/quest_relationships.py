"""Quest/access relationship records designed for later graph expansion."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base
from app.db.types import JSONBType


class KnowledgeAccess(Base):
    __tablename__ = "knowledge_accesses"
    __table_args__ = (
        Index("uq_knowledge_access_entity", "knowledge_entity_id", unique=True),
        Index("ix_knowledge_access_normalized_name", "normalized_name"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    knowledge_entity_id = Column(
        Uuid(as_uuid=True), ForeignKey("knowledge_entities.uuid", ondelete="CASCADE"), nullable=False
    )
    access_code = Column(String(255), nullable=False, unique=True)
    canonical_name = Column(String(255), nullable=False)
    normalized_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    unlocked_by_quest_entity_uuid = Column(
        Uuid(as_uuid=True), ForeignKey("knowledge_entities.uuid", ondelete="SET NULL"), nullable=True
    )
    required_quests = Column(JSONBType, nullable=False, default=list)
    required_items = Column(JSONBType, nullable=False, default=list)
    destination_name = Column(String(255), nullable=True)
    provider_metadata = Column(JSONBType, nullable=False, default=dict)
    protected_fields = Column(JSONBType, nullable=False, default=list)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    knowledge_entity = relationship("KnowledgeEntity", foreign_keys=[knowledge_entity_id])
    unlocked_by_quest = relationship("KnowledgeEntity", foreign_keys=[unlocked_by_quest_entity_uuid])


class KnowledgeQuestRelation(Base):
    __tablename__ = "knowledge_quest_relations"
    __table_args__ = (
        UniqueConstraint(
            "provider_id", "quest_entity_uuid", "scope_key", "relation_type",
            "target_entity_type", "normalized_target_name",
            name="uq_knowledge_quest_relation_fact",
        ),
        CheckConstraint(
            "resolution_status IN ('resolved','unresolved','ambiguous')",
            name="ck_knowledge_quest_relation_resolution",
        ),
        Index("ix_knowledge_quest_relations_quest", "quest_entity_uuid"),
        Index("ix_knowledge_quest_relations_target", "target_entity_uuid"),
        Index("ix_knowledge_quest_relations_mission", "mission_id"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    provider_id = Column(
        String(64), ForeignKey("knowledge_providers.provider_id", ondelete="RESTRICT"), nullable=False
    )
    quest_entity_uuid = Column(
        Uuid(as_uuid=True), ForeignKey("knowledge_entities.uuid", ondelete="CASCADE"), nullable=False
    )
    mission_id = Column(Uuid(as_uuid=True), ForeignKey("quest_missions.id", ondelete="CASCADE"), nullable=True)
    scope_key = Column(String(512), nullable=False, default="quest")
    relation_type = Column(String(64), nullable=False)
    target_entity_type = Column(String(64), nullable=False)
    target_entity_uuid = Column(
        Uuid(as_uuid=True), ForeignKey("knowledge_entities.uuid", ondelete="SET NULL"), nullable=True
    )
    target_name = Column(String(255), nullable=False)
    normalized_target_name = Column(String(255), nullable=False)
    resolution_status = Column(String(32), nullable=False, default="unresolved")
    confidence = Column(String(32), nullable=False, default="exact")
    source_document_ids = Column(JSONBType, nullable=False, default=list)
    source_contexts = Column(JSONBType, nullable=False, default=list)
    relation_metadata = Column("metadata", JSONBType, nullable=False, default=dict)
    protected = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    quest_entity = relationship("KnowledgeEntity", foreign_keys=[quest_entity_uuid])
    target_entity = relationship("KnowledgeEntity", foreign_keys=[target_entity_uuid])
    mission = relationship("QuestMission")
    provider = relationship("KnowledgeProvider")
