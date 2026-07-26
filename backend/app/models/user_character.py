from sqlalchemy import CheckConstraint, Column, Integer, String, DateTime, ForeignKey, Index, text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base

class UserCharacter(Base):
    __tablename__ = "user_characters"
    __table_args__ = (
        Index(
            "uq_user_characters_verified_normalized_name",
            "normalized_name",
            unique=True,
            postgresql_where=text("ownership_status = 'verified'"),
            sqlite_where=text("ownership_status = 'verified'"),
        ),
        CheckConstraint(
            "ownership_status != 'verified' OR normalized_name IS NOT NULL",
            name="ck_user_character_verified_has_normalized_name",
        ),
        CheckConstraint(
            "ownership_status IN ('legacy_unverified','verified','disputed')",
            name="ck_user_character_ownership_status",
        ),
    )
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    character_name = Column(String(100), unique=True, index=True, nullable=False)
    normalized_name = Column(String(100), nullable=True, index=True)
    ownership_status = Column(String(30), nullable=False, default="legacy_unverified")
    ownership_verified_at = Column(DateTime(timezone=True), nullable=True)
    ownership_claim_id = Column(Integer, ForeignKey("character_ownership_claims.id", ondelete="SET NULL"), nullable=True)
    # optional cached Tibia data
    level = Column(Integer, nullable=True)
    vocation = Column(String(50), nullable=True)
    world_name = Column(String(100), nullable=True)
    guild_name = Column(String(200), nullable=True)
    guild_rank = Column(String(100), nullable=True)
    residence = Column(String(100), nullable=True)
    achievement_points = Column(Integer, nullable=True)
    sex = Column(String(20), nullable=True)
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    last_seen = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="characters")
