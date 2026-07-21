from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, selectinload

from app.api.v1.endpoints.auth import get_current_active_user, get_current_manager_user
from app.core.permissions import (
    can_administer_raffle, can_execute_raffle, can_publish_raffle,
    can_update_raffle_delivery, can_view_private_raffle_results,
    can_manage_guild, is_global_admin, is_matching_raffle_leader,
)
from app.core import security
from app.db.database import get_db
from app.models.events import Event
from app.models.guild import Announcement, AnnouncementType
from app.models.raffle import (
    Raffle, RaffleEligibilitySnapshot, RaffleManagerGrant, RaffleParticipant,
    RafflePrize, RafflePrizeDelivery, RaffleRun, RaffleRunResult, RaffleWinner,
)
from app.models.user import User
from app.models.user_character import UserCharacter
from app.schemas.raffle import (
    RaffleCreate,
    RaffleDrawRequest,
    RaffleExecutionResponse,
    RafflePrizeCreate,
    RaffleResponse,
    RaffleRerunRequest,
    RaffleUpdate,
    RaffleWeightUpdateRequest,
    AutomaticExecutionRequest,
    AutomaticRerunRequest,
    AutomaticRunResponse,
    DeliveryUpdateRequest,
    DeliveryResponse,
    EligibilityPreviewResponse,
    ManagerGrantRequest,
    ManagerGrantResponse,
    PublicationResponse,
    PublicRaffleResponse,
)
from app.services.automatic_raffle_service import AutomaticRaffleError, AutomaticRaffleService, serialize_run, validate_automatic_prizes
from app.services.raffle_eligibility_service import RaffleEligibilityError, RaffleEligibilityService
from app.services.raffle_service import RaffleService, normalize_access_mode, normalize_status, sync_legacy_raffle_fields
from app.services.public_code import generate_unique_code
from app.services.tibia_api import get_character_info, get_guild_info
from app.services.text_utils import normalize_search_text, slugify

router = APIRouter()
logger = logging.getLogger(__name__)


class PublicRaffleRegisterRequest(BaseModel):
    character_name: str = Field(..., min_length=2)


def _ensure_public_code(db: Session, raffle: Raffle) -> None:
    if raffle.public_code:
        return
    raffle.public_code = generate_unique_code(db, Raffle)
    db.add(raffle)


def _require_raffle_management(current_user: User, raffle: Raffle) -> None:
    if can_manage_guild(current_user, raffle.guild_name):
        return
    raise HTTPException(status_code=403, detail="Insufficient permissions for this guild raffle")


def _ensure_raffle_state_for_registration(raffle: Raffle) -> None:
    sync_legacy_raffle_fields(raffle)
    if raffle.is_deleted or raffle.status in {"deleted", "draft"}:
        raise HTTPException(status_code=404, detail="Raffle not available")
    if raffle.status != "open":
        raise HTTPException(status_code=400, detail="This raffle is not accepting participants")


def _apply_raffle_defaults(raffle: Raffle) -> Raffle:
    raffle.access_mode = normalize_access_mode(getattr(raffle, "access_mode", None), getattr(raffle, "visibility", None))
    raffle.status = normalize_status(getattr(raffle, "status", None), is_deleted=raffle.is_deleted)
    raffle.show_participants = bool(getattr(raffle, "show_participants", True))
    raffle.visibility = "private" if raffle.access_mode == "guild_only" else "public"
    raffle.registration_enabled = raffle.status == "open"
    raffle.is_active = raffle.status in {"draft", "open", "closed", "completed"}
    return raffle


