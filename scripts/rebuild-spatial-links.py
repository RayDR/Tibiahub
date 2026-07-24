#!/usr/bin/env python3
"""Rebuild graph and entity-location links without changing coordinates."""

from __future__ import annotations

import argparse

from app.core.config import settings
from app.db.database import SessionLocal
from app.knowledge.models import KnowledgeRelationship, SpatialEntityLocationLink, SpatialMapPoint, SpatialMapRegion
from app.knowledge.services.graph import KnowledgeGraphService, RelationshipInput


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if settings.database_url.database != "tibiahub" or settings.database_url.get_backend_name() != "postgresql":
        raise SystemExit("Spatial link rebuild is restricted to the TibiaHub PostgreSQL database")
    counts = {"located_at": 0, "represented_by": 0, "entity_location_links": 0}
    with SessionLocal() as db:
        links = db.query(SpatialEntityLocationLink).filter_by(is_current=True).all()
        points = db.query(SpatialMapPoint).filter(SpatialMapPoint.is_current.is_(True), SpatialMapPoint.location_entity_id.isnot(None)).all()
        regions = db.query(SpatialMapRegion).filter(SpatialMapRegion.is_current.is_(True), SpatialMapRegion.location_entity_id.isnot(None)).all()
        relationships = db.query(KnowledgeRelationship).filter(
            KnowledgeRelationship.relationship_type_code.in_({
                "located_at", "occurs_at_location", "mission_occurs_at_location", "appears_in",
            }),
            KnowledgeRelationship.target_entity_id.isnot(None),
            KnowledgeRelationship.resolution_state == "resolved",
            KnowledgeRelationship.is_current.is_(True),
        ).all()
        counts["located_at"] = sum(link.location_entity_id is not None for link in links)
        counts["represented_by"] = len(points) + len(regions)
        representations = {}
        for row in [*points, *regions]:
            representations.setdefault(row.location_entity_id, []).append(row)
        missing = []
        for relationship in relationships:
            for representation in representations.get(relationship.target_entity_id, []):
                point_id = representation.id if isinstance(representation, SpatialMapPoint) else None
                region_id = representation.id if isinstance(representation, SpatialMapRegion) else None
                exists = db.query(SpatialEntityLocationLink.id).filter_by(
                    source_entity_id=relationship.source_entity_id,
                    location_entity_id=relationship.target_entity_id,
                    map_point_id=point_id,
                    map_region_id=region_id,
                    is_current=True,
                ).first()
                if exists is None:
                    missing.append((relationship, representation, point_id, region_id))
        counts["entity_location_links"] = len(missing)
        if args.execute:
            for link in links:
                if link.location_entity_id is None:
                    continue
                mutation = KnowledgeGraphService.upsert(db, RelationshipInput(
                    source_entity_id=link.source_entity_id, source_scope="spatial_location",
                    relationship_type="located_at", target_entity_id=link.location_entity_id,
                    resolution_state="resolved", confidence=link.confidence,
                    source_provider_id=link.source_provider_id,
                    source_context={"context": "spatial.rebuild"},
                ))
                link.graph_relationship_id = mutation.relationship.id
            for row in [*points, *regions]:
                KnowledgeGraphService.upsert(db, RelationshipInput(
                    source_entity_id=row.location_entity_id, source_scope="map_representation",
                    relationship_type="represented_by", target_entity_id=row.knowledge_entity_id,
                    resolution_state="resolved", confidence=row.confidence,
                    source_provider_id=row.source_provider_id,
                    source_context={"context": "spatial.rebuild"},
                ))
            for relationship, representation, point_id, region_id in missing:
                provider = representation.source_provider_id or relationship.source_provider_id
                db.add(SpatialEntityLocationLink(
                    source_entity_id=relationship.source_entity_id,
                    location_entity_id=relationship.target_entity_id,
                    map_point_id=point_id,
                    map_region_id=region_id,
                    graph_relationship_id=relationship.id,
                    external_id=f"graph:{relationship.id}:{representation.id}",
                    source_provider_id=provider,
                    source_reference="spatial-link-rebuild",
                    source_metadata={"relationship_type": relationship.relationship_type_code},
                    confidence=relationship.confidence,
                    verification_state="verified" if relationship.manual_override else "pending",
                ))
            db.commit()
    mode = "executed" if args.execute else "dry-run"
    print(
        f"Spatial link rebuild {mode}: located_at={counts['located_at']} "
        f"represented_by={counts['represented_by']} "
        f"entity_location_links={counts['entity_location_links']}"
    )


if __name__ == "__main__":
    main()
