"""Local-only catalog and detail APIs for normalized NPCs and locations."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.knowledge.services import KnowledgeGraphService
from app.models.external_data import TibiaWikiLocation, TibiaWikiNpc
from app.services.entity_metadata_service import EntityMetadataService
from app.services.text_utils import normalize_search_text


router = APIRouter(tags=["knowledge reference catalogs"])


class NamedReferenceSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    knowledge_entity_id: UUID
    entity_type: str
    description: str | None = None
    image_url: str | None = None
    source_url: str | None = None
    data_version: int
    last_synced_at: datetime | None = None


class NamedRelationship(BaseModel):
    relationship_type: str
    target_name: str
    target_type: str
    target_slug: str | None = None
    resolution_state: str


class NpcDetail(NamedReferenceSummary):
    title: str | None = None
    occupation: str | None = None
    sex: str | None = None
    location_name: str | None = None
    buys: list[dict[str, Any]]
    sells: list[dict[str, Any]]
    destinations: list[dict[str, Any]]
    related_quests: list[dict[str, Any]]
    relationships: list[NamedRelationship]


class LocationDetail(NamedReferenceSummary):
    location_kind: str | None = None
    region: str | None = None
    parent_location: str | None = None
    premium_required: bool | None = None
    minimum_level: int | None = None
    maximum_level: int | None = None
    npcs: list[dict[str, Any]]
    creatures: list[dict[str, Any]]
    quests: list[dict[str, Any]]
    sublocations: list[dict[str, Any]]
    access_notes: str | None = None
    relationships: list[NamedRelationship]


def _summary(row) -> NamedReferenceSummary:
    return NamedReferenceSummary(
        id=row.id,
        name=row.name,
        slug=row.slug,
        knowledge_entity_id=row.knowledge_entity_id,
        entity_type=row.knowledge_entity.entity_type,
        description=row.description,
        image_url=row.image_url,
        source_url=row.source_url,
        data_version=row.data_version,
        last_synced_at=row.last_synced_at,
    )


def _relationships(db: Session, entity_id: UUID) -> list[NamedRelationship]:
    values = [*KnowledgeGraphService.outgoing(db, entity_id), *KnowledgeGraphService.incoming(db, entity_id)]
    return [NamedRelationship(
        relationship_type=value.relationship_type, target_name=value.target_name,
        target_type=value.target_type, target_slug=value.target_slug,
        resolution_state=value.resolution_state,
    ) for value in values]


def _find(query, model, identifier: str):
    if identifier.isdigit():
        return query.filter(or_(model.id == int(identifier), model.external_id == identifier)).first()
    return query.filter(or_(model.slug == identifier, model.normalized_name == normalize_search_text(identifier))).first()


@router.get("/npcs/", response_model=list[NamedReferenceSummary])
def search_npcs(
    search: str | None = Query(None, min_length=2),
    location: str | None = Query(None, min_length=1, max_length=255),
    skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(TibiaWikiNpc)
    if search:
        query = query.filter(TibiaWikiNpc.normalized_name.contains(normalize_search_text(search)))
    if location:
        query = query.filter(TibiaWikiNpc.location_name.ilike(location))
    rows = query.order_by(TibiaWikiNpc.name.asc()).offset(skip).limit(limit).all()
    if rows and search:
        EntityMetadataService.record_searches(db, entity_type="npc", matches=[
            (row.normalized_name, row.name, row.id) for row in rows[:5]
        ])
        db.commit()
    return [_summary(row) for row in rows]


@router.get("/npcs/{identifier}", response_model=NpcDetail)
def get_npc(identifier: str, db: Session = Depends(get_db)):
    row = _find(db.query(TibiaWikiNpc), TibiaWikiNpc, identifier)
    if row is None:
        raise HTTPException(status_code=404, detail="NPC not found")
    return NpcDetail(
        **_summary(row).model_dump(), title=row.title, occupation=row.occupation, sex=row.sex,
        location_name=row.location_name, buys=list(row.buys or []), sells=list(row.sells or []),
        destinations=list(row.destinations or []), related_quests=list(row.related_quests or []),
        relationships=_relationships(db, row.knowledge_entity_id),
    )


@router.get("/locations/", response_model=list[NamedReferenceSummary])
def search_locations(
    search: str | None = Query(None, min_length=2),
    kind: str | None = Query(None, min_length=1, max_length=100),
    region: str | None = Query(None, min_length=1, max_length=255),
    skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(TibiaWikiLocation)
    if search:
        query = query.filter(TibiaWikiLocation.normalized_name.contains(normalize_search_text(search)))
    if kind:
        query = query.filter(TibiaWikiLocation.location_kind.ilike(kind))
    if region:
        query = query.filter(TibiaWikiLocation.region.ilike(region))
    rows = query.order_by(TibiaWikiLocation.name.asc()).offset(skip).limit(limit).all()
    if rows and search:
        for entity_type in {row.knowledge_entity.entity_type for row in rows[:5]}:
            EntityMetadataService.record_searches(db, entity_type=entity_type, matches=[
                (row.normalized_name, row.name, row.id)
                for row in rows[:5] if row.knowledge_entity.entity_type == entity_type
            ])
        db.commit()
    return [_summary(row) for row in rows]


@router.get("/locations/{identifier}", response_model=LocationDetail)
def get_location(identifier: str, db: Session = Depends(get_db)):
    row = _find(db.query(TibiaWikiLocation), TibiaWikiLocation, identifier)
    if row is None:
        raise HTTPException(status_code=404, detail="Location not found")
    return LocationDetail(
        **_summary(row).model_dump(), location_kind=row.location_kind, region=row.region,
        parent_location=row.parent_location, premium_required=row.premium_required,
        minimum_level=row.minimum_level, maximum_level=row.maximum_level,
        npcs=list(row.npcs or []), creatures=list(row.creatures or []), quests=list(row.quests or []),
        sublocations=list(row.sublocations or []), access_notes=row.access_notes,
        relationships=_relationships(db, row.knowledge_entity_id),
    )
