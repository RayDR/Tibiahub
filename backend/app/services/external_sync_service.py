"""
Background synchronization service for external APIs
Handles syncing creatures, items, quests, hunting places to local database
"""
import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.external_data import Item, HuntingPlace, TibiaWikiQuest, APISync
from app.models.creature import Creature
from app.services.external_apis import (
    get_creatures, get_items, get_hunting_places, get_quests,
    APISource
)
from app.db.database import SessionLocal

logger = logging.getLogger(__name__)

class ExternalSyncService:
    """Handles synchronization of external APIs to local database"""
    
    @staticmethod
    async def sync_creatures(db: Session, mode: str = "auto") -> Dict[str, Any]:
        """Sync creatures from TibiaWiki API"""
        sync_log = APISync(
            api_name="creatures",
            endpoint="/tibiawiki/creatures",
            status="running",
            message="Starting creature sync..."
        )
        db.add(sync_log)
        db.commit()
        
        try:
            logger.info("Starting creatures synchronization...")
            
            # Fetch from external API
            response = await get_creatures(expand=True)
            sync_log.source = response.source.value
            
            if not response.success():
                sync_log.status = "error"
                sync_log.error_details = response.error
                db.commit()
                logger.error(f"Failed to fetch creatures: {response.error}")
                return {
                    "api": "creatures",
                    "status": "error",
                    "error": response.error,
                    "sync_id": sync_log.id
                }
            
            creatures_data = response.data if isinstance(response.data, list) else list(response.data.values()) if isinstance(response.data, dict) else []
            sync_log.total_items = len(creatures_data)
            db.commit()
            
            # Process and save to database
            created = 0
            updated = 0
            errors = 0
            
            for idx, creature_data in enumerate(creatures_data):
                try:
                    sync_log.processed_items = idx + 1
                    if (idx + 1) % 10 == 0:
                        db.commit()
                        logger.info(f"Processing creatures: {idx + 1}/{len(creatures_data)}")
                    
                    name = creature_data.get('name')
                    if not name:
                        continue
                    
                    # Check if creature exists
                    existing = db.query(Creature).filter(Creature.name == name).first()
                    
                    # Get required fields with defaults
                    hitpoints = creature_data.get('hitpoints') or creature_data.get('health') or 1
                    experience = creature_data.get('experience') or 0
                    armor = creature_data.get('armor') or 0
                    
                    if existing:
                        # Update
                        existing.experience = experience or existing.experience
                        existing.hitpoints = hitpoints or existing.hitpoints
                        existing.armor = armor or existing.armor
                        updated += 1
                    else:
                        # Create new
                        creature = Creature(
                            name=name,
                            hitpoints=hitpoints,
                            experience=experience,
                            armor=armor
                        )
                        db.add(creature)
                        created += 1
                
                except Exception as e:
                    errors += 1
                    sync_log.error_count = errors
                    logger.error(f"Error processing creature {creature_data.get('name')}: {str(e)}")
            
            db.commit()
            
            sync_log.status = "success"
            sync_log.completed_at = datetime.utcnow()
            sync_log.message = f"Created: {created}, Updated: {updated}, Errors: {errors}"
            db.commit()
            
            logger.info(f"✅ Creatures sync complete: Created={created}, Updated={updated}, Errors={errors}")
            
            return {
                "api": "creatures",
                "status": "success",
                "source": response.source.value,
                "created": created,
                "updated": updated,
                "errors": errors,
                "total": len(creatures_data),
                "sync_id": sync_log.id
            }
        
        except Exception as e:
            logger.error(f"❌ Creatures sync failed: {str(e)}")
            sync_log.status = "error"
            sync_log.error_details = str(e)
            sync_log.completed_at = datetime.utcnow()
            db.commit()
            return {
                "api": "creatures",
                "status": "error",
                "error": str(e),
                "sync_id": sync_log.id
            }
    
    @staticmethod
    async def sync_items(db: Session) -> Dict[str, Any]:
        """Sync items from TibiaWiki API"""
        sync_log = APISync(
            api_name="items",
            endpoint="/tibiawiki/items",
            status="running",
            message="Starting items sync..."
        )
        db.add(sync_log)
        db.commit()
        
        try:
            logger.info("Starting items synchronization...")
            
            response = await get_items(expand=True)
            sync_log.source = response.source.value
            
            if not response.success():
                sync_log.status = "error"
                sync_log.error_details = response.error
                db.commit()
                logger.error(f"Failed to fetch items: {response.error}")
                return {
                    "api": "items",
                    "status": "error",
                    "error": response.error,
                    "sync_id": sync_log.id
                }
            
            items_data = response.data
            sync_log.total_items = len(items_data)
            db.commit()
            
            created = 0
            updated = 0
            errors = 0
            
            for idx, item_data in enumerate(items_data):
                try:
                    sync_log.processed_items = idx + 1
                    if (idx + 1) % 10 == 0:
                        db.commit()
                        logger.info(f"Processing items: {idx + 1}/{len(items_data)}")
                    
                    name = item_data.get('name')
                    if not name:
                        continue
                    
                    existing = db.query(Item).filter(Item.name == name).first()
                    
                    if existing:
                        existing.item_id = item_data.get('id')
                        existing.description = item_data.get('description')
                        existing.type = item_data.get('type')
                        existing.weight = item_data.get('weight')
                        existing.value = item_data.get('value')
                        existing.attack = item_data.get('attack')
                        existing.defense = item_data.get('defense')
                        existing.armor = item_data.get('armor')
                        existing.level_required = item_data.get('levelrequired')
                        existing.vocation_required = item_data.get('vocationrequired')
                        existing.tradeable = item_data.get('tradeable', True)
                        existing.stackable = item_data.get('stackable', False)
                        existing.raw_data = item_data
                        updated += 1
                    else:
                        item = Item(
                            name=name,
                            item_id=item_data.get('id'),
                            description=item_data.get('description'),
                            type=item_data.get('type'),
                            weight=item_data.get('weight'),
                            value=item_data.get('value'),
                            attack=item_data.get('attack'),
                            defense=item_data.get('defense'),
                            armor=item_data.get('armor'),
                            level_required=item_data.get('levelrequired'),
                            vocation_required=item_data.get('vocationrequired'),
                            tradeable=item_data.get('tradeable', True),
                            stackable=item_data.get('stackable', False),
                            raw_data=item_data
                        )
                        db.add(item)
                        created += 1
                
                except Exception as e:
                    errors += 1
                    sync_log.error_count = errors
                    logger.error(f"Error processing item {item_data.get('name')}: {str(e)}")
            
            db.commit()
            
            sync_log.status = "success"
            sync_log.completed_at = datetime.utcnow()
            sync_log.message = f"Created: {created}, Updated: {updated}, Errors: {errors}"
            db.commit()
            
            logger.info(f"✅ Items sync complete: Created={created}, Updated={updated}, Errors={errors}")
            
            return {
                "api": "items",
                "status": "success",
                "source": response.source.value,
                "created": created,
                "updated": updated,
                "errors": errors,
                "total": len(items_data),
                "sync_id": sync_log.id
            }
        
        except Exception as e:
            logger.error(f"❌ Items sync failed: {str(e)}")
            sync_log.status = "error"
            sync_log.error_details = str(e)
            sync_log.completed_at = datetime.utcnow()
            db.commit()
            return {
                "api": "items",
                "status": "error",
                "error": str(e),
                "sync_id": sync_log.id
            }
    
    @staticmethod
    def get_sync_logs(db: Session, api_name: Optional[str] = None, limit: int = 100) -> list:
        """Get recent synchronization logs"""
        query = db.query(APISync)
        
        if api_name:
            query = query.filter(APISync.api_name == api_name)
        
        return query.order_by(desc(APISync.created_at)).limit(limit).all()
    
    @staticmethod
    def get_sync_stats(db: Session) -> Dict[str, Any]:
        """Get statistics about synced data"""
        return {
            "creatures": db.query(Creature).count(),
            "items": db.query(Item).count(),
            "hunting_places": db.query(HuntingPlace).count(),
            "quests": db.query(TibiaWikiQuest).count(),
            "sync_logs": db.query(APISync).count(),
        }
    
    @staticmethod
    async def check_creature_conflicts(db: Session) -> List[Dict[str, Any]]:
        """Check for conflicts before syncing creatures"""
        conflicts = []
        
        # Fetch new data
        response = await get_creatures(expand=True)
        if not response.success():
            return conflicts
        
        creatures_data = response.data if isinstance(response.data, list) else list(response.data.values()) if isinstance(response.data, dict) else []
        
        for creature_data in creatures_data:
            name = creature_data.get('name')
            if not name:
                continue
            
            # Check if exists
            existing = db.query(Creature).filter(Creature.name == name).first()
            if not existing:
                continue  # No conflict, it's new
            
            # Compare data
            comparisons = []
            hitpoints_new = creature_data.get('hitpoints') or creature_data.get('health') or existing.hitpoints
            experience_new = creature_data.get('experience') or existing.experience
            armor_new = creature_data.get('armor') or existing.armor
            
            if hitpoints_new != existing.hitpoints:
                comparisons.append({
                    "field": "hitpoints",
                    "old_value": existing.hitpoints,
                    "new_value": hitpoints_new,
                    "different": True
                })
            
            if experience_new != existing.experience:
                comparisons.append({
                    "field": "experience",
                    "old_value": existing.experience,
                    "new_value": experience_new,
                    "different": True
                })
            
            if armor_new != existing.armor:
                comparisons.append({
                    "field": "armor",
                    "old_value": existing.armor,
                    "new_value": armor_new,
                    "different": True
                })
            
            # Only add if there are actual differences
            if comparisons:
                conflicts.append({
                    "api_name": "creatures",
                    "item_name": name,
                    "conflicts": comparisons,
                    "action": "pending"
                })
        
        return conflicts
    
    @staticmethod
    async def resolve_conflicts(db: Session, conflicts: List[Dict[str, Any]], action: str) -> Dict[str, Any]:
        """
        Resolve conflicts by applying the chosen action
        action: 'skip_all' or 'overwrite_all'
        """
        applied = 0
        skipped = 0
        
        if action == "skip_all":
            # Don't do anything, just count
            skipped = len(conflicts)
            logger.info(f"Skipped {skipped} conflicts as requested")
        
        elif action == "overwrite_all":
            # Get fresh data and apply updates
            response = await get_creatures(expand=True)
            if not response.success():
                raise Exception("Failed to fetch creature data")
            
            creatures_data = response.data if isinstance(response.data, list) else list(response.data.values()) if isinstance(response.data, dict) else []
            creature_dict = {c.get('name'): c for c in creatures_data if c.get('name')}
            
            for conflict in conflicts:
                item_name = conflict.get("item_name")
                if not item_name or item_name not in creature_dict:
                    skipped += 1
                    continue
                
                creature_data = creature_dict[item_name]
                existing = db.query(Creature).filter(Creature.name == item_name).first()
                
                if existing:
                    # Apply updates
                    hitpoints = creature_data.get('hitpoints') or creature_data.get('health') or existing.hitpoints
                    experience = creature_data.get('experience') or existing.experience
                    armor = creature_data.get('armor') or existing.armor
                    
                    existing.hitpoints = hitpoints
                    existing.experience = experience
                    existing.armor = armor
                    applied += 1
            
            db.commit()
            logger.info(f"Applied updates to {applied} creatures")
        
        return {
            "applied": applied,
            "skipped": skipped
        }
