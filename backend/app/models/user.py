"""User model for authentication and admin privileges."""
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, false, true
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
    email_verified_at = Column(DateTime(timezone=True), nullable=True)
    avatar_url = Column(String(255), nullable=True)
    avatar_managed_key = Column(String(80), nullable=True, unique=True)
    avatar_updated_at = Column(DateTime(timezone=True), nullable=True)
    hashed_password = Column(String(255), nullable=False)
    guild_rank = Column(String(50), nullable=True, default="Unranked")
    discord_id = Column(String(100), nullable=True)
    discord_username = Column(String(100), nullable=True)
    join_date = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True, server_default=true(), nullable=False)
    is_superuser = Column(Boolean, default=False, server_default=false(), nullable=False)
    # Independent platform capabilities; users may hold any combination.
    is_moderator = Column(Boolean, default=False, server_default=false(), nullable=False)
    is_writer = Column(Boolean, default=False, server_default=false(), nullable=False)
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

    # Canonical display preference. Authorization evaluates every verified
    # UserCharacter and never relies on this selection or the legacy cache.
    primary_character_id = Column(
        Integer,
        ForeignKey("user_characters.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
        index=True,
    )
    in_app_notifications_enabled = Column(Boolean, default=True, server_default=true(), nullable=False)
    email_notifications_enabled = Column(Boolean, default=True, server_default=true(), nullable=False)
    
    # Legacy compatibility only; new reset tokens live in auth_one_time_tokens.
    reset_token = Column(String(255), nullable=True)
    reset_token_expires = Column(DateTime(timezone=True), nullable=True)
    
    characters = relationship("UserCharacter", back_populates="user", foreign_keys="UserCharacter.user_id")
    primary_character = relationship("UserCharacter", foreign_keys=[primary_character_id], post_update=True)

    def __repr__(self):
        return f"<User {self.username}>"
