"""
Extended models for Tibia items, quests, and hunting places
Stores complete data from external APIs locally
Note: Quest and Quest models already exist - these are for API synced data
"""
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, Boolean, ForeignKey, Index, UniqueConstraint, Uuid, text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from uuid import uuid4
from app.db.database import Base
from app.db.types import JSONBType

class Item(Base):
    """Store item data from TibiaWiki API"""
    __tablename__ = "tibiawiki_items"
    __table_args__ = (
        UniqueConstraint("source_name", "external_id", name="uq_tibiawiki_items_source_external"),
        Index("uq_tibiawiki_items_knowledge_entity_id", "knowledge_entity_id", unique=True),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), index=True, nullable=False)
    normalized_name = Column(String(255), nullable=True, index=True)
    slug = Column(String(255), nullable=True, index=True)
    item_id = Column(Integer, nullable=True, unique=True)  # Tibia item ID
    external_id = Column(String(100), nullable=True, index=True)  # Stable provider page ID
    source_name = Column(String(50), nullable=True, index=True)
    source_url = Column(String(1024), nullable=True)
    image_url = Column(String(1024), nullable=True)
    knowledge_entity_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("knowledge_entities.uuid", ondelete="SET NULL"),
        nullable=True,
    )
    data_version = Column(Integer, nullable=False, default=1)
    protected_fields = Column(JSONBType, nullable=False, default=list)
    description = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    type = Column(String(100), nullable=True, index=True)  # e.g., "weapon", "armor", "consumable"
    item_class = Column(String(100), nullable=True, index=True)
    category = Column(String(100), nullable=True, index=True)
    
    # Item properties
    weight = Column(Float, nullable=True)
    value = Column(Integer, nullable=True)
    attack = Column(Integer, nullable=True)
    defense = Column(Integer, nullable=True)
    armor = Column(Integer, nullable=True)
    range = Column(Integer, nullable=True)
    imbuement_slots = Column(Integer, nullable=True)
    slots = Column(JSONBType, nullable=False, default=list)
    attributes = Column(JSONBType, nullable=False, default=dict)
    resistances = Column(JSONBType, nullable=False, default=dict)
    bonuses = Column(JSONBType, nullable=False, default=dict)
    
    # Requirements
    level_required = Column(Integer, nullable=True)
    vocation_required = Column(String(100), nullable=True)
    vocation_requirements = Column(JSONBType, nullable=False, default=list)
    
    # Classification
    tradeable = Column(Boolean, nullable=True)
    stackable = Column(Boolean, nullable=True)
    buy_from = Column(JSONBType, nullable=False, default=list)
    sell_to = Column(JSONBType, nullable=False, default=list)
    rewards_from = Column(JSONBType, nullable=False, default=list)
    required_for = Column(JSONBType, nullable=False, default=list)
    
    # Full raw data from API
    raw_data = Column(JSONBType, nullable=True)
    last_synced_at = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    knowledge_entity = relationship("KnowledgeEntity")

