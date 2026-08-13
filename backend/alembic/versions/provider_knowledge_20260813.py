"""Preserve unknown provider values and add canonical Hunt Zone provenance.

Revision ID: provider_knowledge_20260813
Revises: hunt_analyzer_20260812
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "provider_knowledge_20260813"
down_revision = "hunt_analyzer_20260812"
branch_labels = None
depends_on = None

JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade():
    op.add_column("knowledge_providers", sa.Column(
        "provider_roles", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")
    ))
    op.add_column("knowledge_providers", sa.Column(
        "observation_capabilities", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")
    ))
    op.add_column("knowledge_providers", sa.Column(
        "spatial_capabilities", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")
    ))

    op.create_table(
        "knowledge_provider_observations",
        sa.Column("uuid", sa.Uuid(), nullable=False),
        sa.Column("provider_id", sa.String(64), sa.ForeignKey("knowledge_providers.provider_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("observation_type", sa.String(64), nullable=False),
        sa.Column("observation_key", sa.String(512), nullable=False),
        sa.Column("entity_uuid", sa.Uuid(), sa.ForeignKey("knowledge_entities.uuid", ondelete="SET NULL"), nullable=True),
        sa.Column("document_uuid", sa.Uuid(), sa.ForeignKey("knowledge_documents.uuid", ondelete="RESTRICT"), nullable=False),
        sa.Column("normalized_payload", JSONB, nullable=False),
        sa.Column("supplied_fields", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("source_url", sa.String(2048), nullable=True),
        sa.Column("normalization_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("uuid"),
        sa.UniqueConstraint(
            "provider_id", "observation_type", "observation_key", "document_uuid",
            "normalization_version", name="uq_knowledge_observation_document_version",
        ),
    )
    op.create_index(
        "uq_knowledge_observation_current", "knowledge_provider_observations",
        ["provider_id", "observation_type", "observation_key"], unique=True,
        postgresql_where=sa.text("is_current"),
    )
    op.create_index("ix_knowledge_observation_entity_time", "knowledge_provider_observations", ["entity_uuid", "observed_at"])
    op.create_index("ix_knowledge_observation_type_time", "knowledge_provider_observations", ["observation_type", "observed_at"])

    op.create_table(
        "world_map_datasets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("upstream_commit", sa.String(64), nullable=False),
        sa.Column("upstream_url", sa.String(1024), nullable=False),
        sa.Column("license_name", sa.String(64), nullable=False),
        sa.Column("attribution", sa.Text(), nullable=False),
        sa.Column("bounds", JSONB, nullable=False),
        sa.Column("manifest", JSONB, nullable=False),
        sa.Column("markers_sha256", sa.String(64), nullable=False),
        sa.Column("storage_path", sa.String(1024), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "upstream_commit", name="uq_world_map_dataset_provider_commit"),
    )
    op.create_index(
        "uq_world_map_dataset_current", "world_map_datasets", ["provider"], unique=True,
        postgresql_where=sa.text("is_current"),
    )
    op.add_column("world_map_floors", sa.Column(
        "dataset_id", sa.Integer(), sa.ForeignKey("world_map_datasets.id", ondelete="RESTRICT"), nullable=True,
    ))
    op.create_index("ix_world_map_floors_dataset_id", "world_map_floors", ["dataset_id"])
    op.add_column("world_map_markers", sa.Column(
        "resolved_entity_id", sa.Uuid(), sa.ForeignKey("knowledge_entities.uuid", ondelete="SET NULL"), nullable=True,
    ))
    op.add_column("world_map_markers", sa.Column("resolution_state", sa.String(32), nullable=False, server_default="unresolved"))
    op.add_column("world_map_markers", sa.Column("resolution_method", sa.String(64), nullable=True))
    op.create_index("ix_world_map_markers_resolved_entity_id", "world_map_markers", ["resolved_entity_id"])
    op.create_index("ix_world_map_markers_resolution_state", "world_map_markers", ["resolution_state"])

    op.add_column("hunt_zones", sa.Column("external_id", sa.String(100), nullable=True))
    op.add_column("hunt_zones", sa.Column(
        "knowledge_entity_id",
        sa.Uuid(),
        sa.ForeignKey("knowledge_entities.uuid", ondelete="SET NULL"),
        nullable=True,
    ))
    op.add_column("hunt_zones", sa.Column("provider_metadata", JSONB, nullable=True))
    op.add_column("hunt_zones", sa.Column("supplied_fields", JSONB, nullable=True))
    op.add_column("hunt_zones", sa.Column(
        "protected_fields", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")
    ))
    op.add_column("hunt_zones", sa.Column("data_version", sa.Integer(), nullable=False, server_default="1"))
    op.create_index("ix_hunt_zones_external_id", "hunt_zones", ["external_id"])
    op.create_index("uq_hunt_zones_knowledge_entity_id", "hunt_zones", ["knowledge_entity_id"], unique=True)
    op.create_unique_constraint(
        "uq_hunt_zones_source_external", "hunt_zones", ["source_provider", "external_id"]
    )

    op.alter_column("hunt_zones", "min_level", existing_type=sa.Integer(), nullable=True)
    for column in (
        "knights_recommended", "paladins_recommended", "sorcerers_recommended",
        "druids_recommended", "monks_recommended", "requires_quest", "requires_premium",
    ):
        op.alter_column(
            "hunt_zones", column, existing_type=sa.Boolean(), nullable=True, server_default=None,
        )

    for column in ("hitpoints", "experience", "armor", "speed"):
        op.alter_column(
            "creatures", column, existing_type=sa.Integer(), nullable=True, server_default=None,
        )
    for column, default in (("tradeable", sa.true()), ("stackable", sa.false())):
        op.alter_column(
            "tibiawiki_items", column, existing_type=sa.Boolean(), nullable=True, server_default=None,
        )


def downgrade():
    # The old schema cannot express unknowns; only a deliberate downgrade
    # restores its historical compatibility defaults.
    op.execute("UPDATE tibiawiki_items SET tradeable = true WHERE tradeable IS NULL")
    op.execute("UPDATE tibiawiki_items SET stackable = false WHERE stackable IS NULL")
    for column, default in (("tradeable", sa.true()), ("stackable", sa.false())):
        op.alter_column(
            "tibiawiki_items", column, existing_type=sa.Boolean(), nullable=False,
            server_default=default,
        )
    for column in ("hitpoints", "experience", "armor", "speed"):
        op.execute(f"UPDATE creatures SET {column} = 0 WHERE {column} IS NULL")
        op.alter_column(
            "creatures", column, existing_type=sa.Integer(), nullable=False,
            server_default=sa.text("0") if column in {"armor", "speed"} else None,
        )
    for column in (
        "knights_recommended", "paladins_recommended", "sorcerers_recommended",
        "druids_recommended", "monks_recommended", "requires_quest", "requires_premium",
    ):
        op.execute(f"UPDATE hunt_zones SET {column} = false WHERE {column} IS NULL")
        op.alter_column(
            "hunt_zones", column, existing_type=sa.Boolean(), nullable=False, server_default=sa.false(),
        )
    op.execute("UPDATE hunt_zones SET min_level = 0 WHERE min_level IS NULL")
    op.alter_column("hunt_zones", "min_level", existing_type=sa.Integer(), nullable=False)

    op.drop_constraint("uq_hunt_zones_source_external", "hunt_zones", type_="unique")
    op.drop_index("uq_hunt_zones_knowledge_entity_id", table_name="hunt_zones")
    op.drop_index("ix_hunt_zones_external_id", table_name="hunt_zones")
    for column in (
        "data_version", "protected_fields", "supplied_fields", "provider_metadata",
        "knowledge_entity_id", "external_id",
    ):
        op.drop_column("hunt_zones", column)

    op.drop_index("ix_world_map_markers_resolution_state", table_name="world_map_markers")
    op.drop_index("ix_world_map_markers_resolved_entity_id", table_name="world_map_markers")
    op.drop_column("world_map_markers", "resolution_method")
    op.drop_column("world_map_markers", "resolution_state")
    op.drop_column("world_map_markers", "resolved_entity_id")
    op.drop_index("ix_world_map_floors_dataset_id", table_name="world_map_floors")
    op.drop_column("world_map_floors", "dataset_id")
    op.drop_index("uq_world_map_dataset_current", table_name="world_map_datasets")
    op.drop_table("world_map_datasets")
    op.drop_index("ix_knowledge_observation_type_time", table_name="knowledge_provider_observations")
    op.drop_index("ix_knowledge_observation_entity_time", table_name="knowledge_provider_observations")
    op.drop_index("uq_knowledge_observation_current", table_name="knowledge_provider_observations")
    op.drop_table("knowledge_provider_observations")
    op.drop_column("knowledge_providers", "spatial_capabilities")
    op.drop_column("knowledge_providers", "observation_capabilities")
    op.drop_column("knowledge_providers", "provider_roles")
