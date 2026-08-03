"""Character ownership API; provider verification is always worker-driven."""

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.v1.endpoints.auth import get_current_active_user, get_current_admin_user
from app.db.database import get_db
from app.models.character_ownership import CharacterOwnershipClaim
from app.models.guild_management import GuildRosterCharacter
from app.models.user import User
from app.models.user_character import UserCharacter
from app.services.account_identity_service import AccountIdentityError, AccountIdentityService
from app.services.character_ownership_service import CharacterOwnershipService
from app.services.character_ownership_service import normalize_character_name
from app.services.guild_authorization_service import GuildAuthorizationService
from app.services.tibia_api import get_character_info

router = APIRouter()
admin_router = APIRouter()


class ClaimCreate(BaseModel):
    character_name: str = Field(..., min_length=2, max_length=100)


class DisputeCreate(BaseModel):
    reason: str = Field(..., min_length=10, max_length=2000)


class AdminResolution(BaseModel):
    approve_transfer: bool
    reason: str = Field(..., min_length=10, max_length=2000)


class AdminCharacterLink(BaseModel):
    user_id: int
    character_name: str = Field(..., min_length=2, max_length=100)
    set_primary: bool = False
    allow_transfer: bool = False
    reason: str = Field(..., min_length=10, max_length=1000)
    confirmation: str = Field(..., min_length=5, max_length=240)


def _claim_data(row: CharacterOwnershipClaim, *, include_challenge: str | None = None) -> dict:
    data = {
        "id": row.id,
        "character_name": row.character_name,
        "status": row.status,
        "expires_at": row.expires_at,
        "verification_requested_at": row.verification_requested_at,
        "verified_at": row.verified_at,
        "safe_failure_code": row.safe_failure_code,
        "created_at": row.created_at,
    }
    if include_challenge:
        data["challenge"] = include_challenge
    return data


def _own_claim(db: Session, claim_id: int, user: User) -> CharacterOwnershipClaim:
    row = db.query(CharacterOwnershipClaim).filter_by(id=claim_id, user_id=user.id).first()
    if row is None:
        raise HTTPException(404, "Ownership claim not found")
    return row


@router.post("/claims", status_code=201)
def create_claim(payload: ClaimCreate, db: Session = Depends(get_db), user: User = Depends(get_current_active_user)):
    try:
        claim, raw_challenge = CharacterOwnershipService.create_claim(db, user, payload.character_name)
        db.commit()
        db.refresh(claim)
        return _claim_data(claim, include_challenge=raw_challenge)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(409, str(exc)) from exc


@router.get("/claims")
def list_claims(db: Session = Depends(get_db), user: User = Depends(get_current_active_user)):
    rows = db.query(CharacterOwnershipClaim).filter_by(user_id=user.id).order_by(CharacterOwnershipClaim.created_at.desc()).all()
    result = []
    for row in rows:
        challenge = CharacterOwnershipService.active_challenge(row, user)
        result.append(_claim_data(row, include_challenge=challenge))
    db.commit()
    return result


@router.get("/claims/{claim_id}")
def get_claim(claim_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_active_user)):
    row = _own_claim(db, claim_id, user)
    challenge = CharacterOwnershipService.active_challenge(row, user)
    db.commit()
    return _claim_data(row, include_challenge=challenge)