class HuntingPlace(Base):
    """Store hunting place data from TibiaWiki API"""
    __tablename__ = "tibiawiki_hunting_places"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    location = Column(String(255), nullable=True)
    
    # Difficulty
    min_level_recommended = Column(Integer, nullable=True)
    max_level_recommended = Column(Integer, nullable=True)
    
    # Creatures
    creatures = Column(JSONBType, nullable=True)  # List of creature names found here
    
    # Loot
    loot_expectation = Column(String(50), nullable=True)  # e.g., "low", "medium", "high"
    common_loot = Column(JSONBType, nullable=True)
    
    # Full raw data from API
    raw_data = Column(JSONBType, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class TibiaWikiNpc(Base):
    """Canonical NPC bridge populated only by the Knowledge worker."""

    __tablename__ = "tibiawiki_npcs"
    __table_args__ = (
        UniqueConstraint("source_name", "external_id", name="uq_tibiawiki_npcs_source_external"),
        Index("uq_tibiawiki_npcs_knowledge_entity_id", "knowledge_entity_id", unique=True),
    )

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False, index=True)
    normalized_name = Column(String(255), nullable=False, index=True)
    slug = Column(String(180), nullable=False, index=True)
    external_id = Column(String(100), nullable=False, index=True)
    source_name = Column(String(50), nullable=False, index=True)
    source_url = Column(String(1024), nullable=True)
    image_url = Column(String(1024), nullable=True)
    knowledge_entity_id = Column(Uuid(as_uuid=True), ForeignKey("knowledge_entities.uuid", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=True)
    occupation = Column(String(255), nullable=True)
    sex = Column(String(32), nullable=True)
    location_name = Column(String(255), nullable=True, index=True)
    description = Column(Text, nullable=True)
    buys = Column(JSONBType, nullable=False, default=list)
    sells = Column(JSONBType, nullable=False, default=list)
    destinations = Column(JSONBType, nullable=False, default=list)
    related_quests = Column(JSONBType, nullable=False, default=list)
    provider_metadata = Column(JSONBType, nullable=False, default=dict)
    supplied_fields = Column(JSONBType, nullable=False, default=list)
    protected_fields = Column(JSONBType, nullable=False, default=list)
    data_version = Column(Integer, nullable=False, default=1)
    last_synced_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    knowledge_entity = relationship("KnowledgeEntity")


class TibiaWikiLocation(Base):
    """Canonical named location bridge; coordinates and map data stay out of scope."""

    __tablename__ = "tibiawiki_locations"
    __table_args__ = (
        UniqueConstraint("source_name", "external_id", name="uq_tibiawiki_locations_source_external"),
        Index("uq_tibiawiki_locations_knowledge_entity_id", "knowledge_entity_id", unique=True),
    )

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False, index=True)
    normalized_name = Column(String(255), nullable=False, index=True)
    slug = Column(String(180), nullable=False, index=True)
    external_id = Column(String(100), nullable=False, index=True)
    source_name = Column(String(50), nullable=False, index=True)
    source_url = Column(String(1024), nullable=True)
    image_url = Column(String(1024), nullable=True)
    knowledge_entity_id = Column(Uuid(as_uuid=True), ForeignKey("knowledge_entities.uuid", ondelete="CASCADE"), nullable=False)
    location_kind = Column(String(100), nullable=True, index=True)
    region = Column(String(255), nullable=True, index=True)
    parent_location = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    premium_required = Column(Boolean, nullable=True)
    minimum_level = Column(Integer, nullable=True)
    maximum_level = Column(Integer, nullable=True)
    npcs = Column(JSONBType, nullable=False, default=list)
    creatures = Column(JSONBType, nullable=False, default=list)
    quests = Column(JSONBType, nullable=False, default=list)
    sublocations = Column(JSONBType, nullable=False, default=list)
    access_notes = Column(Text, nullable=True)
    provider_metadata = Column(JSONBType, nullable=False, default=dict)
    supplied_fields = Column(JSONBType, nullable=False, default=list)
    protected_fields = Column(JSONBType, nullable=False, default=list)
    data_version = Column(Integer, nullable=False, default=1)
    last_synced_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    knowledge_entity = relationship("KnowledgeEntity")

