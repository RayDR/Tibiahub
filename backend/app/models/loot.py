"""
Loot model - Items dropped by creatures
"""
from sqlalchemy import Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import relationship

from app.db.database import Base


class Loot(Base):
    """Loot item model"""
    __tablename__ = "loot"
    
    id = Column(Integer, primary_key=True, index=True)
    creature_id = Column(Integer, ForeignKey('creatures.id'), nullable=False)
    
    item_name = Column(String(100), nullable=False)
    rarity = Column(String(20))  # Always, Common, Uncommon, Semi-rare, Rare, Very Rare
    percentage = Column(Float)  # Drop chance percentage
    min_amount = Column(Integer, default=1)
    max_amount = Column(Integer, default=1)
    
    # Item info
    item_value = Column(Integer)  # Gold value
    item_type = Column(String(50))  # Gold, Equipment, Resource, etc.
    
    # Relationships
    creature = relationship("Creature", back_populates="loot_items")
    
    def __repr__(self):
        return f"<Loot {self.item_name} from {self.creature.name if self.creature else 'Unknown'}>"
