from __future__ import annotations

import random
from typing import Dict, List, Optional

from sqlalchemy.orm import Session, selectinload

from app.models.raffle import Raffle, RaffleParticipant, RafflePrize, RaffleWinner
from app.models.user import User
from app.services.tibia_api import get_guild_info


def participant_weight_from_rank(rank: Optional[str]) -> float:
    if not rank:
        return 1.0
    return 1.1 if rank.strip().lower() == "vice leader" else 1.0


def pick_weighted_participant(participants: List[dict], rng: Optional[random.Random] = None) -> dict:
    if not participants:
        raise ValueError("No participants available")
    rng = rng or random.Random()
    total_weight = sum(max(item.get("weight", 0.0), 0.0) for item in participants)
    if total_weight <= 0:
        raise ValueError("Total weight must be positive")
    threshold = rng.uniform(0, total_weight)
    current = 0.0
    for participant in participants:
        current += max(participant.get("weight", 0.0), 0.0)
        if current >= threshold:
            return participant
    return participants[-1]


def select_weighted_winners(participants: List[dict], prizes: List[dict], rng: Optional[random.Random] = None) -> List[dict]:
    rng = rng or random.Random()
    remaining = list(participants)
    winners: List[dict] = []

    for prize in prizes:
        if not remaining:
            break
        winner = pick_weighted_participant(remaining, rng=rng)
        winners.append({"prize": prize, "participant": winner})
        remaining = [item for item in remaining if item["user_id"] != winner["user_id"]]

    return winners


