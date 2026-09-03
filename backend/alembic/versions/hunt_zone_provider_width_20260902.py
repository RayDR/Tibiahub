"""Align Hunt Zone bridge widths with provider entity contracts.

Revision ID: hunt_zone_width_20260902
Revises: hunt_zone_provider_20260902
"""

from alembic import op
import sqlalchemy as sa


revision = "hunt_zone_width_20260902"
down_revision = "hunt_zone_provider_20260902"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("hunt_zones", "name", existing_type=sa.String(100), type_=sa.String(255))
    op.alter_column("hunt_zones", "normalized_name", existing_type=sa.String(150), type_=sa.String(255))
    op.alter_column("hunt_zones", "slug", existing_type=sa.String(150), type_=sa.String(255))
    op.alter_column("hunt_zones", "source_url", existing_type=sa.String(255), type_=sa.String(1024))
    op.alter_column("hunt_zones", "map_image_url", existing_type=sa.String(255), type_=sa.String(1024))


def downgrade() -> None:
    op.alter_column("hunt_zones", "map_image_url", existing_type=sa.String(1024), type_=sa.String(255))
    op.alter_column("hunt_zones", "source_url", existing_type=sa.String(1024), type_=sa.String(255))
    op.alter_column("hunt_zones", "slug", existing_type=sa.String(255), type_=sa.String(150))
    op.alter_column("hunt_zones", "normalized_name", existing_type=sa.String(255), type_=sa.String(150))
    op.alter_column("hunt_zones", "name", existing_type=sa.String(255), type_=sa.String(100))
