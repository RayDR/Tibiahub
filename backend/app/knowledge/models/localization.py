"""Durable, reviewable localized content for the Knowledge Platform."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.sql import func

from app.db.database import Base
from app.db.types import JSONBType


LOCALIZATION_STATUSES = ("generated", "reviewed", "approved", "stale", "failed")
LOCALIZATION_ORIGINS = ("provider", "machine", "human")


class KnowledgeLocalization(Base):
    """One localized field value for a stable TibiaHub resource.

    The source domain row remains canonical. This table stores language variants
    and their provenance so machine translations can be regenerated without
    overwriting reviewed or approved human work.
    """

    __tablename__ = "knowledge_localizations"
    __table_args__ = (
        UniqueConstraint(
            "resource_type",
            "resource_key",
            "field_path",
            "language",
            name="uq_knowledge_localization_resource_field_language",
        ),
        CheckConstraint(
            "status IN ('generated','reviewed','approved','stale','failed')",
            name="ck_knowledge_localization_status",
        ),
        CheckConstraint(
            "origin IN ('provider','machine','human')",
            name="ck_knowledge_localization_origin",
        ),
        Index("ix_knowledge_localizations_entity_language", "entity_uuid", "language"),
        Index("ix_knowledge_localizations_resource_language", "resource_type", "resource_key", "language"),
        Index("ix_knowledge_localizations_review", "status", "language", "updated_at"),
        Index("ix_knowledge_localizations_source_hash", "source_text_hash"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    entity_uuid = Column(
        Uuid(as_uuid=True),
        ForeignKey("knowledge_entities.uuid", ondelete="SET NULL"),
        nullable=True,
    )
    resource_type = Column(String(64), nullable=False)
    resource_key = Column(String(255), nullable=False)
    field_path = Column(String(255), nullable=False)
    language = Column(String(32), nullable=False)
    text = Column(Text, nullable=False)

    source_language = Column(String(32), nullable=False)
    source_text_hash = Column(String(64), nullable=False)
    origin = Column(String(16), nullable=False, default="machine")
    status = Column(String(16), nullable=False, default="generated")

    provider = Column(String(64), nullable=True)
    provider_model = Column(String(128), nullable=True)
    provider_metadata = Column(JSONBType, nullable=False, default=dict)

    # A locked or approved localization is never silently replaced by sync.
    locked = Column(Boolean, nullable=False, default=False)
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    approved_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
