"""PostGIS-backed canonical spatial records with immutable version history."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, SmallInteger, String, Text, UniqueConstraint, Uuid, text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base
from app.db.types import JSONBType, geometry_column_type


class SpatialProvenanceMixin:
    source_provider_id = Column(String(64), ForeignKey("knowledge_providers.provider_id", ondelete="SET NULL"), nullable=True)
    source_document_id = Column(Uuid(as_uuid=True), ForeignKey("knowledge_documents.uuid", ondelete="SET NULL"), nullable=True)
    source_job_id = Column(Uuid(as_uuid=True), ForeignKey("knowledge_jobs.id", ondelete="SET NULL"), nullable=True)
    source_reference = Column(String(1024), nullable=True)
    source_metadata = Column(JSONBType, nullable=False, default=dict)
    confidence = Column(String(32), nullable=False, default="unknown")
    verification_state = Column(String(32), nullable=False, default="pending")
    verified_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    rejection_reason = Column(Text, nullable=True)
    version = Column(Integer, nullable=False, default=1)
    is_current = Column(Boolean, nullable=False, default=True)
    valid_from = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    valid_until = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class SpatialMapPoint(SpatialProvenanceMixin, Base):
    __tablename__ = "spatial_map_points"
    __table_args__ = (
        CheckConstraint("confidence IN ('verified','high','medium','low','unknown')", name="ck_spatial_point_confidence"),
        CheckConstraint("verification_state IN ('pending','verified','rejected','unresolved','ambiguous')", name="ck_spatial_point_verification"),
        CheckConstraint("tibia_x IS NULL OR tibia_x BETWEEN 0 AND 65535", name="ck_spatial_point_x"),
        CheckConstraint("tibia_y IS NULL OR tibia_y BETWEEN 0 AND 65535", name="ck_spatial_point_y"),
        CheckConstraint("tibia_z IS NULL OR tibia_z BETWEEN 0 AND 15", name="ck_spatial_point_floor"),
        CheckConstraint("(tibia_x IS NULL AND tibia_y IS NULL AND tibia_z IS NULL AND geom IS NULL) OR (tibia_x IS NOT NULL AND tibia_y IS NOT NULL AND tibia_z IS NOT NULL AND geom IS NOT NULL)", name="ck_spatial_point_complete"),
        CheckConstraint("(tibia_x IS NULL AND min_x IS NULL AND max_x IS NULL AND min_y IS NULL AND max_y IS NULL AND min_z IS NULL AND max_z IS NULL) OR (min_x=tibia_x AND max_x=tibia_x AND min_y=tibia_y AND max_y=tibia_y AND min_z=tibia_z AND max_z=tibia_z)", name="ck_spatial_point_bounds"),
        UniqueConstraint("source_provider_id", "external_id", "version", name="uq_spatial_point_provider_version"),
        Index("uq_spatial_point_current_entity", "knowledge_entity_id", unique=True, postgresql_where=text("is_current"), sqlite_where=text("is_current = 1")),
        Index("ix_spatial_map_points_geom", "geom", postgresql_using="gist"),
        Index("ix_spatial_map_points_floor_current", "tibia_z", "is_current"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    knowledge_entity_id = Column(Uuid(as_uuid=True), ForeignKey("knowledge_entities.uuid", ondelete="CASCADE"), nullable=False)
    location_entity_id = Column(Uuid(as_uuid=True), ForeignKey("knowledge_entities.uuid", ondelete="SET NULL"), nullable=True)
    external_id = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    tibia_x = Column(Integer, nullable=True)
    tibia_y = Column(Integer, nullable=True)
    tibia_z = Column(SmallInteger, nullable=True)
    geom = Column(geometry_column_type("PointZ"), nullable=True)
    min_x = Column(Integer, nullable=True)
    min_y = Column(Integer, nullable=True)
    max_x = Column(Integer, nullable=True)
    max_y = Column(Integer, nullable=True)
    min_z = Column(SmallInteger, nullable=True)
    max_z = Column(SmallInteger, nullable=True)
    unresolved_location_name = Column(String(255), nullable=True)
    normalized_unresolved_location_name = Column(String(255), nullable=True)

    knowledge_entity = relationship("KnowledgeEntity", foreign_keys=[knowledge_entity_id])
    location_entity = relationship("KnowledgeEntity", foreign_keys=[location_entity_id])


class SpatialMapRegion(SpatialProvenanceMixin, Base):
    __tablename__ = "spatial_map_regions"
    __table_args__ = (
        CheckConstraint("confidence IN ('verified','high','medium','low','unknown')", name="ck_spatial_region_confidence"),
        CheckConstraint("verification_state IN ('pending','verified','rejected','unresolved','ambiguous')", name="ck_spatial_region_verification"),
        CheckConstraint("min_z IS NULL OR min_z BETWEEN 0 AND 15", name="ck_spatial_region_min_floor"),
        CheckConstraint("max_z IS NULL OR max_z BETWEEN 0 AND 15", name="ck_spatial_region_max_floor"),
        CheckConstraint("min_z IS NULL OR max_z IS NULL OR min_z <= max_z", name="ck_spatial_region_floor_order"),
        CheckConstraint("(min_z IS NULL AND max_z IS NULL) OR (min_z IS NOT NULL AND max_z IS NOT NULL)", name="ck_spatial_region_floor_complete"),
        CheckConstraint("(min_x IS NULL AND max_x IS NULL) OR (min_x BETWEEN 0 AND 65535 AND max_x BETWEEN 0 AND 65535 AND min_x <= max_x)", name="ck_spatial_region_x_bounds"),
        CheckConstraint("(min_y IS NULL AND max_y IS NULL) OR (min_y BETWEEN 0 AND 65535 AND max_y BETWEEN 0 AND 65535 AND min_y <= max_y)", name="ck_spatial_region_y_bounds"),
        UniqueConstraint("source_provider_id", "external_id", "version", name="uq_spatial_region_provider_version"),
        Index("uq_spatial_region_current_entity", "knowledge_entity_id", unique=True, postgresql_where=text("is_current"), sqlite_where=text("is_current = 1")),
        Index("ix_spatial_map_regions_geom", "geom", postgresql_using="gist"),
        Index("ix_spatial_map_regions_bounds", "min_x", "min_y", "max_x", "max_y"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    knowledge_entity_id = Column(Uuid(as_uuid=True), ForeignKey("knowledge_entities.uuid", ondelete="CASCADE"), nullable=False)
    location_entity_id = Column(Uuid(as_uuid=True), ForeignKey("knowledge_entities.uuid", ondelete="SET NULL"), nullable=True)
    external_id = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    geom = Column(geometry_column_type("MultiPolygonZ"), nullable=True)
    min_x = Column(Integer, nullable=True)
    min_y = Column(Integer, nullable=True)
    max_x = Column(Integer, nullable=True)
    max_y = Column(Integer, nullable=True)
    min_z = Column(SmallInteger, nullable=True)
    max_z = Column(SmallInteger, nullable=True)
    unresolved_location_name = Column(String(255), nullable=True)
    normalized_unresolved_location_name = Column(String(255), nullable=True)

    knowledge_entity = relationship("KnowledgeEntity", foreign_keys=[knowledge_entity_id])
    location_entity = relationship("KnowledgeEntity", foreign_keys=[location_entity_id])


class SpatialRoute(SpatialProvenanceMixin, Base):
    __tablename__ = "spatial_routes"
    __table_args__ = (
        CheckConstraint("confidence IN ('verified','high','medium','low','unknown')", name="ck_spatial_route_confidence"),
        CheckConstraint("verification_state IN ('pending','verified','rejected','unresolved','ambiguous')", name="ck_spatial_route_verification"),
        CheckConstraint("step_count BETWEEN 0 AND 250", name="ck_spatial_route_step_count"),
        CheckConstraint("(min_x IS NULL AND max_x IS NULL) OR (min_x BETWEEN 0 AND 65535 AND max_x BETWEEN 0 AND 65535 AND min_x <= max_x)", name="ck_spatial_route_x_bounds"),
        CheckConstraint("(min_y IS NULL AND max_y IS NULL) OR (min_y BETWEEN 0 AND 65535 AND max_y BETWEEN 0 AND 65535 AND min_y <= max_y)", name="ck_spatial_route_y_bounds"),
        CheckConstraint("(min_z IS NULL AND max_z IS NULL) OR (min_z BETWEEN 0 AND 15 AND max_z BETWEEN 0 AND 15 AND min_z <= max_z)", name="ck_spatial_route_z_bounds"),
        UniqueConstraint("source_provider_id", "external_id", "version", name="uq_spatial_route_provider_version"),
        Index("uq_spatial_route_current_entity", "knowledge_entity_id", unique=True, postgresql_where=text("is_current"), sqlite_where=text("is_current = 1")),
        Index("ix_spatial_routes_geom", "geom", postgresql_using="gist"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    knowledge_entity_id = Column(Uuid(as_uuid=True), ForeignKey("knowledge_entities.uuid", ondelete="CASCADE"), nullable=False)
    external_id = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), nullable=False)
    start_location_entity_id = Column(Uuid(as_uuid=True), ForeignKey("knowledge_entities.uuid", ondelete="SET NULL"), nullable=True)
    end_location_entity_id = Column(Uuid(as_uuid=True), ForeignKey("knowledge_entities.uuid", ondelete="SET NULL"), nullable=True)
    unresolved_start_name = Column(String(255), nullable=True)
    unresolved_end_name = Column(String(255), nullable=True)
    geom = Column(geometry_column_type("LineStringZ"), nullable=True)
    min_x = Column(Integer, nullable=True)
    min_y = Column(Integer, nullable=True)
    max_x = Column(Integer, nullable=True)
    max_y = Column(Integer, nullable=True)
    min_z = Column(SmallInteger, nullable=True)
    max_z = Column(SmallInteger, nullable=True)
    step_count = Column(Integer, nullable=False, default=0)

    knowledge_entity = relationship("KnowledgeEntity", foreign_keys=[knowledge_entity_id])
    start_location = relationship("KnowledgeEntity", foreign_keys=[start_location_entity_id])
    end_location = relationship("KnowledgeEntity", foreign_keys=[end_location_entity_id])
    steps = relationship("SpatialRouteStep", back_populates="route", cascade="all, delete-orphan", order_by="SpatialRouteStep.sequence")


class SpatialRouteStep(Base):
    __tablename__ = "spatial_route_steps"
    __table_args__ = (
        UniqueConstraint("route_id", "sequence", name="uq_spatial_route_step_sequence"),
        CheckConstraint("sequence BETWEEN 1 AND 250", name="ck_spatial_route_step_sequence"),
        CheckConstraint("tibia_z IS NULL OR tibia_z BETWEEN 0 AND 15", name="ck_spatial_route_step_floor"),
        CheckConstraint("tibia_x IS NULL OR tibia_x BETWEEN 0 AND 65535", name="ck_spatial_route_step_x"),
        CheckConstraint("tibia_y IS NULL OR tibia_y BETWEEN 0 AND 65535", name="ck_spatial_route_step_y"),
        CheckConstraint("(tibia_x IS NULL AND tibia_y IS NULL AND tibia_z IS NULL AND geom IS NULL) OR (tibia_x IS NOT NULL AND tibia_y IS NOT NULL AND tibia_z IS NOT NULL AND geom IS NOT NULL)", name="ck_spatial_route_step_complete"),
        CheckConstraint("instruction IS NOT NULL OR location_entity_id IS NOT NULL OR unresolved_location_name IS NOT NULL OR geom IS NOT NULL", name="ck_spatial_route_step_content"),
        Index("ix_spatial_route_steps_route_order", "route_id", "sequence"),
        Index("ix_spatial_route_steps_geom", "geom", postgresql_using="gist"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    route_id = Column(Uuid(as_uuid=True), ForeignKey("spatial_routes.id", ondelete="CASCADE"), nullable=False)
    sequence = Column(Integer, nullable=False)
    step_kind = Column(String(64), nullable=False, default="travel")
    instruction = Column(Text, nullable=True)
    location_entity_id = Column(Uuid(as_uuid=True), ForeignKey("knowledge_entities.uuid", ondelete="SET NULL"), nullable=True)
    unresolved_location_name = Column(String(255), nullable=True)
    tibia_x = Column(Integer, nullable=True)
    tibia_y = Column(Integer, nullable=True)
    tibia_z = Column(SmallInteger, nullable=True)
    geom = Column(geometry_column_type("PointZ"), nullable=True)
    source_metadata = Column(JSONBType, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    route = relationship("SpatialRoute", back_populates="steps")
    location_entity = relationship("KnowledgeEntity")


class SpatialEntityLocationLink(SpatialProvenanceMixin, Base):
    __tablename__ = "spatial_entity_location_links"
    __table_args__ = (
        CheckConstraint("confidence IN ('verified','high','medium','low','unknown')", name="ck_spatial_link_confidence"),
        CheckConstraint("verification_state IN ('pending','verified','rejected','unresolved','ambiguous')", name="ck_spatial_link_verification"),
        CheckConstraint("location_entity_id IS NOT NULL OR unresolved_location_name IS NOT NULL", name="ck_spatial_link_location"),
        CheckConstraint("map_point_id IS NULL OR map_region_id IS NULL", name="ck_spatial_link_single_representation"),
        UniqueConstraint("source_provider_id", "external_id", "version", name="uq_spatial_link_provider_version"),
        Index("ix_spatial_links_source_current", "source_entity_id", "is_current"),
        Index("ix_spatial_links_location_current", "location_entity_id", "is_current"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    source_entity_id = Column(Uuid(as_uuid=True), ForeignKey("knowledge_entities.uuid", ondelete="CASCADE"), nullable=False)
    location_entity_id = Column(Uuid(as_uuid=True), ForeignKey("knowledge_entities.uuid", ondelete="SET NULL"), nullable=True)
    map_point_id = Column(Uuid(as_uuid=True), ForeignKey("spatial_map_points.id", ondelete="SET NULL"), nullable=True)
    map_region_id = Column(Uuid(as_uuid=True), ForeignKey("spatial_map_regions.id", ondelete="SET NULL"), nullable=True)
    graph_relationship_id = Column(Uuid(as_uuid=True), ForeignKey("knowledge_relationships.id", ondelete="SET NULL"), nullable=True)
    external_id = Column(String(255), nullable=False)
    unresolved_location_name = Column(String(255), nullable=True)
    normalized_unresolved_location_name = Column(String(255), nullable=True)

    source_entity = relationship("KnowledgeEntity", foreign_keys=[source_entity_id])
    location_entity = relationship("KnowledgeEntity", foreign_keys=[location_entity_id])
    map_point = relationship("SpatialMapPoint")
    map_region = relationship("SpatialMapRegion")
    graph_relationship = relationship("KnowledgeRelationship")