class RaffleService:
    @staticmethod
    async def sync_participants(db: Session, raffle: Raffle) -> List[RaffleParticipant]:
        guild_info = await get_guild_info(raffle.guild_name)
        if not guild_info:
            raise ValueError(f"Guild '{raffle.guild_name}' not found in TibiaData")

        guild_members = guild_info.get("members") or []
        member_lookup: Dict[str, dict] = {}
        for member in guild_members:
            name = (member.get("name") or "").strip().lower()
            if name:
                member_lookup[name] = member

        users = (
            db.query(User)
            .options(selectinload(User.characters))
            .filter(User.is_active == True)
            .all()
        )

        db.query(RaffleParticipant).filter(RaffleParticipant.raffle_id == raffle.id).update(
            {RaffleParticipant.is_eligible: False},
            synchronize_session=False,
        )

        synced: List[RaffleParticipant] = []
        seen_user_ids = set()
        for user in users:
            candidate_names = []
            if user.tibia_character_name:
                candidate_names.append(user.tibia_character_name)
            candidate_names.extend(character.character_name for character in user.characters)

            selected_name = None
            member_data = None
            for candidate in candidate_names:
                lookup = member_lookup.get(candidate.strip().lower())
                if lookup:
                    selected_name = lookup.get("name") or candidate
                    member_data = lookup
                    break

            if not selected_name or not member_data or user.id in seen_user_ids:
                continue

            seen_user_ids.add(user.id)
            existing = db.query(RaffleParticipant).filter(
                RaffleParticipant.raffle_id == raffle.id,
                RaffleParticipant.user_id == user.id,
            ).first()
            weight = participant_weight_from_rank(member_data.get("rank") or member_data.get("title") or member_data.get("position"))
            if existing:
                existing.character_name = selected_name
                existing.guild_rank = member_data.get("rank") or member_data.get("title") or member_data.get("position")
                if existing.source != "manual_override":
                    existing.weight = weight
                existing.is_eligible = True
                existing.is_deleted = False
                existing.deleted_at = None
                existing.deleted_by_user_id = None
                existing.delete_reason = None
                existing.source_data = member_data
                synced.append(existing)
                continue

            participant = RaffleParticipant(
                raffle_id=raffle.id,
                user_id=user.id,
                character_name=selected_name,
                guild_rank=member_data.get("rank") or member_data.get("title") or member_data.get("position"),
                weight=weight,
                source="guild_sync",
                source_data=member_data,
                is_deleted=False,
            )
            db.add(participant)
            synced.append(participant)

        db.commit()
        db.refresh(raffle)
        return synced

    @staticmethod
    def execute_raffle(db: Session, raffle: Raffle, executed_by: User, *, rerun_reason: Optional[str] = None) -> List[RaffleWinner]:
        participants = (
            db.query(RaffleParticipant)
            .options(selectinload(RaffleParticipant.user))
            .filter(RaffleParticipant.raffle_id == raffle.id, RaffleParticipant.is_eligible == True)
            .filter(RaffleParticipant.is_deleted == False)
            .all()
        )
        prizes = db.query(RafflePrize).filter(RafflePrize.raffle_id == raffle.id).order_by(RafflePrize.order_index.asc()).all()
        if not participants:
            raise ValueError("No eligible participants found")
        if not prizes:
            raise ValueError("No prizes configured")

        run_number = raffle.current_run_number + 1
        picks = select_weighted_winners(
            [
                {
                    "participant_id": participant.id,
                    "user_id": participant.user_id,
                    "username": participant.user.username,
                    "character_name": participant.character_name,
                    "guild_rank": participant.guild_rank,
                    "weight": participant.weight,
                }
                for participant in participants
            ],
            [{"prize_id": prize.id, "name": prize.name, "reward": prize.reward} for prize in prizes],
        )

        winners: List[RaffleWinner] = []
        snapshot = [
            {
                "user_id": participant.user_id,
                "username": participant.user.username,
                "character_name": participant.character_name,
                "guild_rank": participant.guild_rank,
                "weight": participant.weight,
            }
            for participant in participants
        ]

        for pick in picks:
            participant = next(item for item in participants if item.id == pick["participant"]["participant_id"])
            prize = next(item for item in prizes if item.id == pick["prize"]["prize_id"])
            winner = RaffleWinner(
                raffle_id=raffle.id,
                prize_id=prize.id,
                participant_id=participant.id,
                executed_by_id=executed_by.id,
                run_number=run_number,
                is_rerun=run_number > 1,
                rerun_reason=rerun_reason,
                participant_snapshot=snapshot,
            )
            db.add(winner)
            winners.append(winner)

        raffle.current_run_number = run_number
        raffle.rerun_count = max(0, run_number - 1)
        raffle.last_executed_by_id = executed_by.id
        raffle.status = "completed"
        db.commit()
        for winner in winners:
            db.refresh(winner)
        db.refresh(raffle)
        return winners

    @staticmethod
    def serialize_raffle(raffle: Raffle) -> dict:
        current_run = raffle.current_run_number
        current_winners = [winner for winner in raffle.winners if winner.run_number == current_run]
        history = list(raffle.winners)
        return {
            "id": raffle.id,
            "title": raffle.title,
            "description": raffle.description,
            "guild_name": raffle.guild_name,
            "status": raffle.status,
            "current_run_number": raffle.current_run_number,
            "rerun_count": raffle.rerun_count,
            "created_at": raffle.created_at,
            "updated_at": raffle.updated_at,
            "participants": [
                {
                    "id": participant.id,
                    "user_id": participant.user_id,
                    "username": participant.user.username,
                    "character_name": participant.character_name,
                    "guild_rank": participant.guild_rank,
                    "weight": participant.weight,
                    "is_eligible": participant.is_eligible,
                    "created_at": participant.created_at,
                }
                for participant in raffle.participants
                if not participant.is_deleted
            ],
            "prizes": [
                {
                    "id": prize.id,
                    "name": prize.name,
                    "reward": prize.reward,
                    "order_index": prize.order_index,
                }
                for prize in raffle.prizes
            ],
            "current_winners": [RaffleService.serialize_winner(winner) for winner in current_winners],
            "history": [RaffleService.serialize_winner(winner) for winner in history],
        }

    @staticmethod
    def serialize_winner(winner: RaffleWinner) -> dict:
        participant = winner.participant
        prize = winner.prize
        return {
            "id": winner.id,
            "prize_id": prize.id,
            "prize_name": prize.name,
            "reward": prize.reward,
            "participant_id": participant.id,
            "user_id": participant.user_id,
            "username": participant.user.username,
            "character_name": participant.character_name,
            "run_number": winner.run_number,
            "is_rerun": winner.is_rerun,
            "rerun_reason": winner.rerun_reason,
            "created_at": winner.created_at,
        }
