"""Bind canonical Items to existing verified MediaAsset rows.

Revision ID: item_media_binding_20260906
Revises: guild_hunt_zone_20260902
"""

from alembic import op
import sqlalchemy as sa


revision = "item_media_binding_20260906"
down_revision = "guild_hunt_zone_20260902"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tibiawiki_items",
        sa.Column("image_asset_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_tibiawiki_items_image_asset",
        "tibiawiki_items",
        "media_assets",
        ["image_asset_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_tibiawiki_items_image_asset_id",
        "tibiawiki_items",
        ["image_asset_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_tibiawiki_items_image_asset_id",
        table_name="tibiawiki_items",
    )
    op.drop_constraint(
        "fk_tibiawiki_items_image_asset",
        "tibiawiki_items",
        type_="foreignkey",
    )
    op.drop_column("tibiawiki_items", "image_asset_id")
