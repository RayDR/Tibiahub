"""Index pending relationship target reconciliation lookups."""

from alembic import op
import sqlalchemy as sa


revision = "knowledge_rel_target_20260830"
down_revision = "creature_mapping_m2o_20260830"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_knowledge_relationships_pending_target_lookup",
        "knowledge_relationships",
        ["target_entity_type_id", "normalized_unresolved_name"],
        postgresql_where=sa.text(
            "is_current AND manual_override = false "
            "AND resolution_state IN ('unresolved','ambiguous')"
        ),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_knowledge_relationships_pending_target_lookup",
        table_name="knowledge_relationships",
    )
