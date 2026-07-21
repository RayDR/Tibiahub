"""User model for authentication and admin privileges."""
from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    display_name = Column(String(100), nullable=True)
    title = Column(String(100), nullable=True)
    email = Column(String(100), unique=True, index=True, nullable=True)
    avatar_url = Column(String(255), nullable=True)
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
    world_name = Column(String(100), nullable=True)
    guild_name = Column(String(200), nullable=True)
    residence = Column(String(100), nullable=True)
    achievement_points = Column(Integer, nullable=True)
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    last_app_login_at = Column(DateTime(timezone=True), nullable=True)
    tibia_status = Column(String(50), nullable=True)
    tibia_last_error = Column(String(255), nullable=True)
    last_updated = Column(DateTime(timezone=True), nullable=True)
    
    # Password reset fields
    reset_token = Column(String(255), nullable=True)
    reset_token_expires = Column(DateTime(timezone=True), nullable=True)
    
    characters = relationship("UserCharacter", back_populates="user")

    def __repr__(self):
        return f"<User {self.username}>"
