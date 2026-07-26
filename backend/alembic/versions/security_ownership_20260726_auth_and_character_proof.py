"""Secure auth tokens and proof-based character ownership.

Revision ID: security_ownership_20260726
Revises: maps_postgis_20260724
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "security_ownership_20260726"
down_revision = "maps_postgis_20260724"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "auth_one_time_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("purpose", sa.String(40), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("purpose IN ('password_reset','email_verification')", name="ck_auth_token_purpose"),
        sa.CheckConstraint("length(token_hash) = 64", name="ck_auth_token_hash_length"),
    )
    op.create_index("ix_auth_one_time_tokens_lookup", "auth_one_time_tokens", ["purpose", "token_hash"], unique=True)
    op.create_index("ix_auth_one_time_tokens_user_recent", "auth_one_time_tokens", ["user_id", "purpose", "created_at"])

    op.create_table(
        "auth_request_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("purpose", sa.String(40), nullable=False),
        sa.Column("subject_hash", sa.String(64), nullable=False),
        sa.Column("requester_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("purpose IN ('password_reset','email_verification')", name="ck_auth_request_purpose"),
    )
    op.create_index("ix_auth_request_events_subject_recent", "auth_request_events", ["purpose", "subject_hash", "created_at"])
    op.create_index("ix_auth_request_events_requester_recent", "auth_request_events", ["purpose", "requester_hash", "created_at"])

    op.create_table(
        "character_ownership_claims",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("character_name", sa.String(100), nullable=False),
        sa.Column("normalized_name", sa.String(100), nullable=False),
        sa.Column("challenge_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verification_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("safe_failure_code", sa.String(50), nullable=True),
        sa.Column("dispute_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('pending','queued','processing','verified','transfer_pending','disputed','rejected','expired','failed')",
            name="ck_character_claim_status",
        ),
        sa.CheckConstraint("length(challenge_hash) = 64", name="ck_character_claim_hash_length"),
    )
    op.create_index("ix_character_ownership_claims_user_id", "character_ownership_claims", ["user_id"])
    op.create_index("ix_character_ownership_claims_normalized_name", "character_ownership_claims", ["normalized_name"])
    op.create_index("ix_character_ownership_claims_status", "character_ownership_claims", ["status"])
    op.create_index("ix_character_claims_queue", "character_ownership_claims", ["status", "next_attempt_at", "id"])
    op.create_index(
        "uq_character_active_claim_user_name",
        "character_ownership_claims",
        ["user_id", "normalized_name"],
        unique=True,
        postgresql_where=sa.text("status IN ('pending','queued','processing','transfer_pending','disputed')"),
    )

    op.create_table(
        "character_ownership_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("normalized_name", sa.String(100), nullable=False),
        sa.Column("character_name", sa.String(100), nullable=False),
        sa.Column("claim_id", sa.Integer(), sa.ForeignKey("character_ownership_claims.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("from_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("to_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("safe_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_character_ownership_history_name", "character_ownership_history", ["normalized_name", "created_at"])

    op.add_column("user_characters", sa.Column("normalized_name", sa.String(100), nullable=True))
    op.add_column("user_characters", sa.Column("ownership_status", sa.String(30), nullable=False, server_default="legacy_unverified"))
    op.add_column("user_characters", sa.Column("ownership_verified_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("user_characters", sa.Column("ownership_claim_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_user_characters_ownership_claim",
        "user_characters", "character_ownership_claims",
        ["ownership_claim_id"], ["id"], ondelete="SET NULL",
    )
    op.execute("UPDATE user_characters SET normalized_name = lower(trim(regexp_replace(character_name, '\\s+', ' ', 'g'))) WHERE normalized_name IS NULL")
    op.create_index("ix_user_characters_normalized_name", "user_characters", ["normalized_name"])
    op.create_index(
        "uq_user_characters_verified_normalized_name",
        "user_characters", ["normalized_name"], unique=True,
        postgresql_where=sa.text("ownership_status = 'verified'"),
    )
    op.create_check_constraint(
        "ck_user_character_verified_has_normalized_name",
        "user_characters",
        "ownership_status != 'verified' OR normalized_name IS NOT NULL",
    )
    op.create_check_constraint(
        "ck_user_character_ownership_status",
        "user_characters",
        "ownership_status IN ('legacy_unverified','verified','disputed')",
    )

    # Ownership history is append-only even for direct SQL operators. Corrections
    # are represented as new history rows, never rewrites.
    op.execute("""
        CREATE FUNCTION tibiahub_ownership_history_immutable() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'character ownership history is immutable';
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER trg_character_ownership_history_immutable
        BEFORE UPDATE OR DELETE ON character_ownership_history
        FOR EACH ROW EXECUTE FUNCTION tibiahub_ownership_history_immutable()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_character_ownership_history_immutable ON character_ownership_history")
    op.execute("DROP FUNCTION IF EXISTS tibiahub_ownership_history_immutable()")
    op.drop_constraint("ck_user_character_ownership_status", "user_characters", type_="check")
    op.drop_constraint("ck_user_character_verified_has_normalized_name", "user_characters", type_="check")
    op.drop_index("uq_user_characters_verified_normalized_name", table_name="user_characters")
    op.drop_index("ix_user_characters_normalized_name", table_name="user_characters")
    op.drop_constraint("fk_user_characters_ownership_claim", "user_characters", type_="foreignkey")
    op.drop_column("user_characters", "ownership_claim_id")
    op.drop_column("user_characters", "ownership_verified_at")
    op.drop_column("user_characters", "ownership_status")
    op.drop_column("user_characters", "normalized_name")
    op.drop_index("ix_character_ownership_history_name", table_name="character_ownership_history")
    op.drop_table("character_ownership_history")
    op.drop_index("uq_character_active_claim_user_name", table_name="character_ownership_claims")
    op.drop_index("ix_character_claims_queue", table_name="character_ownership_claims")
    op.drop_index("ix_character_ownership_claims_status", table_name="character_ownership_claims")
    op.drop_index("ix_character_ownership_claims_normalized_name", table_name="character_ownership_claims")
    op.drop_index("ix_character_ownership_claims_user_id", table_name="character_ownership_claims")
    op.drop_table("character_ownership_claims")
    op.drop_index("ix_auth_request_events_requester_recent", table_name="auth_request_events")
    op.drop_index("ix_auth_request_events_subject_recent", table_name="auth_request_events")
    op.drop_table("auth_request_events")
    op.drop_index("ix_auth_one_time_tokens_user_recent", table_name="auth_one_time_tokens")
    op.drop_index("ix_auth_one_time_tokens_lookup", table_name="auth_one_time_tokens")
    op.drop_table("auth_one_time_tokens")
    op.drop_column("users", "email_verified_at")
