"""
User model for Authentication and Admin privileges
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=True)
    hashed_password = Column(String(255), nullable=False)
    guild_rank = Column(String(50), nullable=True, default="Unranked")
    discord_id = Column(String(100), nullable=True)
    discord_username = Column(String(100), nullable=True)
    join_date = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Player info from Tibia API
    vocation = Column(String(50), nullable=True)  # Sorcerer, Druid, Paladin, Knight
    level = Column(Integer, nullable=True)
    tibia_character_name = Column(String(100), nullable=True, index=True)
    last_updated = Column(DateTime(timezone=True), nullable=True)
    
    # Password reset fields
    reset_token = Column(String(255), nullable=True)
    reset_token_expires = Column(DateTime(timezone=True), nullable=True)
    
    characters = relationship("UserCharacter", back_populates="user")

    def __repr__(self):
        return f"<User {self.username}>"

