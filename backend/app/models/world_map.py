"""Locally cached TibiaMaps world floors and upstream markers."""
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base
from app.db.types import JSONBType


class WorldMapFloor(Base):
    __tablename__ = "world_map_floors"
    __table_args__ = (
        UniqueConstraint("provider", "upstream_commit", "floor", name="uq_world_map_floor_provider_commit_floor"),
        Index("uq_world_map_floor_current", "provider", "floor", unique=True, postgresql_where=text("is_current"), sqlite_where=text("is_current = 1")),
    )

    id = Column(Integer, primary_key=True)
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

    world_floor = relationship("WorldMapFloor")
