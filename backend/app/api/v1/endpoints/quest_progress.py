"""Authenticated per-character Quest progress endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

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

QuestProgressStatus = Literal["not_started", "in_progress", "completed"]


class QuestProgressUpdate(BaseModel):
    # `completed` is retained for backwards compatibility with the original
    # complete/incomplete control.
    completed: bool | None = None
    status: QuestProgressStatus | None = None
    completed_mission_ids: list[str] | None = None


class QuestProgressResponse(BaseModel):
    quest_id: int
    character_id: int
    status: QuestProgressStatus
    completed: bool
    completed_mission_ids: list[str]
    completed_steps: int
    total_steps: int
    current_mission_id: str | None = None
    completed_at: str | None = None
    updated_at: str | None = None


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


def _ordered_mission_ids(quest: TibiaWikiQuest) -> list[str]:
    return [str(mission.id) for mission in sorted(quest.missions, key=lambda mission: mission.sequence)]


def _validated_mission_ids(quest: TibiaWikiQuest, requested: list[str]) -> list[str]:
    ordered = _ordered_mission_ids(quest)
    allowed = set(ordered)
    normalized: set[str] = set()

    for value in requested:
        try:
            mission_id = str(UUID(str(value)))
        except (TypeError, ValueError, AttributeError) as exc:
            raise HTTPException(status_code=400, detail="Invalid Quest mission id") from exc
        if mission_id not in allowed:
            raise HTTPException(status_code=400, detail="Quest mission does not belong to this Quest")
        normalized.add(mission_id)

    return [mission_id for mission_id in ordered if mission_id in normalized]


def _response(
    quest: TibiaWikiQuest,
    character: UserCharacter,
    progress: QuestCompletion | None,
) -> QuestProgressResponse:
    mission_ids = _ordered_mission_ids(quest)
    status: QuestProgressStatus = "not_started" if progress is None else progress.status
    completed_ids = [] if progress is None else list(progress.completed_mission_ids or [])
    if status == "completed":
        completed_ids = mission_ids
    else:
        completed_ids = [mission_id for mission_id in mission_ids if mission_id in set(completed_ids)]

    completed_set = set(completed_ids)
    current_mission_id = next((mission_id for mission_id in mission_ids if mission_id not in completed_set), None)

    return QuestProgressResponse(
        quest_id=quest.id,
        character_id=character.id,
        status=status,
        completed=status == "completed",
        completed_mission_ids=completed_ids,
        completed_steps=len(completed_ids),
        total_steps=len(mission_ids),
        current_mission_id=None if status == "completed" else current_mission_id,
        completed_at=(progress.completed_at.isoformat() if progress and progress.completed_at else None),
        updated_at=(progress.updated_at.isoformat() if progress and progress.updated_at else None),
    )


@router.get("", response_model=list[QuestProgressResponse])
def list_quest_progress(
    character_id: int = Query(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    character = _verified_character(db, current_user.id, character_id)
    rows = (
        db.query(QuestCompletion)
        .filter(QuestCompletion.character_id == character.id)
        .order_by(QuestCompletion.updated_at.desc(), QuestCompletion.id.desc())
        .all()
    )
    return [_response(row.quest, character, row) for row in rows]


@router.get("/{identifier}", response_model=QuestProgressResponse)
def get_quest_progress(
    identifier: str,
    character_id: int = Query(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    quest = _quest_by_identifier(db, identifier)
    character = _verified_character(db, current_user.id, character_id)
    progress = (
        db.query(QuestCompletion)
        .filter(
            QuestCompletion.character_id == character.id,
            QuestCompletion.quest_id == quest.id,
        )
        .first()
    )
    return _response(quest, character, progress)


@router.put("/{identifier}", response_model=QuestProgressResponse)
def set_quest_progress(
    identifier: str,
    payload: QuestProgressUpdate,
    character_id: int = Query(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    quest = _quest_by_identifier(db, identifier)
    character = _verified_character(db, current_user.id, character_id)
    progress = (
        db.query(QuestCompletion)
        .filter(
            QuestCompletion.character_id == character.id,
            QuestCompletion.quest_id == quest.id,
        )
        .first()
    )

    if payload.completed is not None and payload.status is not None:
        completed_status = payload.status == "completed"
        if payload.status == "not_started" and payload.completed is False:
            pass
        elif completed_status != payload.completed:
            raise HTTPException(status_code=400, detail="Conflicting Quest progress state")

    requested_ids = None
    if payload.completed_mission_ids is not None:
        requested_ids = _validated_mission_ids(quest, payload.completed_mission_ids)

    target_status = payload.status
    if payload.completed is True:
        target_status = "completed"
    elif payload.completed is False and payload.status is None and requested_ids is None:
        # Preserve the original API contract: completed=false clears progress.
        target_status = "not_started"

    if target_status is None and requested_ids is not None:
        total = len(_ordered_mission_ids(quest))
        target_status = (
            "completed" if total > 0 and len(requested_ids) == total
            else "in_progress" if requested_ids
            else "not_started"
        )

    if target_status is None:
        raise HTTPException(status_code=400, detail="Quest progress update is empty")

    if target_status == "not_started":
        if progress is not None:
            db.delete(progress)
            db.commit()
        return _response(quest, character, None)

    now = datetime.now(UTC)
    was_completed = progress is not None and progress.status == "completed"
    if progress is None:
        progress = QuestCompletion(character_id=character.id, quest_id=quest.id)
        db.add(progress)

    progress.status = target_status
    if target_status == "completed":
        progress.completed_mission_ids = _ordered_mission_ids(quest)
        if not was_completed or progress.completed_at is None:
            progress.completed_at = now
    else:
        progress.completed_mission_ids = requested_ids if requested_ids is not None else list(progress.completed_mission_ids or [])
        progress.completed_at = None

    db.commit()
    db.refresh(progress)
    return _response(quest, character, progress)
