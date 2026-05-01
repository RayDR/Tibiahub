"""Admin endpoints for data synchronization and local metadata curation."""
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db.database import get_db
from app.models.user import User
from app.api.v1.endpoints.auth import get_current_admin_user
from app.services.external_sync_service import ExternalSyncService
from app.models.external_data import APISync, Item, HuntingPlace, TibiaWikiQuest
from app.models.creature import Creature
from app.services.entity_metadata_service import EntityMetadataService
from datetime import datetime

router = APIRouter()

class SyncResponse(BaseModel):
    """Response from sync operations"""
    api: str
    status: str
    source: Optional[str] = None
    created: int = 0
    updated: int = 0
    errors: int = 0
    total: int = 0
    error: Optional[str] = None
    sync_id: int
    message: Optional[str] = None
    conflicts: Optional[List[dict[str, Any]]] = None

class SyncLogResponse(BaseModel):
    """Sync log entry"""
    id: int
    api_name: str
    endpoint: str
    status: str
    source: Optional[str]
    total_items: Optional[int]
    processed_items: int
    error_count: int
    message: Optional[str]
    error_details: Optional[str]
    started_at: datetime
    completed_at: Optional[datetime]

class SyncStats(BaseModel):
    """Sync statistics"""
    creatures: int
    items: int
    hunting_places: int
    quests: int
    sync_logs: int

class DataComparison(BaseModel):
    """Comparison between old and new data"""
    field: str
    old_value: Any
    new_value: Any
    different: bool

class ConflictItem(BaseModel):
    """Item with conflicts"""
    api_name: str
    item_name: str
    conflicts: List[DataComparison]
    action: str = "pending"

class ConflictResolution(BaseModel):
    """Resolution for conflicts"""
    conflicts: List[ConflictItem]
    action: str  # 'skip_all' or 'overwrite_all'


class MetadataFlagRequest(BaseModel):
    entity_type: str
    entity_key: str
    display_name: str
    entity_id: Optional[int] = None
    is_featured: Optional[bool] = None
    is_pinned: Optional[bool] = None
    is_favorite: Optional[bool] = None
    notes: Optional[str] = None

# ============ SYNC ENDPOINTS ============

