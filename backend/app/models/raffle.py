"""
Guild raffle models.

This system is account-based through local users, while keeping the winning
character that represents each account inside the guild raffle.
"""
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class Raffle(Base):
    __tablename__ = "raffles"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    guild_name = Column(String(200), nullable=False)
    status = Column(String(50), nullable=False, default="draft")
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    last_executed_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    current_run_number = Column(Integer, nullable=False, default=0)
    rerun_count = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    created_by = relationship("User", foreign_keys=[created_by_id], backref="created_raffles")
    last_executed_by = relationship("User", foreign_keys=[last_executed_by_id], backref="executed_raffles")
    participants = relationship("RaffleParticipant", back_populates="raffle", cascade="all, delete-orphan")
    prizes = relationship("RafflePrize", back_populates="raffle", cascade="all, delete-orphan", order_by="RafflePrize.order_index")
    winners = relationship("RaffleWinner", back_populates="raffle", cascade="all, delete-orphan", order_by="RaffleWinner.created_at")


class RaffleParticipant(Base):
    __tablename__ = "raffle_participants"
    __table_args__ = (
        UniqueConstraint("raffle_id", "user_id", name="uq_raffle_participant_user"),
        UniqueConstraint("raffle_id", "character_name", name="uq_raffle_participant_character"),
    )

    id = Column(Integer, primary_key=True, index=True)
    raffle_id = Column(Integer, ForeignKey("raffles.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    character_name = Column(String(100), nullable=False, index=True)
    guild_rank = Column(String(100), nullable=True)
    weight = Column(Float, nullable=False, default=1.0)
    is_eligible = Column(Boolean, nullable=False, default=True)
    source = Column(String(50), nullable=False, default="guild_sync")
    source_data = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    raffle = relationship("Raffle", back_populates="participants")
    user = relationship("User", backref="raffle_participations")
    winners = relationship("RaffleWinner", back_populates="participant")


class RafflePrize(Base):
    __tablename__ = "raffle_prizes"

    id = Column(Integer, primary_key=True, index=True)
    raffle_id = Column(Integer, ForeignKey("raffles.id"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    reward = Column(String(200), nullable=False)
    order_index = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    raffle = relationship("Raffle", back_populates="prizes")
    winners = relationship("RaffleWinner", back_populates="prize")


class RaffleWinner(Base):
    __tablename__ = "raffle_winners"

    id = Column(Integer, primary_key=True, index=True)
    raffle_id = Column(Integer, ForeignKey("raffles.id"), nullable=False, index=True)
    prize_id = Column(Integer, ForeignKey("raffle_prizes.id"), nullable=False, index=True)
    participant_id = Column(Integer, ForeignKey("raffle_participants.id"), nullable=False, index=True)
    executed_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    run_number = Column(Integer, nullable=False, default=1)
    is_rerun = Column(Boolean, nullable=False, default=False)
    rerun_reason = Column(Text, nullable=True)
    participant_snapshot = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    raffle = relationship("Raffle", back_populates="winners")
    prize = relationship("RafflePrize", back_populates="winners")
    participant = relationship("RaffleParticipant", back_populates="winners")
    executed_by = relationship("User", backref="raffle_winner_executions")