def _serialize_public_raffle(db: Session, raffle: Raffle) -> dict:
    participants = [
        {"character_name": participant.character_name, "guild_rank": participant.guild_rank}
        for participant in raffle.participants
        if not participant.is_deleted
    ]
    winners = []
    if raffle.publication_status == "published":
        active_results = db.query(RaffleRunResult).join(RaffleRun).filter(
            RaffleRun.raffle_id == raffle.id,
            RaffleRunResult.is_active.is_(True),
        ).all()
        order = {"second": 0, "first": 1}
        for result in sorted(active_results, key=lambda row: order.get(row.prize_position, 99)):
            winners.append({
                "prize_position": result.prize_position,
                "prize_name": result.prize.name,
                "amount": result.prize.amount,
                "currency": result.prize.currency,
                "character_name": result.participant_character_name,
                "delivery_status": result.delivery.status,
                "delivery_deadline_at": result.delivery.delivery_deadline_at,
            })
    return {
        "public_code": raffle.public_code,
        "title": raffle.title,
        "description": raffle.description,
        "guild_name": raffle.guild_name,
        "access_mode": raffle.access_mode,
        "purpose": raffle.purpose,
        "timezone_name": raffle.timezone_name,
        "scheduled_run_at": raffle.scheduled_run_at,
        "status": raffle.status,
        "publication_status": raffle.publication_status,
        "show_participants": raffle.show_participants,
        "participant_count": len(participants),
        "participants": participants if raffle.show_participants else [],
        "prizes": [{
            "id": prize.id, "name": prize.name, "reward": prize.reward,
            "order_index": prize.order_index, "position": prize.position,
            "amount": prize.amount, "currency": prize.currency,
        } for prize in raffle.prizes],
        "winners": winners,
    }


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
        hashed_password=security.get_password_hash(f"guest::{normalized}::{datetime.now(UTC).isoformat()}"),
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
    current_user: User = Depends(get_current_active_user),
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
    visible = [raffle for raffle in raffles if can_administer_raffle(db, current_user, raffle)]

    updated = False
    for raffle in visible:
        if not raffle.public_code:
            _ensure_public_code(db, raffle)
            updated = True
    if updated:
        db.commit()

    return [RaffleService.serialize_raffle(raffle) for raffle in visible]


@router.get("/{raffle_id}", response_model=RaffleResponse)
def get_raffle(
    raffle_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
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
    _require_capability(can_view_private_raffle_results(db, current_user, raffle))
    if raffle.is_deleted:
        raise HTTPException(status_code=404, detail="Raffle not found")
    if not raffle.public_code:
        _ensure_public_code(db, raffle)
        db.commit()
        db.refresh(raffle)
    return RaffleService.serialize_raffle(raffle)


@router.post("/", response_model=RaffleResponse, status_code=status.HTTP_201_CREATED)
def create_raffle(
    payload: RaffleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager_user),
):
    automatic_stage1 = payload.run_mode == "automatic" or payload.purpose in {"test", "real"}
    allowed = (
        is_global_admin(current_user) or is_matching_raffle_leader(current_user, payload.guild_name)
        if automatic_stage1 else can_manage_guild(current_user, payload.guild_name)
    )
    if not allowed:
        raise HTTPException(status_code=403, detail="You can only manage raffles for your guild")
    access_mode = normalize_access_mode(payload.access_mode, payload.visibility)
    raffle = Raffle(
        title=payload.title,
        description=payload.description,
        public_code=generate_unique_code(db, Raffle),
        guild_name=payload.guild_name,
        access_mode=access_mode,
        show_participants=payload.show_participants,
        visibility="private" if access_mode == "guild_only" else "public",
        registration_enabled=False,
        run_mode=(payload.run_mode or "manual").lower(),
        scheduled_run_at=payload.scheduled_run_at,
        purpose=payload.purpose,
        timezone_name=payload.timezone_name,
        eligibility_days=payload.eligibility_days,
        eligibility_cutoff_at=payload.eligibility_cutoff_at,
        archive_after_days=max(1, min(365, payload.archive_after_days or 7)),
        created_by_id=current_user.id,
        status="draft",
    )
    _apply_raffle_defaults(raffle)
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
                position=prize.position,
                amount=prize.amount,
                currency=(prize.currency or "").upper() or None,
            )
        )

    if raffle.run_mode == "automatic" or raffle.purpose in {"test", "real"}:
        if raffle.run_mode != "automatic" or raffle.access_mode != "guild_only":
            raise HTTPException(status_code=400, detail="Test and real automatic raffles must be guild-only and automatic")
        try:
            db.flush()
            db.refresh(raffle)
            validate_automatic_prizes(raffle)
        except AutomaticRaffleError as exc:
            db.rollback()
            raise HTTPException(status_code=400, detail=exc.summary) from exc

    db.commit()
    db.refresh(raffle)
    return get_raffle(raffle.id, db, current_user)