@router.post("/sync/creatures", response_model=SyncResponse)
async def sync_creatures(
    mode: str = Query("compare", description="Sync mode: 'auto' or 'compare'"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    Sync creatures from TibiaWiki API
    Runs in background, returns sync ID to track progress
    Mode: 'auto' (overwrite without asking) or 'compare' (check conflicts first)
    """
    _ = current_user
    if mode == "compare":
        conflicts = await ExternalSyncService.check_creature_conflicts(db)
        if conflicts:
            return SyncResponse(api="creatures", status="conflicts_found", sync_id=0, message=f"Found {len(conflicts)} conflicts. Resolve them first.", conflicts=conflicts)
    result = await ExternalSyncService.sync_creatures(db, mode=mode)
    return SyncResponse(**result)

@router.post("/sync/items", response_model=SyncResponse)
async def sync_items(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    Sync items from TibiaWiki API
    Runs in background
    """
    _ = current_user
    result = await ExternalSyncService.sync_items(db)
    return SyncResponse(**result)

@router.post("/sync/hunting-places", response_model=SyncResponse)
async def sync_hunting_places(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    Sync hunting places from TibiaWiki API
    Runs in background
    """
    _ = current_user
    result = await ExternalSyncService.sync_hunting_places(db)
    return SyncResponse(**result)

@router.post("/sync/quests", response_model=SyncResponse)
async def sync_quests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    Sync quests from TibiaWiki API
    Runs in background
    """
    _ = current_user
    result = await ExternalSyncService.sync_quests(db)
    return SyncResponse(**result)

@router.post("/sync/all", response_model=dict)
async def sync_all(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    Sync all external APIs in background
    Returns status for each sync
    """
    _ = current_user
    results = {
        "creatures": await ExternalSyncService.sync_creatures(db, mode="auto"),
        "items": await ExternalSyncService.sync_items(db),
        "hunting_places": await ExternalSyncService.sync_hunting_places(db),
        "quests": await ExternalSyncService.sync_quests(db),
    }
    return {
        "status": "completed",
        "apis": ["creatures", "items", "hunting_places", "quests"],
        "results": results,
    }

# ============ LOGS ENDPOINTS ============

@router.get("/sync/logs", response_model=List[SyncLogResponse])
def get_sync_logs(
    api_name: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    Get synchronization logs
    Filter by API name if provided
    """
    logs = ExternalSyncService.get_sync_logs(db, api_name=api_name, limit=limit)
    
    return [
        SyncLogResponse(
            id=log.id,
            api_name=log.api_name,
            endpoint=log.endpoint,
            status=log.status,
            source=log.source,
            total_items=log.total_items,
            processed_items=log.processed_items,
            error_count=log.error_count,
            message=log.message,
            error_details=log.error_details,
            started_at=log.started_at,
            completed_at=log.completed_at
        )
        for log in logs
    ]

@router.get("/sync/logs/{sync_id}", response_model=SyncLogResponse)
def get_sync_log(
    sync_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    Get specific sync log details
    """
    log = db.query(APISync).filter(APISync.id == sync_id).first()
    
    if not log:
        raise HTTPException(status_code=404, detail="Sync log not found")
    
    return SyncLogResponse(
        id=log.id,
        api_name=log.api_name,
        endpoint=log.endpoint,
        status=log.status,
        source=log.source,
        total_items=log.total_items,
        processed_items=log.processed_items,
        error_count=log.error_count,
        message=log.message,
        error_details=log.error_details,
        started_at=log.started_at,
        completed_at=log.completed_at
    )

@router.get("/sync/logs/{sync_id}/progress")
def get_sync_progress(
    sync_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    Get current progress of a sync operation
    """
    log = db.query(APISync).filter(APISync.id == sync_id).first()
    
    if not log:
        raise HTTPException(status_code=404, detail="Sync log not found")
    
    percentage = 0
    if log.total_items and log.total_items > 0:
        percentage = int((log.processed_items / log.total_items) * 100)
    
    return {
        "sync_id": log.id,
        "api": log.api_name,
        "status": log.status,
        "total": log.total_items,
        "processed": log.processed_items,
        "percentage": percentage,
        "errors": log.error_count,
        "message": log.message
    }

# ============ STATISTICS ENDPOINTS ============

@router.get("/sync/stats", response_model=SyncStats)
def get_sync_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    Get statistics about synced data
    """
    stats = ExternalSyncService.get_sync_stats(db)
    return SyncStats(**stats)

@router.get("/data/creatures", response_model=dict)
def get_creatures_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Get creature statistics"""
    total = db.query(Creature).count()
    by_level = db.query(Creature.level).filter(Creature.level != None).all()
    
    return {
        "total": total,
        "levels": [level[0] for level in by_level]
    }

@router.get("/data/items", response_model=dict)
def get_items_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Get item statistics"""
    total = db.query(Item).count()
    by_type = {}
    
    items = db.query(Item.type).all()
    for item_type in items:
        if item_type[0]:
            by_type[item_type[0]] = by_type.get(item_type[0], 0) + 1
    
    return {
        "total": total,
        "by_type": by_type
    }

# ============ CONFLICT RESOLUTION ENDPOINTS ============

@router.post("/resolve-conflicts")
async def resolve_conflicts(
    resolution: ConflictResolution,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    Resolve conflicts by applying the chosen action
    Actions: 'skip_all' (keep existing) or 'overwrite_all' (use new data)
    """
    try:
        result = await ExternalSyncService.resolve_conflicts(
            db, 
            resolution.conflicts, 
            resolution.action
        )
        return {
            "status": "success",
            "message": f"Applied {resolution.action} to {len(resolution.conflicts)} items",
            "applied": result.get("applied", 0),
            "skipped": result.get("skipped", 0)
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/metadata/flags")
def set_entity_metadata_flags(
    payload: MetadataFlagRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    _ = current_user
    record = EntityMetadataService.set_flags(
        db,
        entity_type=payload.entity_type,
        entity_key=payload.entity_key,
        display_name=payload.display_name,
        entity_id=payload.entity_id,
        is_featured=payload.is_featured,
        is_pinned=payload.is_pinned,
        is_favorite=payload.is_favorite,
        notes=payload.notes,
    )
    db.commit()
    db.refresh(record)
    return {
        "status": "success",
        "id": record.id,
        "entity_type": record.entity_type,
        "entity_key": record.entity_key,
        "display_name": record.display_name,
        "entity_id": record.entity_id,
        "is_featured": record.is_featured,
        "is_pinned": record.is_pinned,
        "is_favorite": record.is_favorite,
        "search_count": record.search_count,
        "notes": record.notes,
    }
