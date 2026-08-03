"""Canonical account characters, avatars, guild directory, and email outbox.

Revision ID: account_identity_20260803
Revises: guild_raffle_arch_20260802
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "account_identity_20260803"
down_revision = "guild_raffle_arch_20260802"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("primary_character_id", sa.Integer(), nullable=True))
    op.add_column("users", sa.Column("avatar_managed_key", sa.String(80), nullable=True))
    op.add_column("users", sa.Column("avatar_updated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("in_app_notifications_enabled", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("users", sa.Column("email_notifications_enabled", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_foreign_key(
        "fk_users_primary_character", "users", "user_characters",
        ["primary_character_id"], ["id"], ondelete="SET NULL", use_alter=True,
    )
    op.create_index("ix_users_primary_character_id", "users", ["primary_character_id"])
    op.create_unique_constraint("uq_users_avatar_managed_key", "users", ["avatar_managed_key"])

    for column in (
        sa.Column("verification_method", sa.String(40), nullable=True),
        sa.Column("verified_by_user_id", sa.Integer(), nullable=True),
        sa.Column("verification_reason", sa.Text(), nullable=True),
        sa.Column("unlinked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("unlinked_by_user_id", sa.Integer(), nullable=True),
    ):
        op.add_column("user_characters", column)
    op.create_foreign_key("fk_user_characters_verified_by", "user_characters", "users", ["verified_by_user_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_user_characters_unlinked_by", "user_characters", "users", ["unlinked_by_user_id"], ["id"], ondelete="SET NULL")
    op.drop_constraint("ck_user_character_ownership_status", "user_characters", type_="check")
    op.create_check_constraint(
        "ck_user_character_ownership_status", "user_characters",
        "ownership_status IN ('legacy_unverified','verified','disputed','unlinked')",
    )
    op.execute("UPDATE user_characters SET verification_method='public_comment' WHERE ownership_status='verified' AND ownership_claim_id IS NOT NULL")
    op.execute("""
        UPDATE users u SET primary_character_id = c.id
        FROM user_characters c
        WHERE c.user_id = u.id
          AND c.ownership_status = 'verified'
          AND lower(regexp_replace(btrim(c.character_name), '\\s+', ' ', 'g')) =
              lower(regexp_replace(btrim(u.tibia_character_name), '\\s+', ' ', 'g'))
          AND NOT EXISTS (
            SELECT 1 FROM user_characters conflict
            WHERE conflict.id <> c.id
              AND conflict.ownership_status = 'verified'
              AND conflict.normalized_name = c.normalized_name
          )
    """)

    op.add_column("character_ownership_claims", sa.Column("challenge_ciphertext", sa.Text(), nullable=True))

    op.create_table(
        "guild_directory",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("guild_name", sa.String(200), nullable=False),
        sa.Column("normalized_guild_name", sa.String(200), nullable=False),
        sa.Column("world_name", sa.String(100), nullable=False),
        sa.Column("normalized_world_name", sa.String(100), nullable=False),
        sa.Column("source", sa.String(50), nullable=False, server_default="verified_character"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("first_discovered_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_synchronized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_successful_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sync_status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("sync_failure_code", sa.String(80), nullable=True),
        sa.Column("member_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("leader_character_name", sa.String(100), nullable=True),
        sa.UniqueConstraint("normalized_guild_name", "normalized_world_name", name="uq_guild_directory_identity"),
    )
    op.create_index("ix_guild_directory_guild_name", "guild_directory", ["guild_name"])
    op.create_index("ix_guild_directory_normalized_guild_name", "guild_directory", ["normalized_guild_name"])
    op.create_index("ix_guild_directory_active_sync", "guild_directory", ["is_active", "last_successful_sync_at"])
    op.execute("""
        INSERT INTO guild_directory (
          guild_name, normalized_guild_name, world_name, normalized_world_name,
          source, is_active, first_discovered_at, last_synchronized_at,
          last_successful_sync_at, sync_status, member_count, leader_character_name
        )
        SELECT min(guild_name), normalized_guild_name, min(world_name), normalized_world_name,
          'tibiadata', true, min(first_synchronized_at), max(last_synchronized_at),
          max(last_synchronized_at), 'synchronized', count(*) FILTER (WHERE is_current),
          min(character_name) FILTER (WHERE lower(coalesce(guild_rank,'')) IN ('leader','guild leader','alpha warbringer'))
        FROM guild_roster_characters
        GROUP BY normalized_guild_name, normalized_world_name
    """)

    op.create_table(
        "email_outbox",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("message_type", sa.String(60), nullable=False),
        sa.Column("recipient_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("recipient_email", sa.String(320), nullable=False),
        sa.Column("locale", sa.String(8), nullable=False, server_default="en"),
        sa.Column("template_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("secret_payload_ciphertext", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.String(160), nullable=False, unique=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("safe_failure_category", sa.String(80), nullable=True),
        sa.CheckConstraint("status IN ('pending','processing','sent','retry','failed','cancelled')", name="ck_email_outbox_status"),
    )
    op.create_index("ix_email_outbox_message_type", "email_outbox", ["message_type"])
    op.create_index("ix_email_outbox_recipient_user_id", "email_outbox", ["recipient_user_id"])
    op.create_index("ix_email_outbox_status", "email_outbox", ["status"])
    op.create_index("ix_email_outbox_next_attempt_at", "email_outbox", ["next_attempt_at"])
    op.create_index("ix_email_outbox_due", "email_outbox", ["status", "next_attempt_at", "id"])

    op.create_table(
        "email_worker_heartbeats",
        sa.Column("worker_id", sa.String(100), primary_key=True),
        sa.Column("state", sa.String(30), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_job_id", sa.Integer(), sa.ForeignKey("email_outbox.id", ondelete="SET NULL"), nullable=True),
        sa.Column("version", sa.String(40), nullable=False),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failure_category", sa.String(80), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )

    op.add_column("public_event_participants", sa.Column("guild_roster_character_id", sa.Integer(), nullable=True))
    op.add_column("public_event_participants", sa.Column("user_character_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_public_event_roster_character", "public_event_participants", "guild_roster_characters", ["guild_roster_character_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_public_event_user_character", "public_event_participants", "user_characters", ["user_character_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_public_event_participants_guild_roster_character_id", "public_event_participants", ["guild_roster_character_id"])
    op.create_index("ix_public_event_participants_user_character_id", "public_event_participants", ["user_character_id"])


def downgrade() -> None:
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM email_outbox WHERE status IN ('pending','processing','retry')) THEN
        RAISE EXCEPTION 'Cannot downgrade while durable email deliveries are pending; restore a pre-migration snapshot instead';
      END IF;
    END $$""")
    op.drop_index("ix_public_event_participants_user_character_id", table_name="public_event_participants")
    op.drop_index("ix_public_event_participants_guild_roster_character_id", table_name="public_event_participants")
    op.drop_constraint("fk_public_event_user_character", "public_event_participants", type_="foreignkey")
    op.drop_constraint("fk_public_event_roster_character", "public_event_participants", type_="foreignkey")
    op.drop_column("public_event_participants", "user_character_id")
    op.drop_column("public_event_participants", "guild_roster_character_id")
    op.drop_table("email_worker_heartbeats")
    op.drop_table("email_outbox")
    op.drop_table("guild_directory")
    op.drop_column("character_ownership_claims", "challenge_ciphertext")
    op.drop_constraint("ck_user_character_ownership_status", "user_characters", type_="check")
    op.create_check_constraint(
        "ck_user_character_ownership_status", "user_characters",
        "ownership_status IN ('legacy_unverified','verified','disputed')",
    )
    op.drop_constraint("fk_user_characters_unlinked_by", "user_characters", type_="foreignkey")
    op.drop_constraint("fk_user_characters_verified_by", "user_characters", type_="foreignkey")
    for column in ("unlinked_by_user_id", "unlinked_at", "verification_reason", "verified_by_user_id", "verification_method"):
        op.drop_column("user_characters", column)
    op.drop_constraint("uq_users_avatar_managed_key", "users", type_="unique")
    op.drop_index("ix_users_primary_character_id", table_name="users")
    op.drop_constraint("fk_users_primary_character", "users", type_="foreignkey")
    for column in ("email_notifications_enabled", "in_app_notifications_enabled", "avatar_updated_at", "avatar_managed_key", "primary_character_id"):
        op.drop_column("users", column)
