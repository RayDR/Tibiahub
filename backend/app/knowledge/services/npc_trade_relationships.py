"""Exact, provenance-preserving Item/NPC trade relationship normalization."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.knowledge.dto import ItemNpcReference
from app.knowledge.indexing import normalize_name
from app.knowledge.models import KnowledgeEntity, KnowledgeEntityAlias, KnowledgeSearchMetadata
from app.knowledge.services.graph import KnowledgeGraphService, RelationshipInput


def _npc_candidates_by_name(
    db: Session,
    names: set[str],
) -> dict[str, list[KnowledgeEntity]]:
    normalized_names = {normalize_name(name) for name in names if normalize_name(name)}
    result: dict[str, dict[UUID, KnowledgeEntity]] = {
        name: {} for name in normalized_names
    }
    if not normalized_names:
        return {}
    for entity, normalized in (
        db.query(KnowledgeEntity, KnowledgeSearchMetadata.normalized_name)
        .join(KnowledgeSearchMetadata, KnowledgeSearchMetadata.entity_uuid == KnowledgeEntity.uuid)
        .filter(
            KnowledgeEntity.entity_type == "npc",
            KnowledgeEntity.status == "active",
            KnowledgeSearchMetadata.normalized_name.in_(normalized_names),
        )
    ):
        result[normalized][entity.uuid] = entity
    for entity, normalized in (
        db.query(KnowledgeEntity, KnowledgeEntityAlias.normalized_alias)
        .join(KnowledgeEntityAlias, KnowledgeEntityAlias.entity_uuid == KnowledgeEntity.uuid)
        .filter(
            KnowledgeEntity.entity_type == "npc",
            KnowledgeEntityAlias.entity_type == "npc",
            KnowledgeEntityAlias.normalized_alias.in_(normalized_names),
        )
    ):
        result[normalized][entity.uuid] = entity
    return {name: list(matches.values()) for name, matches in result.items()}


def link_item_npc_trade(
    db: Session,
    *,
    item_entity_uuid: UUID,
    buy_from: tuple[ItemNpcReference, ...],
    sell_to: tuple[ItemNpcReference, ...],
    provider_id: str,
    source_document_id: str,
) -> dict[str, int]:
    """Store Item-source facts; graph inversion exposes them from the NPC side.

    ``buy_from`` means the player buys the Item from the NPC, so the Item is
    ``sold_by_npc``. ``sell_to`` means the NPC buys the Item from the player,
    so the Item is ``bought_by_npc``.
    """
    definitions = (
        ("sold_by_npc", "trade:sold_by_npc", buy_from, "npc_sells_to_player"),
        ("bought_by_npc", "trade:bought_by_npc", sell_to, "npc_buys_from_player"),
    )
    names = {
        reference.name.strip()
        for _relationship, _scope, references, _semantic in definitions
        for reference in references
        if reference.name.strip()
    }
    candidate_index = _npc_candidates_by_name(db, names)
    metrics = {"source": 0, "resolved": 0, "unresolved": 0, "ambiguous": 0, "created": 0}
    for relationship_type, scope, references, semantic in definitions:
        current_ids: set[UUID] = set()
        grouped: dict[str, list[ItemNpcReference]] = {}
        for reference in references:
            normalized = normalize_name(reference.name)
            if normalized:
                grouped.setdefault(normalized, []).append(reference)
        for normalized, evidence in grouped.items():
            name = evidence[0].name.strip()
            matches = candidate_index.get(normalized, [])
            target = matches[0] if len(matches) == 1 else None
            state = "resolved" if target else "ambiguous" if len(matches) > 1 else "unresolved"
            offers: list[dict] = []
            for reference in evidence:
                offer = {
                    "price": reference.price,
                    "currency": reference.currency,
                    "location": reference.location,
                    "qualifier": reference.qualifier,
                }
                if offer not in offers:
                    offers.append(offer)
            only_offer = offers[0] if len(offers) == 1 else {}
            mutation = KnowledgeGraphService.upsert(db, RelationshipInput(
                source_entity_id=item_entity_uuid,
                source_scope=scope,
                relationship_type=relationship_type,
                target_entity_id=target.uuid if target else None,
                target_entity_type="npc",
                unresolved_name=None if target else name,
                resolution_state=state,
                confidence="high",
                source_provider_id=provider_id,
                source_document_ref=source_document_id,
                source_context={
                    "semantic": semantic,
                    "price": only_offer.get("price"),
                    "currency": only_offer.get("currency"),
                    "location": only_offer.get("location"),
                    "qualifier": only_offer.get("qualifier"),
                    "offers": offers,
                    "resolution_policy": "exact_name_or_alias_only",
                    "candidate_entity_ids": [str(match.uuid) for match in matches]
                    if len(matches) > 1 else [],
                },
            ))
            current_ids.add(mutation.relationship.id)
            metrics["source"] += len(evidence)
            metrics[state] += 1
            metrics["created"] += int(mutation.created)
        KnowledgeGraphService.reconcile_provider(
            db,
            source_entity_id=item_entity_uuid,
            source_scope=scope,
            provider_id=provider_id,
            relationship_types={relationship_type},
            current_ids=current_ids,
        )
    return metrics
