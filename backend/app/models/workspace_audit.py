from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class WorkspaceAudit(Base):
    __tablename__ = "workspace_audits"

    id = Column(Integer, primary_key=True)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    workspace_type = Column(String(40), nullable=False)
    guild_name = Column(String(200), nullable=True, index=True)
    action = Column(String(100), nullable=False, index=True)
    target_type = Column(String(80), nullable=True)
    target_id = Column(String(100), nullable=True)
    assisted = Column(Boolean, nullable=False, default=False)
    safe_metadata = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    actor = relationship("User")
