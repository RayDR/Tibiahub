"""Creature model - Represents monsters in Tibia."""
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, String, Table, Text, Uuid
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base
from app.db.types import JSONBType


# Association table for creature weaknesses (many-to-many)
creature_weaknesses = Table(
    'creature_weaknesses',
    Base.metadata,
    Column('creature_id', Integer, ForeignKey('creatures.id'), primary_key=True),
    Column('element_id', Integer, ForeignKey('elements.id'), primary_key=True),
    Column('percentage', Integer)  # How much weaker (e.g., 110 means 110% damage)
)

# Association table for creature resistances (many-to-many)
creature_resistances = Table(
    'creature_resistances',
    Base.metadata,
    Column('creature_id', Integer, ForeignKey('creatures.id'), primary_key=True),
    Column('element_id', Integer, ForeignKey('elements.id'), primary_key=True),
    Column('percentage', Integer)  # How much resistant (e.g., 80 means 80% damage)
)


class Creature(Base):
    """Creature/Monster model"""
    __tablename__ = "creatures"
    __table_args__ = (Index("uq_creatures_knowledge_entity_id", "knowledge_entity_id", unique=True),)
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), index=True, nullable=False)
    normalized_name = Column(String(150), index=True)
    slug = Column(String(150), index=True)
    external_id = Column(String(100), nullable=True, index=True)
    source_name = Column(String(50), nullable=True, index=True)
    source_url = Column(String(255), nullable=True)
    knowledge_entity_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("knowledge_entities.uuid", ondelete="SET NULL"),
        nullable=True,
    )
    data_version = Column(Integer, nullable=False, default=1)
    protected_fields = Column(JSONBType, nullable=False, default=list)
    article = Column(String(10))  # "a" or "an"
    plural = Column(String(100))
    
    # Basic stats
    hitpoints = Column(Integer, nullable=True)
    experience = Column(Integer, nullable=True)
    armor = Column(Integer, nullable=True)
    speed = Column(Integer, nullable=True)
    
    # Combat info
    max_damage = Column(Integer)  # Maximum damage output
    summon_cost = Column(Integer)  # Mana cost to summon (0 if not summonable)
    convince_cost = Column(Integer)  # Mana cost to convince (0 if not convincible)
    
    # Classification
    difficulty = Column(String(20))  # Trivial, Easy, Medium, Hard
    occurrence = Column(String(20))  # Common, Uncommon, Rare, Very Rare
    is_boss = Column(Boolean, default=False)
    is_hidden = Column(Boolean, default=False)
    
    # Loot info
    loot_value = Column(Float)  # Average gold value
    
    # Description
    description = Column(Text)
    behavior = Column(Text)  # How the creature behaves in combat
    bestiary_class = Column(String(100), nullable=True)
    bestiary_level = Column(String(50), nullable=True)
    charm_points = Column(Integer, nullable=True)
    classification = Column(String(50), nullable=True, index=True)
    creature_class = Column(String(100), nullable=True)
    primary_type = Column(String(100), nullable=True)
    
    # Image
    image_url = Column(String(255))
    image_alias = Column(String(255), nullable=True)       # e.g. "Demon" when creature is "Angry Demon"
    image_url_override = Column(String(1024), nullable=True)  # full URL manually set by admin
    image_source_name = Column(String(255), nullable=True)  # e.g. "tibiawiki"
    image_locked = Column(Boolean, default=False)           # if True, sync must not overwrite image fields
    image_asset_id = Column(Integer, ForeignKey("media_assets.id"), nullable=True)
    data_sources = Column(JSONBType, nullable=True)
    missing_fields = Column(JSONBType, nullable=True)
    related_tasks = Column(JSONBType, nullable=True)
    locations = Column(JSONBType, nullable=True)
    raw_data = Column(JSONBType, nullable=True)
    last_synced_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    weaknesses = relationship(
        "Element",
        secondary=creature_weaknesses,
        back_populates="weak_creatures"
    )
    resistances = relationship(
        "Element",
        secondary=creature_resistances,
        back_populates="resistant_creatures"
    )
    loot_items = relationship("Loot", back_populates="creature", cascade="all, delete-orphan")
    spawn_locations = relationship("SpawnLocation", back_populates="creature", cascade="all, delete-orphan")
    knowledge_entity = relationship("KnowledgeEntity")
    
    def __repr__(self):
        return f"<Creature {self.name}>"

    @property
    def canonical_id(self):
        return self.knowledge_entity_id

    @property
    def source_provider(self):
        return self.source_name

    @property
    def supplied_fields(self):
        raw = self.raw_data if isinstance(self.raw_data, dict) else {}
        recorded = raw.get("supplied_fields") or raw.get("provided_fields")
        if recorded:
            return recorded
        fields = (
            "article", "plural", "hitpoints", "experience", "armor", "speed",
            "max_damage", "summon_cost", "convince_cost", "difficulty", "occurrence",
            "description", "behavior", "bestiary_class", "bestiary_level", "charm_points",
            "classification", "creature_class", "primary_type", "locations", "related_tasks",
        )
        return [field for field in fields if getattr(self, field, None) not in (None, "", [], {})]
