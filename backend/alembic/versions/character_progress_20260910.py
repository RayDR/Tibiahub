"""Add partial Quest progress and character-scoped activity.

Revision ID: character_progress_20260910
Revises: item_media_binding_20260906
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "character_progress_20260910"
down_revision = "item_media_binding_20260906"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "quest_completions",
        sa.Column("status", sa.String(length=20), nullable=False, server_default="completed"),
    )
    op.add_column(
        "quest_completions",
        sa.Column(
            "completed_mission_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.alter_column("quest_completions", "completed_at", existing_type=sa.DateTime(timezone=True), nullable=True)
    op.create_check_constraint(
        "ck_quest_completion_status",
        "quest_completions",
        "status IN ('in_progress','completed')",
    )

    op.add_column("user_activities", sa.Column("character_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_user_activities_character_id",
        "user_activities",
        "user_characters",
        ["character_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_user_activities_character_id", "user_activities", ["character_id"])
    op.create_index(
        "ix_user_activities_user_character_created",
        "user_activities",
        ["user_id", "character_id", "created_at"],
    )

    op.alter_column("quest_completions", "status", server_default=None)
    op.alter_column("quest_completions", "completed_mission_ids", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_user_activities_user_character_created", table_name="user_activities")
    op.drop_index("ix_user_activities_character_id", table_name="user_activities")
    op.drop_constraint("fk_user_activities_character_id", "user_activities", type_="foreignkey")
    op.drop_column("user_activities", "character_id")

    op.drop_constraint("ck_quest_completion_status", "quest_completions", type_="check")
    op.execute("DELETE FROM quest_completions WHERE status <> 'completed'")
    op.alter_column("quest_completions", "completed_at", existing_type=sa.DateTime(timezone=True), nullable=False)
    op.drop_column("quest_completions", "completed_mission_ids")
    op.drop_column("quest_completions", "status")
