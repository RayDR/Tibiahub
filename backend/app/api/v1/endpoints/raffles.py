from __future__ import annotations

from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, selectinload

from app.api.v1.endpoints.auth import get_current_admin_user, get_current_manager_user
from app.core.permissions import can_manage_guild
from app.core import security
from app.db.database import get_db
from app.models.events import Event
from app.models.guild import Announcement, AnnouncementType
from app.models.raffle import Raffle, RaffleParticipant, RafflePrize, RaffleWinner
from app.models.user import User
from app.models.user_character import UserCharacter
from app.schemas.raffle import RaffleCreate, RaffleExecutionResponse, RafflePrizeCreate, RaffleResponse, RaffleRerunRequest
from app.services.raffle_service import RaffleService
from app.services.tibia_api import get_guild_info
from app.services.text_utils import normalize_search_text, slugify

router = APIRouter()


class PublicRaffleRegisterRequest(BaseModel):
    character_name: str = Field(..., min_length=2)


def _require_raffle_management(current_user: User, raffle: Raffle) -> None:
    if can_manage_guild(current_user, raffle.guild_name):
        return
    raise HTTPException(status_code=403, detail="Insufficient permissions for this guild raffle")


def _get_or_create_public_user(db: Session, character_name: str) -> User:
    normalized = normalize_search_text(character_name)

    linked_character = (
        db.query(UserCharacter)
        .filter(UserCharacter.character_name.ilike(character_name))
        .first()
    )
    if linked_character:
        return linked_character.user

    linked_user = db.query(User).filter(User.tibia_character_name.ilike(character_name)).first()
    if linked_user:
        return linked_user

    guest_username = f"guest_{slugify(character_name)}"
    existing_guest = db.query(User).filter(User.username == guest_username).first()
    if existing_guest:
        return existing_guest

    guest = User(
        username=guest_username,
        email=None,
        hashed_password=security.get_password_hash(f"guest::{normalized}::{datetime.utcnow().isoformat()}"),
        guild_rank="Member",
        is_active=True,
        is_superuser=False,
        tibia_character_name=character_name,
    )
    db.add(guest)
    db.flush()
    return guest


@router.get("/", response_model=List[RaffleResponse])
def list_raffles(
    db: Session = Depends(get_db),
    include_deleted: bool = False,
    current_user: User = Depends(get_current_manager_user),
):
    raffles = (
        db.query(Raffle)
        .options(
            selectinload(Raffle.participants).selectinload(RaffleParticipant.user),
            selectinload(Raffle.prizes),
            selectinload(Raffle.winners).selectinload(RaffleWinner.participant).selectinload(RaffleParticipant.user),
            selectinload(Raffle.winners).selectinload(RaffleWinner.prize),
        )
        .filter(Raffle.is_deleted == True if include_deleted else Raffle.is_deleted == False)
        .order_by(Raffle.created_at.desc())
        .all()
    )
    visible = [raffle for raffle in raffles if can_manage_guild(current_user, raffle.guild_name)]
    return [RaffleService.serialize_raffle(raffle) for raffle in visible]


@router.get("/{raffle_id}", response_model=RaffleResponse)
def get_raffle(
    raffle_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager_user),
):
    _ = current_user
    raffle = (
        db.query(Raffle)
        .options(
            selectinload(Raffle.participants).selectinload(RaffleParticipant.user),
            selectinload(Raffle.prizes),
            selectinload(Raffle.winners).selectinload(RaffleWinner.participant).selectinload(RaffleParticipant.user),
            selectinload(Raffle.winners).selectinload(RaffleWinner.prize),
        )
        .filter(Raffle.id == raffle_id)
        .first()
    )
    if not raffle:
        raise HTTPException(status_code=404, detail="Raffle not found")
    _require_raffle_management(current_user, raffle)
    if raffle.is_deleted:
        raise HTTPException(status_code=404, detail="Raffle not found")
    return RaffleService.serialize_raffle(raffle)


