from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base

class UserCharacter(Base):
    __tablename__ = "user_characters"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    character_name = Column(String(100), unique=True, index=True, nullable=False)
    # optional cached Tibia data
    level = Column(Integer, nullable=True)
    vocation = Column(String(50), nullable=True)
    last_seen = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="characters")
