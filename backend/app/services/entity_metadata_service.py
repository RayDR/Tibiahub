"""Local metadata management for featured and most-searched entities."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from app.models.entity_metadata import EntityMetadata
from app.services.text_utils import normalize_search_text


class EntityMetadataService:
    @staticmethod
    def ensure_record(
        db: Session,
        *,
        entity_type: str,
        entity_key: str,
        display_name: str,
        entity_id: Optional[int] = None,
    ) -> EntityMetadata:
        normalized_key = normalize_search_text(entity_key)
        record = (
            db.query(EntityMetadata)
            .filter(EntityMetadata.entity_type == entity_type, EntityMetadata.entity_key == normalized_key)
            .first()
        )
        if not record:
            record = EntityMetadata(
                entity_type=entity_type,
                entity_key=normalized_key,
                display_name=display_name,
                entity_id=entity_id,
            )
            db.add(record)
            db.flush()
        else:
            record.display_name = display_name
            if entity_id is not None:
                record.entity_id = entity_id
        return record

    @staticmethod
    def update_sync_timestamp(db: Session, *, entity_type: str, entity_key: str, display_name: str, entity_id: Optional[int] = None) -> None:
        record = EntityMetadataService.ensure_record(
            db,
            entity_type=entity_type,
            entity_key=entity_key,
            display_name=display_name,
            entity_id=entity_id,
        )
        record.last_synced_at = datetime.now(UTC)

    @staticmethod
    def record_searches(
        db: Session,
        *,
        entity_type: str,
        matches: Iterable[tuple[str, str, Optional[int]]],
        increment: int = 1,
    ) -> None:
        for entity_key, display_name, entity_id in matches:
            record = EntityMetadataService.ensure_record(
                db,
                entity_type=entity_type,
                entity_key=entity_key,
                display_name=display_name,
                entity_id=entity_id,
            )
            record.search_count = max(0, (record.search_count or 0) + increment)
            record.last_viewed_at = datetime.now(UTC)

    @staticmethod
    def set_flags(
        db: Session,
        *,
        entity_type: str,
        entity_key: str,
        display_name: str,
        entity_id: Optional[int] = None,
        is_featured: Optional[bool] = None,
        is_pinned: Optional[bool] = None,
        is_favorite: Optional[bool] = None,
        notes: Optional[str] = None,
    ) -> EntityMetadata:
        record = EntityMetadataService.ensure_record(
            db,
            entity_type=entity_type,
            entity_key=entity_key,
            display_name=display_name,
            entity_id=entity_id,
        )
        if is_featured is not None:
            record.is_featured = is_featured
        if is_pinned is not None:
            record.is_pinned = is_pinned
        if is_favorite is not None:
            record.is_favorite = is_favorite
        if notes is not None:
            record.notes = notes
        record.updated_at = datetime.now(UTC)
        db.flush()
        return record

    @staticmethod
    def get_highlights(db: Session, *, entity_type: str, limit: int = 12) -> list[EntityMetadata]:
        return (
            db.query(EntityMetadata)
            .filter(EntityMetadata.entity_type == entity_type)
            .order_by(
                EntityMetadata.is_pinned.desc(),
                EntityMetadata.is_featured.desc(),
                EntityMetadata.is_favorite.desc(),
                EntityMetadata.search_count.desc(),
                EntityMetadata.updated_at.desc(),
            )
            .limit(limit)
            .all()
        )
