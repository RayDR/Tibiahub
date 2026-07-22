"""Local metadata for featured, pinned, and search-ranked entities."""
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from app.db.database import Base
from app.db.types import JSONBType


class EntityMetadata(Base):
    __tablename__ = "entity_metadata"
    __table_args__ = (
        UniqueConstraint("entity_type", "entity_key", name="uq_entity_metadata_type_key"),
    )

    id = Column(Integer, primary_key=True, index=True)
    entity_type = Column(String(30), nullable=False, index=True)
    entity_key = Column(String(200), nullable=False, index=True)
    display_name = Column(String(255), nullable=False)
    entity_id = Column(Integer, nullable=True, index=True)
    is_featured = Column(Boolean, nullable=False, default=False)
    is_pinned = Column(Boolean, nullable=False, default=False)
    is_favorite = Column(Boolean, nullable=False, default=False)
    search_count = Column(Integer, nullable=False, default=0)
    last_synced_at = Column(DateTime(timezone=True), nullable=True)
    last_viewed_at = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)
    extra_data = Column(JSONBType, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
