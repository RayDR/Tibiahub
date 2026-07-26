"""Add the service-backed Guild Hunt Planner.

Revision ID: guild_hunt_planner_20260726
Revises: security_ownership_20260726
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "guild_hunt_planner_20260726"
down_revision = "security_ownership_20260726"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "INSERT INTO knowledge_entity_types (entity_type, display_name, enabled, metadata) "
        "VALUES ('mission','Mission',true,'{}'::jsonb) ON CONFLICT (entity_type) DO NOTHING"
    )
    op.execute(
        "UPDATE knowledge_providers SET supports_entities="
        "'[\"creature\",\"boss\",\"item\",\"quest\",\"mission\",\"access\",\"npc\",\"location\",\"area\",\"town\",\"map_point\",\"map_region\",\"route\"]'::jsonb, "
        "updated_at=now() WHERE provider_id='tibiawiki'"
    )
    op.create_table(
        "guild_hunts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("guild_name", sa.String(200), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timezone_name", sa.String(64), nullable=False, server_default="UTC"),
        sa.Column("server_name", sa.String(100), nullable=False),
        sa.Column("location", sa.String(200), nullable=False),
        sa.Column("target", sa.String(200), nullable=False),
        sa.Column("recommended_level", sa.Integer(), nullable=False),
        sa.Column("recommended_vocations", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("maximum_participants", sa.Integer(), nullable=False),
        sa.Column("required_ek", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("required_ed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("required_rp", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("required_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("discord_channel", sa.String(200), nullable=True),
        sa.Column("voice_channel", sa.String(200), nullable=True),
        sa.Column("status", sa.String(24), nullable=False, server_default="scheduled"),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("cancelled_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("cancellation_reason", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('scheduled','in_progress','finished','cancelled')", name="ck_guild_hunt_status"),
        sa.CheckConstraint("maximum_participants > 0", name="ck_guild_hunt_positive_capacity"),
        sa.CheckConstraint("recommended_level > 0", name="ck_guild_hunt_positive_level"),
        sa.CheckConstraint("required_ek >= 0 AND required_ed >= 0 AND required_rp >= 0 AND required_ms >= 0", name="ck_guild_hunt_nonnegative_roles"),
    )
    op.create_index("ix_guild_hunts_guild_schedule", "guild_hunts", ["guild_name", "scheduled_at"])
    op.create_index("ix_guild_hunts_guild_status", "guild_hunts", ["guild_name", "status"])

    op.create_table(
        "guild_hunt_participants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("hunt_id", sa.Integer(), sa.ForeignKey("guild_hunts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("character_name", sa.String(100), nullable=False),
        sa.Column("vocation", sa.String(30), nullable=True),
        sa.Column("attendance_status", sa.String(20), nullable=False, server_default="registered"),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("left_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attendance_marked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attendance_marked_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.UniqueConstraint("hunt_id", "user_id", name="uq_guild_hunt_participant_user"),
        sa.CheckConstraint("attendance_status IN ('registered','attended','absent','left')", name="ck_guild_hunt_attendance_status"),
    )
    op.create_index("ix_guild_hunt_participants_hunt_status", "guild_hunt_participants", ["hunt_id", "attendance_status"])


def downgrade() -> None:
    op.drop_index("ix_guild_hunt_participants_hunt_status", table_name="guild_hunt_participants")
    op.drop_table("guild_hunt_participants")
    op.drop_index("ix_guild_hunts_guild_status", table_name="guild_hunts")
    op.drop_index("ix_guild_hunts_guild_schedule", table_name="guild_hunts")
    op.drop_table("guild_hunts")
    op.execute(
        "UPDATE knowledge_providers SET supports_entities="
        "'[\"creature\",\"item\",\"quest\",\"npc\",\"location\",\"area\",\"town\"]'::jsonb, "
        "updated_at=now() WHERE provider_id='tibiawiki'"
    )
    op.execute(
        "DELETE FROM knowledge_entity_types WHERE entity_type='mission' "
        "AND NOT EXISTS (SELECT 1 FROM knowledge_entities WHERE entity_type='mission')"
    )
