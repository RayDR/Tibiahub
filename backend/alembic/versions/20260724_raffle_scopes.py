"""Normalize raffle scopes without removing legacy access modes.

Revision ID: raffle_scopes_20260724
Revises: workspace_foundation_20260723
"""
from alembic import op
import sqlalchemy as sa

revision = "raffle_scopes_20260724"
down_revision = "workspace_foundation_20260723"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("raffles")}
    if "scope_type" not in columns:
        op.add_column("raffles", sa.Column("scope_type", sa.String(20), nullable=False, server_default="guild"))
    if "world_name" not in columns:
        op.add_column("raffles", sa.Column("world_name", sa.String(100), nullable=True))
    if "access_mode" in columns:
        op.execute("UPDATE raffles SET scope_type = CASE WHEN access_mode = 'world_only' THEN 'server' WHEN access_mode = 'public' THEN 'global' ELSE 'guild' END")
    op.create_index("ix_raffles_scope_type", "raffles", ["scope_type"], unique=False)
    op.create_index("ix_raffles_world_name", "raffles", ["world_name"], unique=False)
    if "raffle_delivery_audits" not in set(sa.inspect(op.get_bind()).get_table_names()):
        op.create_table(
            "raffle_delivery_audits",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("delivery_id", sa.Integer(), sa.ForeignKey("raffle_prize_deliveries.id"), nullable=False),
            sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("previous_status", sa.String(20), nullable=False),
            sa.Column("new_status", sa.String(20), nullable=False),
            sa.Column("note", sa.Text()),
            sa.Column("admin_override", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_raffle_delivery_audits_delivery_id", "raffle_delivery_audits", ["delivery_id"])


def downgrade() -> None:
    if "raffle_delivery_audits" in set(sa.inspect(op.get_bind()).get_table_names()):
        op.drop_table("raffle_delivery_audits")
    op.drop_index("ix_raffles_world_name", table_name="raffles")
    op.drop_index("ix_raffles_scope_type", table_name="raffles")
    op.drop_column("raffles", "world_name")
    op.drop_column("raffles", "scope_type")
