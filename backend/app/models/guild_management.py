"""Canonical guild roster and guild-scoped module grants."""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base
from app.db.types import JSONBType


class GuildRosterCharacter(Base):
    __tablename__ = "guild_roster_characters"
    __table_args__ = (
        UniqueConstraint("normalized_guild_name", "normalized_world_name", "normalized_character_name", name="uq_guild_roster_identity"),
        Index("ix_guild_roster_current_activity", "normalized_guild_name", "is_current", "last_activity_at"),
    )

    id = Column(Integer, primary_key=True)
    guild_name = Column(String(200), nullable=False, index=True)
    normalized_guild_name = Column(String(200), nullable=False, index=True)
    world_name = Column(String(100), nullable=False)
    normalized_world_name = Column(String(100), nullable=False)
    character_name = Column(String(100), nullable=False, index=True)
    normalized_character_name = Column(String(100), nullable=False, index=True)
    guild_rank = Column(String(100), nullable=True)
    level = Column(Integer, nullable=True)
    vocation = Column(String(100), nullable=True)
    last_activity_at = Column(DateTime(timezone=True), nullable=True, index=True)
    last_online_seen_at = Column(DateTime(timezone=True), nullable=True)
    first_synchronized_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_synchronized_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    is_current = Column(Boolean, nullable=False, default=True, index=True)
    source = Column(String(50), nullable=False, default="tibiadata")
    source_metadata = Column(JSONBType, nullable=False, default=dict)
    linked_user_character_id = Column(Integer, ForeignKey("user_characters.id", ondelete="SET NULL"), nullable=True, index=True)
    linked_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    linked_user_character = relationship("UserCharacter")
    linked_user = relationship("User")


class GuildManagementGrant(Base):
    __tablename__ = "guild_management_grants"
    __table_args__ = (
        UniqueConstraint("user_id", "normalized_guild_name", "capability", name="uq_guild_management_grant"),
        Index("ix_guild_management_grants_active", "user_id", "normalized_guild_name", "capability", postgresql_where=text("revoked_at IS NULL"), sqlite_where=text("revoked_at IS NULL")),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    guild_name = Column(String(200), nullable=False, index=True)
    normalized_guild_name = Column(String(200), nullable=False, index=True)
    capability = Column(String(80), nullable=False, index=True)
    granted_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    granted_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    revoked_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    reason = Column(Text, nullable=True)
    audit_metadata = Column(JSONBType, nullable=False, default=dict)

    user = relationship("User", foreign_keys=[user_id])
    granted_by = relationship("User", foreign_keys=[granted_by_id])
    revoked_by = relationship("User", foreign_keys=[revoked_by_id])
