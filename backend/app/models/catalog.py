"""
Catalog Model - General catalog for hunts, quests, and other content
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, func
from app.db.database import Base

class Catalog(Base):
    __tablename__ = "catalog"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    type = Column(String(50), nullable=False)  # 'hunt', 'quest', 'custom'
    name = Column(String(200), nullable=False)
    location = Column(String(200), nullable=False)
    level_min = Column(Integer, nullable=True)
    level_max = Column(Integer, nullable=True)
    vocation = Column(Text, nullable=True)
    exp_per_hour = Column(Integer, nullable=True)
    profit_per_hour = Column(Integer, nullable=True)
    creatures = Column(Text, nullable=True)
    
    # Quest specific fields
    quest_reward = Column(Text, nullable=True)
    quest_requirements = Column(Text, nullable=True)
    
    # General fields
    strategy = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    difficulty = Column(String(50), nullable=True)  # 'easy', 'medium', 'hard', 'extreme'
    
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
