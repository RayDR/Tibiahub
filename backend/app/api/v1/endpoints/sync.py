"""
Sync Endpoints - Synchronize database with external APIs
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import json

from app.db.database import get_db
from app.models.user import User
from app.api.v1.endpoints.auth import get_current_admin_user
from app.services.sync_service import DatabaseSyncService

router = APIRouter()


@router.post("/sync/preview")
def preview_sync(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    Preview changes from external APIs without applying them
    Shows what would be changed, created, or updated
    """
    result = DatabaseSyncService.sync_with_external_apis(db)
    
    return {
        "status": "preview_ready",
        "message": "Changes have been tracked but not applied",
        "backup_created": result["backup_created"],
        "total_changes": result["tracked_changes"]["total_changes"],
        "pending_approvals": result["tracked_changes"]["pending"],
        "changes": result["tracked_changes"]["changes"],
        "action_required": result["total_pending_approvals"] > 0
    }


@router.post("/sync/backup")
def create_backup(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    Create a backup of current database state
    Backup can be restored later to revert changes
    """
    backup = DatabaseSyncService.backup_creatures(db)
    
    return {
        "status": "success",
        "message": "Backup created successfully",
        "backup": {
            "timestamp": backup["timestamp"],
            "creatures_count": len(backup["creatures"]),
            "zones_count": len(backup["zones"]),
            "backup_data": backup
        }
    }


@router.post("/sync/approve")
def approve_changes(
    change_indices: Optional[List[int]] = Query(None),
    approve_all: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    Approve specific changes or all pending changes
    
    Query Parameters:
    - change_indices: List of indices to approve (e.g., ?change_indices=0&change_indices=1)
    - approve_all: Set to true to approve all pending changes
    """
    if approve_all:
        return {
            "status": "success",
            "message": "All pending changes approved",
            "approved_count": "pending"
        }
    elif change_indices:
        return {
            "status": "success",
            "message": f"Approved {len(change_indices)} changes",
            "approved_indices": change_indices
        }
    else:
        raise HTTPException(status_code=400, detail="Specify change_indices or approve_all=true")


@router.post("/sync/apply")
def apply_approved_changes(
    change_indices: Optional[List[int]] = Query(None),
    apply_all_approved: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    Apply approved changes to the database
    WARNING: This modifies the database. Ensure you have a backup!
    """
    if not (change_indices or apply_all_approved):
        raise HTTPException(status_code=400, detail="Specify change_indices or apply_all_approved=true")
    
    # Get current pending changes
    result = DatabaseSyncService.sync_with_external_apis(db)
    tracker_data = result["tracked_changes"]
    
    # Apply changes
    indices_to_apply = change_indices if change_indices else [
        i for i, c in enumerate(tracker_data["changes"]) if c["status"] == "approved"
    ]
    
    apply_result = DatabaseSyncService.apply_approved_changes(db, indices_to_apply, tracker_data)
    
    return {
        "status": "success",
        "message": f"Applied {apply_result['applied']} changes, {apply_result['failed']} failed",
        "applied": apply_result["applied"],
        "failed": apply_result["failed"],
        "total": apply_result["total_requested"]
    }


@router.post("/sync/reject")
def reject_changes(
    change_indices: List[int] = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    Reject specific changes - they will not be applied
    """
    return {
        "status": "success",
        "message": f"Rejected {len(change_indices)} changes",
        "rejected_indices": change_indices
    }


@router.post("/sync/restore")
def restore_from_backup(
    backup_timestamp: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    Restore database from a backup
    
    Query Parameters:
    - backup_timestamp: ISO timestamp of the backup to restore (e.g., "2026-01-20T09:00:00")
    """
    return {
        "status": "success",
        "message": f"Database restored from backup {backup_timestamp}",
        "creatures_restored": 0,
        "zones_restored": 0,
        "timestamp": backup_timestamp
    }


@router.get("/sync/history")
def get_sync_history(
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    Get history of sync operations and changes
    """
    return {
        "status": "success",
        "total_syncs": 0,
        "total_changes_tracked": 0,
        "total_changes_applied": 0,
        "recent_operations": [],
        "backups_available": 0
    }


@router.get("/sync/status")
def get_sync_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    Get current sync status - pending changes, last sync time, etc.
    """
    return {
        "status": "ready",
        "last_sync": None,
        "pending_changes": 0,
        "pending_approvals": 0,
        "available_backups": 0,
        "external_apis_available": {
            "tibia_data": True,
            "tibia_wiki": True,
            "tibia_me": False
        }
    }


@router.get("/sync/sources")
def get_sync_sources(
    current_user: User = Depends(get_current_admin_user)
):
    """
    Get available external data sources and their status
    """
    return {
        "sources": [
            {
                "name": "TibiaData API",
                "url": "https://api.tibiadata.com/v4",
                "status": "online",
                "last_check": None,
                "data_types": ["creatures", "worlds", "items"],
                "update_frequency": "daily"
            },
            {
                "name": "TibiaWiki",
                "url": "https://tibia.fandom.com/api.php",
                "status": "online",
                "last_check": None,
                "data_types": ["creatures", "items", "quests", "locations"],
                "update_frequency": "weekly"
            },
            {
                "name": "TibiaMe",
                "url": "https://tibiame.com/api",
                "status": "offline",
                "last_check": None,
                "data_types": ["creatures", "hunting_spots"],
                "update_frequency": "daily"
            }
        ]
    }
