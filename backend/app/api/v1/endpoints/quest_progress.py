"""Authenticated per-character Quest completion endpoints."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.v1.endpoints.auth import get_current_user
from app.db.database import get_db
from app.models.external_data import TibiaWikiQuest
from app.models.quest_progress import QuestCompletion
from app.models.user import User
from app.models.user_character import UserCharacter
from app.services.text_utils import normalize_search_text

router = APIRouter(prefix="/quest-progress", tags=["Quest Progress"])


class QuestCompletionUpdate(BaseModel):
    completed: bool


class QuestCompletionResponse(BaseModel):
    quest_id: int
    character_id: int
    completed: bool
    completed_at: str | None = None


def _quest_by_identifier(db: Session, identifier: str) -> TibiaWikiQuest:
    query = db.query(TibiaWikiQuest)
    if identifier.isdigit():
        quest = query.filter(
            or_(
                TibiaWikiQuest.id == int(identifier),
                TibiaWikiQuest.external_id == identifier,
            )
        ).first()
    else:
        quest = query.filter(
            or_(
                TibiaWikiQuest.slug == identifier,
                TibiaWikiQuest.normalized_name == normalize_search_text(identifier),
            )
        ).first()
    if quest is None:
        raise HTTPException(status_code=404, detail="Quest not found")
    return quest


def _verified_character(db: Session, user_id: int, character_id: int) -> UserCharacter:
    character = (
        db.query(UserCharacter)
        .filter(
            UserCharacter.id == character_id,
            UserCharacter.user_id == user_id,
            UserCharacter.ownership_status == "verified",
        )
        .first()
    )
    if character is None:
        raise HTTPException(status_code=404, detail="Verified character not found")
    return character


def _response(
    quest: TibiaWikiQuest,
    character: UserCharacter,
    completion: QuestCompletion | None,
) -> QuestCompletionResponse:
    return QuestCompletionResponse(
        quest_id=quest.id,
        character_id=character.id,
        completed=completion is not None,
        completed_at=(completion.completed_at.isoformat() if completion and completion.completed_at else None),
    )


@router.get("/{identifier}", response_model=QuestCompletionResponse)
def get_quest_completion(
    identifier: str,
    character_id: int = Query(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    quest = _quest_by_identifier(db, identifier)
    character = _verified_character(db, current_user.id, character_id)
    completion = (
        db.query(QuestCompletion)
        .filter(
            QuestCompletion.character_id == character.id,
            QuestCompletion.quest_id == quest.id,
        )
        .first()
    )
    return _response(quest, character, completion)


@router.put("/{identifier}", response_model=QuestCompletionResponse)
def set_quest_completion(
    identifier: str,
    payload: QuestCompletionUpdate,
    character_id: int = Query(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    quest = _quest_by_identifier(db, identifier)
    character = _verified_character(db, current_user.id, character_id)
    completion = (
        db.query(QuestCompletion)
        .filter(
            QuestCompletion.character_id == character.id,
            QuestCompletion.quest_id == quest.id,
        )
        .first()
    )

    if payload.completed:
        if completion is None:
            completion = QuestCompletion(
                character_id=character.id,
                quest_id=quest.id,
                completed_at=datetime.now(UTC),
            )
            db.add(completion)
            db.commit()
            db.refresh(completion)
        return _response(quest, character, completion)

    if completion is not None:
        db.delete(completion)
        db.commit()
    return _response(quest, character, None)