class TibiaWikiQuest(Base):
    """Store quest data from TibiaWiki API"""
    __tablename__ = "tibiawiki_quests"
    __table_args__ = (
        UniqueConstraint("source_name", "external_id", name="uq_tibiawiki_quests_source_external"),
        Index("uq_tibiawiki_quests_knowledge_entity_id", "knowledge_entity_id", unique=True),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), index=True, nullable=False)
    normalized_name = Column(String(255), nullable=True, index=True)
    slug = Column(String(180), nullable=True, index=True)
    external_id = Column(String(100), nullable=True, index=True)
    source_name = Column(String(50), nullable=True, index=True)
    description = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    source_url = Column(String(1024), nullable=True)
    image_url = Column(String(1024), nullable=True)
    knowledge_entity_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("knowledge_entities.uuid", ondelete="SET NULL"),
        nullable=True,
    )
    data_version = Column(Integer, nullable=False, default=1)
    protected_fields = Column(JSONBType, nullable=False, default=list)
    group_name = Column(String(255), nullable=True)
    parent_page = Column(String(255), nullable=True)
    is_group = Column(Boolean, default=False, nullable=False)
    quest_type = Column(String(100), nullable=True, index=True)
    category = Column(String(100), nullable=True, index=True)
    difficulty = Column(String(100), nullable=True)
    
    # Quest properties
    min_level = Column(Integer, nullable=True)
    max_level = Column(Integer, nullable=True)
    experience_reward = Column(Integer, nullable=True)
    treasure = Column(JSONBType, nullable=True)  # List of reward items
    
    # Quest details
    duration = Column(String(100), nullable=True)  # e.g., "daily", "repeatable", "one-time"
    premium_required = Column(Boolean, nullable=True, index=True)
    repeatable = Column(Boolean, nullable=True, index=True)
    solo_possible = Column(Boolean, nullable=True)
    location = Column(String(255), nullable=True)
    npc = Column(String(255), nullable=True)  # NPC who gives the quest
    rewards = Column(JSONBType, nullable=True)
    requirements = Column(JSONBType, nullable=True)
    related_creatures = Column(JSONBType, nullable=True)
    starting_npcs = Column(JSONBType, nullable=False, default=list)
    related_npcs = Column(JSONBType, nullable=False, default=list)
    required_items = Column(JSONBType, nullable=False, default=list)
    rewarded_items = Column(JSONBType, nullable=False, default=list)
    required_quests = Column(JSONBType, nullable=False, default=list)
    unlocked_quests = Column(JSONBType, nullable=False, default=list)
    required_creatures = Column(JSONBType, nullable=False, default=list)
    bosses = Column(JSONBType, nullable=False, default=list)
    locations = Column(JSONBType, nullable=False, default=list)
    access_unlocks = Column(JSONBType, nullable=False, default=list)
    parser_metadata = Column(JSONBType, nullable=False, default=dict)
    last_synced_at = Column(DateTime(timezone=True), nullable=True)
    
    # Full raw data from API
    raw_data = Column(JSONBType, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    knowledge_entity = relationship("KnowledgeEntity")
    missions = relationship(
        "QuestMission",
        back_populates="quest",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="QuestMission.sequence",
    )


class QuestMission(Base):
    """Stable, ordered mission normalized from one quest provider document."""

    __tablename__ = "quest_missions"
    __table_args__ = (
        UniqueConstraint("quest_id", "provider_id", "identity_key", name="uq_quest_mission_identity"),
        UniqueConstraint("quest_id", "sequence", name="uq_quest_mission_sequence"),
        Index("ix_quest_missions_quest_sequence", "quest_id", "sequence"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    quest_id = Column(Integer, ForeignKey("tibiawiki_quests.id", ondelete="CASCADE"), nullable=False)
    provider_id = Column(String(64), ForeignKey("knowledge_providers.provider_id", ondelete="RESTRICT"), nullable=False)
    external_id = Column(String(255), nullable=True)
    identity_key = Column(String(512), nullable=False)
    title = Column(String(255), nullable=False)
    normalized_title = Column(String(255), nullable=False)
    sequence = Column(Integer, nullable=False)
    description = Column(Text, nullable=True)
    objectives = Column(JSONBType, nullable=False, default=list)
    required_items = Column(JSONBType, nullable=False, default=list)
    rewarded_items = Column(JSONBType, nullable=False, default=list)
    related_npcs = Column(JSONBType, nullable=False, default=list)
    related_creatures = Column(JSONBType, nullable=False, default=list)
    locations = Column(JSONBType, nullable=False, default=list)
    supplied_fields = Column(JSONBType, nullable=False, default=list)
    protected_fields = Column(JSONBType, nullable=False, default=list)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    quest = relationship("TibiaWikiQuest", back_populates="missions")

class APISync(Base):
    """Track API synchronization logs and progress"""
    __tablename__ = "api_syncs"
    
    id = Column(Integer, primary_key=True, index=True)
    api_name = Column(String(100), index=True, nullable=False)  # "creatures", "items", "hunting_places", "quests"
    endpoint = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False)  # "pending", "running", "success", "error"
    source = Column(String(50), nullable=True)  # "tibiawiki", "tibiadata", "local"
    
    # Progress tracking
    total_items = Column(Integer, nullable=True)
    processed_items = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    
    # Details
    message = Column(Text, nullable=True)
    error_details = Column(Text, nullable=True)
    
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class SyncJob(Base):
    """Persistent async sync job status."""
    __tablename__ = "sync_jobs"
    __table_args__ = (
        Index(
            "uq_sync_jobs_one_active_full", "job_type", unique=True,
            postgresql_where=text("job_type = 'full' AND status IN ('pending','running')"),
            sqlite_where=text("job_type = 'full' AND status IN ('pending','running')"),
        ),
    )

    id = Column(String(64), primary_key=True, index=True)
    job_type = Column(String(100), nullable=False, index=True)
    status = Column(String(30), nullable=False, index=True)  # pending|running|completed|failed|cancelled
    progress = Column(Integer, nullable=False, default=0)
    progress_current = Column(Integer, nullable=False, default=0)
    progress_total = Column(Integer, nullable=False, default=0)
    progress_percent = Column(Integer, nullable=False, default=0)
    current_step = Column(String(255), nullable=True)
    message = Column(Text, nullable=True)
    result_summary = Column(JSONBType, nullable=True)
    requester = Column(String(255), nullable=True)
    job_limit = Column(Integer, nullable=True)
    requested_by_user_id = Column(Integer, nullable=True, index=True)
    error = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    cancel_requested = Column(Boolean, nullable=False, default=False)
    current_entity_type = Column(String(50), nullable=True, index=True)
    current_offset = Column(Integer, nullable=False, default=0)
    processed_count = Column(Integer, nullable=False, default=0)
    failed_count = Column(Integer, nullable=False, default=0)
    last_successful_external_id = Column(String(255), nullable=True)
    checkpoint = Column(JSONBType, nullable=True)
    batch_size = Column(Integer, nullable=False, default=100)
    max_retries = Column(Integer, nullable=False, default=3)
    external_timeout_seconds = Column(Integer, nullable=False, default=15)
    force_refresh = Column(Boolean, nullable=False, default=False)
    skip_images = Column(Boolean, nullable=False, default=False)
    include_knowledge = Column(Boolean, nullable=False, default=False)
    include_guild_rosters = Column(Boolean, nullable=False, default=False)
    continue_on_error = Column(Boolean, nullable=False, default=True)
    maintenance_requested = Column(Boolean, nullable=False, default=False)
    operation_label = Column(String(255), nullable=True)
    worker_id = Column(String(128), nullable=True, index=True)
    claimed_at = Column(DateTime(timezone=True), nullable=True)
    lease_expires_at = Column(DateTime(timezone=True), nullable=True, index=True)
    next_retry_at = Column(DateTime(timezone=True), nullable=True, index=True)
    terminal_reason = Column(String(255), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class SyncJobError(Base):
    """Per-entity error records for sync jobs."""

    __tablename__ = "sync_job_errors"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String(64), ForeignKey("sync_jobs.id"), nullable=False, index=True)
    entity_type = Column(String(50), nullable=False, index=True)
    external_id = Column(String(255), nullable=True, index=True)
    entity_name = Column(String(255), nullable=True)
    error_message = Column(Text, nullable=False)
    error_category = Column(String(80), nullable=True)
    phase_key = Column(String(64), nullable=True, index=True)
    provider = Column(String(120), nullable=True)
    safe_url = Column(String(1024), nullable=True)
    http_status = Column(Integer, nullable=True, index=True)
    retryable = Column(Boolean, nullable=True, index=True)
    checkpoint_offset = Column(Integer, nullable=True)
    attempt = Column(Integer, nullable=True)
    occurrence_count = Column(Integer, nullable=False, default=1)
    first_occurred_at = Column(DateTime(timezone=True), nullable=True)
    last_seen_at = Column(DateTime(timezone=True), nullable=True, index=True)
    fingerprint = Column(String(64), nullable=True, unique=True, index=True)
    retry_count = Column(Integer, nullable=False, default=0)
    status = Column(String(30), nullable=False, default="failed")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CachedResource(Base):
    """Cached external resources metadata (images/maps/etc.)."""
    __tablename__ = "cached_resources"

    id = Column(Integer, primary_key=True, index=True)
    resource_type = Column(String(50), nullable=False, index=True)
    entity_type = Column(String(50), nullable=False, index=True)
    entity_id = Column(Integer, nullable=True, index=True)
    source_url = Column(String(1024), nullable=False)
    resolved_url = Column(String(1024), nullable=True)
    local_path = Column(String(1024), nullable=True)
    resource_key = Column(String(128), nullable=True, index=True)
    content_type = Column(String(100), nullable=True)
    size_bytes = Column(Integer, nullable=True)
    checksum = Column(String(128), nullable=True)
    etag_hash = Column(String(128), nullable=True)
    status = Column(String(30), nullable=False, default="pending")
    last_fetched_at = Column(DateTime(timezone=True), nullable=True)
    fetch_attempts = Column(Integer, nullable=False, default=0)
    error = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
