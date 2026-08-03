"""Raffle candidate queries and atomic participant-list mutations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation

from sqlalchemy import or_
from sqlalchemy.orm import Session, selectinload

from app.models.guild_management import GuildRosterCharacter
from app.models.raffle import Raffle, RaffleParticipant
from app.models.user import User
from app.models.workspace_audit import WorkspaceAudit
from app.services.character_ownership_service import normalize_character_name
from app.services.guild_roster_service import normalize_guild_identity


ACTIVITY_WINDOWS = (7, 15, 30)


class RaffleParticipantError(ValueError):
    def __init__(self, code: str, summary: str):
        super().__init__(summary)
        self.code = code
        self.summary = summary


def _account_key(user_id: int | None) -> str | None:
    return f"user:{user_id}" if user_id is not None else None


def _require_editable(raffle: Raffle) -> None:
    if raffle.is_deleted:
        raise RaffleParticipantError("raffle_deleted", "Deleted raffles cannot be changed")
    if raffle.eligibility_snapshots:
        raise RaffleParticipantError("eligibility_frozen", "Participants cannot change after eligibility is frozen")
    if raffle.execution_state in {"claimed", "running", "succeeded"} or raffle.runs or raffle.winners:
        raise RaffleParticipantError("execution_started", "Participants cannot change after execution has begun")


class RaffleCandidateService:
    @staticmethod
    def list_candidates(db: Session, raffle: Raffle, *, days: int, search: str | None = None) -> list[dict]:
        if days not in ACTIVITY_WINDOWS:
            raise RaffleParticipantError("invalid_activity_window", "Activity window must be 7, 15, or 30 days")
        cutoff = datetime.now(UTC) - timedelta(days=days)
        query = db.query(GuildRosterCharacter).options(
            selectinload(GuildRosterCharacter.linked_user),
        ).filter(
            GuildRosterCharacter.normalized_guild_name == normalize_guild_identity(raffle.guild_name),
            GuildRosterCharacter.is_current.is_(True),
        )
        if search and search.strip():
            term = f"%{search.strip()}%"
            query = query.filter(or_(
                GuildRosterCharacter.character_name.ilike(term),
                GuildRosterCharacter.guild_rank.ilike(term),
                GuildRosterCharacter.vocation.ilike(term),
            ))
        roster = query.order_by(GuildRosterCharacter.character_name).all()
        account_activity: dict[int, datetime] = {}
        for row in roster:
            if row.linked_user_id is None or row.last_activity_at is None:
                continue
            activity = row.last_activity_at.replace(tzinfo=UTC) if row.last_activity_at.tzinfo is None else row.last_activity_at.astimezone(UTC)
            if row.linked_user_id not in account_activity or activity > account_activity[row.linked_user_id]:
                account_activity[row.linked_user_id] = activity
        qualifying_account_ids = {user_id for user_id, activity in account_activity.items() if activity >= cutoff}
        roster = [
            row for row in roster
            if (
                row.last_activity_at is not None
                and (row.last_activity_at.replace(tzinfo=UTC) if row.last_activity_at.tzinfo is None else row.last_activity_at.astimezone(UTC)) >= cutoff
            ) or (row.linked_user_id is not None and row.linked_user_id in qualifying_account_ids)
        ][:500]
        active = [row for row in raffle.participants if not row.is_deleted]
        character_names = {row.normalized_character_name for row in active}
        account_keys = {row.known_account_identity_key for row in active if row.known_account_identity_key}
        result = []
        for row in roster:
            known_key = _account_key(row.linked_user_id)
            already = row.normalized_character_name in character_names
            account_conflict = bool(raffle.unique_account_participation and known_key and known_key in account_keys)
            reason = "already_participating" if already else "known_account_already_participating" if account_conflict else None
            result.append({
                "roster_character_id": row.id,
                "character_name": row.character_name,
                "rank": row.guild_rank,
                "level": row.level,
                "vocation": row.vocation,
                "last_activity_at": account_activity.get(row.linked_user_id, row.last_activity_at) if row.linked_user_id is not None else row.last_activity_at,
                "linked_user_id": row.linked_user_id,
                "linked_username": row.linked_user.username if row.linked_user else None,
                "account_identity_key": known_key,
                "account_identity_known": known_key is not None,
                "already_participating": already,
                "selectable": not already and not account_conflict,
                "reason": reason,
            })
        return result


@dataclass(frozen=True)
class ParticipantMutationResult:
    added: int = 0
    restored: int = 0
    removed: int = 0
    unchanged: int = 0

    def to_dict(self) -> dict:
        return {"added": self.added, "restored": self.restored, "removed": self.removed, "unchanged": self.unchanged}


class RaffleParticipantService:
    @staticmethod
    def _audit(db: Session, raffle: Raffle, actor: User, action: str, metadata: dict) -> None:
        db.add(WorkspaceAudit(
            actor_id=actor.id, workspace_type="guild", guild_name=raffle.guild_name,
            action=action, target_type="raffle", target_id=str(raffle.id),
            assisted=bool(actor.is_superuser), safe_metadata=metadata,
        ))

    @staticmethod
    def _validate_weight(value) -> Decimal:
        try:
            weight = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise RaffleParticipantError("invalid_weight", "Participant weight must be a positive number") from exc
        if not weight.is_finite() or weight <= 0 or weight > Decimal("1000000"):
            raise RaffleParticipantError("invalid_weight", "Participant weight must be greater than 0 and no more than 1000000")
        return weight.quantize(Decimal("0.0001"))

    @classmethod
    def add_roster_characters(
        cls, db: Session, raffle: Raffle, actor: User, *, roster_character_ids: list[int], replace_existing: bool = False,
    ) -> ParticipantMutationResult:
        _require_editable(raffle)
        ids = list(dict.fromkeys(roster_character_ids))
        roster = db.query(GuildRosterCharacter).filter(
            GuildRosterCharacter.id.in_(ids),
            GuildRosterCharacter.normalized_guild_name == normalize_guild_identity(raffle.guild_name),
            GuildRosterCharacter.is_current.is_(True),
        ).all() if ids else []
        if len(roster) != len(ids):
            raise RaffleParticipantError("invalid_roster_selection", "One or more selected characters are not current members of this guild")

        existing = {row.normalized_character_name: row for row in raffle.participants}
        selected_names = {row.normalized_character_name for row in roster}
        if not replace_existing and any(
            name in existing and not existing[name].is_deleted for name in selected_names
        ):
            raise RaffleParticipantError("duplicate_character", "One or more selected characters already participate in this raffle")
        known_keys = [_account_key(row.linked_user_id) for row in roster if row.linked_user_id is not None]
        if raffle.unique_account_participation and len(known_keys) != len(set(known_keys)):
            raise RaffleParticipantError("duplicate_known_account", "The selection contains more than one character from a known account")

        removed = 0
        now = datetime.now(UTC)
        if replace_existing:
            for participant in raffle.participants:
                if not participant.is_deleted and participant.normalized_character_name not in selected_names:
                    participant.is_deleted = True
                    participant.is_eligible = False
                    participant.deleted_at = now
                    participant.deleted_by_user_id = actor.id
                    participant.delete_reason = "participant list replaced"
                    removed += 1

        active_account_keys = {
            participant.known_account_identity_key
            for participant in raffle.participants
            if not participant.is_deleted
            and participant.normalized_character_name not in selected_names
            and participant.known_account_identity_key
        }
        if raffle.unique_account_participation and active_account_keys.intersection(known_keys):
            raise RaffleParticipantError("duplicate_known_account", "A participant from this known account is already entered")

        added = restored = unchanged = 0
        for roster_row in roster:
            known_key = _account_key(roster_row.linked_user_id)
            participant = existing.get(roster_row.normalized_character_name)
            if participant and not participant.is_deleted:
                unchanged += 1
                continue
            values = {
                "user_id": roster_row.linked_user_id,
                "guild_roster_character_id": roster_row.id,
                "character_name": roster_row.character_name,
                "normalized_character_name": roster_row.normalized_character_name,
                "known_account_identity_key": known_key,
                "enforced_account_identity_key": known_key if raffle.unique_account_participation else None,
                "guild_name_snapshot": raffle.guild_name,
                "world_name_snapshot": roster_row.world_name,
                "guild_rank": roster_row.guild_rank,
                "source": "guild_roster",
                "source_data": {"roster_character_id": roster_row.id, "account_identity_known": known_key is not None},
                "is_eligible": True,
                "weight": Decimal("1"),
                "weight_multiplier": Decimal("1"),
                "is_deleted": False,
                "deleted_at": None,
                "deleted_by_user_id": None,
                "delete_reason": None,
            }
            if participant:
                for key, value in values.items():
                    setattr(participant, key, value)
                restored += 1
            else:
                db.add(RaffleParticipant(raffle=raffle, **values))
                added += 1

        cls._audit(db, raffle, actor, "raffle_participants_replaced" if replace_existing else "raffle_participants_added", {
            "added": added, "restored": restored, "removed": removed, "unchanged": unchanged,
        })
        db.flush()
        return ParticipantMutationResult(added=added, restored=restored, removed=removed, unchanged=unchanged)

    @classmethod
    def remove(cls, db: Session, raffle: Raffle, actor: User, *, participant_ids: list[int], reason: str | None = None) -> ParticipantMutationResult:
        _require_editable(raffle)
        ids = list(dict.fromkeys(participant_ids))
        rows = db.query(RaffleParticipant).filter(
            RaffleParticipant.raffle_id == raffle.id,
            RaffleParticipant.id.in_(ids),
            RaffleParticipant.is_deleted.is_(False),
        ).all() if ids else []
        if len(rows) != len(ids):
            raise RaffleParticipantError("participant_not_found", "One or more participants are unavailable")
        now = datetime.now(UTC)
        for row in rows:
            row.is_deleted = True
            row.is_eligible = False
            row.deleted_at = now
            row.deleted_by_user_id = actor.id
            row.delete_reason = (reason or "").strip() or "removed by raffle manager"
        cls._audit(db, raffle, actor, "raffle_participants_removed", {"removed": len(rows)})
        db.flush()
        return ParticipantMutationResult(removed=len(rows))

    @classmethod
    def update_settings(cls, db: Session, raffle: Raffle, actor: User, *, unique_account_participation: bool | None = None, weighting_mode: str | None = None) -> None:
        _require_editable(raffle)
        if weighting_mode is not None and weighting_mode not in {"equal", "weighted"}:
            raise RaffleParticipantError("invalid_weighting_mode", "Weighting mode must be equal or weighted")
        if unique_account_participation is not None:
            active = [row for row in raffle.participants if not row.is_deleted]
            keys = [row.known_account_identity_key for row in active if row.known_account_identity_key]
            if unique_account_participation and len(keys) != len(set(keys)):
                raise RaffleParticipantError("duplicate_known_account", "Remove duplicate known-account participants before enabling this setting")
            raffle.unique_account_participation = unique_account_participation
            for row in active:
                row.enforced_account_identity_key = row.known_account_identity_key if unique_account_participation else None
        if weighting_mode is not None:
            raffle.weighting_mode = weighting_mode
        cls._audit(db, raffle, actor, "raffle_participation_settings_updated", {
            "unique_account_participation": raffle.unique_account_participation,
            "weighting_mode": raffle.weighting_mode,
        })
        db.flush()

    @classmethod
    def update_weight(cls, db: Session, raffle: Raffle, actor: User, *, participant_id: int, weight) -> RaffleParticipant:
        _require_editable(raffle)
        row = db.query(RaffleParticipant).filter_by(id=participant_id, raffle_id=raffle.id, is_deleted=False).one_or_none()
        if row is None:
            raise RaffleParticipantError("participant_not_found", "Participant not found")
        row.weight = cls._validate_weight(weight)
        cls._audit(db, raffle, actor, "raffle_participant_weight_updated", {"participant_id": row.id, "weight": str(row.weight)})
        db.flush()
        return row
