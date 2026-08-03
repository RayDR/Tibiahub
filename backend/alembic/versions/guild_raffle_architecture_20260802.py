"""Guild roster, module grants, and external raffle participants.

Revision ID: guild_raffle_arch_20260802
Revises: guild_hunt_planner_20260726

Downgrade is intentionally refused while external-only participants exist,
because restoring a mandatory users foreign key would discard their identity.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "guild_raffle_arch_20260802"
down_revision = "guild_hunt_planner_20260726"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "guild_roster_characters",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("guild_name", sa.String(200), nullable=False),
        sa.Column("normalized_guild_name", sa.String(200), nullable=False),
        sa.Column("world_name", sa.String(100), nullable=False),
        sa.Column("normalized_world_name", sa.String(100), nullable=False),
        sa.Column("character_name", sa.String(100), nullable=False),
        sa.Column("normalized_character_name", sa.String(100), nullable=False),
        sa.Column("guild_rank", sa.String(100)),
        sa.Column("level", sa.Integer()),
        sa.Column("vocation", sa.String(100)),
        sa.Column("last_activity_at", sa.DateTime(timezone=True)),
        sa.Column("last_online_seen_at", sa.DateTime(timezone=True)),
        sa.Column("first_synchronized_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_synchronized_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("source", sa.String(50), nullable=False, server_default="tibiadata"),
        sa.Column("source_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("linked_user_character_id", sa.Integer(), sa.ForeignKey("user_characters.id", ondelete="SET NULL")),
        sa.Column("linked_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.UniqueConstraint("normalized_guild_name", "normalized_world_name", "normalized_character_name", name="uq_guild_roster_identity"),
    )
    for name, cols in (
        ("ix_guild_roster_characters_guild_name", ["guild_name"]),
        ("ix_guild_roster_characters_normalized_guild_name", ["normalized_guild_name"]),
        ("ix_guild_roster_characters_character_name", ["character_name"]),
        ("ix_guild_roster_characters_normalized_character_name", ["normalized_character_name"]),
        ("ix_guild_roster_characters_last_activity_at", ["last_activity_at"]),
        ("ix_guild_roster_characters_last_synchronized_at", ["last_synchronized_at"]),
        ("ix_guild_roster_characters_is_current", ["is_current"]),
        ("ix_guild_roster_characters_linked_user_character_id", ["linked_user_character_id"]),
        ("ix_guild_roster_characters_linked_user_id", ["linked_user_id"]),
        ("ix_guild_roster_current_activity", ["normalized_guild_name", "is_current", "last_activity_at"]),
    ):
        op.create_index(name, "guild_roster_characters", cols)

    op.create_table(
        "guild_management_grants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("guild_name", sa.String(200), nullable=False),
        sa.Column("normalized_guild_name", sa.String(200), nullable=False),
        sa.Column("capability", sa.String(80), nullable=False),
        sa.Column("granted_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_by_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("reason", sa.Text()),
        sa.Column("audit_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.UniqueConstraint("user_id", "normalized_guild_name", "capability", name="uq_guild_management_grant"),
    )
    for name, cols in (
        ("ix_guild_management_grants_user_id", ["user_id"]),
        ("ix_guild_management_grants_guild_name", ["guild_name"]),
        ("ix_guild_management_grants_normalized_guild_name", ["normalized_guild_name"]),
        ("ix_guild_management_grants_capability", ["capability"]),
    ):
        op.create_index(name, "guild_management_grants", cols)
    op.create_index("ix_guild_management_grants_active", "guild_management_grants", ["user_id", "normalized_guild_name", "capability"], postgresql_where=sa.text("revoked_at IS NULL"))

    op.add_column("raffles", sa.Column("unique_account_participation", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("raffles", sa.Column("weighting_mode", sa.String(20), nullable=False, server_default="equal"))
    op.add_column("raffles", sa.Column("published_by_character_name", sa.String(100)))
    op.create_check_constraint("ck_raffles_weighting_mode", "raffles", "weighting_mode IN ('equal','weighted')")

    for column in (
        sa.Column("guild_roster_character_id", sa.Integer()),
        sa.Column("normalized_character_name", sa.String(100)),
        sa.Column("known_account_identity_key", sa.String(100)),
        sa.Column("enforced_account_identity_key", sa.String(100)),
        sa.Column("guild_name_snapshot", sa.String(200)),
        sa.Column("world_name_snapshot", sa.String(100)),
    ):
        op.add_column("raffle_participants", column)
    op.create_foreign_key("fk_raffle_participant_roster", "raffle_participants", "guild_roster_characters", ["guild_roster_character_id"], ["id"], ondelete="SET NULL")
    op.execute("""
        UPDATE raffle_participants p SET
          normalized_character_name = lower(regexp_replace(btrim(p.character_name), '\\s+', ' ', 'g')),
          known_account_identity_key = CASE WHEN p.user_id IS NULL THEN NULL ELSE 'user:' || p.user_id::text END,
          enforced_account_identity_key = CASE WHEN p.user_id IS NULL THEN NULL ELSE 'user:' || p.user_id::text END,
          guild_name_snapshot = r.guild_name,
          world_name_snapshot = r.world_name
        FROM raffles r WHERE r.id = p.raffle_id
    """)
    op.drop_constraint("uq_raffle_participant_user", "raffle_participants", type_="unique")
    op.drop_constraint("uq_raffle_participant_character", "raffle_participants", type_="unique")
    op.execute("""
        WITH duplicates AS (
          SELECT id, row_number() OVER (
            PARTITION BY raffle_id, normalized_character_name ORDER BY is_deleted, id
          ) AS occurrence
          FROM raffle_participants WHERE is_deleted IS FALSE
        )
        UPDATE raffle_participants p SET
          is_deleted = TRUE,
          is_eligible = FALSE,
          deleted_at = now(),
          delete_reason = COALESCE(p.delete_reason, 'migration: duplicate normalized character')
        FROM duplicates d WHERE p.id = d.id AND d.occurrence > 1
    """)
    op.alter_column("raffle_participants", "user_id", existing_type=sa.Integer(), nullable=True)
    op.drop_constraint("raffle_participants_user_id_fkey", "raffle_participants", type_="foreignkey")
    op.create_foreign_key("raffle_participants_user_id_fkey", "raffle_participants", "users", ["user_id"], ["id"], ondelete="SET NULL")
    op.alter_column("raffle_participants", "normalized_character_name", nullable=False)
    op.alter_column("raffle_participants", "guild_name_snapshot", nullable=False)
    op.alter_column("raffle_participants", "weight", existing_type=sa.Float(), type_=sa.Numeric(12, 4), existing_nullable=False, postgresql_using="weight::numeric(12,4)")
    op.alter_column("raffle_participants", "weight_multiplier", existing_type=sa.Float(), type_=sa.Numeric(12, 4), existing_nullable=False, postgresql_using="weight_multiplier::numeric(12,4)")
    op.create_check_constraint("ck_raffle_participant_positive_weight", "raffle_participants", "weight > 0")
    op.create_index("ix_raffle_participants_guild_roster_character_id", "raffle_participants", ["guild_roster_character_id"])
    op.create_index("ix_raffle_participants_normalized_character_name", "raffle_participants", ["normalized_character_name"])
    op.create_index("ix_raffle_participants_known_account_identity_key", "raffle_participants", ["known_account_identity_key"])
    op.create_index("uq_raffle_active_participant_character", "raffle_participants", ["raffle_id", "normalized_character_name"], unique=True, postgresql_where=sa.text("is_deleted IS FALSE"))
    op.create_index("uq_raffle_active_known_account", "raffle_participants", ["raffle_id", "enforced_account_identity_key"], unique=True, postgresql_where=sa.text("is_deleted IS FALSE AND enforced_account_identity_key IS NOT NULL"))

    for column in (
        sa.Column("participant_id", sa.Integer()),
        sa.Column("guild_roster_character_id", sa.Integer()),
        sa.Column("normalized_character_name", sa.String(100)),
        sa.Column("known_account_identity_key", sa.String(100)),
        sa.Column("world_name", sa.String(100)),
        sa.Column("weight_snapshot", sa.Numeric(12, 4), nullable=False, server_default="1"),
    ):
        op.add_column("raffle_eligibility_entries", column)
    op.create_foreign_key("fk_raffle_eligibility_participant", "raffle_eligibility_entries", "raffle_participants", ["participant_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_raffle_eligibility_roster", "raffle_eligibility_entries", "guild_roster_characters", ["guild_roster_character_id"], ["id"], ondelete="SET NULL")
    op.execute("UPDATE raffle_eligibility_entries SET normalized_character_name = lower(regexp_replace(btrim(COALESCE(character_name, 'user-' || user_id::text)), '\\s+', ' ', 'g')), known_account_identity_key = 'user:' || user_id::text")
    op.drop_constraint("uq_raffle_snapshot_user", "raffle_eligibility_entries", type_="unique")
    op.drop_constraint("raffle_eligibility_entries_user_id_fkey", "raffle_eligibility_entries", type_="foreignkey")
    op.alter_column("raffle_eligibility_entries", "user_id", existing_type=sa.Integer(), nullable=True)
    op.create_foreign_key("raffle_eligibility_entries_user_id_fkey", "raffle_eligibility_entries", "users", ["user_id"], ["id"], ondelete="SET NULL")
    op.alter_column("raffle_eligibility_entries", "normalized_character_name", nullable=False)

    for column in (
        sa.Column("participant_roster_character_id", sa.Integer()),
        sa.Column("participant_normalized_character_name", sa.String(100)),
        sa.Column("participant_account_identity_key", sa.String(100)),
        sa.Column("participant_guild_name", sa.String(200)),
        sa.Column("participant_world_name", sa.String(100)),
        sa.Column("participant_weight", sa.Numeric(12, 4), nullable=False, server_default="1"),
    ):
        op.add_column("raffle_run_results", column)
    op.create_foreign_key("fk_raffle_run_result_roster", "raffle_run_results", "guild_roster_characters", ["participant_roster_character_id"], ["id"], ondelete="SET NULL")
    op.execute("""
        UPDATE raffle_run_results rr SET
          participant_normalized_character_name = lower(regexp_replace(btrim(rr.participant_character_name), '\\s+', ' ', 'g')),
          participant_account_identity_key = CASE WHEN rr.participant_user_id IS NULL THEN NULL ELSE 'user:' || rr.participant_user_id::text END,
          participant_guild_name = r.guild_name,
          participant_world_name = r.world_name
        FROM raffle_runs run, raffles r WHERE run.id = rr.run_id AND r.id = run.raffle_id
    """)
    op.drop_constraint("raffle_run_results_participant_user_id_fkey", "raffle_run_results", type_="foreignkey")
    op.alter_column("raffle_run_results", "participant_user_id", existing_type=sa.Integer(), nullable=True)
    op.create_foreign_key("raffle_run_results_participant_user_id_fkey", "raffle_run_results", "users", ["participant_user_id"], ["id"], ondelete="SET NULL")
    op.alter_column("raffle_run_results", "participant_normalized_character_name", nullable=False)
    op.alter_column("raffle_run_results", "participant_guild_name", nullable=False)

    op.add_column("raffle_test_audits", sa.Column("raffle_id_snapshot", sa.Integer()))
    op.add_column("raffle_test_audits", sa.Column("raffle_title_snapshot", sa.String(200)))
    op.add_column("raffle_test_audits", sa.Column("guild_name_snapshot", sa.String(200)))
    op.execute("UPDATE raffle_test_audits a SET raffle_id_snapshot=a.raffle_id, raffle_title_snapshot=r.title, guild_name_snapshot=r.guild_name FROM raffles r WHERE r.id=a.raffle_id")
    op.alter_column("raffle_test_audits", "raffle_id_snapshot", nullable=False)
    op.alter_column("raffle_test_audits", "raffle_title_snapshot", nullable=False)
    op.alter_column("raffle_test_audits", "guild_name_snapshot", nullable=False)
    op.create_index(
        op.f("ix_raffle_test_audits_raffle_id_snapshot"),
        "raffle_test_audits",
        ["raffle_id_snapshot"],
        unique=False,
    )
    op.drop_constraint("raffle_test_audits_raffle_id_fkey", "raffle_test_audits", type_="foreignkey")
    op.alter_column("raffle_test_audits", "raffle_id", existing_type=sa.Integer(), nullable=True)
    op.create_foreign_key("raffle_test_audits_raffle_id_fkey", "raffle_test_audits", "raffles", ["raffle_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    op.execute("""DO $$ BEGIN IF EXISTS (SELECT 1 FROM raffle_participants WHERE user_id IS NULL) OR EXISTS (SELECT 1 FROM raffle_eligibility_entries WHERE user_id IS NULL) OR EXISTS (SELECT 1 FROM raffle_run_results WHERE participant_user_id IS NULL) THEN RAISE EXCEPTION 'Cannot downgrade while external or deleted-user raffle identities exist'; END IF; END $$""")
    op.execute("""DO $$ BEGIN IF EXISTS (SELECT 1 FROM raffle_participants GROUP BY raffle_id, user_id HAVING count(*) > 1) THEN RAISE EXCEPTION 'Cannot downgrade while a raffle contains multiple characters for one local account'; END IF; END $$""")
    op.drop_constraint("raffle_test_audits_raffle_id_fkey", "raffle_test_audits", type_="foreignkey")
    op.alter_column("raffle_test_audits", "raffle_id", nullable=False)
    op.create_foreign_key("raffle_test_audits_raffle_id_fkey", "raffle_test_audits", "raffles", ["raffle_id"], ["id"])
    op.drop_index(op.f("ix_raffle_test_audits_raffle_id_snapshot"), table_name="raffle_test_audits")
    for column in ("guild_name_snapshot", "raffle_title_snapshot", "raffle_id_snapshot"):
        op.drop_column("raffle_test_audits", column)
    op.drop_constraint("fk_raffle_run_result_roster", "raffle_run_results", type_="foreignkey")
    op.drop_constraint("raffle_run_results_participant_user_id_fkey", "raffle_run_results", type_="foreignkey")
    op.alter_column("raffle_run_results", "participant_user_id", nullable=False)
    op.create_foreign_key("raffle_run_results_participant_user_id_fkey", "raffle_run_results", "users", ["participant_user_id"], ["id"])
    for column in ("participant_weight", "participant_world_name", "participant_guild_name", "participant_account_identity_key", "participant_normalized_character_name", "participant_roster_character_id"):
        op.drop_column("raffle_run_results", column)
    op.drop_constraint("fk_raffle_eligibility_participant", "raffle_eligibility_entries", type_="foreignkey")
    op.drop_constraint("fk_raffle_eligibility_roster", "raffle_eligibility_entries", type_="foreignkey")
    op.drop_constraint("raffle_eligibility_entries_user_id_fkey", "raffle_eligibility_entries", type_="foreignkey")
    op.alter_column("raffle_eligibility_entries", "user_id", nullable=False)
    op.create_foreign_key("raffle_eligibility_entries_user_id_fkey", "raffle_eligibility_entries", "users", ["user_id"], ["id"])
    op.create_unique_constraint("uq_raffle_snapshot_user", "raffle_eligibility_entries", ["snapshot_id", "user_id"])
    for column in ("weight_snapshot", "world_name", "known_account_identity_key", "normalized_character_name", "guild_roster_character_id", "participant_id"):
        op.drop_column("raffle_eligibility_entries", column)
    op.drop_index("uq_raffle_active_known_account", table_name="raffle_participants")
    op.drop_index("uq_raffle_active_participant_character", table_name="raffle_participants")
    op.drop_index("ix_raffle_participants_known_account_identity_key", table_name="raffle_participants")
    op.drop_index("ix_raffle_participants_normalized_character_name", table_name="raffle_participants")
    op.drop_index("ix_raffle_participants_guild_roster_character_id", table_name="raffle_participants")
    op.drop_constraint("ck_raffle_participant_positive_weight", "raffle_participants", type_="check")
    op.alter_column("raffle_participants", "weight_multiplier", type_=sa.Float(), postgresql_using="weight_multiplier::double precision")
    op.alter_column("raffle_participants", "weight", type_=sa.Float(), postgresql_using="weight::double precision")
    op.drop_constraint("fk_raffle_participant_roster", "raffle_participants", type_="foreignkey")
    op.drop_constraint("raffle_participants_user_id_fkey", "raffle_participants", type_="foreignkey")
    op.alter_column("raffle_participants", "user_id", nullable=False)
    op.create_foreign_key("raffle_participants_user_id_fkey", "raffle_participants", "users", ["user_id"], ["id"])
    for column in ("world_name_snapshot", "guild_name_snapshot", "enforced_account_identity_key", "known_account_identity_key", "normalized_character_name", "guild_roster_character_id"):
        op.drop_column("raffle_participants", column)
    op.create_unique_constraint("uq_raffle_participant_user", "raffle_participants", ["raffle_id", "user_id"])
    op.create_unique_constraint("uq_raffle_participant_character", "raffle_participants", ["raffle_id", "character_name"])
    op.drop_constraint("ck_raffles_weighting_mode", "raffles", type_="check")
    op.drop_column("raffles", "published_by_character_name")
    op.drop_column("raffles", "weighting_mode")
    op.drop_column("raffles", "unique_account_participation")
    op.drop_table("guild_management_grants")
    op.drop_table("guild_roster_characters")
