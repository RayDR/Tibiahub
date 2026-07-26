"""PostGIS spatial foundation

Revision ID: maps_postgis_20260724
Revises: knowledge_named_places_20260724
Create Date: 2026-07-24
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "maps_postgis_20260724"
down_revision = "knowledge_named_places_20260724"
branch_labels = None
depends_on = None

JSONB = postgresql.JSONB(astext_type=sa.Text())


class Geometry(sa.types.UserDefinedType):
    cache_ok = True

    def __init__(self, kind: str):
        self.kind = kind

    def get_col_spec(self, **_kw) -> str:
        return f"geometry({self.kind},0)"


RELATIONSHIP_TYPES = (
    ("represented_by", "represents_location", ["area", "town", "location"], ["map_point", "map_region"]),
    ("represents_location", "represented_by", ["map_point", "map_region"], ["area", "town", "location"]),
    ("starts_at", "start_of_route", ["route"], ["area", "town", "location"]),
    ("start_of_route", "starts_at", ["area", "town", "location"], ["route"]),
    ("ends_at", "end_of_route", ["route"], ["area", "town", "location"]),
    ("end_of_route", "ends_at", ["area", "town", "location"], ["route"]),
    ("passes_through", "traversed_by_route", ["route"], ["area", "town", "location"]),
    ("traversed_by_route", "passes_through", ["area", "town", "location"], ["route"]),
    ("appears_in", "has_creature", ["creature", "boss"], ["area", "location"]),
    ("has_creature", "appears_in", ["area", "location"], ["creature", "boss"]),
)


def _provenance_columns():
    return (
        sa.Column("source_provider_id", sa.String(64), sa.ForeignKey("knowledge_providers.provider_id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_document_id", sa.Uuid(), sa.ForeignKey("knowledge_documents.uuid", ondelete="SET NULL"), nullable=True),
        sa.Column("source_job_id", sa.Uuid(), sa.ForeignKey("knowledge_jobs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_reference", sa.String(1024), nullable=True),
        sa.Column("source_metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("confidence", sa.String(32), nullable=False, server_default="unknown"),
        sa.Column("verification_state", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("verified_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def _require_postgis() -> None:
    op.execute("""
        DO $tibiahub$
        BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_available_extensions WHERE name='postgis') THEN
            RAISE EXCEPTION 'PostGIS server package is required before the Maps foundation migration';
          END IF;
          IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname='postgis') THEN
            RAISE EXCEPTION 'PostGIS must be enabled in the TibiaHub database by a PostgreSQL administrator';
          END IF;
        END
        $tibiahub$;
    """)


def _register_graph() -> None:
    for entity_type, display_name in (("map_point", "Map Point"), ("map_region", "Map Region"), ("route", "Route")):
        op.execute(sa.text("""
            INSERT INTO knowledge_entity_types (entity_type, display_name, enabled, metadata)
            VALUES (:entity_type, :display_name, true, '{}'::jsonb)
            ON CONFLICT (entity_type) DO UPDATE SET display_name=EXCLUDED.display_name, enabled=true, updated_at=now()
        """).bindparams(entity_type=entity_type, display_name=display_name))
    for code, _inverse, sources, targets in RELATIONSHIP_TYPES:
        op.execute(sa.text("""
            INSERT INTO knowledge_relationship_types (
                code, display_translation_key, inverse_code, source_entity_types, target_entity_types
            ) VALUES (:code, :translation, :code, CAST(:sources AS jsonb), CAST(:targets AS jsonb))
            ON CONFLICT (code) DO UPDATE SET
                display_translation_key=EXCLUDED.display_translation_key,
                source_entity_types=EXCLUDED.source_entity_types,
                target_entity_types=EXCLUDED.target_entity_types,
                active=true, updated_at=now()
        """).bindparams(code=code, translation=f"knowledgeGraph.relationships.{code}",
                          sources=__import__("json").dumps(sources), targets=__import__("json").dumps(targets)))
    for code, inverse, _sources, _targets in RELATIONSHIP_TYPES:
        op.execute(sa.text("UPDATE knowledge_relationship_types SET inverse_code=:inverse, updated_at=now() WHERE code=:code").bindparams(code=code, inverse=inverse))
    op.execute("""
        UPDATE knowledge_relationship_types
        SET source_entity_types='["creature","item","quest","npc","boss","hunt_zone","access"]'::jsonb,
            updated_at=now()
        WHERE code='located_at'
    """)


def upgrade() -> None:
    _require_postgis()
    _register_graph()
    op.create_table(
        "spatial_map_points",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("knowledge_entity_id", sa.Uuid(), sa.ForeignKey("knowledge_entities.uuid", ondelete="CASCADE"), nullable=False),
        sa.Column("location_entity_id", sa.Uuid(), sa.ForeignKey("knowledge_entities.uuid", ondelete="SET NULL"), nullable=True),
        sa.Column("external_id", sa.String(255), nullable=False), sa.Column("name", sa.String(255), nullable=False),
        sa.Column("tibia_x", sa.Integer(), nullable=True), sa.Column("tibia_y", sa.Integer(), nullable=True),
        sa.Column("tibia_z", sa.SmallInteger(), nullable=True), sa.Column("geom", Geometry("PointZ"), nullable=True),
        sa.Column("min_x", sa.Integer()), sa.Column("min_y", sa.Integer()), sa.Column("max_x", sa.Integer()), sa.Column("max_y", sa.Integer()),
        sa.Column("min_z", sa.SmallInteger()), sa.Column("max_z", sa.SmallInteger()),
        sa.Column("unresolved_location_name", sa.String(255)), sa.Column("normalized_unresolved_location_name", sa.String(255)),
        *_provenance_columns(),
        sa.CheckConstraint("confidence IN ('verified','high','medium','low','unknown')", name="ck_spatial_point_confidence"),
        sa.CheckConstraint("verification_state IN ('pending','verified','rejected','unresolved','ambiguous')", name="ck_spatial_point_verification"),
        sa.CheckConstraint("tibia_x IS NULL OR tibia_x BETWEEN 0 AND 65535", name="ck_spatial_point_x"),
        sa.CheckConstraint("tibia_y IS NULL OR tibia_y BETWEEN 0 AND 65535", name="ck_spatial_point_y"),
        sa.CheckConstraint("tibia_z IS NULL OR tibia_z BETWEEN 0 AND 15", name="ck_spatial_point_floor"),
        sa.CheckConstraint("(tibia_x IS NULL AND tibia_y IS NULL AND tibia_z IS NULL AND geom IS NULL) OR (tibia_x IS NOT NULL AND tibia_y IS NOT NULL AND tibia_z IS NOT NULL AND geom IS NOT NULL)", name="ck_spatial_point_complete"),
        sa.CheckConstraint("(tibia_x IS NULL AND min_x IS NULL AND max_x IS NULL AND min_y IS NULL AND max_y IS NULL AND min_z IS NULL AND max_z IS NULL) OR (min_x=tibia_x AND max_x=tibia_x AND min_y=tibia_y AND max_y=tibia_y AND min_z=tibia_z AND max_z=tibia_z)", name="ck_spatial_point_bounds"),
        sa.UniqueConstraint("source_provider_id", "external_id", "version", name="uq_spatial_point_provider_version"),
    )
    op.create_index("uq_spatial_point_current_entity", "spatial_map_points", ["knowledge_entity_id"], unique=True, postgresql_where=sa.text("is_current"))
    op.create_index("ix_spatial_map_points_geom", "spatial_map_points", ["geom"], postgresql_using="gist")
    op.create_index("ix_spatial_map_points_floor_current", "spatial_map_points", ["tibia_z", "is_current"])

    op.create_table(
        "spatial_map_regions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("knowledge_entity_id", sa.Uuid(), sa.ForeignKey("knowledge_entities.uuid", ondelete="CASCADE"), nullable=False),
        sa.Column("location_entity_id", sa.Uuid(), sa.ForeignKey("knowledge_entities.uuid", ondelete="SET NULL")),
        sa.Column("external_id", sa.String(255), nullable=False), sa.Column("name", sa.String(255), nullable=False),
        sa.Column("geom", Geometry("MultiPolygonZ")),
        sa.Column("min_x", sa.Integer()), sa.Column("min_y", sa.Integer()), sa.Column("max_x", sa.Integer()), sa.Column("max_y", sa.Integer()),
        sa.Column("min_z", sa.SmallInteger()), sa.Column("max_z", sa.SmallInteger()),
        sa.Column("unresolved_location_name", sa.String(255)), sa.Column("normalized_unresolved_location_name", sa.String(255)),
        *_provenance_columns(),
        sa.CheckConstraint("confidence IN ('verified','high','medium','low','unknown')", name="ck_spatial_region_confidence"),
        sa.CheckConstraint("verification_state IN ('pending','verified','rejected','unresolved','ambiguous')", name="ck_spatial_region_verification"),
        sa.CheckConstraint("min_z IS NULL OR min_z BETWEEN 0 AND 15", name="ck_spatial_region_min_floor"),
        sa.CheckConstraint("max_z IS NULL OR max_z BETWEEN 0 AND 15", name="ck_spatial_region_max_floor"),
        sa.CheckConstraint("min_z IS NULL OR max_z IS NULL OR min_z <= max_z", name="ck_spatial_region_floor_order"),
        sa.CheckConstraint("(min_z IS NULL AND max_z IS NULL) OR (min_z IS NOT NULL AND max_z IS NOT NULL)", name="ck_spatial_region_floor_complete"),
        sa.CheckConstraint("(min_x IS NULL AND max_x IS NULL) OR (min_x BETWEEN 0 AND 65535 AND max_x BETWEEN 0 AND 65535 AND min_x <= max_x)", name="ck_spatial_region_x_bounds"),
        sa.CheckConstraint("(min_y IS NULL AND max_y IS NULL) OR (min_y BETWEEN 0 AND 65535 AND max_y BETWEEN 0 AND 65535 AND min_y <= max_y)", name="ck_spatial_region_y_bounds"),
        sa.UniqueConstraint("source_provider_id", "external_id", "version", name="uq_spatial_region_provider_version"),
    )
    op.create_index("uq_spatial_region_current_entity", "spatial_map_regions", ["knowledge_entity_id"], unique=True, postgresql_where=sa.text("is_current"))
    op.create_index("ix_spatial_map_regions_geom", "spatial_map_regions", ["geom"], postgresql_using="gist")
    op.create_index("ix_spatial_map_regions_bounds", "spatial_map_regions", ["min_x", "min_y", "max_x", "max_y"])

    op.create_table(
        "spatial_routes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("knowledge_entity_id", sa.Uuid(), sa.ForeignKey("knowledge_entities.uuid", ondelete="CASCADE"), nullable=False),
        sa.Column("external_id", sa.String(255), nullable=False), sa.Column("name", sa.String(255), nullable=False), sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("start_location_entity_id", sa.Uuid(), sa.ForeignKey("knowledge_entities.uuid", ondelete="SET NULL")),
        sa.Column("end_location_entity_id", sa.Uuid(), sa.ForeignKey("knowledge_entities.uuid", ondelete="SET NULL")),
        sa.Column("unresolved_start_name", sa.String(255)), sa.Column("unresolved_end_name", sa.String(255)),
        sa.Column("geom", Geometry("LineStringZ")),
        sa.Column("min_x", sa.Integer()), sa.Column("min_y", sa.Integer()), sa.Column("max_x", sa.Integer()), sa.Column("max_y", sa.Integer()),
        sa.Column("min_z", sa.SmallInteger()), sa.Column("max_z", sa.SmallInteger()), sa.Column("step_count", sa.Integer(), nullable=False, server_default="0"),
        *_provenance_columns(),
        sa.CheckConstraint("confidence IN ('verified','high','medium','low','unknown')", name="ck_spatial_route_confidence"),
        sa.CheckConstraint("verification_state IN ('pending','verified','rejected','unresolved','ambiguous')", name="ck_spatial_route_verification"),
        sa.CheckConstraint("step_count BETWEEN 0 AND 250", name="ck_spatial_route_step_count"),
        sa.CheckConstraint("(min_x IS NULL AND max_x IS NULL) OR (min_x BETWEEN 0 AND 65535 AND max_x BETWEEN 0 AND 65535 AND min_x <= max_x)", name="ck_spatial_route_x_bounds"),
        sa.CheckConstraint("(min_y IS NULL AND max_y IS NULL) OR (min_y BETWEEN 0 AND 65535 AND max_y BETWEEN 0 AND 65535 AND min_y <= max_y)", name="ck_spatial_route_y_bounds"),
        sa.CheckConstraint("(min_z IS NULL AND max_z IS NULL) OR (min_z BETWEEN 0 AND 15 AND max_z BETWEEN 0 AND 15 AND min_z <= max_z)", name="ck_spatial_route_z_bounds"),
        sa.UniqueConstraint("source_provider_id", "external_id", "version", name="uq_spatial_route_provider_version"),
    )
    op.create_index("uq_spatial_route_current_entity", "spatial_routes", ["knowledge_entity_id"], unique=True, postgresql_where=sa.text("is_current"))
    op.create_index("ix_spatial_routes_geom", "spatial_routes", ["geom"], postgresql_using="gist")

    op.create_table(
        "spatial_route_steps",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("route_id", sa.Uuid(), sa.ForeignKey("spatial_routes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False), sa.Column("step_kind", sa.String(64), nullable=False, server_default="travel"),
        sa.Column("instruction", sa.Text()), sa.Column("location_entity_id", sa.Uuid(), sa.ForeignKey("knowledge_entities.uuid", ondelete="SET NULL")),
        sa.Column("unresolved_location_name", sa.String(255)), sa.Column("tibia_x", sa.Integer()), sa.Column("tibia_y", sa.Integer()), sa.Column("tibia_z", sa.SmallInteger()),
        sa.Column("geom", Geometry("PointZ")), sa.Column("source_metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("sequence BETWEEN 1 AND 250", name="ck_spatial_route_step_sequence"),
        sa.CheckConstraint("tibia_z IS NULL OR tibia_z BETWEEN 0 AND 15", name="ck_spatial_route_step_floor"),
        sa.CheckConstraint("tibia_x IS NULL OR tibia_x BETWEEN 0 AND 65535", name="ck_spatial_route_step_x"),
        sa.CheckConstraint("tibia_y IS NULL OR tibia_y BETWEEN 0 AND 65535", name="ck_spatial_route_step_y"),
        sa.CheckConstraint("(tibia_x IS NULL AND tibia_y IS NULL AND tibia_z IS NULL AND geom IS NULL) OR (tibia_x IS NOT NULL AND tibia_y IS NOT NULL AND tibia_z IS NOT NULL AND geom IS NOT NULL)", name="ck_spatial_route_step_complete"),
        sa.CheckConstraint("instruction IS NOT NULL OR location_entity_id IS NOT NULL OR unresolved_location_name IS NOT NULL OR geom IS NOT NULL", name="ck_spatial_route_step_content"),
        sa.UniqueConstraint("route_id", "sequence", name="uq_spatial_route_step_sequence"),
    )
    op.create_index("ix_spatial_route_steps_route_order", "spatial_route_steps", ["route_id", "sequence"])
    op.create_index("ix_spatial_route_steps_geom", "spatial_route_steps", ["geom"], postgresql_using="gist")

    op.create_table(
        "spatial_entity_location_links",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("source_entity_id", sa.Uuid(), sa.ForeignKey("knowledge_entities.uuid", ondelete="CASCADE"), nullable=False),
        sa.Column("location_entity_id", sa.Uuid(), sa.ForeignKey("knowledge_entities.uuid", ondelete="SET NULL")),
        sa.Column("map_point_id", sa.Uuid(), sa.ForeignKey("spatial_map_points.id", ondelete="SET NULL")),
        sa.Column("map_region_id", sa.Uuid(), sa.ForeignKey("spatial_map_regions.id", ondelete="SET NULL")),
        sa.Column("graph_relationship_id", sa.Uuid(), sa.ForeignKey("knowledge_relationships.id", ondelete="SET NULL")),
        sa.Column("external_id", sa.String(255), nullable=False), sa.Column("unresolved_location_name", sa.String(255)), sa.Column("normalized_unresolved_location_name", sa.String(255)),
        *_provenance_columns(),
        sa.CheckConstraint("confidence IN ('verified','high','medium','low','unknown')", name="ck_spatial_link_confidence"),
        sa.CheckConstraint("verification_state IN ('pending','verified','rejected','unresolved','ambiguous')", name="ck_spatial_link_verification"),
        sa.CheckConstraint("location_entity_id IS NOT NULL OR unresolved_location_name IS NOT NULL", name="ck_spatial_link_location"),
        sa.CheckConstraint("map_point_id IS NULL OR map_region_id IS NULL", name="ck_spatial_link_single_representation"),
        sa.UniqueConstraint("source_provider_id", "external_id", "version", name="uq_spatial_link_provider_version"),
    )
    op.create_index("ix_spatial_links_source_current", "spatial_entity_location_links", ["source_entity_id", "is_current"])
    op.create_index("ix_spatial_links_location_current", "spatial_entity_location_links", ["location_entity_id", "is_current"])


def downgrade() -> None:
    op.drop_table("spatial_entity_location_links")
    op.drop_table("spatial_route_steps")
    op.drop_table("spatial_routes")
    op.drop_table("spatial_map_regions")
    op.drop_table("spatial_map_points")
    codes = [code for code, _inverse, _sources, _targets in RELATIONSHIP_TYPES]
    relationship_types = sa.table(
        "knowledge_relationship_types",
        sa.column("code", sa.String()),
        sa.column("inverse_code", sa.String()),
    )
    op.execute(
        relationship_types.update()
        .where(relationship_types.c.code.in_(codes))
        .values(inverse_code=relationship_types.c.code)
    )
    op.execute(relationship_types.delete().where(relationship_types.c.code.in_(codes)))
    op.execute("UPDATE knowledge_relationship_types SET source_entity_types='[\"npc\"]'::jsonb, updated_at=now() WHERE code='located_at'")
    op.execute("DELETE FROM knowledge_entity_types WHERE entity_type IN ('map_point','map_region','route') AND NOT EXISTS (SELECT 1 FROM knowledge_entities WHERE entity_type IN ('map_point','map_region','route'))")
