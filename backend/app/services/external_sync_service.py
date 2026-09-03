"""Synchronization service for external APIs with local metadata preservation."""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.creature import Creature
from app.models.external_data import APISync, Item, TibiaWikiQuest
from app.models.hunt_zone import HuntZone
from app.services.bestiary_source import BestiarySourceError
from app.services.creature_storage_service import upsert_creature_payload
from app.services.entity_metadata_service import EntityMetadataService
from app.services.external_apis import get_creatures, get_items, get_quests
from app.services.text_utils import normalize_search_text

logger = logging.getLogger(__name__)


class ExternalSyncService:
    """Handles synchronization of external APIs to the local database."""

    @staticmethod
    def _start_sync_log(db: Session, *, api_name: str, endpoint: str) -> APISync:
        sync_log = APISync(api_name=api_name, endpoint=endpoint, status="running", message=f"Starting {api_name} sync")
        db.add(sync_log)
        db.commit()
        db.refresh(sync_log)
        return sync_log

    @staticmethod
    def _finish_sync_log(sync_log: APISync, *, status: str, message: str, error: Optional[str] = None) -> None:
        sync_log.status = status
        sync_log.message = message
        sync_log.error_details = error
        sync_log.completed_at = datetime.now(UTC)

    @staticmethod
    async def sync_creatures(db: Session, mode: str = "auto") -> Dict[str, Any]:
        sync_log = ExternalSyncService._start_sync_log(db, api_name="creatures", endpoint="/external/creatures")
        try:
            response = await get_creatures(expand=True)
            sync_log.source = response.source.value
            if not response.success():
                ExternalSyncService._finish_sync_log(sync_log, status="error", message="Creature sync failed", error=response.error)
                db.commit()
                return {"api": "creatures", "status": "error", "error": response.error, "sync_id": sync_log.id}

            payloads = response.data if isinstance(response.data, list) else []
            sync_log.total_items = len(payloads)
            created = 0
            updated = 0
            for index, payload in enumerate(payloads, start=1):
                existing = db.query(Creature).filter(Creature.normalized_name == normalize_search_text(payload.get("name"))).first()
                upsert_creature_payload(db, payload)
                if existing:
                    updated += 1
                else:
                    created += 1
                sync_log.processed_items = index
            db.commit()
            ExternalSyncService._finish_sync_log(sync_log, status="success", message=f"Created: {created}, Updated: {updated}, Errors: 0")
            db.commit()
            return {
                "api": "creatures",
                "status": "success",
                "source": response.source.value,
                "created": created,
                "updated": updated,
                "errors": 0,
                "total": len(payloads),
                "sync_id": sync_log.id,
                "message": sync_log.message,
            }
        except Exception as exc:
            logger.exception("creature_sync_failed error=%s", exc)
            ExternalSyncService._finish_sync_log(sync_log, status="error", message="Creature sync failed", error=str(exc))
            db.commit()
            return {"api": "creatures", "status": "error", "error": str(exc), "sync_id": sync_log.id, "message": sync_log.message}

    @staticmethod
    async def sync_items(db: Session) -> Dict[str, Any]:
        sync_log = ExternalSyncService._start_sync_log(db, api_name="items", endpoint="/external/items")
        try:
            response = await get_items(expand=True)
            sync_log.source = response.source.value
            if not response.success():
                ExternalSyncService._finish_sync_log(sync_log, status="error", message="Item sync failed", error=response.error)
                db.commit()
                return {"api": "items", "status": "error", "error": response.error, "sync_id": sync_log.id}

            items_data = response.data or []
            sync_log.total_items = len(items_data)
            created = 0
            updated = 0
            for index, item_data in enumerate(items_data, start=1):
                name = item_data.get("name")
                if not name:
                    continue
                existing = db.query(Item).filter(Item.name == name).first()
                if not existing:
                    existing = Item(name=name)
                    db.add(existing)
                    created += 1
                else:
                    updated += 1
                existing.item_id = item_data.get("item_id") or existing.item_id
                existing.description = item_data.get("description") or existing.description
                existing.type = item_data.get("type") or existing.type
                existing.weight = item_data.get("weight") if item_data.get("weight") is not None else existing.weight
                existing.value = item_data.get("value") if item_data.get("value") is not None else existing.value
                existing.attack = item_data.get("attack") if item_data.get("attack") is not None else existing.attack
                existing.defense = item_data.get("defense") if item_data.get("defense") is not None else existing.defense
                existing.armor = item_data.get("armor") if item_data.get("armor") is not None else existing.armor
                existing.level_required = item_data.get("levelrequired") if item_data.get("levelrequired") is not None else existing.level_required
                existing.vocation_required = item_data.get("vocationrequired") or existing.vocation_required
                existing.tradeable = item_data.get("tradeable", existing.tradeable)
                existing.stackable = item_data.get("stackable", existing.stackable)
                existing.raw_data = item_data
                existing.updated_at = datetime.now(UTC)
                EntityMetadataService.update_sync_timestamp(db, entity_type="item", entity_key=name, display_name=name)
                sync_log.processed_items = index
            db.commit()
            ExternalSyncService._finish_sync_log(sync_log, status="success", message=f"Created: {created}, Updated: {updated}, Errors: 0")
            db.commit()
            return {
                "api": "items",
                "status": "success",
                "source": response.source.value,
                "created": created,
                "updated": updated,
                "errors": 0,
                "total": len(items_data),
                "sync_id": sync_log.id,
                "message": sync_log.message,
            }
        except Exception as exc:
            logger.exception("item_sync_failed error=%s", exc)
            ExternalSyncService._finish_sync_log(sync_log, status="error", message="Item sync failed", error=str(exc))
            db.commit()
            return {"api": "items", "status": "error", "error": str(exc), "sync_id": sync_log.id, "message": sync_log.message}

    @staticmethod
    async def sync_hunting_places(db: Session) -> Dict[str, Any]:
        """Retain the legacy callable without bypassing canonical Knowledge ingestion."""

        _ = db
        return {
            "api": "hunting_places",
            "status": "deprecated",
            "created": 0,
            "updated": 0,
            "errors": 0,
            "total": 0,
            "source": "tibiawiki",
            "reason": "Use the durable tibiawiki hunt_zone_catalog Knowledge job",
        }

    @staticmethod
    async def sync_quests(db: Session) -> Dict[str, Any]:
        sync_log = ExternalSyncService._start_sync_log(db, api_name="quests", endpoint="/external/quests")
        try:
            response = await get_quests(expand=True)
            sync_log.source = response.source.value
            if not response.success():
                ExternalSyncService._finish_sync_log(sync_log, status="error", message="Quest sync failed", error=response.error)
                db.commit()
                return {"api": "quests", "status": "error", "error": response.error, "sync_id": sync_log.id}

            quests_data = response.data or []
            sync_log.total_items = len(quests_data)
            created = 0
            updated = 0
            for index, quest in enumerate(quests_data, start=1):
                name = quest.get("name")
                if not name:
                    continue
                existing = db.query(TibiaWikiQuest).filter(TibiaWikiQuest.name == name).first()
                if not existing:
                    existing = TibiaWikiQuest(name=name)
                    db.add(existing)
                    created += 1
                else:
                    updated += 1
                existing.description = quest.get("description") or existing.description
                existing.min_level = quest.get("min_level") if quest.get("min_level") is not None else existing.min_level
                existing.max_level = quest.get("max_level") if quest.get("max_level") is not None else existing.max_level
                existing.experience_reward = quest.get("experience_reward") if quest.get("experience_reward") is not None else existing.experience_reward
                existing.treasure = quest.get("treasure") or existing.treasure
                existing.location = quest.get("location") or existing.location
                existing.npc = quest.get("npc") or existing.npc
                existing.raw_data = quest
                sync_log.processed_items = index
            db.commit()
            ExternalSyncService._finish_sync_log(sync_log, status="success", message=f"Created: {created}, Updated: {updated}, Errors: 0")
            db.commit()
            return {
                "api": "quests",
                "status": "success",
                "source": response.source.value,
                "created": created,
                "updated": updated,
                "errors": 0,
                "total": len(quests_data),
                "sync_id": sync_log.id,
                "message": sync_log.message,
            }
        except Exception as exc:
            logger.exception("quest_sync_failed error=%s", exc)
            ExternalSyncService._finish_sync_log(sync_log, status="error", message="Quest sync failed", error=str(exc))
            db.commit()
            return {"api": "quests", "status": "error", "error": str(exc), "sync_id": sync_log.id, "message": sync_log.message}

    @staticmethod
    def get_sync_logs(db: Session, api_name: Optional[str] = None, limit: int = 100) -> list[APISync]:
        query = db.query(APISync)
        if api_name:
            query = query.filter(APISync.api_name == api_name)
        return query.order_by(desc(APISync.created_at)).limit(limit).all()

    @staticmethod
    def get_sync_stats(db: Session) -> Dict[str, Any]:
        return {
            "creatures": db.query(Creature).count(),
            "items": db.query(Item).count(),
            "hunting_places": db.query(HuntZone).count(),
            "quests": db.query(TibiaWikiQuest).count(),
            "sync_logs": db.query(APISync).count(),
        }

    @staticmethod
    async def check_creature_conflicts(db: Session) -> List[Dict[str, Any]]:
        response = await get_creatures(expand=True)
        if not response.success():
            return []
        conflicts = []
        for payload in response.data or []:
            existing = db.query(Creature).filter(Creature.normalized_name == normalize_search_text(payload.get("name"))).first()
            if not existing:
                continue
            changed_fields = []
            for field in ["hitpoints", "experience", "armor", "description", "behavior"]:
                new_value = payload.get(field)
                old_value = getattr(existing, field, None)
                if new_value not in (None, "") and new_value != old_value:
                    changed_fields.append({"field": field, "old_value": old_value, "new_value": new_value, "different": True})
            if changed_fields:
                conflicts.append({"api_name": "creatures", "item_name": existing.name, "conflicts": changed_fields, "action": "pending"})
        return conflicts

    @staticmethod
    async def resolve_conflicts(db: Session, conflicts: List[Dict[str, Any]], action: str) -> Dict[str, Any]:
        if action != "overwrite_all":
            return {"applied": 0, "skipped": len(conflicts)}
        response = await get_creatures(expand=True)
        if not response.success():
            raise BestiarySourceError(response.error or "Failed to fetch creature data")
        payload_by_name = {normalize_search_text(item.get("name")): item for item in response.data or [] if item.get("name")}
        applied = 0
        skipped = 0
        for conflict in conflicts:
            key = normalize_search_text(conflict.get("item_name"))
            payload = payload_by_name.get(key)
            if not payload:
                skipped += 1
                continue
            upsert_creature_payload(db, payload)
            applied += 1
        db.commit()
        return {"applied": applied, "skipped": skipped}
