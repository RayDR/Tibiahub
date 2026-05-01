"""Loot model - Items dropped by creatures."""
from sqlalchemy import Column, Float, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import relationship

from app.db.database import Base


class Loot(Base):
    """Loot item model"""
    __tablename__ = "loot"
    
    id = Column(Integer, primary_key=True, index=True)
    creature_id = Column(Integer, ForeignKey('creatures.id'), nullable=False)
    
    item_name = Column(String(100), nullable=False)
    normalized_name = Column(String(150), index=True)
    external_id = Column(String(100), nullable=True, index=True)
    rarity = Column(String(20))  # Always, Common, Uncommon, Semi-rare, Rare, Very Rare
    percentage = Column(Float)  # Drop chance percentage
    min_amount = Column(Integer, default=1)
    max_amount = Column(Integer, default=1)
    
    # Item info
    item_value = Column(Integer)  # Gold value
    item_type = Column(String(50))  # Gold, Equipment, Resource, etc.
    item_image_url = Column(String(255), nullable=True)
    source_url = Column(String(255), nullable=True)
    raw_data = Column(JSON, nullable=True)
    
    # Relationships
    creature = relationship("Creature", back_populates="loot_items")
    
    def __repr__(self):
        return f"<Loot {self.item_name} from {self.creature.name if self.creature else 'Unknown'}>"