@router.post("/", response_model=RaffleResponse, status_code=status.HTTP_201_CREATED)
def create_raffle(
    payload: RaffleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager_user),
):
    if not can_manage_guild(current_user, payload.guild_name):
        raise HTTPException(status_code=403, detail="You can only manage raffles for your guild")
    raffle = Raffle(
        title=payload.title,
        description=payload.description,
        guild_name=payload.guild_name,
        created_by_id=current_user.id,
        status="draft",
    )
    db.add(raffle)
    db.flush()

    announcement = Announcement(
        title=f"Raffle: {payload.title}",
        content=payload.description or f"New raffle created for guild {payload.guild_name}.",
        author_id=current_user.id,
        type=AnnouncementType.GENERAL,
    )
    db.add(announcement)
    db.flush()

    raffle_event = Event(
        type="raffle",
        title=payload.title,
        description=payload.description or "Guild raffle event",
        rules="One participant per account. Vice leaders get +10% weight.",
        reward=", ".join([f"{prize.name}: {prize.reward}" for prize in (payload.prizes or [])]) or "Guild rewards",
        start_date=datetime.utcnow(),
        draw_date=datetime.utcnow() + timedelta(days=1),
        status="active",
        is_active=True,
        is_public=True,
        participant_mode="manual",
        guild_name=payload.guild_name,
        creator_id=current_user.id,
        announcement_id=announcement.id,
    )
    db.add(raffle_event)

    prizes = payload.prizes or []
    for index, prize in enumerate(prizes, start=1):
        db.add(
            RafflePrize(
                raffle_id=raffle.id,
                name=prize.name,
                reward=prize.reward,
                order_index=prize.order_index or index,
            )
        )

    db.commit()
    db.refresh(raffle)
    return get_raffle(raffle.id, db, current_user)


@router.post("/{raffle_id}/prizes", response_model=RaffleResponse)
def add_prize(
    raffle_id: int,
    payload: RafflePrizeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager_user),
):
    raffle = db.query(Raffle).filter(Raffle.id == raffle_id).first()
    if not raffle:
        raise HTTPException(status_code=404, detail="Raffle not found")
    _require_raffle_management(current_user, raffle)

    current_max = db.query(RafflePrize.order_index).filter(RafflePrize.raffle_id == raffle_id).order_by(RafflePrize.order_index.desc()).first()
    order_index = payload.order_index or ((current_max[0] + 1) if current_max else 1)
    db.add(RafflePrize(raffle_id=raffle_id, name=payload.name, reward=payload.reward, order_index=order_index))
    db.commit()
    return get_raffle(raffle_id, db, current_user)


@router.post("/{raffle_id}/participants/sync", response_model=RaffleResponse)
async def sync_raffle_participants(
    raffle_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager_user),
):
    raffle = db.query(Raffle).filter(Raffle.id == raffle_id).first()
    if not raffle:
        raise HTTPException(status_code=404, detail="Raffle not found")
    _require_raffle_management(current_user, raffle)
    try:
        await RaffleService.sync_participants(db, raffle)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return get_raffle(raffle_id, db, current_user)


@router.post("/{raffle_id}/draw", response_model=RaffleExecutionResponse)
def execute_raffle(
    raffle_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager_user),
):
    raffle = (
        db.query(Raffle)
        .options(
            selectinload(Raffle.participants).selectinload(RaffleParticipant.user),
            selectinload(Raffle.prizes),
            selectinload(Raffle.winners).selectinload(RaffleWinner.participant).selectinload(RaffleParticipant.user),
            selectinload(Raffle.winners).selectinload(RaffleWinner.prize),
        )
        .filter(Raffle.id == raffle_id)
        .first()
    )
    if not raffle:
        raise HTTPException(status_code=404, detail="Raffle not found")
    _require_raffle_management(current_user, raffle)
    try:
        winners = RaffleService.execute_raffle(db, raffle, current_user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "raffle_id": raffle.id,
        "run_number": raffle.current_run_number,
        "winner_count": len(winners),
        "winners": [RaffleService.serialize_winner(winner) for winner in winners],
    }


@router.post("/{raffle_id}/rerun", response_model=RaffleExecutionResponse)
def rerun_raffle(
    raffle_id: int,
    payload: RaffleRerunRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager_user),
):
    raffle = (
        db.query(Raffle)
        .options(
            selectinload(Raffle.participants).selectinload(RaffleParticipant.user),
            selectinload(Raffle.prizes),
            selectinload(Raffle.winners).selectinload(RaffleWinner.participant).selectinload(RaffleParticipant.user),
            selectinload(Raffle.winners).selectinload(RaffleWinner.prize),
        )
        .filter(Raffle.id == raffle_id)
        .first()
    )
    if not raffle:
        raise HTTPException(status_code=404, detail="Raffle not found")
    _require_raffle_management(current_user, raffle)
    try:
        winners = RaffleService.execute_raffle(db, raffle, current_user, rerun_reason=payload.reason)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "raffle_id": raffle.id,
        "run_number": raffle.current_run_number,
        "winner_count": len(winners),
        "winners": [RaffleService.serialize_winner(winner) for winner in winners],
    }


