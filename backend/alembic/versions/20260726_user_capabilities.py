"""Add independent moderator and writer capabilities to users.

Revision ID: user_capabilities_20260726
Revises: guild_leadership_20260725
"""
from alembic import op
import sqlalchemy as sa

revision = "user_capabilities_20260726"
down_revision = "guild_leadership_20260725"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("users")}
    if "is_moderator" not in columns:
        op.add_column("users", sa.Column("is_moderator", sa.Boolean(), nullable=False, server_default=sa.false()))
    if "is_writer" not in columns:
        op.add_column("users", sa.Column("is_writer", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("users", "is_writer")
    op.drop_column("users", "is_moderator")
