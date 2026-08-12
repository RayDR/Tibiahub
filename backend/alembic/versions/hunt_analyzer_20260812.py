"""Add moderated Hunt Analyzer storage.

Revision ID: hunt_analyzer_20260812
Revises: world_maps_20260812
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "hunt_analyzer_20260812"
down_revision = "world_maps_20260812"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("hunt_analyzer_submissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("submitted_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("zone_name", sa.String(255), nullable=False), sa.Column("normalized_zone", sa.String(255), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=False), sa.Column("raw_exp", sa.Integer(), nullable=False), sa.Column("profit", sa.Integer(), nullable=False),
        sa.Column("source_kind", sa.String(32), nullable=False), sa.Column("source_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("moderation_status", sa.String(32), nullable=False, server_default="pending"), sa.Column("moderation_reason", sa.Text(), nullable=True),
        sa.Column("moderated_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("moderated_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_hunt_analyzer_submissions_submitted_by_id", "hunt_analyzer_submissions", ["submitted_by_id"])
    op.create_index("ix_hunt_analyzer_submissions_normalized_zone", "hunt_analyzer_submissions", ["normalized_zone"])
    op.create_index("ix_hunt_analyzer_submissions_moderation_status", "hunt_analyzer_submissions", ["moderation_status"])
    op.create_index("ix_hunt_analyzer_zone_status", "hunt_analyzer_submissions", ["normalized_zone", "moderation_status"])


def downgrade():
    op.drop_table("hunt_analyzer_submissions")