@router.put("/{raffle_id}", response_model=RaffleResponse)
def update_raffle(
    raffle_id: int,
    payload: RaffleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    raffle = db.query(Raffle).filter(Raffle.id == raffle_id).first()
    if not raffle:
        raise HTTPException(status_code=404, detail="Raffle not found")
    automatic_stage1 = raffle.run_mode == "automatic" or raffle.purpose in {"test", "real"}
    _require_capability(can_administer_raffle(db, current_user, raffle) if automatic_stage1 else can_manage_guild(current_user, raffle.guild_name))
    if payload.guild_name is not None and payload.guild_name != raffle.guild_name:
        automatic_stage1 = raffle.run_mode == "automatic" or raffle.purpose in {"test", "real"}
        allowed = (
            is_global_admin(current_user) or is_matching_raffle_leader(current_user, payload.guild_name)
            if automatic_stage1 else can_manage_guild(current_user, payload.guild_name)
        )
        if not allowed:
            raise HTTPException(status_code=403, detail="Cannot move raffle outside your guild scope")
        raffle.guild_name = payload.guild_name

    for field in ["title", "description", "scheduled_run_at"]:
        value = getattr(payload, field)
        if value is not None:
            setattr(raffle, field, value)

    if payload.show_participants is not None:
        raffle.show_participants = payload.show_participants

    if payload.access_mode is not None:
        raffle.access_mode = normalize_access_mode(payload.access_mode, payload.visibility)

    if payload.visibility is not None:
        raffle.access_mode = normalize_access_mode(raffle.access_mode, payload.visibility)

    if payload.run_mode is not None:
        run_mode = payload.run_mode.lower()
        if run_mode not in {"manual", "automatic"}:
            raise HTTPException(status_code=400, detail="Invalid run mode")
        raffle.run_mode = run_mode

    if payload.archive_after_days is not None:
        raffle.archive_after_days = max(1, min(365, payload.archive_after_days))

    if payload.status is not None:
        new_status = normalize_status(payload.status)
        if new_status not in {"draft", "open", "closed", "completed", "cancelled"}:
            raise HTTPException(status_code=400, detail="Invalid status")
        raffle.status = new_status

    _apply_raffle_defaults(raffle)
    if raffle.purpose in {"test", "real"} and (raffle.run_mode != "automatic" or raffle.access_mode != "guild_only"):
        raise HTTPException(status_code=400, detail="Test and real raffles must remain guild-only and automatic")

    db.commit()
    db.refresh(raffle)
    return get_raffle(raffle.id, db, current_user)


@router.get("/{raffle_id}/share")
def share_raffle(
    raffle_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager_user),
):
    raffle = db.query(Raffle).filter(Raffle.id == raffle_id).first()
    if not raffle:
        raise HTTPException(status_code=404, detail="Raffle not found")
    _require_raffle_management(current_user, raffle)
    return {"public_code": raffle.public_code, "url": f"https://tibiahub.domoforge.com/raffles/{raffle.public_code}"}


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
    if raffle.run_mode == "automatic" or raffle.purpose in {"test", "real"}:
        raise HTTPException(status_code=409, detail="Automatic raffle prize configuration is fixed at creation")

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
    payload: RaffleDrawRequest | None = None,
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
        winners = RaffleService.execute_raffle(db, raffle, current_user, dry_run=bool(payload and payload.dry_run))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "raffle_id": raffle.id,
        "run_number": raffle.current_run_number,
        "winner_count": len(winners),
        "winners": [RaffleService.serialize_winner(winner) for winner in winners],
    }


