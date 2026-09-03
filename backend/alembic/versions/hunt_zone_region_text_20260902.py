"""Preserve provider location prose without truncation.

Revision ID: hunt_zone_region_20260902
Revises: hunt_zone_width_20260902
"""

from alembic import op
import sqlalchemy as sa


revision = "hunt_zone_region_20260902"
down_revision = "hunt_zone_width_20260902"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("hunt_zones", "region", existing_type=sa.String(100), type_=sa.Text())


def downgrade() -> None:
    op.alter_column("hunt_zones", "region", existing_type=sa.Text(), type_=sa.String(100))
