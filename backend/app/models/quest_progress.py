"""Per-character Quest progress owned by verified Tibia characters."""

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base
from app.db.types import JSONBType


class QuestCompletion(Base):
    """Quest progress row.

    The legacy table name is intentionally preserved so existing completed
    quests migrate without losing history. Absence of a row means not started.
    """

    __tablename__ = "quest_completions"
    __table_args__ = (
        UniqueConstraint("character_id", "quest_id", name="uq_quest_completion_character_quest"),
        CheckConstraint("status IN ('in_progress','completed')", name="ck_quest_completion_status"),
        Index("ix_quest_completions_character", "character_id", "completed_at"),
        Index("ix_quest_completions_quest", "quest_id", "completed_at"),
    )

    id = Column(Integer, primary_key=True)
    character_id = Column(Integer, ForeignKey("user_characters.id", ondelete="CASCADE"), nullable=False)
    quest_id = Column(Integer, ForeignKey("tibiawiki_quests.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(20), nullable=False, default="in_progress")
    completed_mission_ids = Column(JSONBType, nullable=False, default=list)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    character = relationship("UserCharacter")
    quest = relationship("TibiaWikiQuest")
