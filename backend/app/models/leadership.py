from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class GuildLeadershipRole(Base):
    __tablename__ = "guild_leadership_roles"
    __table_args__ = (UniqueConstraint("guild_name", "role_code", name="uq_leadership_role_guild_code"),)

    id = Column(Integer, primary_key=True)
    guild_name = Column(String(200), nullable=False, index=True)
    role_code = Column(String(50), nullable=False)
    display_name_key = Column(String(200), nullable=False)
    description_key = Column(String(200), nullable=False)
    target_count = Column(Integer, nullable=False, default=4)
    is_active = Column(Boolean, nullable=False, default=True)
    recruitment_enabled = Column(Boolean, nullable=False, default=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class GuildLeadershipOpening(Base):
    __tablename__ = "guild_leadership_openings"

    id = Column(Integer, primary_key=True)
    guild_name = Column(String(200), nullable=False, index=True)
    role_id = Column(Integer, ForeignKey("guild_leadership_roles.id"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    responsibilities = Column(Text, nullable=False)
    requirements = Column(Text, nullable=False)
    openings_count = Column(Integer, nullable=False, default=1)
    application_deadline = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(20), nullable=False, default="draft", index=True)
    allow_viceleader_review = Column(Boolean, nullable=False, default=True)
    voting_enabled = Column(Boolean, nullable=False, default=False)
    votes_required = Column(Integer, nullable=False, default=1)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    opened_at = Column(DateTime(timezone=True), nullable=True)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    version = Column(Integer, nullable=False, default=1)

    role = relationship("GuildLeadershipRole")
    applications = relationship("GuildLeadershipApplication", back_populates="opening")


class GuildLeadershipApplication(Base):
    __tablename__ = "guild_leadership_applications"
    __table_args__ = (Index("uq_leadership_active_application", "opening_id", "applicant_user_id", unique=True, sqlite_where=text("status IN ('applied','under_review','more_information_requested','interview','voting')"), postgresql_where=text("status IN ('applied','under_review','more_information_requested','interview','voting')")),)

    id = Column(Integer, primary_key=True)
    opening_id = Column(Integer, ForeignKey("guild_leadership_openings.id"), nullable=False, index=True)
    applicant_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    character_name = Column(String(100), nullable=False)
    status = Column(String(40), nullable=False, default="applied", index=True)
    why_apply = Column(Text, nullable=False)
    contribution = Column(Text, nullable=False)
    availability = Column(Text, nullable=False)
    leadership_experience = Column(Text, nullable=False)
    applicant_message = Column(Text, nullable=True)
    profile_snapshot = Column(JSON, nullable=False, default=dict)
    conduct_agreed_at = Column(DateTime(timezone=True), nullable=False)
    conduct_version = Column(String(30), nullable=False)
    submitted_at = Column(DateTime(timezone=True), nullable=False)
    withdrawn_at = Column(DateTime(timezone=True), nullable=True)
    final_decision_at = Column(DateTime(timezone=True), nullable=True)
    final_decision_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    rejection_reason = Column(Text, nullable=True)
    accepted_assignment_id = Column(Integer, ForeignKey("guild_leadership_assignments.id", use_alter=True), nullable=True)
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    opening = relationship("GuildLeadershipOpening", back_populates="applications")
    applicant = relationship("User", foreign_keys=[applicant_user_id])
    histories = relationship("GuildLeadershipApplicationHistory", back_populates="application", order_by="GuildLeadershipApplicationHistory.created_at")
    messages = relationship("GuildLeadershipApplicationMessage", back_populates="application", order_by="GuildLeadershipApplicationMessage.created_at")
    votes = relationship("GuildLeadershipVote", back_populates="application")
    interview = relationship("GuildLeadershipInterview", back_populates="application", uselist=False)


class GuildLeadershipAssignment(Base):
    __tablename__ = "guild_leadership_assignments"
    __table_args__ = (Index("uq_leadership_active_assignment", "guild_name", "role_id", "user_id", unique=True, sqlite_where=text("is_active = 1"), postgresql_where=text("is_active IS TRUE")),)

    id = Column(Integer, primary_key=True)
    guild_name = Column(String(200), nullable=False, index=True)
    role_id = Column(Integer, ForeignKey("guild_leadership_roles.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    character_name = Column(String(100), nullable=False)
    assigned_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    assignment_source = Column(String(40), nullable=False, default="recruitment")
    started_at = Column(DateTime(timezone=True), nullable=False)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    notes = Column(Text, nullable=True)
    in_game_promotion_status = Column(String(20), nullable=False, default="pending")
    in_game_promoted_at = Column(DateTime(timezone=True), nullable=True)
    in_game_promoted_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    role = relationship("GuildLeadershipRole")
    user = relationship("User", foreign_keys=[user_id])


class GuildLeadershipApplicationHistory(Base):
    __tablename__ = "guild_leadership_application_history"
    id = Column(Integer, primary_key=True)
    application_id = Column(Integer, ForeignKey("guild_leadership_applications.id"), nullable=False, index=True)
    from_status = Column(String(40), nullable=True)
    to_status = Column(String(40), nullable=False)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    actor_context = Column(String(40), nullable=False)
    reason = Column(Text, nullable=True)
    safe_metadata = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    application = relationship("GuildLeadershipApplication", back_populates="histories")


class GuildLeadershipApplicationMessage(Base):
    __tablename__ = "guild_leadership_application_messages"
    id = Column(Integer, primary_key=True)
    application_id = Column(Integer, ForeignKey("guild_leadership_applications.id"), nullable=False, index=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    audience = Column(String(20), nullable=False)
    message_type = Column(String(40), nullable=False)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    edited_at = Column(DateTime(timezone=True), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    application = relationship("GuildLeadershipApplication", back_populates="messages")
    author = relationship("User")


class GuildLeadershipInterview(Base):
    __tablename__ = "guild_leadership_interviews"
    id = Column(Integer, primary_key=True)
    application_id = Column(Integer, ForeignKey("guild_leadership_applications.id"), nullable=False, unique=True)
    scheduled_at = Column(DateTime(timezone=True), nullable=False)
    timezone = Column(String(64), nullable=False)
    meeting_location = Column(String(255), nullable=False)
    interview_notes = Column(Text, nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    completed_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    application = relationship("GuildLeadershipApplication", back_populates="interview")


class GuildLeadershipVote(Base):
    __tablename__ = "guild_leadership_votes"
    __table_args__ = (UniqueConstraint("application_id", "voter_user_id", name="uq_leadership_vote_application_voter"),)
    id = Column(Integer, primary_key=True)
    application_id = Column(Integer, ForeignKey("guild_leadership_applications.id"), nullable=False, index=True)
    voter_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    vote = Column(String(20), nullable=False)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    application = relationship("GuildLeadershipApplication", back_populates="votes")
    voter = relationship("User")
