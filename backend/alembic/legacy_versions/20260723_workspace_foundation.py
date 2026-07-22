"""Add focused workspace assistance audit foundation.

Revision ID: workspace_foundation_20260723
Revises: raffle_test_workflow_20260722
"""
from alembic import op
import sqlalchemy as sa

revision = "workspace_foundation_20260723"
down_revision = "raffle_test_workflow_20260722"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "workspace_audits" in set(sa.inspect(op.get_bind()).get_table_names()):
        return
    op.create_table(
        "workspace_audits",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("workspace_type", sa.String(40), nullable=False),
        sa.Column("guild_name", sa.String(200)),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("target_type", sa.String(80)),
        sa.Column("target_id", sa.String(100)),
        sa.Column("assisted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("safe_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_workspace_audits_actor_id", "workspace_audits", ["actor_id"])
    op.create_index("ix_workspace_audits_guild_name", "workspace_audits", ["guild_name"])
    op.create_index("ix_workspace_audits_action", "workspace_audits", ["action"])


def downgrade() -> None:
    if "workspace_audits" in set(sa.inspect(op.get_bind()).get_table_names()):
        op.drop_table("workspace_audits")
