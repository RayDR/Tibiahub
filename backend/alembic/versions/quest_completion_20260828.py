"""Add per-character Quest completion state.

Revision ID: quest_completion_20260828
Revises: hunt_zone_registry_20260815
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "quest_completion_20260828"
down_revision = "hunt_zone_registry_20260815"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "quest_completions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("character_id", sa.Integer(), nullable=False),
        sa.Column("quest_id", sa.Integer(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["character_id"], ["user_characters.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["quest_id"], ["tibiawiki_quests.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("character_id", "quest_id", name="uq_quest_completion_character_quest"),
    )
    op.create_index(
        "ix_quest_completions_character",
        "quest_completions",
        ["character_id", "completed_at"],
    )
    op.create_index(
        "ix_quest_completions_quest",
        "quest_completions",
        ["quest_id", "completed_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_quest_completions_quest", table_name="quest_completions")
    op.drop_index("ix_quest_completions_character", table_name="quest_completions")
    op.drop_table("quest_completions")
