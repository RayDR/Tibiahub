"""User activity model for personalized history and continue flow."""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from app.db.database import Base
from app.db.types import JSONBType


class UserActivity(Base):
    __tablename__ = "user_activities"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    activity_type = Column(String(50), index=True, nullable=False)
    entity_type = Column(String(50), nullable=True)
    entity_id = Column(String(120), nullable=True)
    query = Column(String(255), nullable=True)
    meta_payload = Column("metadata", JSONBType, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    def __repr__(self):
        return f"<UserActivity user_id={self.user_id} type={self.activity_type}>"