@router.delete("/{raffle_id}/participants/{participant_id}", response_model=RaffleResponse)
def remove_participant(
    raffle_id: int,
    participant_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager_user),
):
    raffle = db.query(Raffle).filter(Raffle.id == raffle_id).first()
    if not raffle:
        raise HTTPException(status_code=404, detail="Raffle not found")
    _require_raffle_management(current_user, raffle)

    participant = (
        db.query(RaffleParticipant)
        .filter(RaffleParticipant.id == participant_id, RaffleParticipant.raffle_id == raffle_id)
        .first()
    )
    if not participant:
        raise HTTPException(status_code=404, detail="Participant not found")
    participant.is_deleted = True
    participant.deleted_at = datetime.utcnow()
    participant.deleted_by_user_id = current_user.id
    participant.is_eligible = False
    participant.delete_reason = "removed by manager"
    db.commit()
    return get_raffle(raffle_id, db, current_user)


@router.delete("/{raffle_id}", response_model=RaffleResponse)
def soft_delete_raffle(
    raffle_id: int,
    reason: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager_user),
):
    raffle = db.query(Raffle).filter(Raffle.id == raffle_id).first()
    if not raffle:
        raise HTTPException(status_code=404, detail="Raffle not found")
    _require_raffle_management(current_user, raffle)
    raffle.is_deleted = True
    raffle.deleted_at = datetime.utcnow()
    raffle.deleted_by_user_id = current_user.id
    raffle.delete_reason = reason
    raffle.is_active = False
    db.commit()
    db.refresh(raffle)
    return RaffleService.serialize_raffle(raffle)


@router.post("/{raffle_id}/restore", response_model=RaffleResponse)
def restore_raffle(
    raffle_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager_user),
):
    raffle = db.query(Raffle).filter(Raffle.id == raffle_id).first()
    if not raffle:
        raise HTTPException(status_code=404, detail="Raffle not found")
    _require_raffle_management(current_user, raffle)
    raffle.is_deleted = False
    raffle.deleted_at = None
    raffle.deleted_by_user_id = None
    raffle.delete_reason = None
    raffle.is_active = True
    db.commit()
    return get_raffle(raffle_id, db, current_user)


@router.get("/public/{raffle_id}", response_model=RaffleResponse)
def get_public_raffle(
    raffle_id: int,
    db: Session = Depends(get_db),
):
    raffle = (
        db.query(Raffle)
        .options(
            selectinload(Raffle.participants).selectinload(RaffleParticipant.user),
            selectinload(Raffle.prizes),
            selectinload(Raffle.winners).selectinload(RaffleWinner.participant).selectinload(RaffleParticipant.user),
            selectinload(Raffle.winners).selectinload(RaffleWinner.prize),
        )
        .filter(Raffle.id == raffle_id, Raffle.is_deleted == False)
        .first()
    )
    if not raffle:
        raise HTTPException(status_code=404, detail="Raffle not found")
    return RaffleService.serialize_raffle(raffle)


@router.post("/public/{raffle_id}/register", response_model=RaffleResponse)
async def register_public_participant(
    raffle_id: int,
    payload: PublicRaffleRegisterRequest,
    db: Session = Depends(get_db),
):
    raffle = db.query(Raffle).filter(Raffle.id == raffle_id).first()
    if not raffle:
        raise HTTPException(status_code=404, detail="Raffle not found")

    guild_info = await get_guild_info(raffle.guild_name)
    if not guild_info:
        raise HTTPException(status_code=503, detail="Guild data unavailable")

    member_lookup = {
        (member.get("name") or "").strip().lower(): member
        for member in (guild_info.get("members") or [])
        if (member.get("name") or "").strip()
    }
    character_name = payload.character_name.strip()
    member = member_lookup.get(character_name.lower())
    if not member:
        raise HTTPException(status_code=400, detail="Character does not belong to the raffle guild")

    user = _get_or_create_public_user(db, member.get("name") or character_name)

    existing_user = (
        db.query(RaffleParticipant)
        .filter(RaffleParticipant.raffle_id == raffle.id, RaffleParticipant.user_id == user.id)
        .first()
    )
    if existing_user:
        raise HTTPException(status_code=400, detail="This account is already registered")

    existing_character = (
        db.query(RaffleParticipant)
        .filter(RaffleParticipant.raffle_id == raffle.id, RaffleParticipant.character_name.ilike(character_name))
        .first()
    )
    if existing_character:
        raise HTTPException(status_code=400, detail="This character is already registered")

    rank = member.get("rank") or member.get("title") or member.get("position")
    participant = RaffleParticipant(
        raffle_id=raffle.id,
        user_id=user.id,
        character_name=member.get("name") or character_name,
        guild_rank=rank,
        weight=1.1 if str(rank or "").strip().lower() == "vice leader" else 1.0,
        source="public_registration",
        source_data=member,
    )
    db.add(participant)
    db.commit()
    return get_public_raffle(raffle_id, db)