@router.post("/{raffle_id}/simulate", response_model=RaffleExecutionResponse)
def simulate_raffle(
    raffle_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager_user),
):
    """
    Dry-run simulation: returns potential winners without persisting anything.
    Useful for admins to validate weights and eligibility before executing a real draw.
    """
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
        simulated_winners = RaffleService.execute_raffle(db, raffle, current_user, dry_run=True)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("raffle_simulate_failed raffle_id=%s", raffle_id)
        raise HTTPException(status_code=400, detail="Unable to simulate raffle with the current data") from exc

    return RaffleService.build_simulation_payload(raffle, simulated_winners)


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


@router.patch("/{raffle_id}/participants/{participant_id}/weight", response_model=RaffleResponse)
def update_participant_weight(
    raffle_id: int,
    participant_id: int,
    payload: RaffleWeightUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager_user),
):
    raffle = db.query(Raffle).filter(Raffle.id == raffle_id).first()
    if not raffle:
        raise HTTPException(status_code=404, detail="Raffle not found")
    _require_raffle_management(current_user, raffle)
    if raffle.run_mode == "automatic" or raffle.purpose in {"test", "real"}:
        raise HTTPException(status_code=400, detail="Automatic raffles use equal probability and do not support weight overrides")
    participant = (
        db.query(RaffleParticipant)
        .filter(RaffleParticipant.id == participant_id, RaffleParticipant.raffle_id == raffle_id, RaffleParticipant.is_deleted == False)
        .first()
    )
    if not participant:
        raise HTTPException(status_code=404, detail="Participant not found")
    participant.weight_multiplier = max(1.0, min(5.0, payload.weight_multiplier))
    base_weight = 1.1 if (participant.guild_rank or "").strip().lower() == "vice leader" else 1.0
    participant.weight = base_weight * participant.weight_multiplier
    participant.source = "manual_override"
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
    raffle.status = "deleted"
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
    raffle.status = "active"
    db.commit()
    return get_raffle(raffle_id, db, current_user)


@router.get("/public/{raffle_id}", response_model=PublicRaffleResponse)
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
    _apply_raffle_defaults(raffle)
    if raffle.status in {"deleted", "draft"} or raffle.is_deleted:
        raise HTTPException(status_code=404, detail="Raffle not found")
    if not raffle.public_code:
        _ensure_public_code(db, raffle)
        db.commit()
        db.refresh(raffle)
    return _serialize_public_raffle(db, raffle)


@router.get("/public/code/{public_code}", response_model=PublicRaffleResponse)
def get_public_raffle_by_code(
    public_code: str,
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
        .filter(Raffle.public_code == public_code, Raffle.is_deleted == False)
        .first()
    )
    if not raffle:
        raise HTTPException(status_code=404, detail="Raffle not found")
    _apply_raffle_defaults(raffle)
    if raffle.status in {"deleted", "draft"} or raffle.is_deleted:
        raise HTTPException(status_code=404, detail="Raffle not found")
    if not raffle.public_code:
        _ensure_public_code(db, raffle)
        db.commit()
        db.refresh(raffle)
    return _serialize_public_raffle(db, raffle)


