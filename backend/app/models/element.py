"""
Element model - Damage types in Tibia
"""
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

from app.db.database import Base
from app.models.creature import creature_weaknesses, creature_resistances


class Element(Base):
    """Element/Damage type model"""
    __tablename__ = "elements"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)  # Physical, Fire, Ice, Energy, Earth, Holy, Death
    icon_url = Column(String(255))
    color = Column(String(7))  # Hex color for UI
    
    # Relationships
    weak_creatures = relationship(
        "Creature",
        secondary=creature_weaknesses,
        back_populates="weaknesses"
    )
    resistant_creatures = relationship(
        "Creature",
        secondary=creature_resistances,
        back_populates="resistances"
    )
    
    def __repr__(self):
        return f"<Element {self.name}>"
