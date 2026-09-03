"""Resumable historical replay for Item-backed NPC trade evidence."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.knowledge.adapters import (
    KnowledgeDocumentDTO,
    KnowledgeNormalizationContext,
    TibiaWikiItemAdapter,
)
from app.knowledge.models import KnowledgeDocument
from app.knowledge.services.normalization import KnowledgeNormalizationService
from app.models import Item


@dataclass(frozen=True, slots=True)
class NpcTradeRepairBatch:
    processed_items: int
    skipped_items: int
    next_item_id: int | None
    has_more: bool


class NpcTradeRelationshipRepairService:
    """Replay only Item rows that already retain explicit provider trade evidence.

    Normal Item detail ingestion remains the production path. This service is
    the bounded, resumable historical path for immutable documents imported
    before trade graph normalization existed.
    """

    @staticmethod
    def run_batch(
        db: Session,
        *,
        after_item_id: int = 0,
        limit: int = 100,
    ) -> NpcTradeRepairBatch:
        if after_item_id < 0 or not 1 <= limit <= 500:
            raise ValueError("NPC trade repair batches require a nonnegative cursor and 1 to 500 items")

        rows = (
            db.query(Item)
            .filter(
                Item.id > after_item_id,
                Item.knowledge_entity_id.isnot(None),
                Item.external_id.isnot(None),
                or_(Item.buy_from != [], Item.sell_to != []),
            )
            .order_by(Item.id)
            .limit(limit + 1)
            .all()
        )
        has_more = len(rows) > limit
        selected = rows[:limit]
        if not selected:
            return NpcTradeRepairBatch(0, 0, None, False)

        refs = {f"item:{row.external_id}" for row in selected}
        documents = (
            db.query(KnowledgeDocument)
            .filter(
                KnowledgeDocument.provider_id == "tibiawiki",
                KnowledgeDocument.provider_document_id.in_(refs),
            )
            .order_by(
                KnowledgeDocument.provider_document_id,
                KnowledgeDocument.retrieved_at.desc(),
            )
            .all()
        )
        latest: dict[str, KnowledgeDocument] = {}
        for document in documents:
            latest.setdefault(document.provider_document_id, document)

        adapter = TibiaWikiItemAdapter()
        processed = skipped = 0
        for item in selected:
            document = latest.get(f"item:{item.external_id}")
            if document is None:
                skipped += 1
                continue
            dto = KnowledgeDocumentDTO(
                provider_code=document.provider_id,
                provider_document_id=document.provider_document_id,
                raw_json=document.raw_json,
                version=document.version,
                etag=document.etag,
                language=document.language,
                metadata={
                    **dict(document.document_metadata or {}),
                    "document_kind": "item_detail",
                    "normalization_mode": "renormalize",
                },
            )
            normalization = adapter.normalize(
                dto,
                KnowledgeNormalizationContext(
                    job_id=UUID(int=0),
                    attempt_id=UUID(int=0),
                    correlation_id=UUID(int=0),
                    provider_code="tibiawiki",
                    entity_type="item",
                ),
            )
            if normalization.action == "noop":
                skipped += 1
                continue
            KnowledgeNormalizationService.apply(db, normalization)
            processed += 1

        db.flush()
        return NpcTradeRepairBatch(
            processed_items=processed,
            skipped_items=skipped,
            next_item_id=selected[-1].id,
            has_more=has_more,
        )
