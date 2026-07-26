"""Add reset token fields to users table

Revision ID: add_reset_token
Revises: 
Create Date: 2026-01-20

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_reset_token'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Add reset_token and reset_token_expires columns to users table
    op.add_column('users', sa.Column('reset_token', sa.String(255), nullable=True))
    op.add_column('users', sa.Column('reset_token_expires', sa.DateTime(timezone=True), nullable=True))


def downgrade():
    # Remove reset_token columns
    op.drop_column('users', 'reset_token_expires')
    op.drop_column('users', 'reset_token')
