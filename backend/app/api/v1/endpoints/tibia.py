"""Local-first TibiaData-backed public endpoints and explicit sync actions."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.api.v1.endpoints.auth import get_current_active_user, get_current_admin_user
from app.db.database import get_db
from app.knowledge.models import KnowledgeDocument, KnowledgeEntity, KnowledgeExternalMapping
from app.models.user import User
from app.services.tibia_sync_service import try_sync_user_character_snapshot

router = APIRouter(prefix="/tibia", tags=["tibia-api"])

_EXPECTED_FIELDS = {
    "character": {"name", "world", "vocation", "level", "residence", "guild", "last_login", "account_status"},
    "guild": {"name", "world", "description", "founded", "members", "logo_url"},
    "world": {"name", "status", "players_online", "location", "pvp_type", "premium_only", "battleye_protected"},
}


def _canonical_provider_payload(db: Session, entity_type: str, identifier: str) -> dict | None:
    mapping = (
        db.query(KnowledgeExternalMapping)
        .join(KnowledgeExternalMapping.entity)
        .filter(
            KnowledgeExternalMapping.provider_id == "tibiadata",
            KnowledgeExternalMapping.entity_type_id == entity_type,
            or_(
                func.lower(KnowledgeExternalMapping.external_id) == identifier.casefold(),
                func.lower(KnowledgeEntity.canonical_name) == identifier.casefold(),
            ),
        )
        .first()
    )
    if mapping is None:
        return None
    metadata = dict(mapping.provider_metadata or {})
    fields = dict(metadata.get("fields") or {})
    supplied = sorted(set(metadata.get("supplied_fields") or fields.keys()))
    document = (
        db.query(KnowledgeDocument)
        .filter(
            KnowledgeDocument.provider_id == "tibiadata",
            KnowledgeDocument.provider_document_id == f"{entity_type}:{mapping.external_id}",
        )
        .order_by(KnowledgeDocument.retrieved_at.desc())
        .first()
    )
    if entity_type == "character":
        outer = ((document.raw_json.get("character") or {}) if document and isinstance(document.raw_json, dict) else {})
        account_information = outer.get("account_information") if isinstance(outer, dict) else None
        fields.setdefault("last_login_at", fields.get("last_login"))
        fields.setdefault("account_information", account_information or {})
        if fields.get("achievement_points") is None and isinstance(account_information, dict):
            fields["achievement_points"] = account_information.get("achievement_points")
    elif entity_type == "guild":
        members = fields.get("members")
        fields.setdefault("member_count", len(members) if isinstance(members, list) else None)
    return {
        **fields,
        "canonical_id": mapping.entity_uuid,
        "knowledge_entity_id": mapping.entity_uuid,
        "external_id": mapping.external_id,
        "source_provider": mapping.provider_id,
        "source_url": metadata.get("source_url"),
        "supplied_fields": supplied,
        "missing_fields": sorted(_EXPECTED_FIELDS[entity_type] - set(supplied)),
        "data_version": metadata.get("data_version", 1),
        "last_synced_at": document.retrieved_at if document else mapping.updated_at,
    }


@router.get("/character/{character_name}")
def get_character(character_name: str, db: Session = Depends(get_db)):
    """Return the latest locally normalized TibiaData character document."""
    payload = _canonical_provider_payload(db, "character", character_name)
    if payload is None:
        raise HTTPException(status_code=404, detail=f"Character '{character_name}' not found in local Knowledge")
    return payload


@router.post("/sync/me")
async def sync_my_character(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    if not current_user.primary_character or current_user.primary_character.ownership_status != "verified":
        raise HTTPException(status_code=409, detail="Select a verified primary character before synchronizing")
    payload, error = await try_sync_user_character_snapshot(db, current_user)
    if error:
        raise HTTPException(status_code=503, detail=error)
    return {"status": "ok", "character": payload}


@router.post("/sync/user/{user_id}")
async def sync_user_character(
    user_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    _ = current_user
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.primary_character or user.primary_character.ownership_status != "verified":
        raise HTTPException(status_code=409, detail="The account has no verified primary character")
    payload, error = await try_sync_user_character_snapshot(db, user)
    if error:
        raise HTTPException(status_code=503, detail=error)
    return {"status": "ok", "user_id": user.id, "character": payload}

@router.get("/worlds")
def get_worlds_list(db: Session = Depends(get_db)):
    """Return all locally normalized TibiaData worlds."""
    mappings = db.query(KnowledgeExternalMapping).filter_by(
        provider_id="tibiadata", entity_type_id="world",
    ).order_by(KnowledgeExternalMapping.external_id.asc()).all()
    worlds = [
        payload for mapping in mappings
        if (payload := _canonical_provider_payload(db, "world", mapping.external_id)) is not None
    ]
    return {"worlds": worlds, "count": len(worlds)}

@router.get("/guild/{guild_name}")
def get_guild(guild_name: str, db: Session = Depends(get_db)):
    """Return the latest locally normalized TibiaData guild document."""
    payload = _canonical_provider_payload(db, "guild", guild_name)
    if payload is None:
        raise HTTPException(status_code=404, detail=f"Guild '{guild_name}' not found in local Knowledge")
    return payload
