"""Safe, local-only Knowledge Graph traversal endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.knowledge.models import KnowledgeEntity, KnowledgeRelationshipType
from app.knowledge.schemas import KnowledgeRelationshipPage, KnowledgeRelationshipResponse
from app.knowledge.services import KnowledgeGraphService


router = APIRouter(prefix="/knowledge", tags=["Knowledge Graph"])


def _response(value) -> KnowledgeRelationshipResponse:
    return KnowledgeRelationshipResponse(
        id=value.relationship_id,
        source_entity_id=value.source_entity_id,
        source_name=value.source_name,
        source_type=value.source_type,
        relationship_type=value.relationship_type,
        display_translation_key=value.display_translation_key,
        target_entity_id=value.target_entity_id,
        target_name=value.target_name,
        target_type=value.target_type,
        target_slug=value.target_slug,
        resolution_state=value.resolution_state,
        confidence=value.confidence,
        contributing_providers=list(value.contributing_providers),
        manual_verified=value.manual_verified,
        freshness=value.freshness,
        source_scope=value.source_scope,
        provenance_count=value.provenance_count,
    )


def _page(db: Session, values, skip: int, limit: int) -> KnowledgeRelationshipPage:
    # Candidate lists, raw source context, internal users, and provider payloads
    # intentionally never enter this public DTO.
    visible_codes = {row[0] for row in db.query(KnowledgeRelationshipType.code).filter_by(
        active=True, user_visible=True,
    ).all()}
    visible = [value for value in values if value.resolution_state != "ambiguous" and value.relationship_type in visible_codes]
    return KnowledgeRelationshipPage(
        items=[_response(value) for value in visible[skip:skip + limit]],
        total=len(visible), skip=skip, limit=limit,
    )


def _entity(db: Session, entity_id: UUID) -> None:
    if db.get(KnowledgeEntity, entity_id) is None:
        raise HTTPException(status_code=404, detail={"code": "knowledge_entity_not_found"})


@router.get("/entities/{entity_id}/relationships", response_model=KnowledgeRelationshipPage)
def relationships(entity_id: UUID, relationship_type: str | None = None,
                  skip: int = Query(0, ge=0), limit: int = Query(25, ge=1, le=100),
                  db: Session = Depends(get_db)):
    _entity(db, entity_id)
    outgoing, incoming = KnowledgeGraphService.depth_one(db, entity_id, relationship_type=relationship_type)
    return _page(db, outgoing + incoming, skip, limit)


@router.get("/entities/{entity_id}/relationships/outgoing", response_model=KnowledgeRelationshipPage)
def outgoing(entity_id: UUID, relationship_type: str | None = None,
             skip: int = Query(0, ge=0), limit: int = Query(25, ge=1, le=100),
             db: Session = Depends(get_db)):
    _entity(db, entity_id)
    return _page(db, KnowledgeGraphService.outgoing(db, entity_id, relationship_type=relationship_type), skip, limit)


@router.get("/entities/{entity_id}/relationships/incoming", response_model=KnowledgeRelationshipPage)
def incoming(entity_id: UUID, relationship_type: str | None = None,
             skip: int = Query(0, ge=0), limit: int = Query(25, ge=1, le=100),
             db: Session = Depends(get_db)):
    _entity(db, entity_id)
    return _page(db, KnowledgeGraphService.incoming(db, entity_id, relationship_type=relationship_type), skip, limit)
