"""Hunt Zone model - Areas where players can hunt."""
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base
from app.db.types import JSONBType


class HuntZone(Base):
    """Hunt zone/area model"""
    __tablename__ = "hunt_zones"
    __table_args__ = (
        UniqueConstraint("source_provider", "external_id", name="uq_hunt_zones_source_external"),
        Index("uq_hunt_zones_knowledge_entity_id", "knowledge_entity_id", unique=True),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    slug = Column(String(150), nullable=True, index=True)
    normalized_name = Column(String(150), index=True)
    city = Column(String(100))  # Nearest city
    region = Column(String(100), nullable=True)
    source_provider = Column(String(50), nullable=True, index=True)
    source_name = Column(String(50), nullable=True, index=True)
    source_url = Column(String(255), nullable=True)
    external_id = Column(String(100), nullable=True, index=True)
    knowledge_entity_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("knowledge_entities.uuid", ondelete="SET NULL"),
        nullable=True,
    )
    provider_metadata = Column(JSONBType, nullable=True)
    supplied_fields = Column(JSONBType, nullable=True)
    protected_fields = Column(JSONBType, nullable=False, default=list)
    data_version = Column(Integer, nullable=False, default=1)
    
    # Level recommendations
    min_level = Column(Integer, nullable=True)
    max_level = Column(Integer)
    recommended_level = Column(Integer)
    recommended_vocations = Column(JSONBType, nullable=True)
    recommended_party_size = Column(String(50), nullable=True)
    exp_rating = Column(String(20), nullable=True)
    profit_rating = Column(String(20), nullable=True)
    danger_rating = Column(String(20), nullable=True)
    
    # Vocations (professions) - Winter Update 2025 includes Monk
    knights_recommended = Column(Boolean, nullable=True)
    paladins_recommended = Column(Boolean, nullable=True)
    sorcerers_recommended = Column(Boolean, nullable=True)
    druids_recommended = Column(Boolean, nullable=True)
    monks_recommended = Column(Boolean, nullable=True)
    
    # Zone info
    size = Column(String(20))  # Small, Medium, Large, Huge
    difficulty = Column(String(20))  # Easy, Medium, Hard, Extreme
    
    # Profit & Experience
    avg_exp_hour = Column(Integer)  # Average exp per hour
    avg_profit_hour = Column(Integer)  # Average gold profit per hour
    
    
    # Access requirements
    requires_quest = Column(Boolean, nullable=True)
    quest_id = Column(Integer, ForeignKey("quests.id"), nullable=True)
    quest = relationship("Quest", back_populates="required_for_zones")
    requires_premium = Column(Boolean, nullable=True)
    
    # Description
    description = Column(Text)
    tips = Column(Text)  # Hunting tips
    
    # Location
    location_x = Column(Integer)
    location_y = Column(Integer)
    location_z = Column(Integer)
    map_x = Column(Integer, nullable=True)
    map_y = Column(Integer, nullable=True)
    map_z = Column(Integer, nullable=True)
    map_bounds = Column(JSONBType, nullable=True)
    map_image_url = Column(String(255))
    map_asset_id = Column(Integer, ForeignKey("media_assets.id"), nullable=True)
    raw_data = Column(JSONBType, nullable=True)
    last_synced_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    creature_spawns = relationship("SpawnLocation", back_populates="hunt_zone", cascade="all, delete-orphan")
    knowledge_entity = relationship("KnowledgeEntity")

    @property
    def quest_name(self):
        return self.quest.name if self.quest else None

    @property
    def quest_slug(self):
        return getattr(self.quest, "slug", None) if self.quest else None

    @property
    def canonical_id(self):
        return self.knowledge_entity_id
    
    def __repr__(self):
        return f"<HuntZone {self.name}>"
