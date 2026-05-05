"""
Database Synchronization Service
Syncs creature data with TibiaWiki, TibiaData, and TibiaMe APIs
Tracks changes and maintains backups
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
import requests
import json
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.database import SessionLocal
from app.models.creature import Creature
from app.models.hunt_zone import HuntZone


class DataChangeTracker:
    """Track changes from external APIs"""
    
    def __init__(self):
        self.changes: List[Dict[str, Any]] = []
        self.timestamp = datetime.utcnow().isoformat()
    
    def add_change(self, change_type: str, source_api: str, entity: str, entity_id: int, 
                   old_data: Optional[Dict] = None, new_data: Optional[Dict] = None, 
                   action: str = "create"):
        """
        Track a change
        change_type: 'creature', 'zone', 'loot'
        action: 'create', 'update', 'delete'
        """
        self.changes.append({
            "timestamp": datetime.utcnow().isoformat(),
            "change_type": change_type,
            "source_api": source_api,
            "entity": entity,
            "entity_id": entity_id,
            "action": action,
            "old_data": old_data,
            "new_data": new_data,
            "status": "pending",  # pending, approved, rejected, applied
            "approval_required": bool(old_data and new_data)  # Update needs approval
        })
    
    def get_pending_changes(self) -> List[Dict]:
        """Get changes awaiting approval"""
        return [c for c in self.changes if c["status"] == "pending"]
    
    def approve_change(self, change_index: int):
        """Approve a change"""
        if 0 <= change_index < len(self.changes):
            self.changes[change_index]["status"] = "approved"
    
    def reject_change(self, change_index: int):
        """Reject a change"""
        if 0 <= change_index < len(self.changes):
            self.changes[change_index]["status"] = "rejected"
    
    def approve_all(self):
        """Approve all pending changes"""
        for change in self.changes:
            if change["status"] == "pending":
                change["status"] = "approved"
    
    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp,
            "total_changes": len(self.changes),
            "pending": len(self.get_pending_changes()),
            "changes": self.changes
        }


class DatabaseSyncService:
    """Service to sync creature data from external APIs"""
    
    TIBIA_DATA_URL = "https://api.tibiadata.com/v4"
    TIBIA_WIKI_URL = "https://tibia.fandom.com/api.php"
    TIBIA_ME_URL = "https://tibiame.com/api"
    CONNECT_TIMEOUT = 3
    READ_TIMEOUT = 10

    @staticmethod
    def _get_with_resilience(url: str, **kwargs):
        timeout = kwargs.pop("timeout", (DatabaseSyncService.CONNECT_TIMEOUT, DatabaseSyncService.READ_TIMEOUT))
        attempts = 3
        last_error = None
        for _ in range(attempts):
            try:
                return requests.get(url, timeout=timeout, **kwargs)
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
                last_error = exc
                continue
        if last_error:
            raise last_error
        raise RuntimeError("Request failed without explicit exception")
    
    @staticmethod
    def backup_creatures(db: Session) -> Dict[str, Any]:
        """Create backup of all creatures and zones"""
        creatures = db.query(Creature).all()
        zones = db.query(HuntZone).all()
        
        backup = {
            "timestamp": datetime.utcnow().isoformat(),
            "creatures": [
                {
                    "id": c.id,
                    "name": c.name,
                    "description": c.description,
                    "health": c.health,
                    "experience": c.experience,
                    "armor": c.armor,
                    "creature_class": c.creature_class,
                    "alignment": c.alignment,
                    "behavior": c.behavior,
                    "abilities": c.abilities,
                    "habitat": c.habitat,
                    "loot": [{"id": l.id, "name": l.name, "rate": l.rate} for l in c.loot]
                }
                for c in creatures
            ],
            "zones": [
                {
                    "id": z.id,
                    "name": z.name,
                    "location": z.location,
                    "creatures": [c.name for c in z.creatures]
                }
                for z in zones
            ]
        }
        return backup
    
    @staticmethod
    def fetch_tibia_data_creatures() -> Dict[str, Any]:
        """Fetch creature data from TibiaData API v4"""
        try:
            # Using TibiaData API v4 - /v4/creatures endpoint
            response = DatabaseSyncService._get_with_resilience(
                f"{DatabaseSyncService.TIBIA_DATA_URL}/creatures",
                headers={'User-Agent': 'TibiaWeeklyTasks/1.0'}
            )
            if response.status_code == 200:
                data = response.json()
                # TibiaData v4 structure: {"creatures": {"creature_list": [...]}}
                return {
                    "status": "success",
                    "source": "TibiaData",
                    "data": data,
                    "creature_count": len(data.get("creatures", {}).get("creature_list", []))
                }
            else:
                return {
                    "status": "error",
                    "source": "TibiaData",
                    "error": f"HTTP {response.status_code}"
                }
        except requests.exceptions.Timeout:
            return {
                "status": "error",
                "source": "TibiaData",
                "error": "Request timeout (>10s)"
            }
        except requests.exceptions.ConnectionError as e:
            return {
                "status": "error",
                "source": "TibiaData",
                "error": f"Connection failed: {str(e)[:100]}"
            }
        except Exception as e:
            return {
                "status": "error",
                "source": "TibiaData",
                "error": str(e)
            }
    
    @staticmethod
    def fetch_tibia_data_creature_detail(race: str) -> Dict[str, Any]:
        """Fetch detailed creature data from TibiaData API v4 - /v4/creature/{race}"""
        try:
            # Convert creature name to URL-safe format (lowercase, spaces to +)
            race_formatted = race.lower().replace(" ", "+")
            response = DatabaseSyncService._get_with_resilience(
                f"{DatabaseSyncService.TIBIA_DATA_URL}/creature/{race_formatted}",
                headers={'User-Agent': 'TibiaWeeklyTasks/1.0'}
            )
            if response.status_code == 200:
                data = response.json()
                # v4 structure: {"creature": {"name": "...", "hitpoints": ..., "experience": ...}}
                return {
                    "status": "success",
                    "source": "TibiaData",
                    "data": data
                }
            else:
                return {
                    "status": "error",
                    "source": "TibiaData",
                    "error": f"HTTP {response.status_code}"
                }
        except Exception as e:
            return {
                "status": "error",
                "source": "TibiaData",
                "error": str(e)
            }
    
    @staticmethod
    def fetch_tibia_wiki_creatures() -> Dict[str, Any]:
        """Fetch creature data from TibiaWiki (Fandom) MediaWiki API"""
        try:
            response = DatabaseSyncService._get_with_resilience(
                DatabaseSyncService.TIBIA_WIKI_URL,
                params={
                    "action": "query",
                    "format": "json",
                    "list": "categorymembers",
                    "cmtitle": "Category:Creatures",
                    "cmlimit": 100
                },
                headers={'User-Agent': 'TibiaWeeklyTasks/1.0'}
            )
            if response.status_code == 200:
                data = response.json()
                creatures = data.get("query", {}).get("categorymembers", [])
                return {
                    "status": "success",
                    "source": "TibiaWiki",
                    "data": data,
                    "creature_count": len(creatures)
                }
            else:
                return {
                    "status": "error",
                    "source": "TibiaWiki",
                    "error": f"HTTP {response.status_code}"
                }
        except requests.exceptions.Timeout:
            return {
                "status": "error",
                "source": "TibiaWiki",
                "error": "Request timeout (>10s)"
            }
        except requests.exceptions.ConnectionError as e:
            return {
                "status": "error",
                "source": "TibiaWiki",
                "error": f"Connection failed: {str(e)[:100]}"
            }
        except Exception as e:
            return {
                "status": "error",
                "source": "TibiaWiki",
                "error": str(e)
            }
    
    @staticmethod
    def compare_creature_data(existing: Creature, api_data: Dict) -> Dict[str, Any]:
        """Compare existing creature with API data to detect changes"""
        changes = {}
        
        # Campos a comparar
        fields_to_check = {
            "health": "health",
            "experience": "experience",
            "armor": "armor",
            "description": "description"
        }
        
        for field, api_field in fields_to_check.items():
            existing_val = getattr(existing, field, None)
            api_val = api_data.get(api_field)
            
            if existing_val != api_val and api_val is not None:
                changes[field] = {
                    "old": existing_val,
                    "new": api_val
                }
        
        return changes
    
    @staticmethod
    def sync_with_external_apis(db: Session) -> Dict[str, Any]:
        """Main sync function - returns tracker with pending changes"""
        tracker = DataChangeTracker()
        
        # 1. Backup existing data
        backup = DatabaseSyncService.backup_creatures(db)
        
        # 2. Fetch from external APIs
        tibia_data = DatabaseSyncService.fetch_tibia_data_creatures()
        tibia_wiki = DatabaseSyncService.fetch_tibia_wiki_creatures()
        
        # 3. Process TibiaData creatures (v4 API structure)
        if tibia_data["status"] == "success":
            # TibiaData v4: {"creatures": {"creature_list": [{"name": "...", "race": "..."}]}}
            creatures_list = tibia_data.get("data", {}).get("creatures", {}).get("creature_list", [])
            
            for api_creature in creatures_list[:10]:  # Limit to 10 for testing
                creature_name = api_creature.get("name")
                
                if not creature_name:
                    continue
                
                # Check if creature exists locally
                existing = db.query(Creature).filter_by(name=creature_name).first()
                
                if existing:
                    # Check for changes
                    changes = DatabaseSyncService.compare_creature_data(existing, api_creature)
                    if changes:
                        tracker.add_change(
                            change_type="creature",
                            source_api="TibiaData",
                            entity=creature_name,
                            entity_id=existing.id,
                            old_data={k: v["old"] for k, v in changes.items()},
                            new_data={k: v["new"] for k, v in changes.items()},
                            action="update"
                        )
                else:
                    # New creature
                    tracker.add_change(
                        change_type="creature",
                        source_api="TibiaData",
                        entity=creature_name,
                        entity_id=0,
                        new_data=api_creature,
                        action="create"
                    )
        
        # 4. Process TibiaWiki creatures
        if tibia_wiki["status"] == "success":
            wiki_creatures = tibia_wiki.get("data", {}).get("query", {}).get("categorymembers", [])
            
            for wiki_creature in wiki_creatures[:5]:  # Limit to 5 for testing
                creature_name = wiki_creature.get("title")
                
                if not creature_name:
                    continue
                
                # Check if creature exists locally
                existing = db.query(Creature).filter_by(name=creature_name).first()
                
                if not existing:
                    # New creature from wiki
                    tracker.add_change(
                        change_type="creature",
                        source_api="TibiaWiki",
                        entity=creature_name,
                        entity_id=0,
                        new_data={"name": creature_name, "source": "wiki"},
                        action="create"
                    )
        
        return {
            "backup_created": backup is not None,
            "backup_timestamp": backup.get("timestamp"),
            "tracked_changes": tracker.to_dict(),
            "sources": ["TibiaData", "TibiaWiki"],
            "total_pending_approvals": len(tracker.get_pending_changes())
        }
    
    @staticmethod
    def apply_approved_changes(db: Session, changes_indices: List[int], tracker_data: Dict) -> Dict[str, Any]:
        """Apply approved changes to the database"""
        applied = 0
        failed = 0
        
        changes = tracker_data.get("changes", [])
        for idx in changes_indices:
            if idx >= len(changes):
                continue
            
            change = changes[idx]
            try:
                if change["action"] == "create":
                    # Create new creature
                    if change.get("change_type") == "creature":
                        new_data = change.get("new_data", {})
                        
                        creature = Creature(
                            name=new_data.get("name"),
                            health=new_data.get("health", 0),
                            experience=new_data.get("experience", 0),
                            armor=new_data.get("armor", 0),
                            description=new_data.get("description", ""),
                            level=new_data.get("level", 1),
                            type=new_data.get("type", ""),
                            max_damage=new_data.get("max_damage", 0),
                            immunities=json.dumps(new_data.get("immunities", [])),
                            resistances=json.dumps(new_data.get("resistances", [])),
                            loot=json.dumps(new_data.get("loot", [])),
                            abilities=json.dumps(new_data.get("abilities", []))
                        )
                        db.add(creature)
                        db.commit()
                        applied += 1
                        
                elif change["action"] == "update":
                    # Update existing creature
                    if change.get("change_type") == "creature":
                        creature = db.query(Creature).filter_by(id=change.get("entity_id")).first()
                        if creature:
                            new_data = change.get("new_data", {})
                            
                            if "health" in new_data:
                                creature.health = new_data["health"]
                            if "experience" in new_data:
                                creature.experience = new_data["experience"]
                            if "armor" in new_data:
                                creature.armor = new_data["armor"]
                            if "description" in new_data:
                                creature.description = new_data["description"]
                            if "loot" in new_data:
                                creature.loot = json.dumps(new_data["loot"])
                            
                            db.commit()
                            applied += 1
                
            except Exception as e:
                db.rollback()
                failed += 1
        
        return {
            "applied": applied,
            "failed": failed,
            "total_requested": len(changes_indices)
        }
    
    @staticmethod
    def restore_from_backup(db: Session, backup_data: Dict) -> Dict[str, Any]:
        """Restore database from backup"""
        try:
            creatures_list = backup_data.get("creatures", [])
            zones_list = backup_data.get("zones", [])
            
            # Delete current creatures
            db.query(Creature).delete()
            
            # Restore creatures from backup
            creatures_restored = 0
            for creature_data in creatures_list:
                try:
                    creature = Creature(
                        name=creature_data.get("name"),
                        health=creature_data.get("health", 0),
                        experience=creature_data.get("experience", 0),
                        armor=creature_data.get("armor", 0),
                        description=creature_data.get("description", ""),
                        level=creature_data.get("level", 1),
                        type=creature_data.get("type", ""),
                        max_damage=creature_data.get("max_damage", 0),
                        immunities=creature_data.get("immunities", "[]"),
                        resistances=creature_data.get("resistances", "[]"),
                        loot=creature_data.get("loot", "[]"),
                        abilities=creature_data.get("abilities", "[]")
                    )
                    db.add(creature)
                    creatures_restored += 1
                except Exception:
                    continue
            
            # Restore zones
            zones_restored = len(zones_list)
            for zone_data in zones_list:
                try:
                    zone = HuntZone(
                        name=zone_data.get("name"),
                        level_min=zone_data.get("level_min", 1),
                        level_max=zone_data.get("level_max", 999),
                        description=zone_data.get("description", ""),
                        creatures=zone_data.get("creatures", "[]")
                    )
                    db.add(zone)
                except Exception:
                    continue
            
            db.commit()
            
            return {
                "status": "success",
                "creatures_restored": creatures_restored,
                "zones_restored": zones_restored,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            db.rollback()
            return {
                "status": "error",
                "error": str(e)
            }
