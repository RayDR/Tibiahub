from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.models.raffle import (
    Raffle, RaffleEligibilityEntry, RaffleEligibilitySnapshot, RafflePrize,
    RafflePrizeDelivery, RaffleRerunAudit, RaffleRun, RaffleRunResult,
)
from app.models.user import User
from app.services.raffle_eligibility_service import RaffleEligibilityError, RaffleEligibilityService


ALGORITHM_VERSION = "hmac-sha256-rejection-v1"
POSITIONS = ("second", "first")
EXPECTED_PRIZES = {"second": (Decimal("100"), "TC"), "first": (Decimal("250"), "TC")}


class AutomaticRaffleError(ValueError):
    def __init__(self, code: str, summary: str):
        super().__init__(summary)
        self.code = code
        self.summary = summary


def now_utc() -> datetime:
    return datetime.now(UTC)


def validate_automatic_prizes(raffle: Raffle) -> dict[str, RafflePrize]:
    prizes = {prize.position: prize for prize in raffle.prizes if prize.position in POSITIONS}
    if len(raffle.prizes) != 2 or set(prizes) != set(POSITIONS):
        raise AutomaticRaffleError("invalid_prizes", "Automatic raffles require exactly second and first prizes")
    for position, (amount, currency) in EXPECTED_PRIZES.items():
        prize = prizes[position]
        if Decimal(prize.amount or 0) != amount or (prize.currency or "").upper() != currency:
            raise AutomaticRaffleError("invalid_prizes", "Automatic raffle prizes must be second 100 TC and first 250 TC")
    return prizes


def _derive_index(entropy: bytes, *, snapshot_hash: str, position: str, candidate_count: int) -> tuple[int, str]:
    if candidate_count < 1:
        raise AutomaticRaffleError("no_candidates", "No eligible candidates remain")
    limit = (1 << 256) - ((1 << 256) % candidate_count)
    counter = 0
    while True:
        message = f"{ALGORITHM_VERSION}|{snapshot_hash}|{position}|{counter}".encode()
        digest = hmac.new(entropy, message, hashlib.sha256).digest()
        value = int.from_bytes(digest, "big")
        if value < limit:
            return value % candidate_count, hashlib.sha256(digest).hexdigest()
        counter += 1


def _serialize_result(result: RaffleRunResult) -> dict:
    delivery = result.delivery
    return {
        "id": result.id,
        "prize_id": result.prize_id,
        "prize_position": result.prize_position,
        "prize_name": result.prize.name,
        "amount": result.prize.amount,
        "currency": result.prize.currency,
        "character_name": result.participant_character_name,
        "selection_index": result.selection_index,
        "candidate_count": result.candidate_count,
        "delivery_status": delivery.status,
        "delivery_deadline_at": delivery.delivery_deadline_at,
        "delivered_at": delivery.delivered_at,
        "delivered_by_name": delivery.delivered_by.username if delivery.delivered_by else None,
        "delivery_note": delivery.note,
        "delivery_history": [{"previous_status": item.previous_status, "new_status": item.new_status, "actor": item.actor.username, "note": item.note, "admin_override": item.admin_override, "created_at": item.created_at} for item in delivery.history],
    }


def serialize_run(run: RaffleRun) -> dict:
    return {
        "id": run.id, "raffle_id": run.raffle_id, "run_number": run.run_number,
        "snapshot_id": run.snapshot_id, "parent_run_id": run.parent_run_id,
        "trigger": run.trigger, "state": run.state, "started_at": run.started_at,
        "completed_at": run.completed_at, "failure_code": run.failure_code,
        "failure_summary": run.failure_summary, "algorithm_version": run.algorithm_version,
        "entropy_commitment": run.entropy_commitment,
        "results": [_serialize_result(result) for result in sorted(run.results, key=lambda row: POSITIONS.index(row.prize_position))],
    }


