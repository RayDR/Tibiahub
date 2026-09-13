"""Separate creature behaviour/strategy/notes semantics.

Revision ID: creature_semantics_20260912
Revises: character_progress_20260910
"""

from alembic import op
import sqlalchemy as sa


revision = "creature_semantics_20260912"
down_revision = "character_progress_20260910"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "creatures",
        sa.Column("strategy", sa.Text(), nullable=True),
    )
    op.add_column(
        "creatures",
        sa.Column("notes", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("creatures", "notes")
    op.drop_column("creatures", "strategy")