async def _register_participant_for_raffle(db: Session, raffle: Raffle, character_name: str) -> Raffle:
    _ensure_raffle_state_for_registration(raffle)

    guild_info = await get_guild_info(raffle.guild_name)
    if not guild_info:
        raise HTTPException(status_code=503, detail="Guild data unavailable")

    member_lookup = {
        (member.get("name") or "").strip().lower(): member
        for member in (guild_info.get("members") or [])
        if (member.get("name") or "").strip()
    }

    selected_name = character_name.strip()
    member = member_lookup.get(selected_name.lower())
    access_mode = normalize_access_mode(getattr(raffle, "access_mode", None), getattr(raffle, "visibility", None))

    character_info = await get_character_info(selected_name)
    if access_mode != "guild_only" and not character_info:
        raise HTTPException(status_code=400, detail="Character not found in Tibia")

    if access_mode == "guild_only" and not member:
        raise HTTPException(status_code=400, detail="Only members of this guild can join")

    raffle_world = (guild_info.get("world") or "").strip().lower()
    character_world = ((character_info or {}).get("world") or raffle_world).strip().lower()
    if access_mode == "world_only" and raffle_world and character_world != raffle_world:
        raise HTTPException(status_code=400, detail="Only characters from the same world can join")

    canonical_name = (member or {}).get("name") or (character_info or {}).get("name") or selected_name
    user = _get_or_create_public_user(db, canonical_name)

    existing_user = (
        db.query(RaffleParticipant)
        .filter(RaffleParticipant.raffle_id == raffle.id, RaffleParticipant.user_id == user.id, RaffleParticipant.is_deleted == False)
        .first()
    )
    if existing_user:
        raise HTTPException(status_code=400, detail="This account is already registered")

    existing_character = (
        db.query(RaffleParticipant)
        .filter(RaffleParticipant.raffle_id == raffle.id, RaffleParticipant.character_name.ilike(selected_name), RaffleParticipant.is_deleted == False)
        .first()
    )
    if existing_character:
        raise HTTPException(status_code=400, detail="This character is already registered")

    rank = None
    if member:
        rank = member.get("rank") or member.get("title") or member.get("position")
    elif character_info and isinstance(character_info.get("guild"), dict):
        rank = (character_info.get("guild") or {}).get("rank")
    participant = RaffleParticipant(
        raffle_id=raffle.id,
        user_id=user.id,
        character_name=canonical_name,
        guild_rank=rank,
        weight=1.1 if str(rank or "").strip().lower() == "vice leader" else 1.0,
        weight_multiplier=1.0,
        source="public_register",
        source_data=member or character_info,
    )
    db.add(participant)
    db.commit()
    return get_public_raffle(raffle.id, db)


@router.post("/public/{raffle_id}/register", response_model=RaffleResponse)
async def register_public_participant(
    raffle_id: int,
    payload: PublicRaffleRegisterRequest,
    db: Session = Depends(get_db),
):
    raffle = db.query(Raffle).filter(Raffle.id == raffle_id).first()
    if not raffle:
        raise HTTPException(status_code=404, detail="Raffle not found")
    return await _register_participant_for_raffle(db, raffle, payload.character_name)


@router.post("/public/code/{public_code}/register", response_model=RaffleResponse)
async def register_public_participant_by_code(
    public_code: str,
    payload: PublicRaffleRegisterRequest,
    db: Session = Depends(get_db),
):
    raffle = db.query(Raffle).filter(Raffle.public_code == public_code, Raffle.is_deleted == False).first()
    if not raffle:
        raise HTTPException(status_code=404, detail="Raffle not found")
    return await _register_participant_for_raffle(db, raffle, payload.character_name)


@router.post("/{raffle_id}/participants/manual", response_model=RaffleResponse)
async def add_participant_manual(
    raffle_id: int,
    payload: PublicRaffleRegisterRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager_user),
):
    raffle = db.query(Raffle).filter(Raffle.id == raffle_id).first()
    if not raffle:
        raise HTTPException(status_code=404, detail="Raffle not found")
    _require_raffle_management(current_user, raffle)
    if raffle.status in {"archived", "deleted"} or raffle.is_deleted:
        raise HTTPException(status_code=400, detail="Raffle does not accept registrations")
    return await _register_participant_for_raffle(db, raffle, payload.character_name)


def _stage1_raffle(db: Session, raffle_id: int) -> Raffle:
    raffle = db.query(Raffle).options(
        selectinload(Raffle.prizes),
        selectinload(Raffle.eligibility_snapshots).selectinload(RaffleEligibilitySnapshot.entries),
    ).filter(Raffle.id == raffle_id, Raffle.is_deleted.is_(False)).first()
    if not raffle:
        raise HTTPException(status_code=404, detail="Raffle not found")
    return raffle


def _require_capability(allowed: bool) -> None:
    if not allowed:
        raise HTTPException(status_code=403, detail="Insufficient raffle permissions")


