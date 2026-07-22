from sqlalchemy import Column, Integer, String, Text, DateTime, func
from app.db.database import Base

class HuntCatalog(Base):
    __tablename__ = "hunt_catalog"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    location = Column(String(200), nullable=False)
    level_min = Column(Integer, nullable=False)
    level_max = Column(Integer, nullable=False)
    vocation = Column(Text)
    exp_per_hour = Column(Integer)
    profit_per_hour = Column(Integer)
    creatures = Column(Text, nullable=False)
    strategy = Column(Text)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
