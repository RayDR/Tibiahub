"""Link scheduled Guild Hunts to canonical Hunting Zone knowledge.

Revision ID: guild_hunt_zone_20260902
Revises: hunt_zone_region_20260902
"""

from alembic import op
import sqlalchemy as sa


revision = "guild_hunt_zone_20260902"
down_revision = "hunt_zone_region_20260902"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "guild_hunts",
        sa.Column("hunting_zone_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_guild_hunts_hunting_zone_knowledge",
        "guild_hunts",
        "knowledge_entities",
        ["hunting_zone_id"],
        ["uuid"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_guild_hunts_hunting_zone_id",
        "guild_hunts",
        ["hunting_zone_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_guild_hunts_hunting_zone_id", table_name="guild_hunts")
    op.drop_constraint(
        "fk_guild_hunts_hunting_zone_knowledge",
        "guild_hunts",
        type_="foreignkey",
    )
    op.drop_column("guild_hunts", "hunting_zone_id")
