"""
Hunt Zone model - Areas where players can hunt
"""
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, ForeignKey
from sqlalchemy.orm import relationship

from app.db.database import Base


class HuntZone(Base):
    """Hunt zone/area model"""
    __tablename__ = "hunt_zones"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    city = Column(String(100))  # Nearest city
    
    # Level recommendations
    min_level = Column(Integer, nullable=False)
    max_level = Column(Integer)
    recommended_level = Column(Integer)
    
    # Vocations (professions) - Winter Update 2025 includes Monk
    knights_recommended = Column(Boolean, default=False)
    paladins_recommended = Column(Boolean, default=False)
    sorcerers_recommended = Column(Boolean, default=False)
    druids_recommended = Column(Boolean, default=False)
    monks_recommended = Column(Boolean, default=False)
    
    # Zone info
    size = Column(String(20))  # Small, Medium, Large, Huge
    difficulty = Column(String(20))  # Easy, Medium, Hard, Extreme
    
    # Profit & Experience
    avg_exp_hour = Column(Integer)  # Average exp per hour
    avg_profit_hour = Column(Integer)  # Average gold profit per hour
    
    
    # Access requirements
    requires_quest = Column(Boolean, default=False)
    quest_id = Column(Integer, ForeignKey("quests.id"), nullable=True)
    quest = relationship("Quest", back_populates="required_for_zones")
    requires_premium = Column(Boolean, default=False)
    
    # Description
    description = Column(Text)
    tips = Column(Text)  # Hunting tips
    
    # Location
    location_x = Column(Integer)
    location_y = Column(Integer)
    location_z = Column(Integer)
    map_image_url = Column(String(255))
    
    # Relationships
    creature_spawns = relationship("SpawnLocation", back_populates="hunt_zone", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<HuntZone {self.name}>"