class AutomaticRaffleService:
    @staticmethod
    def claim(db: Session, raffle: Raffle, *, allow_succeeded: bool = False) -> None:
        if db.bind is not None and db.bind.dialect.name == "postgresql":
            raffle = db.query(Raffle).with_for_update().filter(Raffle.id == raffle.id).one()
        if raffle.execution_state in {"claimed", "running"}:
            raise AutomaticRaffleError("execution_in_progress", "Raffle execution is already in progress")
        if raffle.execution_state == "succeeded" and not allow_succeeded:
            raise AutomaticRaffleError("already_executed", "Raffle has already been executed")
        old_version = raffle.version or 1
        token = secrets.token_hex(32)
        updated = db.query(Raffle).filter(
            Raffle.id == raffle.id, Raffle.version == old_version,
            Raffle.execution_state.notin_(["claimed", "running"]),
        ).update({
            Raffle.execution_state: "claimed", Raffle.claim_token: token,
            Raffle.claimed_at: now_utc(), Raffle.lease_expires_at: now_utc() + timedelta(minutes=15),
            Raffle.version: old_version + 1,
        }, synchronize_session=False)
        if updated != 1:
            raise AutomaticRaffleError("concurrent_execution", "Raffle execution was claimed by another process")
        db.flush()
        db.refresh(raffle)

    @staticmethod
    def _create_run(db: Session, raffle: Raffle, snapshot: RaffleEligibilitySnapshot, actor: User, trigger: str, parent_run_id: int | None = None) -> tuple[RaffleRun, bytes]:
        run_number = (db.query(func.max(RaffleRun.run_number)).filter(RaffleRun.raffle_id == raffle.id).scalar() or 0) + 1
        entropy = secrets.token_bytes(32)
        run = RaffleRun(
            raffle_id=raffle.id, run_number=run_number, snapshot_id=snapshot.id,
            parent_run_id=parent_run_id, trigger=trigger, state="running",
            requested_by_id=actor.id, started_at=now_utc(), algorithm_version=ALGORITHM_VERSION,
            entropy_commitment=hashlib.sha256(entropy).hexdigest(),
        )
        db.add(run)
        db.flush()
        return run, entropy

    @staticmethod
    def _eligible(snapshot: RaffleEligibilitySnapshot) -> list[RaffleEligibilityEntry]:
        return sorted((entry for entry in snapshot.entries if entry.is_eligible), key=lambda row: (row.user_id, (row.character_name or "").casefold()))

    @staticmethod
    def _select(db: Session, *, raffle: Raffle, run: RaffleRun, snapshot: RaffleEligibilitySnapshot, entropy: bytes, positions: list[str], excluded_user_ids: set[int]) -> list[RaffleRunResult]:
        prizes = validate_automatic_prizes(raffle)
        candidates = [entry for entry in AutomaticRaffleService._eligible(snapshot) if entry.user_id not in excluded_user_ids]
        results = []
        for position in POSITIONS:
            if position not in positions:
                continue
            index, entropy_hash = _derive_index(entropy, snapshot_hash=snapshot.snapshot_hash, position=position, candidate_count=len(candidates))
            selected = candidates.pop(index)
            result = RaffleRunResult(
                run_id=run.id, prize_id=prizes[position].id, prize_position=position,
                participant_user_id=selected.user_id, participant_character_name=selected.character_name,
                selection_index=index, candidate_count=len(candidates) + 1,
                derived_entropy_hash=entropy_hash, is_active=True,
            )
            db.add(result)
            db.flush()
            db.add(RafflePrizeDelivery(
                raffle_id=raffle.id, result_id=result.id, status="pending",
                delivery_deadline_at=now_utc() + timedelta(hours=24),
            ))
            results.append(result)
        db.flush()
        return results

    @staticmethod
    async def execute(db: Session, raffle: Raffle, actor: User, *, trigger: str = "manual", claimed_token: str | None = None) -> RaffleRun:
        raffle_id = raffle.id
        actor_id = actor.id
        if raffle.purpose not in {"test", "real"} or raffle.run_mode != "automatic":
            raise AutomaticRaffleError("invalid_raffle_mode", "This endpoint only executes automatic test or real raffles")
        validate_automatic_prizes(raffle)
        if claimed_token is None:
            AutomaticRaffleService.claim(db, raffle)
        elif raffle.execution_state != "claimed" or not hmac.compare_digest(raffle.claim_token or "", claimed_token):
            raise AutomaticRaffleError("claim_lost", "The scheduler claim is no longer valid")
        snapshot = None
        snapshot_id = None
        try:
            raffle.execution_state = "running"
            snapshot = await RaffleEligibilityService.freeze(db, raffle, actor)
            # The immutable snapshot and durable claim survive a later draw
            # failure, allowing an audited failed run to reference the exact
            # candidate set that was evaluated.
            db.commit()
            snapshot_id = snapshot.id
            raffle = db.query(Raffle).options(selectinload(Raffle.prizes)).filter(Raffle.id == raffle_id).one()
            snapshot = db.query(RaffleEligibilitySnapshot).options(selectinload(RaffleEligibilitySnapshot.entries)).filter(RaffleEligibilitySnapshot.id == snapshot_id).one()
            run, entropy = AutomaticRaffleService._create_run(db, raffle, snapshot, actor, trigger)
            results = AutomaticRaffleService._select(db, raffle=raffle, run=run, snapshot=snapshot, entropy=entropy, positions=list(POSITIONS), excluded_user_ids=set())
            completed_at = now_utc()
            for result in results:
                result.delivery.delivery_deadline_at = completed_at + timedelta(hours=24)
            run.state = "succeeded"
            run.completed_at = completed_at
            raffle.execution_state = "succeeded"
            raffle.execution_trigger = trigger
            raffle.executed_at = completed_at
            raffle.publication_status = "private"
            raffle.current_run_number = run.run_number
            raffle.last_executed_by_id = actor.id
            raffle.status = "completed"
            raffle.claim_token = None
            raffle.lease_expires_at = None
            db.commit()
            return AutomaticRaffleService.load_run(db, run.id)
        except (AutomaticRaffleError, RaffleEligibilityError) as exc:
            db.rollback()
            failed = db.query(Raffle).filter(Raffle.id == raffle_id).first()
            if failed:
                failed.execution_state = "failed"
                failed.last_error_code = exc.code
                failed.last_error_summary = exc.summary
                failed.claim_token = None
                failed.lease_expires_at = None
                if snapshot_id is not None:
                    failed_run = RaffleRun(
                        raffle_id=failed.id,
                        run_number=(db.query(func.max(RaffleRun.run_number)).filter(RaffleRun.raffle_id == failed.id).scalar() or 0) + 1,
                        snapshot_id=snapshot_id, trigger=trigger, state="failed", requested_by_id=actor_id,
                        started_at=failed.claimed_at, completed_at=now_utc(), failure_code=exc.code,
                        failure_summary=exc.summary, algorithm_version=ALGORITHM_VERSION,
                    )
                    db.add(failed_run)
                db.commit()
            raise
        except Exception as exc:
            db.rollback()
            failed = db.query(Raffle).filter(Raffle.id == raffle_id).first()
            if failed:
                failed.execution_state = "failed"
                failed.last_error_code = "execution_failed"
                failed.last_error_summary = "Raffle execution failed safely"
                failed.claim_token = None
                failed.lease_expires_at = None
                if snapshot_id is not None:
                    db.add(RaffleRun(
                        raffle_id=failed.id,
                        run_number=(db.query(func.max(RaffleRun.run_number)).filter(RaffleRun.raffle_id == failed.id).scalar() or 0) + 1,
                        snapshot_id=snapshot_id, trigger=trigger, state="failed", requested_by_id=actor_id,
                        started_at=failed.claimed_at, completed_at=now_utc(), failure_code="execution_failed",
                        failure_summary="Raffle execution failed safely", algorithm_version=ALGORITHM_VERSION,
                    ))
                db.commit()
            raise AutomaticRaffleError("execution_failed", "Raffle execution failed safely") from exc

    @staticmethod
    def load_run(db: Session, run_id: int) -> RaffleRun:
        return db.query(RaffleRun).options(
            selectinload(RaffleRun.results).selectinload(RaffleRunResult.prize),
            selectinload(RaffleRun.results).selectinload(RaffleRunResult.delivery),
            selectinload(RaffleRun.results).selectinload(RaffleRunResult.delivery).selectinload(RafflePrizeDelivery.delivered_by),
        ).filter(RaffleRun.id == run_id).one()

    @staticmethod
    def rerun(db: Session, raffle: Raffle, actor: User, *, positions: list[str], reason: str, override_delivered: bool, override_reason: str | None, is_global_admin: bool) -> RaffleRun:
        unique_positions = list(dict.fromkeys(positions))
        if not unique_positions or any(position not in POSITIONS for position in unique_positions):
            raise AutomaticRaffleError("invalid_positions", "Rerun positions must be second and/or first")
        if override_delivered and (not is_global_admin or not (override_reason or "").strip()):
            raise AutomaticRaffleError("invalid_override", "Global-admin delivery override requires a separate reason")
        active = db.query(RaffleRunResult).join(RaffleRun).options(
            selectinload(RaffleRunResult.delivery), selectinload(RaffleRunResult.prize),
        ).filter(RaffleRun.raffle_id == raffle.id, RaffleRunResult.is_active.is_(True)).all()
        active_by_position = {result.prize_position: result for result in active}
        if set(active_by_position) != set(POSITIONS):
            raise AutomaticRaffleError("missing_active_results", "Both active prize results are required")
        for position in unique_positions:
            if active_by_position[position].delivery.status == "delivered" and not override_delivered:
                raise AutomaticRaffleError("prize_already_delivered", "Delivered prizes cannot be rerun")
        AutomaticRaffleService.claim(db, raffle, allow_succeeded=True)
        try:
            source_run = max((result.run for result in active), key=lambda row: row.run_number)
            snapshot = source_run.snapshot
            run, entropy = AutomaticRaffleService._create_run(db, raffle, snapshot, actor, "rerun", source_run.id)
            excluded = {result.participant_user_id for position, result in active_by_position.items() if position not in unique_positions}
            replacements = AutomaticRaffleService._select(db, raffle=raffle, run=run, snapshot=snapshot, entropy=entropy, positions=unique_positions, excluded_user_ids=excluded)
            replacement_by_position = {result.prize_position: result for result in replacements}
            for position in unique_positions:
                previous = active_by_position[position]
                previous.is_active = False
                previous.superseded_by_result_id = replacement_by_position[position].id
            completed_at = now_utc()
            for result in replacements:
                result.delivery.delivery_deadline_at = completed_at + timedelta(hours=24)
            run.state = "succeeded"
            run.completed_at = completed_at
            db.add(RaffleRerunAudit(
                raffle_id=raffle.id, source_run_id=source_run.id, new_run_id=run.id,
                actor_id=actor.id, positions=unique_positions, reason=reason.strip(),
                override_delivered=override_delivered, override_reason=(override_reason or "").strip() or None,
            ))
            raffle.execution_state = "succeeded"
            raffle.execution_trigger = "rerun"
            raffle.executed_at = completed_at
            raffle.publication_status = "private"
            raffle.published_at = None
            raffle.published_by_id = None
            raffle.current_run_number = run.run_number
            raffle.rerun_count = (raffle.rerun_count or 0) + 1
            raffle.last_executed_by_id = actor.id
            raffle.claim_token = None
            db.commit()
            return AutomaticRaffleService.load_run(db, run.id)
        except AutomaticRaffleError:
            db.rollback()
            raise
        except Exception as exc:
            db.rollback()
            raise AutomaticRaffleError("rerun_failed", "Raffle rerun failed safely") from exc
