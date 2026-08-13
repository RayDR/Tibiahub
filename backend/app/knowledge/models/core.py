"""Provider-neutral relational models for the Knowledge Platform."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base
from app.db.types import JSONBType


class KnowledgeProvider(Base):
    """A registered external provider and its current operating metadata."""

    __tablename__ = "knowledge_providers"
    __table_args__ = (
        CheckConstraint("priority >= 0", name="ck_knowledge_provider_priority_nonnegative"),
        CheckConstraint(
            "health IN ('healthy','degraded','unavailable','disabled','unknown')",
            name="ck_knowledge_provider_health",
        ),
        CheckConstraint(
            "consecutive_failures >= 0",
            name="ck_knowledge_provider_failures_nonnegative",
        ),
        Index("ix_knowledge_providers_enabled_priority", "enabled", "priority"),
    )

    provider_id = Column(String(64), primary_key=True)
    provider_name = Column(String(120), nullable=False, unique=True)
    priority = Column(Integer, nullable=False, default=100)
    enabled = Column(Boolean, nullable=False, default=True)
    version = Column(String(64), nullable=True)
    rate_limit = Column(JSONBType, nullable=False, default=dict)
    health = Column(String(32), nullable=False, default="unknown")
    last_sync_at = Column(DateTime(timezone=True), nullable=True)
    last_attempted_at = Column(DateTime(timezone=True), nullable=True)
    last_success_at = Column(DateTime(timezone=True), nullable=True)
    last_failure_at = Column(DateTime(timezone=True), nullable=True)
    consecutive_failures = Column(Integer, nullable=False, default=0)
    cooldown_until = Column(DateTime(timezone=True), nullable=True)
    supports_entities = Column(JSONBType, nullable=False, default=list)
    provider_roles = Column(JSONBType, nullable=False, default=list)
    observation_capabilities = Column(JSONBType, nullable=False, default=list)
    spatial_capabilities = Column(JSONBType, nullable=False, default=list)
    supports_media = Column(Boolean, nullable=False, default=False)
    supports_search = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    documents = relationship("KnowledgeDocument", back_populates="provider")


class KnowledgeEntityType(Base):
    """Data-driven registry entry; adding an entity type needs no schema change."""

    __tablename__ = "knowledge_entity_types"

    entity_type = Column(String(64), primary_key=True)
    display_name = Column(String(120), nullable=False, unique=True)
    enabled = Column(Boolean, nullable=False, default=True)
    type_metadata = Column("metadata", JSONBType, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class KnowledgeEntity(Base):
    """Permanent canonical identity independent of every provider."""

    __tablename__ = "knowledge_entities"
    __table_args__ = (
        UniqueConstraint("entity_type", "slug", name="uq_knowledge_entity_type_slug"),
        UniqueConstraint(
            "entity_type",
            "language_neutral_id",
            name="uq_knowledge_entity_type_language_neutral_id",
        ),
        CheckConstraint("source_priority >= 0", name="ck_knowledge_entity_source_priority_nonnegative"),
        CheckConstraint("search_weight >= 0", name="ck_knowledge_entity_search_weight_nonnegative"),
        CheckConstraint(
            "visibility IN ('public', 'internal', 'private')",
            name="ck_knowledge_entity_visibility",
        ),
        Index("ix_knowledge_entities_type_status", "entity_type", "status"),
        Index("ix_knowledge_entities_visibility_weight", "visibility", "search_weight"),
    )

    uuid = Column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    entity_type = Column(
        String(64),
        ForeignKey("knowledge_entity_types.entity_type", ondelete="RESTRICT"),
        nullable=False,
    )
    canonical_name = Column(String(255), nullable=False)
    slug = Column(String(255), nullable=False)
    language_neutral_id = Column(String(255), nullable=False)
    status = Column(String(32), nullable=False, default="active")
    source_priority = Column(Integer, nullable=False, default=100)
    visibility = Column(String(16), nullable=False, default="public")
    search_weight = Column(Float, nullable=False, default=1.0)
    media_id = Column(Uuid(as_uuid=True), nullable=True)
    thumbnail_id = Column(Uuid(as_uuid=True), nullable=True)
    icon_id = Column(Uuid(as_uuid=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    entity_type_definition = relationship("KnowledgeEntityType")
    aliases = relationship(
        "KnowledgeEntityAlias",
        back_populates="entity",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    documents = relationship("KnowledgeDocument", back_populates="entity")
    search_metadata = relationship(
        "KnowledgeSearchMetadata",
        back_populates="entity",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )


class KnowledgeEntityAlias(Base):
    """Normalized alternate names unique within an entity type."""

    __tablename__ = "knowledge_entity_aliases"
    __table_args__ = (
        UniqueConstraint("entity_type", "normalized_alias", name="uq_knowledge_alias_type_normalized"),
        Index("ix_knowledge_alias_entity", "entity_uuid"),
    )

    uuid = Column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    entity_uuid = Column(
        Uuid(as_uuid=True),
        ForeignKey("knowledge_entities.uuid", ondelete="CASCADE"),
        nullable=False,
    )
    entity_type = Column(String(64), nullable=False)
    alias = Column(String(255), nullable=False)
    normalized_alias = Column(String(255), nullable=False)
    language = Column(String(16), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    entity = relationship("KnowledgeEntity", back_populates="aliases")


class KnowledgeDocument(Base):
    """Immutable raw provider payload retained for future enrichment and replay."""

    __tablename__ = "knowledge_documents"
    __table_args__ = (
        UniqueConstraint("content_identity", name="uq_knowledge_documents_content_identity"),
        Index(
            "ix_knowledge_documents_provider_document_retrieved",
            "provider_id",
            "provider_document_id",
            "retrieved_at",
        ),
        Index("ix_knowledge_documents_entity_retrieved", "entity_uuid", "retrieved_at"),
        Index("ix_knowledge_documents_checksum", "checksum"),
        Index("ix_knowledge_documents_raw_json_gin", "raw_json", postgresql_using="gin").ddl_if(
            dialect="postgresql"
        ),
        Index(
            "ix_knowledge_documents_metadata_gin",
            "metadata",
            postgresql_using="gin",
        ).ddl_if(dialect="postgresql"),
    )

    uuid = Column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    provider_id = Column(
        String(64),
        ForeignKey("knowledge_providers.provider_id", ondelete="RESTRICT"),
        nullable=False,
    )
    provider_document_id = Column(String(512), nullable=False)
    entity_uuid = Column(
        Uuid(as_uuid=True),
        ForeignKey("knowledge_entities.uuid", ondelete="SET NULL"),
        nullable=True,
    )
    raw_json = Column(JSONBType, nullable=False)
    retrieved_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    checksum = Column(String(64), nullable=False)
    version = Column(String(128), nullable=True)
    etag = Column(String(512), nullable=True)
    language = Column(String(16), nullable=True)
    document_metadata = Column("metadata", JSONBType, nullable=False, default=dict)
    content_identity = Column(String(64), nullable=True)

    provider = relationship("KnowledgeProvider", back_populates="documents")
    entity = relationship("KnowledgeEntity", back_populates="documents")


class KnowledgeSearchMetadata(Base):
    """Search-ready, provider-neutral metadata without embeddings."""

    __tablename__ = "knowledge_search_metadata"
    __table_args__ = (
        Index("ix_knowledge_search_normalized_name", "normalized_name"),
        Index("ix_knowledge_search_provider_score", "provider_score"),
        Index("ix_knowledge_search_popularity", "entity_popularity"),
        Index(
            "ix_knowledge_search_tokens_gin",
            "search_tokens",
            postgresql_using="gin",
        ).ddl_if(dialect="postgresql"),
        Index(
            "ix_knowledge_search_aliases_gin",
            "aliases",
            postgresql_using="gin",
        ).ddl_if(dialect="postgresql"),
        Index(
            "ix_knowledge_search_name_trgm",
            "normalized_name",
            postgresql_using="gin",
            postgresql_ops={"normalized_name": "gin_trgm_ops"},
        ).ddl_if(dialect="postgresql"),
    )

    entity_uuid = Column(
        Uuid(as_uuid=True),
        ForeignKey("knowledge_entities.uuid", ondelete="CASCADE"),
        primary_key=True,
    )
    normalized_name = Column(String(255), nullable=False)
    search_tokens = Column(JSONBType, nullable=False, default=list)
    aliases = Column(JSONBType, nullable=False, default=list)
    provider_score = Column(Float, nullable=False, default=0.0)
    entity_popularity = Column(Integer, nullable=False, default=0)
    future_embedding_id = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    entity = relationship("KnowledgeEntity", back_populates="search_metadata")


class KnowledgeDomainEvent(Base):
    """Transactional internal event record; never exposed as a public API."""

    __tablename__ = "knowledge_domain_events"
    __table_args__ = (
        Index("ix_knowledge_events_type_occurred", "event_type", "occurred_at"),
        Index("ix_knowledge_events_unprocessed", "processed_at", "occurred_at"),
    )

    uuid = Column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    event_type = Column(String(64), nullable=False)
    entity_uuid = Column(
        Uuid(as_uuid=True),
        ForeignKey("knowledge_entities.uuid", ondelete="SET NULL"),
        nullable=True,
    )
    provider_id = Column(
        String(64),
        ForeignKey("knowledge_providers.provider_id", ondelete="SET NULL"),
        nullable=True,
    )
    payload = Column(JSONBType, nullable=False, default=dict)
    occurred_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)
