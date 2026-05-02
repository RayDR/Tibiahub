from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.sql import func

from app.db.database import Base


class GuildMemberSnapshot(Base):
    __tablename__ = "guild_member_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    guild_name = Column(String(200), nullable=False, index=True)
    character_name = Column(String(100), nullable=False, index=True)
    level = Column(Integer, nullable=True)
    vocation = Column(String(100), nullable=True)
    rank = Column(String(100), nullable=True)
    role = Column(String(100), nullable=True)
    last_login = Column(String(100), nullable=True)
    world = Column(String(100), nullable=True)
    snapshot_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
