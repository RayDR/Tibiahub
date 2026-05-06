"""
Extended models for Tibia items, quests, and hunting places
Stores complete data from external APIs locally
Note: Quest and Quest models already exist - these are for API synced data
"""
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, JSON, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base

class Item(Base):
    """Store item data from TibiaWiki API"""
    __tablename__ = "tibiawiki_items"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, index=True, nullable=False)
    item_id = Column(Integer, nullable=True, unique=True)  # Tibia item ID
    description = Column(Text, nullable=True)
    type = Column(String(100), nullable=True, index=True)  # e.g., "weapon", "armor", "consumable"
    
    # Item properties
    weight = Column(Float, nullable=True)
    value = Column(Integer, nullable=True)
    attack = Column(Integer, nullable=True)
    defense = Column(Integer, nullable=True)
    armor = Column(Integer, nullable=True)
    
    # Requirements
    level_required = Column(Integer, nullable=True)
    vocation_required = Column(String(100), nullable=True)
    
    # Classification
    tradeable = Column(Boolean, default=True)
    stackable = Column(Boolean, default=False)
    
    # Full raw data from API
    raw_data = Column(JSON, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

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
    creatures = Column(JSON, nullable=True)  # List of creature names found here
    
    # Loot
    loot_expectation = Column(String(50), nullable=True)  # e.g., "low", "medium", "high"
    common_loot = Column(JSON, nullable=True)
    
    # Full raw data from API
    raw_data = Column(JSON, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class TibiaWikiQuest(Base):
    """Store quest data from TibiaWiki API"""
    __tablename__ = "tibiawiki_quests"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    
    # Quest properties
    min_level = Column(Integer, nullable=True)
    max_level = Column(Integer, nullable=True)
    experience_reward = Column(Integer, nullable=True)
    treasure = Column(JSON, nullable=True)  # List of reward items
    
    # Quest details
    duration = Column(String(100), nullable=True)  # e.g., "daily", "repeatable", "one-time"
    location = Column(String(255), nullable=True)
    npc = Column(String(255), nullable=True)  # NPC who gives the quest
    
    # Full raw data from API
    raw_data = Column(JSON, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

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

    id = Column(String(64), primary_key=True, index=True)
    job_type = Column(String(100), nullable=False, index=True)
    status = Column(String(30), nullable=False, index=True)  # pending|running|completed|failed|cancelled
    progress = Column(Integer, nullable=False, default=0)
    progress_current = Column(Integer, nullable=False, default=0)
    progress_total = Column(Integer, nullable=False, default=0)
    progress_percent = Column(Integer, nullable=False, default=0)
    current_step = Column(String(255), nullable=True)
    message = Column(Text, nullable=True)
    result_summary = Column(JSON, nullable=True)
    requester = Column(String(255), nullable=True)
    requested_by_user_id = Column(Integer, nullable=True, index=True)
    error = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    cancel_requested = Column(Boolean, nullable=False, default=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


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
