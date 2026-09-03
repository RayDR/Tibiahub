"""Local-only catalog and detail APIs for normalized NPCs and locations."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import exists, or_
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.db.database import get_db
from app.knowledge.services import KnowledgeGraphService
from app.knowledge.models import KnowledgeEntityAlias
from app.models.external_data import TibiaWikiLocation, TibiaWikiNpc
from app.services.entity_metadata_service import EntityMetadataService
from app.services.npc_projection_service import detail_references, directory_rows
from app.services import media_asset_service as media_svc
from app.api.v1.local_media import (
    LocalMediaDescriptor, build_local_media_file_response,
)
from app.services.text_utils import normalize_search_text


router = APIRouter(tags=["knowledge reference catalogs"])


class NamedReferenceSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    knowledge_entity_id: UUID
    canonical_id: UUID
    external_id: str
    entity_type: str
    description: str | None = None
    image_url: str | None = None
    source_url: str | None = None
    source_provider: str
    supplied_fields: list[str]
    missing_fields: list[str]
    data_version: int
    last_synced_at: datetime | None = None


class NamedRelationship(BaseModel):
    canonical_id: UUID
    relationship_type: str
    target_canonical_id: UUID | None = None
    target_name: str
    target_type: str
    target_slug: str | None = None
    resolution_state: str
    confidence: str
    source_providers: list[str]
    last_synced_at: datetime


class NpcMedia(BaseModel):
    status: str
    url: str | None = None
    source_provider: str | None = None
    source_url: str | None = None


class NpcDirectoryItem(BaseModel):
    id: int
    canonical_id: UUID
    knowledge_entity_id: UUID
    name: str
    slug: str
    title: str | None = None
    occupation: str | None = None
    location_name: str | None = None
    buys_count: int | None = None
    sells_count: int | None = None
    quest_count: int | None = None
    destination_count: int | None = None
    media: NpcMedia
    geometry_status: str
    spatial_state: str
    map_available: bool
    last_synced_at: datetime | None = None


class NpcDirectoryPage(BaseModel):
    items: list[NpcDirectoryItem]
    total: int
    skip: int
    limit: int


class NpcNamedReference(BaseModel):
    name: str
    price: int | float | str | None = None
    currency: str | None = None
    qualifier: str | None = None
    offers: list[dict[str, Any]] = Field(default_factory=list)
    semantic: str
    canonical_id: UUID | None = None
    entity_type: str
    slug: str | None = None
    resolution_state: str
    navigation_url: str | None = None


class NpcSpatial(BaseModel):
    x: int | None = None
    y: int | None = None
    z: int | None = None
    bounds: dict[str, int] | None = None
    geometry_status: str
    spatial_state: str
    geometry_source: str | None = None
    spatial_evidence: list[dict[str, Any]] = Field(default_factory=list)
    location_labels: list[str] = Field(default_factory=list)


class NpcDetail(NamedReferenceSummary):
    title: str | None = None
    occupation: str | None = None
    sex: str | None = None
    location_name: str | None = None
    aliases: list[str]
    field_coverage: dict[str, str]
    buys: list[NpcNamedReference]
    sells: list[NpcNamedReference]
    destinations: list[NpcNamedReference]
    related_quests: list[NpcNamedReference]
    media: NpcMedia
    spatial: NpcSpatial
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
    supplied = sorted(set(row.supplied_fields or []))
    expected = (
        {"description", "title", "occupation", "location_name", "buys", "sells", "destinations", "related_quests"}
        if isinstance(row, TibiaWikiNpc)
        else {"description", "location_kind", "region", "parent_location", "premium_required", "minimum_level", "maximum_level", "npcs", "creatures", "quests", "sublocations", "access_notes"}
    )
    return NamedReferenceSummary(
        id=row.id,
        name=row.name,
        slug=row.slug,
        knowledge_entity_id=row.knowledge_entity_id,
        canonical_id=row.knowledge_entity_id,
        external_id=row.external_id,
        entity_type=row.knowledge_entity.entity_type,
        description=row.description,
        # NPC provider images are reference-only until a local cache contract
        # exists. Locations retain their existing legacy behavior.
        image_url=None if isinstance(row, TibiaWikiNpc) else row.image_url,
        source_url=row.source_url,
        source_provider=row.source_name,
        supplied_fields=supplied,
        missing_fields=sorted(expected - set(supplied)),
        data_version=row.data_version,
        last_synced_at=row.last_synced_at,
    )


def _relationships(db: Session, entity_id: UUID) -> list[NamedRelationship]:
    values = [*KnowledgeGraphService.outgoing(db, entity_id), *KnowledgeGraphService.incoming(db, entity_id)]
    return [NamedRelationship(
        canonical_id=value.relationship_id, relationship_type=value.relationship_type,
        target_canonical_id=value.target_entity_id, target_name=value.target_name,
        target_type=value.target_type, target_slug=value.target_slug,
        resolution_state=value.resolution_state, confidence=value.confidence,
        source_providers=list(value.contributing_providers), last_synced_at=value.freshness,
    ) for value in values]


def _find(query, model, identifier: str):
    if identifier.isdigit():
        return query.filter(or_(model.id == int(identifier), model.external_id == identifier)).first()
    try:
        canonical_id = UUID(identifier)
    except ValueError:
        canonical_id = None
    if canonical_id is not None:
        return query.filter(model.knowledge_entity_id == canonical_id).first()
    return query.filter(or_(model.slug == identifier, model.normalized_name == normalize_search_text(identifier))).first()


def _npc_media_descriptor(db: Session, npc_id: int) -> LocalMediaDescriptor:
    row = db.query(TibiaWikiNpc).filter_by(id=npc_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="NPC not found")
    key = media_svc.build_npc_asset_key(row)
    asset = media_svc.get_asset(db, key)
    cached = bool(asset and asset.status == "cached" and asset.file_exists())
    return LocalMediaDescriptor(
        local_path=str(asset.local_path) if cached and asset.local_path else None,
        content_type=asset.content_type if cached else None,
        size_bytes=asset.size_bytes if cached else None,
        asset_hash=asset.sha256_hash if cached else None,
        asset_key=key,
        status=asset.status if asset else "missing",
        fallback_label=row.name,
    )


def _npc_search_query(db: Session, search: str | None, location: str | None):
    query = db.query(TibiaWikiNpc).options(joinedload(TibiaWikiNpc.knowledge_entity))
    if search:
        normalized = normalize_search_text(search)
        alias_match = exists().where(
            KnowledgeEntityAlias.entity_uuid == TibiaWikiNpc.knowledge_entity_id,
            KnowledgeEntityAlias.entity_type == "npc",
            KnowledgeEntityAlias.normalized_alias.contains(normalized),
        )
        query = query.filter(or_(
            TibiaWikiNpc.normalized_name.contains(normalized),
            TibiaWikiNpc.location_name.ilike(f"%{search.strip()}%"),
            TibiaWikiNpc.occupation.ilike(f"%{search.strip()}%"),
            alias_match,
        ))
    if location:
        query = query.filter(TibiaWikiNpc.location_name.ilike(f"%{location.strip()}%"))
    return query


@router.get("/npcs/", response_model=list[NamedReferenceSummary])
def search_npcs(
    search: str | None = Query(None, min_length=2),
    location: str | None = Query(None, min_length=1, max_length=255),
    skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = _npc_search_query(db, search, location)
    rows = query.order_by(TibiaWikiNpc.normalized_name.asc(), TibiaWikiNpc.id.asc()).offset(skip).limit(limit).all()
    if rows and search:
        EntityMetadataService.record_searches(db, entity_type="npc", matches=[
            (row.normalized_name, row.name, row.id) for row in rows[:5]
        ])
        db.commit()
    return [_summary(row) for row in rows]


@router.get("/npcs/directory", response_model=NpcDirectoryPage)
def npc_directory(
    search: str | None = Query(None, min_length=2, max_length=255),
    location: str | None = Query(None, min_length=1, max_length=255),
    skip: int = Query(0, ge=0),
    limit: int = Query(24, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Return an authoritative total and a lightweight canonical NPC page."""
    query = _npc_search_query(db, search, location)
    total = query.order_by(None).count()
    rows = (
        query.order_by(TibiaWikiNpc.normalized_name.asc(), TibiaWikiNpc.id.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    projected = directory_rows(db, rows)
    if rows and search:
        EntityMetadataService.record_searches(db, entity_type="npc", matches=[
            (row.normalized_name, row.name, row.id) for row in rows[:5]
        ])
        db.commit()
    return NpcDirectoryPage(
        items=[NpcDirectoryItem(**projected[row.knowledge_entity_id]) for row in rows],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/npcs/{npc_id}/image")
def get_npc_image(npc_id: int, request: Request, db: Session = Depends(get_db)):
    """Serve only validated, worker-cached NPC media; never proxy providers."""
    descriptor = _npc_media_descriptor(db, npc_id)
    if descriptor.status != "cached":
        raise HTTPException(
            status_code=404,
            detail="NPC image unavailable",
            headers={
                "X-Image-Source": "unavailable",
                "X-Image-Status": descriptor.status,
                "X-Asset-Key": descriptor.asset_key,
            },
        )
    response = build_local_media_file_response(
        request,
        descriptor,
        default_media_type="image/gif",
        cache_max_age_seconds=settings.IMAGE_CACHE_MAX_AGE_SECONDS,
        extra_headers={
            "X-Image-Source": "local-media-asset",
            "X-Image-Status": "cached",
            "X-Asset-Key": descriptor.asset_key,
        },
    )
    if response is None:
        raise HTTPException(status_code=404, detail="NPC image unavailable")
    return response


@router.get("/npcs/{identifier}", response_model=NpcDetail)
def get_npc(identifier: str, db: Session = Depends(get_db)):
    row = _find(
        db.query(TibiaWikiNpc).options(joinedload(TibiaWikiNpc.knowledge_entity)),
        TibiaWikiNpc,
        identifier,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="NPC not found")
    references = detail_references(db, row)
    return NpcDetail(
        **_summary(row).model_dump(), title=row.title, occupation=row.occupation, sex=row.sex,
        location_name=row.location_name or (row.provider_metadata or {}).get("location_text"),
        aliases=references["aliases"], field_coverage=references["field_coverage"],
        buys=references["buys"], sells=references["sells"],
        destinations=references["destinations"], related_quests=references["related_quests"],
        media=references["media"], spatial=references["spatial"],
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