@router.post("/claims/{claim_id}/cancel")
def cancel_claim(claim_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_active_user)):
    try:
        row = _own_claim(db, claim_id, user)
        CharacterOwnershipService.cancel(db, row, user)
        db.commit()
        return _claim_data(row)
    except PermissionError as exc:
        db.rollback()
        raise HTTPException(403, str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(409, str(exc)) from exc


@router.get("/incoming-transfers")
def incoming_transfers(db: Session = Depends(get_db), user: User = Depends(get_current_active_user)):
    owned_names = [
        row.normalized_name for row in getattr(user, "characters", [])
        if row.normalized_name and row.ownership_status in {"verified", "disputed"}
    ]
    if not owned_names:
        return []
    rows = db.query(CharacterOwnershipClaim).filter(
        CharacterOwnershipClaim.normalized_name.in_(owned_names),
        CharacterOwnershipClaim.status.in_(["transfer_pending", "disputed"]),
        CharacterOwnershipClaim.user_id != user.id,
    ).order_by(CharacterOwnershipClaim.created_at).all()
    return [{**_claim_data(row), "incoming": True} for row in rows]


@router.post("/claims/{claim_id}/verify", status_code=202)
def queue_claim(claim_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_active_user)):
    try:
        row = _own_claim(db, claim_id, user)
        CharacterOwnershipService.queue(db, row, user)
        db.commit()
        return _claim_data(row)
    except PermissionError as exc:
        db.rollback()
        raise HTTPException(403, str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(409, str(exc)) from exc


@router.post("/claims/{claim_id}/approve-transfer")
def approve_transfer(claim_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_active_user)):
    row = db.get(CharacterOwnershipClaim, claim_id)
    if row is None:
        raise HTTPException(404, "Ownership claim not found")
    try:
        CharacterOwnershipService.transfer(db, row, user)
        db.commit()
        return _claim_data(row)
    except PermissionError as exc:
        db.rollback()
        raise HTTPException(403, str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(409, str(exc)) from exc


@router.post("/claims/{claim_id}/dispute")
def dispute(claim_id: int, payload: DisputeCreate, db: Session = Depends(get_db), user: User = Depends(get_current_active_user)):
    row = db.get(CharacterOwnershipClaim, claim_id)
    if row is None:
        raise HTTPException(404, "Ownership claim not found")
    try:
        CharacterOwnershipService.dispute(db, row, user, payload.reason)
        db.commit()
        return _claim_data(row)
    except PermissionError as exc:
        db.rollback()
        raise HTTPException(403, str(exc)) from exc


@admin_router.get("/character-ownership/claims")
def admin_claims(db: Session = Depends(get_db), _admin: User = Depends(get_current_admin_user)):
    rows = db.query(CharacterOwnershipClaim).filter(CharacterOwnershipClaim.status.in_(["transfer_pending", "disputed"])).order_by(CharacterOwnershipClaim.created_at).all()
    return [_claim_data(row) for row in rows]


@admin_router.post("/character-ownership/claims/{claim_id}/resolve")
def admin_resolve(claim_id: int, payload: AdminResolution, db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    row = db.get(CharacterOwnershipClaim, claim_id)
    if row is None:
        raise HTTPException(404, "Ownership claim not found")
    try:
        if payload.approve_transfer:
            CharacterOwnershipService.transfer(db, row, admin, admin_reason=payload.reason)
        else:
            CharacterOwnershipService.reject(db, row, admin, payload.reason)
        db.commit()
        return _claim_data(row)
    except (PermissionError, ValueError) as exc:
        db.rollback()
        raise HTTPException(409, str(exc)) from exc


@admin_router.get("/character-ownership/search")
def admin_character_search(
    query: str,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin_user),
):
    normalized = normalize_character_name(query)
    if len(normalized) < 2:
        return []
    roster = db.query(GuildRosterCharacter).filter(
        GuildRosterCharacter.normalized_character_name.contains(normalized),
        GuildRosterCharacter.is_current.is_(True),
    ).order_by(GuildRosterCharacter.character_name).limit(25).all()
    linked = {
        row.normalized_name: row
        for row in db.query(UserCharacter).filter(
            UserCharacter.normalized_name.in_([item.normalized_character_name for item in roster])
        ).all()
    } if roster else {}
    return [{
        "character_name": row.character_name, "world_name": row.world_name,
        "guild_name": row.guild_name, "guild_rank": row.guild_rank,
        "level": row.level, "vocation": row.vocation,
        "roster_character_id": row.id,
        "linked_user_id": linked.get(row.normalized_character_name).user_id if linked.get(row.normalized_character_name) else None,
        "ownership_status": linked.get(row.normalized_character_name).ownership_status if linked.get(row.normalized_character_name) else None,
    } for row in roster]


@admin_router.post("/character-ownership/link")
async def admin_link_character(
    payload: AdminCharacterLink,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    target = db.get(User, payload.user_id)
    if target is None:
        raise HTTPException(404, "User not found")
    normalized = normalize_character_name(payload.character_name)
    roster = db.query(GuildRosterCharacter).filter(
        GuildRosterCharacter.normalized_character_name == normalized,
        GuildRosterCharacter.is_current.is_(True),
    ).first()
    if roster:
        snapshot = {
            "name": roster.character_name, "world": roster.world_name,
            "level": roster.level, "vocation": roster.vocation,
            "guild": {"name": roster.guild_name, "rank": roster.guild_rank},
        }
        canonical_name = roster.character_name
    else:
        try:
            snapshot = await get_character_info(payload.character_name)
        except Exception as exc:
            raise HTTPException(503, "Character data is temporarily unavailable") from exc
        if not snapshot or normalize_character_name(snapshot.get("name") or "") != normalized:
            raise HTTPException(404, "Character was not found in the synchronized roster or TibiaData")
        canonical_name = snapshot.get("name") or payload.character_name
    action = "TRANSFER" if payload.allow_transfer else "LINK"
    expected = f"{action} {canonical_name} TO {target.username}"
    if payload.confirmation.strip() != expected:
        raise HTTPException(409, f"Confirmation must exactly match: {expected}")
    try:
        character = AccountIdentityService.admin_link(
            db, admin=admin, target=target, character_name=canonical_name,
            snapshot=snapshot, reason=payload.reason, set_primary=payload.set_primary,
            allow_transfer=payload.allow_transfer,
        )
        db.commit()
        db.refresh(character)
        return {
            "character": AccountIdentityService.serialize_character(
                db, character, primary_character_id=target.primary_character_id,
            ),
            "guild_contexts": GuildAuthorizationService.guild_contexts(db, target),
        }
    except AccountIdentityError as exc:
        db.rollback()
        raise HTTPException(409, str(exc)) from exc
