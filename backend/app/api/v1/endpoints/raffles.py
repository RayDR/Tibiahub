from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, selectinload

from app.api.v1.endpoints.auth import get_current_admin_user
from app.db.database import get_db
from app.models.raffle import Raffle, RaffleParticipant, RafflePrize, RaffleWinner
from app.models.user import User
from app.schemas.raffle import RaffleCreate, RaffleExecutionResponse, RafflePrizeCreate, RaffleResponse, RaffleRerunRequest
from app.services.raffle_service import RaffleService

router = APIRouter()


@router.get("/", response_model=List[RaffleResponse])
def list_raffles(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    _ = current_user
    raffles = (
        db.query(Raffle)
        .options(
            selectinload(Raffle.participants).selectinload(RaffleParticipant.user),
            selectinload(Raffle.prizes),
            selectinload(Raffle.winners).selectinload(RaffleWinner.participant).selectinload(RaffleParticipant.user),
            selectinload(Raffle.winners).selectinload(RaffleWinner.prize),
        )
        .order_by(Raffle.created_at.desc())
        .all()
    )
    return [RaffleService.serialize_raffle(raffle) for raffle in raffles]


@router.get("/{raffle_id}", response_model=RaffleResponse)
def get_raffle(
    raffle_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
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
    return RaffleService.serialize_raffle(raffle)


@router.post("/", response_model=RaffleResponse, status_code=status.HTTP_201_CREATED)
def create_raffle(
    payload: RaffleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    raffle = Raffle(
        title=payload.title,
        description=payload.description,
        guild_name=payload.guild_name,
        created_by_id=current_user.id,
        status="draft",
    )
    db.add(raffle)
    db.flush()

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
    current_user: User = Depends(get_current_admin_user),
):
    raffle = db.query(Raffle).filter(Raffle.id == raffle_id).first()
    if not raffle:
        raise HTTPException(status_code=404, detail="Raffle not found")

    current_max = db.query(RafflePrize.order_index).filter(RafflePrize.raffle_id == raffle_id).order_by(RafflePrize.order_index.desc()).first()
    order_index = payload.order_index or ((current_max[0] + 1) if current_max else 1)
    db.add(RafflePrize(raffle_id=raffle_id, name=payload.name, reward=payload.reward, order_index=order_index))
    db.commit()
    return get_raffle(raffle_id, db, current_user)


@router.post("/{raffle_id}/participants/sync", response_model=RaffleResponse)
async def sync_raffle_participants(
    raffle_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    raffle = db.query(Raffle).filter(Raffle.id == raffle_id).first()
    if not raffle:
        raise HTTPException(status_code=404, detail="Raffle not found")
    try:
        await RaffleService.sync_participants(db, raffle)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return get_raffle(raffle_id, db, current_user)


@router.post("/{raffle_id}/draw", response_model=RaffleExecutionResponse)
def execute_raffle(
    raffle_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
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
    current_user: User = Depends(get_current_admin_user),
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
