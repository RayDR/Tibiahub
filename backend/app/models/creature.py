"""Creature model - Represents monsters in Tibia."""
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Table, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


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
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), index=True, nullable=False)
    normalized_name = Column(String(150), index=True)
    slug = Column(String(150), index=True)
    external_id = Column(String(100), nullable=True, index=True)
    source_name = Column(String(50), nullable=True, index=True)
    source_url = Column(String(255), nullable=True)
    article = Column(String(10))  # "a" or "an"
    plural = Column(String(100))
    
    # Basic stats
    hitpoints = Column(Integer, nullable=False)
    experience = Column(Integer, nullable=False)
    armor = Column(Integer, default=0)
    speed = Column(Integer, default=0)
    
    # Combat info
    max_damage = Column(Integer)  # Maximum damage output
    summon_cost = Column(Integer)  # Mana cost to summon (0 if not summonable)
    convince_cost = Column(Integer)  # Mana cost to convince (0 if not convincible)
    
    # Classification
    difficulty = Column(String(20))  # Trivial, Easy, Medium, Hard
    occurrence = Column(String(20))  # Common, Uncommon, Rare, Very Rare
    is_boss = Column(Boolean, default=False)
    
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
    data_sources = Column(JSON, nullable=True)
    missing_fields = Column(JSON, nullable=True)
    related_tasks = Column(JSON, nullable=True)
    locations = Column(JSON, nullable=True)
    raw_data = Column(JSON, nullable=True)
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
    
    def __repr__(self):
        return f"<Creature {self.name}>"
