"""Add product-polish profile, media, bestiary, quest, and guild-scope fields.

Revision ID: product_polish_20260720
Revises: add_reset_token
Create Date: 2026-07-20
"""
from alembic import op
import sqlalchemy as sa


revision = "product_polish_20260720"
down_revision = "add_reset_token"
branch_labels = None
depends_on = None


def _column_names(table: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table)}


def _add_missing_columns(table: str, columns: list[sa.Column]) -> None:
    existing = _column_names(table)
    for column in columns:
        if column.name not in existing:
            op.add_column(table, column)


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())

    if "media_assets" not in tables:
        op.create_table(
            "media_assets",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("asset_key", sa.String(255), nullable=False),
            sa.Column("source_url", sa.String(1024)),
            sa.Column("resolved_url", sa.String(1024)),
            sa.Column("local_path", sa.String(1024)),
            sa.Column("content_type", sa.String(100)),
            sa.Column("size_bytes", sa.Integer()),
            sa.Column("sha256_hash", sa.String(64)),
            sa.Column("width", sa.Integer()),
            sa.Column("height", sa.Integer()),
            sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
            sa.Column("error_message", sa.Text()),
            sa.Column("last_fetched_at", sa.DateTime(timezone=True)),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint("asset_key", name="uq_media_assets_asset_key"),
        )
        op.create_index("ix_media_assets_id", "media_assets", ["id"])
        op.create_index("ix_media_assets_asset_key", "media_assets", ["asset_key"])

    _add_missing_columns("users", [
        sa.Column("display_name", sa.String(100)),
        sa.Column("title", sa.String(100)),
    ])
    _add_missing_columns("creatures", [
        sa.Column("image_alias", sa.String(255)),
        sa.Column("image_url_override", sa.String(1024)),
        sa.Column("image_source_name", sa.String(255)),
        sa.Column("image_locked", sa.Boolean(), server_default=sa.false()),
        sa.Column("image_asset_id", sa.Integer(), sa.ForeignKey("media_assets.id")),
        sa.Column("is_hidden", sa.Boolean(), server_default=sa.false()),
    ])
    _add_missing_columns("loot", [
        sa.Column("item_image_alias", sa.String(255)),
        sa.Column("item_image_url_override", sa.String(1024)),
        sa.Column("item_image_locked", sa.Boolean(), server_default=sa.false()),
        sa.Column("image_asset_id", sa.Integer(), sa.ForeignKey("media_assets.id")),
    ])
    _add_missing_columns("hunt_zones", [
        sa.Column("slug", sa.String(150)),
        sa.Column("source_provider", sa.String(50)),
        sa.Column("region", sa.String(100)),
        sa.Column("recommended_vocations", sa.JSON()),
        sa.Column("recommended_party_size", sa.String(50)),
        sa.Column("exp_rating", sa.String(20)),
        sa.Column("profit_rating", sa.String(20)),
        sa.Column("danger_rating", sa.String(20)),
        sa.Column("map_x", sa.Integer()),
        sa.Column("map_y", sa.Integer()),
        sa.Column("map_z", sa.Integer()),
        sa.Column("map_bounds", sa.JSON()),
        sa.Column("map_asset_id", sa.Integer(), sa.ForeignKey("media_assets.id")),
    ])
    _add_missing_columns("tibiawiki_quests", [
        sa.Column("slug", sa.String(180)),
        sa.Column("source_url", sa.String(1024)),
        sa.Column("group_name", sa.String(255)),
        sa.Column("parent_page", sa.String(255)),
        sa.Column("is_group", sa.Boolean(), server_default=sa.false()),
        sa.Column("rewards", sa.JSON()),
        sa.Column("requirements", sa.JSON()),
        sa.Column("related_creatures", sa.JSON()),
        sa.Column("last_synced_at", sa.DateTime(timezone=True)),
    ])
    _add_missing_columns("announcements", [sa.Column("guild_name", sa.String(200))])
    _add_missing_columns("guild_events", [sa.Column("guild_name", sa.String(200))])
    op.execute(sa.text(
        "UPDATE announcements SET guild_name = "
        "(SELECT users.guild_name FROM users WHERE users.id = announcements.author_id) "
        "WHERE guild_name IS NULL"
    ))
    op.execute(sa.text(
        "UPDATE guild_events SET guild_name = "
        "(SELECT users.guild_name FROM users WHERE users.id = guild_events.author_id) "
        "WHERE guild_name IS NULL"
    ))


def downgrade() -> None:
    # This migration intentionally has no automatic destructive downgrade.
    # Production rollback should restore a verified backup or use a reviewed,
    # environment-specific migration after confirming no new data is needed.
    pass
