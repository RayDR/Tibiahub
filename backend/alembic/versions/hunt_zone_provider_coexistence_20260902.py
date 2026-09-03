"""Allow provider Hunting Zones to coexist with legacy free-text rows.

Revision ID: hunt_zone_provider_20260902
Revises: knowledge_rel_target_20260830
"""

from alembic import op


revision = "hunt_zone_provider_20260902"
down_revision = "knowledge_rel_target_20260830"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_hunt_zones_name", table_name="hunt_zones")
    op.create_index("ix_hunt_zones_name", "hunt_zones", ["name"], unique=False)


def downgrade() -> None:
    # Deliberately do not delete or merge duplicate evidence. If provider and
    # legacy rows now share a name, PostgreSQL will refuse the downgrade until
    # an operator has reviewed the lifecycle decision explicitly.
    op.drop_index("ix_hunt_zones_name", table_name="hunt_zones")
    op.create_index("ix_hunt_zones_name", "hunt_zones", ["name"], unique=True)
