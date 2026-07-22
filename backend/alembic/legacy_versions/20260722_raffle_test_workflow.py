"""Add audited automatic raffle test workflow.

Revision ID: raffle_test_workflow_20260722
Revises: raffle_operations_20260721
"""
from alembic import op
import sqlalchemy as sa

revision = "raffle_test_workflow_20260722"
down_revision = "raffle_operations_20260721"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if "raffle_participants" in tables:
        columns = {column["name"] for column in inspector.get_columns("raffle_participants")}
        if "eligibility_override" not in columns:
            op.add_column("raffle_participants", sa.Column("eligibility_override", sa.Boolean(), nullable=True))
        if "eligibility_override_reason" not in columns:
            op.add_column("raffle_participants", sa.Column("eligibility_override_reason", sa.Text(), nullable=True))
    if "raffle_test_audits" in tables:
        return
    op.create_table(
        "raffle_test_audits",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("raffle_id", sa.Integer(), sa.ForeignKey("raffles.id"), nullable=False),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_raffle_test_audits_raffle_id", "raffle_test_audits", ["raffle_id"])
    op.create_index("ix_raffle_test_audits_action", "raffle_test_audits", ["action"])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if "raffle_test_audits" in tables:
        op.drop_table("raffle_test_audits")
    if "raffle_participants" in tables:
        columns = {column["name"] for column in inspector.get_columns("raffle_participants")}
        if "eligibility_override_reason" in columns:
            op.drop_column("raffle_participants", "eligibility_override_reason")
        if "eligibility_override" in columns:
            op.drop_column("raffle_participants", "eligibility_override")
