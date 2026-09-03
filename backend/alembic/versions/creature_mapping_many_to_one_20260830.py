"""Allow multiple provider identifiers to map to one canonical entity."""

from alembic import op


revision = "creature_mapping_m2o_20260830"
down_revision = "quest_completion_20260828"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_knowledge_external_mapping_entity",
        "knowledge_external_mappings",
        type_="unique",
    )


def downgrade() -> None:
    op.create_unique_constraint(
        "uq_knowledge_external_mapping_entity",
        "knowledge_external_mappings",
        ["provider_id", "entity_type_id", "entity_uuid"],
    )
