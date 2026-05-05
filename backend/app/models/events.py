"""
Events and Raffles Model - System for guild events, contests, and raffles
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, func
from sqlalchemy.orm import relationship
import uuid
from app.db.database import Base

class Event(Base):
    __tablename__ = "events"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(36), default=lambda: str(uuid.uuid4()), unique=True, index=True)
    public_code = Column(String(6), unique=True, index=True, nullable=True)
    type = Column(String(50), nullable=False)  # 'raffle', 'contest', 'hunt_event', 'custom'
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    rules = Column(Text, nullable=True)
    reward = Column(String(500), nullable=True)
    
    # Event timing
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=True)
    draw_date = Column(DateTime, nullable=True)  # For raffles
    
    # Raffle specific
    total_slots = Column(Integer, nullable=True)  # Max participants
    entry_cost = Column(String(200), nullable=True)  # "Free", "10k gold", etc.
    
    # Winner info
    winner_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    winner_number = Column(Integer, nullable=True)
    is_drawn = Column(Boolean, default=False)
    
    # Status
    status = Column(String(50), default='active')  # 'active', 'closed', 'completed', 'cancelled'
    is_active = Column(Boolean, default=True)
    is_public = Column(Boolean, default=False)
    registration_enabled = Column(Boolean, default=True)
    archive_after_days = Column(Integer, default=7)
    archived_at = Column(DateTime, nullable=True)
    
    # Participant configuration
    participant_mode = Column(String(20), default='manual')  # 'manual', 'guild_auto'
    active_days_limit = Column(Integer, default=10)  # For guild_auto mode
    guild_name = Column(String(200), nullable=True)  # Guild name for guild_auto mode
    guild_world = Column(String(100), nullable=True)  # World restriction for participants
    
    # Relations
    creator_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    announcement_id = Column(Integer, ForeignKey('announcements.id'), nullable=True)
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime, nullable=True)
    deleted_by_user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    delete_reason = Column(Text, nullable=True)
    is_deleted = Column(Boolean, default=False, nullable=False)
    
    # Relationships
    participants = relationship("EventParticipant", back_populates="event", cascade="all, delete-orphan")
    creator = relationship("User", foreign_keys=[creator_id], backref="created_events")
    winner = relationship("User", foreign_keys=[winner_id], backref="won_events")


class EventParticipant(Base):
    __tablename__ = "event_participants"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey('events.id'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    assigned_number = Column(Integer, nullable=True)  # For raffles
    entry_data = Column(Text, nullable=True)  # JSON data for custom entries
    
    joined_at = Column(DateTime, server_default=func.now())
    
    # Relationships
    event = relationship("Event", back_populates="participants")
    user = relationship("User", backref="event_participations")


class PublicEventParticipant(Base):
    """Participants for public events - can be non-registered users (Tibia characters)"""
    __tablename__ = "public_event_participants"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey('events.id'), nullable=False)
    
    # Tibia character data
    character_name = Column(String(100), nullable=False)
    character_level = Column(Integer, nullable=True)
    character_vocation = Column(String(50), nullable=True)
    character_world = Column(String(100), nullable=True)
    last_login = Column(String(100), nullable=True)  # ISO string from TibiaData
    
    assigned_number = Column(Integer, nullable=True)  # For raffles
    is_auto_loaded = Column(Boolean, default=False)  # True if loaded from guild, False if manually added
    is_excluded = Column(Boolean, default=False)  # True if admin explicitly excluded from event
    deleted_at = Column(DateTime, nullable=True)
    deleted_by_user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    delete_reason = Column(Text, nullable=True)
    is_deleted = Column(Boolean, default=False, nullable=False)
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    event = relationship("Event", backref="public_participants")
