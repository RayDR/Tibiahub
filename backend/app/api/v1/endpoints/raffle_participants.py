"""Focused raffle roster, candidate, participant, and weighting HTTP handlers."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.v1.endpoints.auth import get_current_active_user
from app.core.permissions import can_administer_raffle
from app.db.database import get_db
from app.models.raffle import Raffle, RaffleParticipant, RaffleWinner
from app.models.user import User
from app.schemas.raffle import (
    RaffleCandidateResponse,
    RaffleParticipantMutationResponse,
    RaffleParticipantsMutationRequest,
    RaffleParticipantsRemoveRequest,
    RaffleParticipationSettingsRequest,
    RaffleResponse,
    RaffleWeightUpdateRequest,
)
from app.services.guild_roster_service import GuildRosterService, GuildRosterSyncError
from app.services.raffle_participant_service import (
    RaffleCandidateService,
    RaffleParticipantError,
    RaffleParticipantService,
)
from app.services.raffle_service import RaffleService


router = APIRouter()


def _managed_raffle(db: Session, current_user: User, raffle_id: int) -> Raffle:
    raffle = db.query(Raffle).options(
        selectinload(Raffle.participants).selectinload(RaffleParticipant.user),
        selectinload(Raffle.prizes),
        selectinload(Raffle.winners).selectinload(RaffleWinner.participant).selectinload(RaffleParticipant.user),
        selectinload(Raffle.winners).selectinload(RaffleWinner.prize),
    ).filter(Raffle.id == raffle_id, Raffle.is_deleted.is_(False)).first()
    if raffle is None:
        raise HTTPException(status_code=404, detail="Raffle not found")
    if not can_administer_raffle(db, current_user, raffle):
        raise HTTPException(status_code=403, detail="Insufficient raffle permissions")
    return raffle


def _participant_error(exc: RaffleParticipantError, status_code: int = 409) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": exc.code, "message": exc.summary})


@router.post("/{raffle_id}/participants/sync", response_model=RaffleResponse)
async def sync_raffle_participants(
    raffle_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    raffle = _managed_raffle(db, current_user, raffle_id)
    try:
        await RaffleService.sync_participants(db, raffle, current_user)
        db.commit()
        return RaffleService.serialize_raffle(raffle)
    except (ValueError, GuildRosterSyncError, RaffleParticipantError) as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{raffle_id}/participant-candidates", response_model=list[RaffleCandidateResponse])
def list_participant_candidates(
    raffle_id: int,
    days: int = 30,
    search: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    raffle = _managed_raffle(db, current_user, raffle_id)
    try:
        return RaffleCandidateService.list_candidates(db, raffle, days=days, search=search)
    except RaffleParticipantError as exc:
        raise _participant_error(exc, 422) from exc


@router.post("/{raffle_id}/guild-roster/sync")
async def synchronize_raffle_guild_roster(
    raffle_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    raffle = _managed_raffle(db, current_user, raffle_id)
    try:
        result = await GuildRosterService.synchronize(db, raffle.guild_name)
        db.commit()
        return result.to_dict()
    except GuildRosterSyncError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/{raffle_id}/participants/bulk", response_model=RaffleParticipantMutationResponse)
def add_raffle_participants_bulk(
    raffle_id: int,
    payload: RaffleParticipantsMutationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    raffle = _managed_raffle(db, current_user, raffle_id)
    ids = payload.roster_character_ids
    try:
        if payload.add_all_eligible:
            ids = [
                item["roster_character_id"]
                for item in RaffleCandidateService.list_candidates(db, raffle, days=payload.activity_days)
                if item["selectable"] or (payload.replace_existing and item["already_participating"])
            ]
        result = RaffleParticipantService.add_roster_characters(
            db, raffle, current_user, roster_character_ids=ids,
            replace_existing=payload.replace_existing,
        )
        db.commit()
        return {"raffle_id": raffle.id, **result.to_dict()}
    except RaffleParticipantError as exc:
        db.rollback()
        raise _participant_error(exc) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail={"code": "participant_conflict", "message": "The participant list changed; refresh and retry"},
        ) from exc


@router.post("/{raffle_id}/participants/remove", response_model=RaffleParticipantMutationResponse)
def remove_raffle_participants_bulk(
    raffle_id: int,
    payload: RaffleParticipantsRemoveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    raffle = _managed_raffle(db, current_user, raffle_id)
    try:
        result = RaffleParticipantService.remove(
            db, raffle, current_user,
            participant_ids=payload.participant_ids, reason=payload.reason,
        )
        db.commit()
        return {"raffle_id": raffle.id, **result.to_dict()}
    except RaffleParticipantError as exc:
        db.rollback()
        raise _participant_error(exc) from exc


@router.patch("/{raffle_id}/participation-settings", response_model=RaffleResponse)
def update_raffle_participation_settings(
    raffle_id: int,
    payload: RaffleParticipationSettingsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    raffle = _managed_raffle(db, current_user, raffle_id)
    try:
        RaffleParticipantService.update_settings(
            db, raffle, current_user,
            unique_account_participation=payload.unique_account_participation,
            weighting_mode=payload.weighting_mode,
        )
        db.commit()
        return RaffleService.serialize_raffle(raffle)
    except RaffleParticipantError as exc:
        db.rollback()
        raise _participant_error(exc) from exc


@router.delete("/{raffle_id}/participants/{participant_id}", response_model=RaffleResponse)
def remove_participant(
    raffle_id: int,
    participant_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    raffle = _managed_raffle(db, current_user, raffle_id)
    try:
        RaffleParticipantService.remove(db, raffle, current_user, participant_ids=[participant_id])
        db.commit()
        return RaffleService.serialize_raffle(raffle)
    except RaffleParticipantError as exc:
        db.rollback()
        raise _participant_error(exc) from exc


@router.patch("/{raffle_id}/participants/{participant_id}/weight", response_model=RaffleResponse)
def update_participant_weight(
    raffle_id: int,
    participant_id: int,
    payload: RaffleWeightUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    raffle = _managed_raffle(db, current_user, raffle_id)
    try:
        RaffleParticipantService.update_weight(
            db, raffle, current_user, participant_id=participant_id, weight=payload.weight,
        )
        db.commit()
        return RaffleService.serialize_raffle(raffle)
    except RaffleParticipantError as exc:
        db.rollback()
        raise _participant_error(exc, 422) from exc
