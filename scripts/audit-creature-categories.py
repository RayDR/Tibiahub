#!/usr/bin/env python3

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.db.database import SessionLocal, verify_connection_and_schema
from app.knowledge.models import KnowledgeDocument
from app.models import Creature
from app.services.creature_category_service import (
    CANONICAL_CREATURE_CATEGORIES,
    resolve_creature_category,
)


def clean(value) -> str:
    value = str(value or "").strip()
    return value or "<missing>"


def print_counter(title: str, counter: Counter, limit: int = 25) -> None:
    print()
    print(f"=== {title} ===")

    if not counter:
        print("<none>")
        return

    for value, count in counter.most_common(limit):
        print(f"{count:5}  {value}")


def main() -> None:
    verify_connection_and_schema()

    with SessionLocal() as db:
        rows = (
            db.query(Creature)
            .filter(
                Creature.is_hidden == False,
                Creature.is_boss == False,
            )
            .order_by(Creature.id)
            .all()
        )

        category_counts = Counter()
        unresolved = []

        for row in rows:
            category = resolve_creature_category(
                bestiary_class=row.bestiary_class,
                creature_class=row.creature_class,
                classification=row.classification,
            )

            if category is None:
                unresolved.append(row)
            else:
                category_counts[category] += 1

        total = len(rows)
        categorized = sum(category_counts.values())

        linked_entity_ids = {
            row.knowledge_entity_id
            for row in unresolved
            if row.knowledge_entity_id is not None
        }

        document_entity_ids = set()

        if linked_entity_ids:
            document_entity_ids = {
                entity_uuid
                for (entity_uuid,) in (
                    db.query(KnowledgeDocument.entity_uuid)
                    .filter(
                        KnowledgeDocument.provider_id == "tibiawiki",
                        KnowledgeDocument.entity_uuid.in_(
                            linked_entity_ids
                        ),
                    )
                    .distinct()
                    .all()
                )
                if entity_uuid is not None
            }

        with_document = sum(
            1
            for row in unresolved
            if row.knowledge_entity_id in document_entity_ids
        )

        linked_without_document = sum(
            1
            for row in unresolved
            if (
                row.knowledge_entity_id is not None
                and row.knowledge_entity_id
                not in document_entity_ids
            )
        )

        no_entity_link = sum(
            1
            for row in unresolved
            if row.knowledge_entity_id is None
        )

        print("=== SUMMARY ===")
        print(f"visible_non_boss_total={total}")
        print(f"categorized={categorized}")
        print(f"unresolved={len(unresolved)}")
        print(
            "coverage_percent="
            f"{(categorized / total * 100) if total else 0:.2f}"
        )
        print(
            f"unresolved_with_tibiawiki_document={with_document}"
        )
        print(
            "unresolved_linked_without_tibiawiki_document="
            f"{linked_without_document}"
        )
        print(
            f"unresolved_without_knowledge_entity={no_entity_link}"
        )

        print()
        print("=== CATEGORY COUNTS ===")

        for category in CANONICAL_CREATURE_CATEGORIES:
            print(
                f"{category_counts[category]:5}  {category}"
            )

        print_counter(
            "UNRESOLVED CREATURE CLASS",
            Counter(
                clean(row.creature_class)
                for row in unresolved
            ),
        )

        print_counter(
            "UNRESOLVED CLASSIFICATION",
            Counter(
                clean(row.classification)
                for row in unresolved
            ),
        )

        print_counter(
            "UNRESOLVED BESTIARY CLASS",
            Counter(
                clean(row.bestiary_class)
                for row in unresolved
            ),
        )

        print_counter(
            "UNRESOLVED SOURCE",
            Counter(
                clean(row.source_name)
                for row in unresolved
            ),
        )

        print_counter(
            "UNRESOLVED COMBINATIONS",
            Counter(
                (
                    f"bestiary={clean(row.bestiary_class)} | "
                    f"class={clean(row.creature_class)} | "
                    f"classification={clean(row.classification)}"
                )
                for row in unresolved
            ),
            limit=40,
        )

        print()
        print("=== UNRESOLVED SAMPLE ===")

        for row in unresolved[:50]:
            has_document = (
                row.knowledge_entity_id
                in document_entity_ids
            )

            print(
                f"id={row.id} "
                f"name={row.name!r} "
                f"bestiary={clean(row.bestiary_class)!r} "
                f"class={clean(row.creature_class)!r} "
                f"classification={clean(row.classification)!r} "
                f"knowledge_entity="
                f"{row.knowledge_entity_id or '<missing>'} "
                f"stored_document={has_document}"
            )


if __name__ == "__main__":
    main()
