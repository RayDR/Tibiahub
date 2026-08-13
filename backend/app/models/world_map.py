"""Versioned authoritative TibiaMaps datasets, floors, paths, and markers."""
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, Uuid, text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base
from app.db.types import JSONBType


class WorldMapDataset(Base):
    __tablename__ = "world_map_datasets"
    __table_args__ = (
        UniqueConstraint("provider", "upstream_commit", name="uq_world_map_dataset_provider_commit"),
        Index(
            "uq_world_map_dataset_current", "provider", unique=True,
            postgresql_where=text("is_current"), sqlite_where=text("is_current = 1"),
        ),
    )

    id = Column(Integer, primary_key=True)
    provider = Column(String(64), nullable=False)
    upstream_commit = Column(String(64), nullable=False)
    upstream_url = Column(String(1024), nullable=False)
    license_name = Column(String(64), nullable=False)
    attribution = Column(Text, nullable=False)
    bounds = Column(JSONBType, nullable=False)
    manifest = Column(JSONBType, nullable=False)
    markers_sha256 = Column(String(64), nullable=False)
    storage_path = Column(String(1024), nullable=False)
    is_current = Column(Boolean, nullable=False, default=True)
    imported_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class WorldMapFloor(Base):
    __tablename__ = "world_map_floors"
    __table_args__ = (
        UniqueConstraint("provider", "upstream_commit", "floor", name="uq_world_map_floor_provider_commit_floor"),
        Index("uq_world_map_floor_current", "provider", "floor", unique=True, postgresql_where=text("is_current"), sqlite_where=text("is_current = 1")),
    )

    id = Column(Integer, primary_key=True)
    dataset_id = Column(Integer, ForeignKey("world_map_datasets.id", ondelete="RESTRICT"), nullable=True, index=True)
    provider = Column(String(64), nullable=False, default="tibiamaps/tibia-map-data")
    upstream_commit = Column(String(64), nullable=False)
    upstream_url = Column(String(1024), nullable=False)
    license_name = Column(String(64), nullable=False, default="MIT")
    attribution = Column(Text, nullable=False)
    floor = Column(Integer, nullable=False, index=True)
    map_path = Column(String(1024), nullable=False)
    pathfinding_path = Column(String(1024), nullable=True)
    map_sha256 = Column(String(64), nullable=False)
    pathfinding_sha256 = Column(String(64), nullable=True)
    width = Column(Integer, nullable=False)
    height = Column(Integer, nullable=False)
    min_x = Column(Integer, nullable=False)
    min_y = Column(Integer, nullable=False)
    max_x = Column(Integer, nullable=False)
    max_y = Column(Integer, nullable=False)
    source_metadata = Column(JSONBType, nullable=False, default=dict)
    is_current = Column(Boolean, nullable=False, default=True, index=True)
    imported_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    dataset = relationship("WorldMapDataset")


class WorldMapMarker(Base):
    __tablename__ = "world_map_markers"
    __table_args__ = (
        UniqueConstraint("floor_id", "source_index", name="uq_world_map_marker_floor_index"),
        Index("ix_world_map_marker_floor_xy", "floor", "x", "y"),
    )

    id = Column(Integer, primary_key=True)
    floor_id = Column(Integer, ForeignKey("world_map_floors.id", ondelete="CASCADE"), nullable=False, index=True)
    source_index = Column(Integer, nullable=False)
    description = Column(String(500), nullable=False, default="")
    normalized_description = Column(String(500), nullable=False, default="", index=True)
    icon = Column(String(64), nullable=True)
    x = Column(Integer, nullable=False)
    y = Column(Integer, nullable=False)
    floor = Column(Integer, nullable=False, index=True)
    raw_data = Column(JSONBType, nullable=False, default=dict)
    resolved_entity_id = Column(
        Uuid(as_uuid=True), ForeignKey("knowledge_entities.uuid", ondelete="SET NULL"), nullable=True, index=True,
    )
    resolution_state = Column(String(32), nullable=False, default="unresolved", index=True)
    resolution_method = Column(String(64), nullable=True)

    world_floor = relationship("WorldMapFloor")
