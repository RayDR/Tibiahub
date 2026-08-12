"""Add independently versioned world-map floors and markers.

Revision ID: world_maps_20260812
Revises: sync_errors_20260803
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "world_maps_20260812"
down_revision = "sync_errors_20260803"
branch_labels = None
depends_on = None

JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade():
    op.create_table(
        "world_map_floors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("upstream_commit", sa.String(64), nullable=False),
        sa.Column("upstream_url", sa.String(1024), nullable=False),
        sa.Column("license_name", sa.String(64), nullable=False),
        sa.Column("attribution", sa.Text(), nullable=False),
        sa.Column("floor", sa.Integer(), nullable=False),
        sa.Column("map_path", sa.String(1024), nullable=False),
        sa.Column("pathfinding_path", sa.String(1024), nullable=True),
        sa.Column("map_sha256", sa.String(64), nullable=False),
        sa.Column("pathfinding_sha256", sa.String(64), nullable=True),
        sa.Column("width", sa.Integer(), nullable=False), sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("min_x", sa.Integer(), nullable=False), sa.Column("min_y", sa.Integer(), nullable=False),
        sa.Column("max_x", sa.Integer(), nullable=False), sa.Column("max_y", sa.Integer(), nullable=False),
        sa.Column("source_metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("provider", "upstream_commit", "floor", name="uq_world_map_floor_provider_commit_floor"),
    )
    op.create_index("ix_world_map_floors_floor", "world_map_floors", ["floor"])
    op.create_index("ix_world_map_floors_is_current", "world_map_floors", ["is_current"])
    op.create_index("uq_world_map_floor_current", "world_map_floors", ["provider", "floor"], unique=True, postgresql_where=sa.text("is_current"))
    op.create_table(
        "world_map_markers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("floor_id", sa.Integer(), sa.ForeignKey("world_map_floors.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_index", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(500), nullable=False, server_default=""),
        sa.Column("normalized_description", sa.String(500), nullable=False, server_default=""),
        sa.Column("icon", sa.String(64), nullable=True),
        sa.Column("x", sa.Integer(), nullable=False), sa.Column("y", sa.Integer(), nullable=False),
        sa.Column("floor", sa.Integer(), nullable=False),
        sa.Column("raw_data", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.UniqueConstraint("floor_id", "source_index", name="uq_world_map_marker_floor_index"),
    )
    op.create_index("ix_world_map_markers_floor_id", "world_map_markers", ["floor_id"])
    op.create_index("ix_world_map_markers_floor", "world_map_markers", ["floor"])
    op.create_index("ix_world_map_markers_normalized_description", "world_map_markers", ["normalized_description"])
    op.create_index("ix_world_map_marker_floor_xy", "world_map_markers", ["floor", "x", "y"])


def downgrade():
    op.drop_table("world_map_markers")
    op.drop_table("world_map_floors")
