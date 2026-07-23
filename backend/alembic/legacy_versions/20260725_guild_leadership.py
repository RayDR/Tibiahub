"""Add extensible guild leadership and recruitment foundation.

Revision ID: guild_leadership_20260725
Revises: raffle_scopes_20260724
"""
from alembic import op
import sqlalchemy as sa

revision = "guild_leadership_20260725"
down_revision = "raffle_scopes_20260724"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("guild_leadership_roles",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("guild_name", sa.String(200), nullable=False),
        sa.Column("role_code", sa.String(50), nullable=False), sa.Column("display_name_key", sa.String(200), nullable=False),
        sa.Column("description_key", sa.String(200), nullable=False), sa.Column("target_count", sa.Integer(), nullable=False, server_default="4"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("recruitment_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.UniqueConstraint("guild_name", "role_code", name="uq_leadership_role_guild_code"))
    op.create_index("ix_guild_leadership_roles_guild_name", "guild_leadership_roles", ["guild_name"])
    op.create_table("guild_leadership_openings",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("guild_name", sa.String(200), nullable=False),
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("guild_leadership_roles.id"), nullable=False), sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text()), sa.Column("responsibilities", sa.Text(), nullable=False), sa.Column("requirements", sa.Text(), nullable=False),
        sa.Column("openings_count", sa.Integer(), nullable=False, server_default="1"), sa.Column("application_deadline", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"), sa.Column("allow_viceleader_review", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("voting_enabled", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("votes_required", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("opened_at", sa.DateTime(timezone=True)), sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    op.create_index("ix_guild_leadership_openings_guild_name", "guild_leadership_openings", ["guild_name"]); op.create_index("ix_guild_leadership_openings_role_id", "guild_leadership_openings", ["role_id"]); op.create_index("ix_guild_leadership_openings_status", "guild_leadership_openings", ["status"])
    op.create_table("guild_leadership_assignments",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("guild_name", sa.String(200), nullable=False), sa.Column("role_id", sa.Integer(), sa.ForeignKey("guild_leadership_roles.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("character_name", sa.String(100), nullable=False), sa.Column("assigned_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("assignment_source", sa.String(40), nullable=False, server_default="recruitment"), sa.Column("started_at", sa.DateTime(timezone=True), nullable=False), sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("notes", sa.Text()), sa.Column("in_game_promotion_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("in_game_promoted_at", sa.DateTime(timezone=True)), sa.Column("in_game_promoted_by_id", sa.Integer(), sa.ForeignKey("users.id")))
    op.create_index("ix_guild_leadership_assignments_guild_name", "guild_leadership_assignments", ["guild_name"]); op.create_index("ix_guild_leadership_assignments_role_id", "guild_leadership_assignments", ["role_id"]); op.create_index("ix_guild_leadership_assignments_user_id", "guild_leadership_assignments", ["user_id"])
    op.create_index("uq_leadership_active_assignment", "guild_leadership_assignments", ["guild_name", "role_id", "user_id"], unique=True, sqlite_where=sa.text("is_active = 1"), postgresql_where=sa.text("is_active IS TRUE"))
    op.create_table("guild_leadership_applications",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("opening_id", sa.Integer(), sa.ForeignKey("guild_leadership_openings.id"), nullable=False), sa.Column("applicant_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("character_name", sa.String(100), nullable=False), sa.Column("status", sa.String(40), nullable=False, server_default="applied"), sa.Column("why_apply", sa.Text(), nullable=False),
        sa.Column("contribution", sa.Text(), nullable=False), sa.Column("availability", sa.Text(), nullable=False), sa.Column("leadership_experience", sa.Text(), nullable=False), sa.Column("applicant_message", sa.Text()),
        sa.Column("profile_snapshot", sa.JSON(), nullable=False), sa.Column("conduct_agreed_at", sa.DateTime(timezone=True), nullable=False), sa.Column("conduct_version", sa.String(30), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False), sa.Column("withdrawn_at", sa.DateTime(timezone=True)), sa.Column("final_decision_at", sa.DateTime(timezone=True)),
        sa.Column("final_decision_by_id", sa.Integer(), sa.ForeignKey("users.id")), sa.Column("rejection_reason", sa.Text()), sa.Column("accepted_assignment_id", sa.Integer(), sa.ForeignKey("guild_leadership_assignments.id")),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_index("ix_guild_leadership_applications_opening_id", "guild_leadership_applications", ["opening_id"]); op.create_index("ix_guild_leadership_applications_applicant_user_id", "guild_leadership_applications", ["applicant_user_id"]); op.create_index("ix_guild_leadership_applications_status", "guild_leadership_applications", ["status"])
    op.create_index("uq_leadership_active_application", "guild_leadership_applications", ["opening_id", "applicant_user_id"], unique=True, sqlite_where=sa.text("status IN ('applied','under_review','more_information_requested','interview','voting')"), postgresql_where=sa.text("status IN ('applied','under_review','more_information_requested','interview','voting')"))
    op.create_table("guild_leadership_application_history", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("application_id", sa.Integer(), sa.ForeignKey("guild_leadership_applications.id"), nullable=False), sa.Column("from_status", sa.String(40)), sa.Column("to_status", sa.String(40), nullable=False), sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("actor_context", sa.String(40), nullable=False), sa.Column("reason", sa.Text()), sa.Column("safe_metadata", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_index("ix_guild_leadership_application_history_application_id", "guild_leadership_application_history", ["application_id"])
    op.create_table("guild_leadership_application_messages", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("application_id", sa.Integer(), sa.ForeignKey("guild_leadership_applications.id"), nullable=False), sa.Column("author_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("audience", sa.String(20), nullable=False), sa.Column("message_type", sa.String(40), nullable=False), sa.Column("body", sa.Text(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("edited_at", sa.DateTime(timezone=True)), sa.Column("deleted_at", sa.DateTime(timezone=True)))
    op.create_index("ix_guild_leadership_application_messages_application_id", "guild_leadership_application_messages", ["application_id"])
    op.create_table("guild_leadership_interviews", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("application_id", sa.Integer(), sa.ForeignKey("guild_leadership_applications.id"), nullable=False, unique=True), sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False), sa.Column("timezone", sa.String(64), nullable=False), sa.Column("meeting_location", sa.String(255), nullable=False), sa.Column("interview_notes", sa.Text()), sa.Column("completed_at", sa.DateTime(timezone=True)), sa.Column("completed_by_id", sa.Integer(), sa.ForeignKey("users.id")), sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_table("guild_leadership_votes", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("application_id", sa.Integer(), sa.ForeignKey("guild_leadership_applications.id"), nullable=False), sa.Column("voter_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("vote", sa.String(20), nullable=False), sa.Column("comment", sa.Text()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.UniqueConstraint("application_id", "voter_user_id", name="uq_leadership_vote_application_voter"))
    op.create_index("ix_guild_leadership_votes_application_id", "guild_leadership_votes", ["application_id"])


def downgrade() -> None:
    # Deliberately non-destructive: leadership decisions and audit history must be preserved.
    pass
