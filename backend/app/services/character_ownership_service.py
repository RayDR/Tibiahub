"""Durable public-comment proof processing for Tibia character ownership."""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import unicodedata
from datetime import UTC, datetime, timedelta
from typing import Awaitable, Callable

from sqlalchemy import func, update
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.database import SessionLocal
from app.models.character_ownership import CharacterOwnershipClaim, CharacterOwnershipHistory
from app.models.user import User
from app.models.user_character import UserCharacter
from app.services.tibia_api import get_character_info


CHALLENGE_PATTERN = re.compile(r"(?<![A-Za-z0-9_-])(TIBIAHUB-[A-Za-z0-9_-]{20,80})(?![A-Za-z0-9_-])")
ACTIVE_CLAIM_STATUSES = {"pending", "queued", "processing", "transfer_pending", "disputed"}


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def normalize_character_name(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).strip().split()).casefold()


def challenge_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _history(db: Session, claim: CharacterOwnershipClaim, action: str, *, from_user_id: int | None = None, to_user_id: int | None = None, actor_user_id: int | None = None, metadata: dict | None = None) -> None:
    db.add(CharacterOwnershipHistory(
        normalized_name=claim.normalized_name,
        character_name=claim.character_name,
        claim_id=claim.id,
        action=action,
        from_user_id=from_user_id,
        to_user_id=to_user_id,
        actor_user_id=actor_user_id,
        safe_metadata=metadata or {},
    ))


def _find_character(db: Session, claim: CharacterOwnershipClaim) -> UserCharacter | None:
    return db.query(UserCharacter).filter(
        (UserCharacter.normalized_name == claim.normalized_name)
        | (func.lower(UserCharacter.character_name) == claim.normalized_name)
    ).with_for_update().first()


def _apply_snapshot(character: UserCharacter, payload: dict) -> None:
    guild = payload.get("guild") or {}
    character.character_name = payload.get("name") or character.character_name
    character.normalized_name = normalize_character_name(character.character_name)
    character.level = payload.get("level")
    character.vocation = payload.get("vocation")
    character.world_name = payload.get("world")
    character.guild_name = guild.get("name")
    character.guild_rank = guild.get("rank")
    character.residence = payload.get("residence")
    character.achievement_points = payload.get("achievement_points")
    character.sex = payload.get("sex")


def _apply_primary(user: User, character: UserCharacter) -> None:
    user.tibia_character_name = character.character_name
    user.level = character.level
    user.vocation = character.vocation
    user.world_name = character.world_name
    user.guild_name = character.guild_name
    user.guild_rank = character.guild_rank
    user.residence = character.residence
    user.achievement_points = character.achievement_points
    user.tibia_status = "ownership_verified"
    user.tibia_last_error = None


