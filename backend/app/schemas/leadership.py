from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

ApplicationStatus = Literal["applied", "under_review", "more_information_requested", "interview", "voting", "accepted", "rejected", "withdrawn", "cancelled"]


class OpeningCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    description: Optional[str] = Field(None, max_length=3000)
    responsibilities: str = Field(..., min_length=10, max_length=5000)
    requirements: str = Field(..., min_length=10, max_length=5000)
    openings_count: int = Field(1, ge=1, le=20)
    application_deadline: Optional[datetime] = None
    allow_viceleader_review: bool = True
    voting_enabled: bool = False
    votes_required: int = Field(1, ge=1, le=100)
    target_count: int = Field(4, ge=1, le=100)


class OpeningUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=200)
    description: Optional[str] = Field(None, max_length=3000)
    responsibilities: Optional[str] = Field(None, min_length=10, max_length=5000)
    requirements: Optional[str] = Field(None, min_length=10, max_length=5000)
    openings_count: Optional[int] = Field(None, ge=1, le=20)
    application_deadline: Optional[datetime] = None
    allow_viceleader_review: Optional[bool] = None
    voting_enabled: Optional[bool] = None
    votes_required: Optional[int] = Field(None, ge=1, le=100)


class ApplicationCreate(BaseModel):
    character_name: str = Field(..., min_length=2, max_length=100)
    why_apply: str = Field(..., min_length=20, max_length=2000)
    contribution: str = Field(..., min_length=20, max_length=2000)
    availability: str = Field(..., min_length=5, max_length=1000)
    leadership_experience: str = Field(..., min_length=5, max_length=2000)
    applicant_message: Optional[str] = Field(None, max_length=2000)
    conduct_agreed: bool

    @field_validator("conduct_agreed")
    @classmethod
    def conduct_required(cls, value: bool) -> bool:
        if not value:
            raise ValueError("Code of conduct agreement is required")
        return value


class StatusUpdate(BaseModel):
    status: ApplicationStatus
    reason: Optional[str] = Field(None, max_length=2000)
    admin_override: bool = False


class MessageCreate(BaseModel):
    audience: Literal["applicant", "reviewers", "both"]
    message_type: Literal["applicant_reply", "information_request", "internal_comment", "interview", "decision", "general"]
    body: str = Field(..., min_length=2, max_length=5000)


class InterviewCreate(BaseModel):
    scheduled_at: datetime
    timezone: str = Field(..., min_length=1, max_length=64)
    meeting_location: str = Field(..., min_length=2, max_length=255)
    interview_notes: Optional[str] = Field(None, max_length=5000)
    completed: bool = False


class VoteCreate(BaseModel):
    vote: Literal["support", "neutral", "oppose"]
    comment: Optional[str] = Field(None, max_length=2000)


class DecisionCreate(BaseModel):
    decision: Literal["accepted", "rejected"]
    reason: Optional[str] = Field(None, max_length=2000)

    @field_validator("reason")
    @classmethod
    def rejection_reason_required(cls, value: Optional[str], info):
        if info.data.get("decision") == "rejected" and not (value or "").strip():
            raise ValueError("A rejection reason is required")
        return value


class PromotionUpdate(BaseModel):
    completed: bool
    note: Optional[str] = Field(None, max_length=2000)


class AssignmentEnd(BaseModel):
    reason: str = Field(..., min_length=3, max_length=2000)
