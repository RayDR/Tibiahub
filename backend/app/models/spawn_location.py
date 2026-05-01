"""
Spawn Location model - Where creatures can be found
"""
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

from app.db.database import Base


class SpawnLocation(Base):
    """Spawn location model"""
    __tablename__ = "spawn_locations"
    
    id = Column(Integer, primary_key=True, index=True)
    creature_id = Column(Integer, ForeignKey('creatures.id'), nullable=False)
    hunt_zone_id = Column(Integer, ForeignKey('hunt_zones.id'), nullable=False)
    
    quantity = Column(String(20))  # Few, Some, Many, Plenty
    notes = Column(String(255))  # Special notes about this spawn
    
    # Relationships
    creature = relationship("Creature", back_populates="spawn_locations")
    hunt_zone = relationship("HuntZone", back_populates="creature_spawns")
    
    def __repr__(self):
        return f"<SpawnLocation {self.creature.name if self.creature else 'Unknown'} at {self.hunt_zone.name if self.hunt_zone else 'Unknown'}>"
