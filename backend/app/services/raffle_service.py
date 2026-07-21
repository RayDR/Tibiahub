from __future__ import annotations

import random
import re
from datetime import UTC, datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session, selectinload

from app.models.raffle import Raffle, RaffleParticipant, RafflePrize, RaffleWinner
from app.models.user import User
from app.services.tibia_api import get_guild_info


ACCESS_MODE_ALIASES = {
    "guild_only": "guild_only",
    "guild": "guild_only",
    "private": "guild_only",
    "world_only": "world_only",
    "world": "world_only",
    "same_world": "world_only",
    "public": "public",
    "anyone": "public",
}

STATUS_ALIASES = {
    "draft": "draft",
    "open": "open",
    "active": "open",
    "closed": "closed",
    "disabled": "closed",
    "completed": "completed",
    "cancelled": "cancelled",
    "canceled": "cancelled",
    "archived": "cancelled",
}


def participant_weight_from_rank(rank: Optional[str]) -> float:
    if not rank:
        return 1.0
    return 1.1 if rank.strip().lower() == "vice leader" else 1.0


def normalize_access_mode(access_mode: Optional[str], visibility: Optional[str] = None) -> str:
    if access_mode:
        normalized = ACCESS_MODE_ALIASES.get(access_mode.strip().lower())
        if normalized:
            return normalized
    if visibility and visibility.strip().lower() == "private":
        return "guild_only"
    return "public"


def normalize_status(status: Optional[str], *, is_deleted: bool = False) -> str:
    if is_deleted:
        return "deleted"
    if not status:
        return "draft"
    return STATUS_ALIASES.get(status.strip().lower(), status.strip().lower())


def sync_legacy_raffle_fields(raffle: Raffle) -> Raffle:
    raffle.access_mode = normalize_access_mode(getattr(raffle, "access_mode", None), getattr(raffle, "visibility", None))
    canonical_status = normalize_status(getattr(raffle, "status", None), is_deleted=raffle.is_deleted)
    raffle.status = canonical_status
    raffle.show_participants = bool(getattr(raffle, "show_participants", True))
    raffle.visibility = "private" if raffle.access_mode == "guild_only" else "public"
    raffle.registration_enabled = canonical_status == "open"
    raffle.is_active = canonical_status in {"draft", "open", "closed", "completed"}
    return raffle


def _reward_value(reward: str | None) -> float:
    if not reward:
        return 0.0
    text = reward.strip().lower()
    match = re.search(r"(\d+(?:\.\d+)?)", text)
    if not match:
        return 0.0
    value = float(match.group(1))
    if "kk" in text:
        return value * 1_000_000
    if "k" in text:
        return value * 1_000
    return value


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


