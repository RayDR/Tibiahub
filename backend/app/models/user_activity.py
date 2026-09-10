"""User activity model for personalized history and continue flow."""

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.sql import func

from app.db.database import Base
from app.db.types import JSONBType


class UserActivity(Base):
    __tablename__ = "user_activities"
    __table_args__ = (
        Index("ix_user_activities_user_character_created", "user_id", "character_id", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    character_id = Column(Integer, ForeignKey("user_characters.id", ondelete="CASCADE"), index=True, nullable=True)
    activity_type = Column(String(50), index=True, nullable=False)
    entity_type = Column(String(50), nullable=True)
    entity_id = Column(String(120), nullable=True)
    query = Column(String(255), nullable=True)
    meta_payload = Column("metadata", JSONBType, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    def __repr__(self):
        return f"<UserActivity user_id={self.user_id} character_id={self.character_id} type={self.activity_type}>"