class CharacterOwnershipService:
    @staticmethod
    def create_claim(db: Session, user: User, character_name: str) -> tuple[CharacterOwnershipClaim, str]:
        normalized = normalize_character_name(character_name)
        if len(normalized) < 2 or len(normalized) > 100:
            raise ValueError("Invalid character name")
        now = datetime.now(UTC)
        active = db.query(CharacterOwnershipClaim).filter(
            CharacterOwnershipClaim.user_id == user.id,
            CharacterOwnershipClaim.normalized_name == normalized,
            CharacterOwnershipClaim.status.in_(ACTIVE_CLAIM_STATUSES),
        ).all()
        for row in active:
            if _as_utc(row.expires_at) > now and row.status in {"queued", "processing", "transfer_pending", "disputed"}:
                raise ValueError("An active claim already exists")
            row.status = "expired"
            row.consumed_at = now
        raw_challenge = f"TIBIAHUB-{secrets.token_urlsafe(24)}"
        claim = CharacterOwnershipClaim(
            user_id=user.id,
            character_name=" ".join(character_name.strip().split()),
            normalized_name=normalized,
            challenge_hash=challenge_hash(raw_challenge),
            status="pending",
            expires_at=now + timedelta(minutes=settings.CHARACTER_CLAIM_TTL_MINUTES),
        )
        db.add(claim)
        db.flush()
        _history(db, claim, "claim_created", to_user_id=user.id, actor_user_id=user.id)
        return claim, raw_challenge

    @staticmethod
    def queue(db: Session, claim: CharacterOwnershipClaim, user: User) -> None:
        now = datetime.now(UTC)
        if claim.user_id != user.id:
            raise PermissionError("Claim is private")
        if claim.status != "pending" or _as_utc(claim.expires_at) <= now:
            raise ValueError("Claim is not available for verification")
        claim.status = "queued"
        claim.verification_requested_at = now
        claim.next_attempt_at = now
        claim.safe_failure_code = None
        _history(db, claim, "verification_queued", to_user_id=user.id, actor_user_id=user.id)

    @staticmethod
    async def process_one(
        *,
        session_factory: sessionmaker = SessionLocal,
        fetch_character: Callable[[str], Awaitable[dict | None]] = get_character_info,
    ) -> bool:
        now = datetime.now(UTC)
        with session_factory.begin() as db:
            # A worker may die after leasing a claim. Requeue expired leases so
            # the durable queue remains self-healing across process restarts.
            db.execute(
                update(CharacterOwnershipClaim)
                .where(
                    CharacterOwnershipClaim.status == "processing",
                    CharacterOwnershipClaim.lease_expires_at <= now,
                    CharacterOwnershipClaim.expires_at > now,
                    CharacterOwnershipClaim.attempt_count < settings.CHARACTER_CLAIM_MAX_ATTEMPTS,
                )
                .values(status="queued", lease_expires_at=None, next_attempt_at=now)
            )
            db.execute(
                update(CharacterOwnershipClaim)
                .where(
                    CharacterOwnershipClaim.status == "processing",
                    CharacterOwnershipClaim.lease_expires_at <= now,
                    CharacterOwnershipClaim.attempt_count >= settings.CHARACTER_CLAIM_MAX_ATTEMPTS,
                )
                .values(
                    status="failed", lease_expires_at=None, consumed_at=now,
                    safe_failure_code="worker_interrupted",
                )
            )
            claim = db.query(CharacterOwnershipClaim).filter(
                CharacterOwnershipClaim.status == "queued",
                CharacterOwnershipClaim.expires_at > now,
                (CharacterOwnershipClaim.next_attempt_at.is_(None)) | (CharacterOwnershipClaim.next_attempt_at <= now),
            ).order_by(CharacterOwnershipClaim.id).with_for_update(skip_locked=True).first()
            if claim is None:
                return False
            claim.status = "processing"
            claim.attempt_count += 1
            claim.lease_expires_at = now + timedelta(minutes=2)
            claim_id = claim.id
            requested_name = claim.character_name

        try:
            payload = await fetch_character(requested_name)
        except Exception:
            payload = None
            provider_failed = True
        else:
            provider_failed = False

        with session_factory.begin() as db:
            claim = db.query(CharacterOwnershipClaim).filter(
                CharacterOwnershipClaim.id == claim_id,
                CharacterOwnershipClaim.status == "processing",
            ).with_for_update().first()
            if claim is None:
                return True
            claim.lease_expires_at = None
            now = datetime.now(UTC)
            if _as_utc(claim.expires_at) <= now:
                claim.status = "expired"
                claim.consumed_at = now
                claim.safe_failure_code = "challenge_expired"
                _history(db, claim, "claim_expired", to_user_id=claim.user_id)
                return True
            if provider_failed:
                if claim.attempt_count < settings.CHARACTER_CLAIM_MAX_ATTEMPTS:
                    claim.status = "queued"
                    claim.next_attempt_at = now + timedelta(minutes=claim.attempt_count)
                else:
                    claim.status = "failed"
                    claim.consumed_at = now
                claim.safe_failure_code = "provider_unavailable"
                _history(db, claim, "verification_deferred" if claim.status == "queued" else "verification_failed", to_user_id=claim.user_id, metadata={"code": claim.safe_failure_code})
                return True
            if not payload or normalize_character_name(str(payload.get("name") or "")) != claim.normalized_name:
                claim.status = "failed"
                claim.consumed_at = now
                claim.safe_failure_code = "character_not_found"
                _history(db, claim, "verification_failed", to_user_id=claim.user_id, metadata={"code": claim.safe_failure_code})
                return True
            candidates = CHALLENGE_PATTERN.findall(str(payload.get("comment") or ""))
            proof_matches = any(hmac.compare_digest(challenge_hash(candidate), claim.challenge_hash) for candidate in candidates)
            if not proof_matches:
                claim.status = "failed" if claim.attempt_count >= settings.CHARACTER_CLAIM_MAX_ATTEMPTS else "pending"
                if claim.status == "failed":
                    claim.consumed_at = now
                claim.safe_failure_code = "challenge_not_visible"
                _history(db, claim, "verification_failed", to_user_id=claim.user_id, metadata={"code": claim.safe_failure_code})
                return True

            existing = _find_character(db, claim)
            if existing and existing.user_id != claim.user_id and existing.ownership_status in {"verified", "disputed"}:
                claim.status = "transfer_pending"
                claim.verified_at = now
                claim.safe_failure_code = None
                _history(db, claim, "transfer_requested", from_user_id=existing.user_id, to_user_id=claim.user_id)
                return True

            legacy_user_id = existing.user_id if existing and existing.user_id != claim.user_id else None
            character = existing or UserCharacter(
                user_id=claim.user_id,
                character_name=payload.get("name") or claim.character_name,
                normalized_name=claim.normalized_name,
            )
            _apply_snapshot(character, payload)
            character.user_id = claim.user_id
            character.ownership_status = "verified"
            character.ownership_verified_at = now
            character.ownership_claim_id = claim.id
            db.add(character)
            db.flush()
            if legacy_user_id is not None:
                legacy_user = db.get(User, legacy_user_id)
                if legacy_user and normalize_character_name(legacy_user.tibia_character_name or "") == claim.normalized_name:
                    legacy_user.tibia_character_name = None
                    legacy_user.tibia_status = "legacy_ownership_replaced"
                _history(db, claim, "legacy_link_replaced", from_user_id=legacy_user_id, to_user_id=claim.user_id)
            _apply_primary(claim.user, character)
            claim.status = "verified"
            claim.verified_at = now
            claim.consumed_at = now
            claim.safe_failure_code = None
            _history(db, claim, "ownership_verified", to_user_id=claim.user_id)
        return True

    @staticmethod
    def transfer(db: Session, claim: CharacterOwnershipClaim, actor: User, *, admin_reason: str | None = None) -> None:
        if claim.status not in {"transfer_pending", "disputed"}:
            raise ValueError("Claim is not awaiting transfer")
        character = _find_character(db, claim)
        if character is None:
            raise ValueError("Current ownership record is missing")
        if not actor.is_superuser and character.user_id != actor.id:
            raise PermissionError("Only the current owner may approve transfer")
        if actor.is_superuser and not (admin_reason or "").strip():
            raise ValueError("Administrative transfer requires a reason")
        previous_user_id = character.user_id
        previous_user = db.get(User, previous_user_id)
        character.user_id = claim.user_id
        character.ownership_status = "verified"
        character.ownership_verified_at = datetime.now(UTC)
        character.ownership_claim_id = claim.id
        if previous_user and normalize_character_name(previous_user.tibia_character_name or "") == claim.normalized_name:
            previous_user.tibia_character_name = None
            previous_user.tibia_status = "ownership_transferred"
        _apply_primary(claim.user, character)
        claim.status = "verified"
        claim.consumed_at = datetime.now(UTC)
        _history(
            db, claim, "transfer_completed",
            from_user_id=previous_user_id, to_user_id=claim.user_id, actor_user_id=actor.id,
            metadata={
                "admin_assistance": actor.is_superuser,
                "reason": admin_reason.strip() if admin_reason else None,
            },
        )

    @staticmethod
    def dispute(db: Session, claim: CharacterOwnershipClaim, actor: User, reason: str) -> None:
        character = _find_character(db, claim)
        allowed = actor.is_superuser or bool(character and character.user_id == actor.id)
        if not allowed or claim.status != "transfer_pending":
            raise PermissionError("Claim cannot be disputed")
        claim.status = "disputed"
        claim.dispute_reason = reason.strip()
        if character:
            character.ownership_status = "disputed"
        _history(db, claim, "ownership_disputed", from_user_id=character.user_id if character else None, to_user_id=claim.user_id, actor_user_id=actor.id, metadata={"reason": claim.dispute_reason})

    @staticmethod
    def reject(db: Session, claim: CharacterOwnershipClaim, actor: User, reason: str) -> None:
        if not actor.is_superuser or claim.status not in {"transfer_pending", "disputed"}:
            raise PermissionError("Claim cannot be rejected")
        character = _find_character(db, claim)
        if character and character.ownership_verified_at is not None:
            character.ownership_status = "verified"
        claim.status = "rejected"
        claim.consumed_at = datetime.now(UTC)
        _history(
            db, claim, "claim_rejected",
            from_user_id=character.user_id if character else None,
            to_user_id=claim.user_id,
            actor_user_id=actor.id,
            metadata={"reason": reason.strip(), "admin_assistance": True},
        )
