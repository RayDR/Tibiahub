"""
Quest model - For tracking access requirements and guides
"""
from sqlalchemy import Column, Integer, String, Text, Boolean
from sqlalchemy.orm import relationship
from app.db.database import Base

class Quest(Base):
    __tablename__ = "quests"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), unique=True, index=True, nullable=False)
    wiki_url = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    
    # PDF Guide Integration
    pdf_page_number = Column(Integer, nullable=True)
    
    # Access to zones
    required_for_zones = relationship("HuntZone", back_populates="quest")

    def __repr__(self):
        return f"<Quest {self.name}>"
