"""Per-character Quest completion state owned by verified Tibia characters."""

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class QuestCompletion(Base):
    __tablename__ = "quest_completions"
    __table_args__ = (
        UniqueConstraint("character_id", "quest_id", name="uq_quest_completion_character_quest"),
        Index("ix_quest_completions_character", "character_id", "completed_at"),
        Index("ix_quest_completions_quest", "quest_id", "completed_at"),
    )

    id = Column(Integer, primary_key=True)
    character_id = Column(Integer, ForeignKey("user_characters.id", ondelete="CASCADE"), nullable=False)
    quest_id = Column(Integer, ForeignKey("tibiawiki_quests.id", ondelete="CASCADE"), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    character = relationship("UserCharacter")
    quest = relationship("TibiaWikiQuest")