@router.post("/{raffle_id}/eligibility/preview", response_model=EligibilityPreviewResponse)
async def preview_automatic_eligibility(
    raffle_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    raffle = _stage1_raffle(db, raffle_id)
    _require_capability(can_execute_raffle(db, current_user, raffle))
    try:
        return await RaffleEligibilityService.preview(db, raffle)
    except RaffleEligibilityError as exc:
        raise HTTPException(status_code=400, detail=exc.summary) from exc


@router.post("/{raffle_id}/eligibility/freeze", response_model=EligibilityPreviewResponse)
async def freeze_automatic_eligibility(
    raffle_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    raffle = _stage1_raffle(db, raffle_id)
    _require_capability(can_execute_raffle(db, current_user, raffle))
    try:
        snapshot = await RaffleEligibilityService.freeze(db, raffle, current_user)
        db.commit()
        db.refresh(snapshot)
        return {
            "raffle_id": raffle.id, "cutoff_at": snapshot.cutoff_at,
            "timezone_name": snapshot.timezone_name, "eligibility_days": snapshot.eligibility_days,
            "candidate_count": snapshot.candidate_count, "eligible_count": snapshot.eligible_count,
            "excluded_count": snapshot.excluded_count, "snapshot_hash": snapshot.snapshot_hash,
            "entries": snapshot.entries, "persisted": True, "snapshot_id": snapshot.id,
        }
    except RaffleEligibilityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=exc.summary) from exc


@router.post("/{raffle_id}/execute", response_model=AutomaticRunResponse)
async def execute_automatic_raffle(
    raffle_id: int,
    payload: AutomaticExecutionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    raffle = _stage1_raffle(db, raffle_id)
    _require_capability(can_execute_raffle(db, current_user, raffle))
    try:
        run = await AutomaticRaffleService.execute(db, raffle, current_user, trigger=payload.trigger)
        return serialize_run(run)
    except (AutomaticRaffleError, RaffleEligibilityError) as exc:
        raise HTTPException(status_code=409 if getattr(exc, "code", "") in {"already_executed", "execution_in_progress", "concurrent_execution"} else 400, detail=exc.summary) from exc


@router.get("/{raffle_id}/runs", response_model=List[AutomaticRunResponse])
def list_automatic_runs(
    raffle_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    raffle = _stage1_raffle(db, raffle_id)
    _require_capability(can_view_private_raffle_results(db, current_user, raffle))
    run_ids = [row[0] for row in db.query(RaffleRun.id).filter(RaffleRun.raffle_id == raffle.id).order_by(RaffleRun.run_number).all()]
    return [serialize_run(AutomaticRaffleService.load_run(db, run_id)) for run_id in run_ids]


@router.post("/{raffle_id}/reruns", response_model=AutomaticRunResponse)
def rerun_automatic_raffle(
    raffle_id: int,
    payload: AutomaticRerunRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    raffle = _stage1_raffle(db, raffle_id)
    _require_capability(can_execute_raffle(db, current_user, raffle))
    try:
        run = AutomaticRaffleService.rerun(
            db, raffle, current_user, positions=payload.positions, reason=payload.reason,
            override_delivered=payload.override_delivered, override_reason=payload.override_reason,
            is_global_admin=is_global_admin(current_user),
        )
        return serialize_run(run)
    except AutomaticRaffleError as exc:
        raise HTTPException(status_code=409 if exc.code in {"execution_in_progress", "concurrent_execution", "prize_already_delivered"} else 400, detail=exc.summary) from exc


@router.patch("/{raffle_id}/results/{result_id}/delivery", response_model=DeliveryResponse)
def update_raffle_delivery(
    raffle_id: int,
    result_id: int,
    payload: DeliveryUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    raffle = _stage1_raffle(db, raffle_id)
    _require_capability(can_update_raffle_delivery(db, current_user, raffle))
    delivery = db.query(RafflePrizeDelivery).join(RaffleRunResult).join(RaffleRun).filter(
        RafflePrizeDelivery.raffle_id == raffle.id,
        RafflePrizeDelivery.result_id == result_id,
        RaffleRun.raffle_id == raffle.id,
    ).first()
    if not delivery:
        raise HTTPException(status_code=404, detail="Prize delivery not found")
    note = (payload.note or "").strip()
    if payload.status in {"disputed", "cancelled"} and not note:
        raise HTTPException(status_code=400, detail="A note is required for disputed or cancelled delivery")
    if delivery.status == "delivered" and payload.status != "delivered":
        if not (is_global_admin(current_user) and payload.admin_override and note):
            raise HTTPException(status_code=409, detail="Delivered prizes require a global-admin override note")
    if payload.admin_override and not is_global_admin(current_user):
        raise HTTPException(status_code=403, detail="Only global administrators may override delivery state")
    delivery.status = payload.status
    delivery.note = note or None
    if payload.status == "delivered":
        delivery.delivered_at = datetime.now(UTC)
        delivery.delivered_by_id = current_user.id
    elif delivery.status != "delivered":
        delivery.delivered_at = None
        delivery.delivered_by_id = None
    db.commit()
    db.refresh(delivery)
    return {
        "result_id": delivery.result_id, "status": delivery.status,
        "delivery_deadline_at": delivery.delivery_deadline_at,
        "delivered_at": delivery.delivered_at, "delivered_by_id": delivery.delivered_by_id,
        "note": delivery.note,
    }


@router.post("/{raffle_id}/publish", response_model=PublicationResponse)
def publish_raffle_results(
    raffle_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    raffle = _stage1_raffle(db, raffle_id)
    _require_capability(can_publish_raffle(current_user, raffle))
    active_count = db.query(RaffleRunResult.id).join(RaffleRun).filter(
        RaffleRun.raffle_id == raffle.id, RaffleRunResult.is_active.is_(True),
    ).count()
    if active_count != 2:
        raise HTTPException(status_code=409, detail="Both active prize results are required before publication")
    raffle.publication_status = "published"
    raffle.published_at = datetime.now(UTC)
    raffle.published_by_id = current_user.id
    db.commit()
    return {"raffle_id": raffle.id, "publication_status": raffle.publication_status, "published_at": raffle.published_at, "published_by_id": raffle.published_by_id}


@router.post("/{raffle_id}/unpublish", response_model=PublicationResponse)
def unpublish_raffle_results(
    raffle_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    raffle = _stage1_raffle(db, raffle_id)
    _require_capability(can_publish_raffle(current_user, raffle))
    raffle.publication_status = "private"
    raffle.published_at = None
    raffle.published_by_id = None
    db.commit()
    return {"raffle_id": raffle.id, "publication_status": raffle.publication_status, "published_at": None, "published_by_id": None}


@router.post("/{raffle_id}/managers", response_model=ManagerGrantResponse)
def grant_raffle_manager(
    raffle_id: int,
    payload: ManagerGrantRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    raffle = _stage1_raffle(db, raffle_id)
    _require_capability(can_publish_raffle(current_user, raffle))
    target = db.query(User).filter(User.id == payload.user_id, User.is_active.is_(True)).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if (target.guild_name or "").casefold() != raffle.guild_name.casefold():
        raise HTTPException(status_code=400, detail="Raffle managers must belong to the raffle guild")
    grant = db.query(RaffleManagerGrant).filter(RaffleManagerGrant.raffle_id == raffle.id, RaffleManagerGrant.user_id == target.id).first()
    if grant:
        grant.revoked_at = None
        grant.granted_by_id = current_user.id
        grant.created_at = datetime.now(UTC)
    else:
        grant = RaffleManagerGrant(raffle_id=raffle.id, user_id=target.id, granted_by_id=current_user.id)
        db.add(grant)
    db.commit()
    db.refresh(grant)
    return grant


@router.delete("/{raffle_id}/managers/{user_id}", response_model=ManagerGrantResponse)
def revoke_raffle_manager(
    raffle_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    raffle = _stage1_raffle(db, raffle_id)
    _require_capability(can_publish_raffle(current_user, raffle))
    grant = db.query(RaffleManagerGrant).filter(
        RaffleManagerGrant.raffle_id == raffle.id, RaffleManagerGrant.user_id == user_id,
        RaffleManagerGrant.revoked_at.is_(None),
    ).first()
    if not grant:
        raise HTTPException(status_code=404, detail="Active raffle manager grant not found")
    grant.revoked_at = datetime.now(UTC)
    db.commit()
    db.refresh(grant)
    return grant