def prepare_participant_pool(participants: List[RaffleParticipant]) -> tuple[List[dict], List[dict], List[str]]:
    eligible: List[dict] = []
    excluded: List[dict] = []
    warnings: List[str] = []
    seen_user_ids: set[int] = set()

    for participant in participants:
        reason: Optional[str] = None
        if participant.is_deleted:
            reason = "participant deleted"
        elif not participant.is_eligible:
            reason = "marked ineligible"
        elif not participant.user_id:
            reason = "missing account"
        elif participant.user is None:
            reason = "missing user relation"
        elif not participant.character_name:
            reason = "missing character name"
        elif participant.weight is None or participant.weight <= 0:
            reason = "non-positive weight"
        elif participant.user_id in seen_user_ids:
            reason = "duplicate account"

        if reason:
            excluded.append(
                {
                    "participant_id": participant.id,
                    "user_id": participant.user_id,
                    "character_name": participant.character_name,
                    "guild_rank": participant.guild_rank,
                    "weight": participant.weight or 0.0,
                    "weight_multiplier": participant.weight_multiplier or 1.0,
                    "reason": reason,
                }
            )
            continue

        seen_user_ids.add(participant.user_id)
        eligible.append(
            {
                "participant_id": participant.id,
                "user_id": participant.user_id,
                "username": participant.user.username,
                "character_name": participant.character_name,
                "guild_rank": participant.guild_rank,
                "weight": participant.weight,
                "weight_multiplier": participant.weight_multiplier or 1.0,
            }
        )

    if eligible and len(eligible) == 1:
        warnings.append("Only one eligible account is available for this draw.")
    return eligible, excluded, warnings


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
                effective_multiplier = existing.weight_multiplier or 1.0
                if existing.source != "manual_override":
                    existing.weight = weight * max(1.0, min(5.0, effective_multiplier))
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
                weight_multiplier=1.0,
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
    def execute_raffle(db: Session, raffle: Raffle, executed_by: User, *, rerun_reason: Optional[str] = None, dry_run: bool = False) -> List[RaffleWinner]:
        sync_legacy_raffle_fields(raffle)
        if raffle.status in {"draft", "cancelled", "deleted"} or raffle.is_deleted:
            raise ValueError("Raffle is not executable")

        participants = (
            db.query(RaffleParticipant)
            .options(selectinload(RaffleParticipant.user))
            .filter(RaffleParticipant.raffle_id == raffle.id, RaffleParticipant.is_eligible == True)
            .filter(RaffleParticipant.is_deleted == False)
            .all()
        )
        prizes = db.query(RafflePrize).filter(RafflePrize.raffle_id == raffle.id).all()
        prizes = sorted(prizes, key=lambda p: (_reward_value(p.reward), p.order_index))
        if not prizes:
            raise ValueError("No prizes configured")

        eligible_pool, _, _ = prepare_participant_pool(participants)
        if not eligible_pool:
            raise ValueError("No eligible participants found")

        run_number = raffle.current_run_number + 1
        picks = select_weighted_winners(
            eligible_pool,
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
            if participant.user is not None and not participant.is_deleted
        ]

        for pick in picks:
            participant = next(item for item in participants if item.id == pick["participant"]["participant_id"])
            prize = next(item for item in prizes if item.id == pick["prize"]["prize_id"])
            if dry_run:
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
                winner.participant = participant
                winner.prize = prize
                winners.append(winner)
                continue

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

        if dry_run:
            return winners

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
    def serialize_raffle(raffle: Raffle, *, include_participants: bool = True) -> dict:
        sync_legacy_raffle_fields(raffle)
        current_run = raffle.current_run_number
        current_winners = [winner for winner in raffle.winners if winner.run_number == current_run]
        history = list(raffle.winners)
        participants = [
            {
                "id": participant.id,
                "user_id": participant.user_id,
                "username": participant.user.username,
                "character_name": participant.character_name,
                "guild_rank": participant.guild_rank,
                "weight": participant.weight,
                "weight_multiplier": participant.weight_multiplier,
                "is_eligible": participant.is_eligible,
                "created_at": participant.created_at,
            }
            for participant in raffle.participants
            if not participant.is_deleted and participant.user is not None
        ]
        return {
            "id": raffle.id,
            "public_code": raffle.public_code,
            "title": raffle.title,
            "description": raffle.description,
            "guild_name": raffle.guild_name,
            "access_mode": raffle.access_mode,
            "show_participants": raffle.show_participants,
            "participant_count": len(participants),
            "visibility": raffle.visibility,
            "registration_enabled": raffle.registration_enabled,
            "run_mode": raffle.run_mode,
            "scheduled_run_at": raffle.scheduled_run_at,
            "purpose": getattr(raffle, "purpose", "legacy"),
            "timezone_name": getattr(raffle, "timezone_name", "America/Chicago"),
            "eligibility_days": getattr(raffle, "eligibility_days", 5),
            "eligibility_cutoff_at": getattr(raffle, "eligibility_cutoff_at", None),
            "publication_status": getattr(raffle, "publication_status", "private"),
            "execution_state": getattr(raffle, "execution_state", "pending"),
            "executed_at": getattr(raffle, "executed_at", None),
            "scheduler_job_id": getattr(raffle, "scheduler_job_id", None),
            "claimed_at": getattr(raffle, "claimed_at", None),
            "lease_expires_at": getattr(raffle, "lease_expires_at", None),
            "last_error_code": getattr(raffle, "last_error_code", None),
            "last_error_summary": getattr(raffle, "last_error_summary", None),
            "retry_count": getattr(raffle, "retry_count", 0) or 0,
            "next_retry_at": getattr(raffle, "next_retry_at", None),
            "archive_after_days": raffle.archive_after_days,
            "archived_at": raffle.archived_at,
            "status": raffle.status,
            "current_run_number": raffle.current_run_number,
            "rerun_count": raffle.rerun_count,
            "created_at": raffle.created_at,
            "updated_at": raffle.updated_at,
            "participants": participants if include_participants else [],
            "prizes": [
                {
                    "id": prize.id,
                    "name": prize.name,
                    "reward": prize.reward,
                    "order_index": prize.order_index,
                    "position": prize.position,
                    "amount": prize.amount,
                    "currency": prize.currency,
                }
                for prize in raffle.prizes
            ],
            "current_winners": [RaffleService.serialize_winner(winner) for winner in current_winners],
            "history": [RaffleService.serialize_winner(winner) for winner in history],
        }

    @staticmethod
    def serialize_winner(winner: RaffleWinner, *, simulated: bool = False, synthetic_index: int = 0) -> dict:
        participant = winner.participant
        prize = winner.prize
        return {
            "id": winner.id if winner.id is not None else -(synthetic_index + 1),
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
            "created_at": winner.created_at or (datetime.now(UTC) if simulated else None),
        }

    @staticmethod
    def build_simulation_payload(raffle: Raffle, winners: List[RaffleWinner]) -> dict:
        sync_legacy_raffle_fields(raffle)
        visible_participants = [participant for participant in raffle.participants if not participant.is_deleted]
        eligible_participants, ineligible_participants, warnings = prepare_participant_pool(visible_participants)
        prizes = [
            {"id": prize.id, "name": prize.name, "reward": prize.reward, "order_index": prize.order_index}
            for prize in sorted(raffle.prizes, key=lambda prize: (_reward_value(prize.reward), prize.order_index))
        ]
        if len(eligible_participants) < len(prizes):
            warnings.append("There are fewer eligible accounts than prizes.")

        return {
            "raffle_id": raffle.id,
            "run_number": raffle.current_run_number + 1,
            "winner_count": len(winners),
            "winners": [
                RaffleService.serialize_winner(winner, simulated=True, synthetic_index=index)
                for index, winner in enumerate(winners)
            ],
            "simulation": True,
            "status": raffle.status,
            "access_mode": raffle.access_mode,
            "participant_count": len(visible_participants),
            "eligible_count": len(eligible_participants),
            "ineligible_count": len(ineligible_participants),
            "prizes": prizes,
            "eligible_participants": eligible_participants,
            "ineligible_participants": ineligible_participants,
            "warnings": warnings,
        }
