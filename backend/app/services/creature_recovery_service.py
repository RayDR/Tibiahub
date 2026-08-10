"""Targeted recovery helpers for Cyclopedia creature data gaps."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.knowledge.models import KnowledgeDocument
from app.knowledge.services.jobs import (
    EnqueueKnowledgeJob,
    KnowledgeJobService,
)
from app.models import Creature, Loot
from app.services.creature_category_service import (
    resolve_creature_category,
)
from app.services.creature_source_policy import (
    is_non_creature_catalog_title,
)
from app.services.text_utils import normalize_search_text


AMOUNT_TOKEN_RE = re.compile(
    r"^\d+(?:\s*-\s*(?:\d+|\?))?\s*[?+]?$"
)


@dataclass(frozen=True, slots=True)
class CreatureRecoveryCandidate:
    creature_id: int
    creature_name: str
    mode: str
    external_id: str | None = None


@dataclass(frozen=True, slots=True)
class CreatureRecoveryEnqueueResult:
    job_ids: tuple[UUID, ...]
    total: int
    renormalize: int
    detail: int
    created: int
    already_active: int


def list_unresolved_creatures(
    db: Session,
) -> list[Creature]:
    rows = (
        db.query(Creature)
        .filter(
            Creature.is_hidden == False,
            Creature.is_boss == False,
        )
        .order_by(Creature.id)
        .all()
    )

    return [
        row
        for row in rows
        if resolve_creature_category(
            bestiary_class=row.bestiary_class,
            creature_class=row.creature_class,
            classification=row.classification,
        )
        is None
    ]


def category_coverage(
    db: Session,
) -> dict[str, int | float]:
    rows = (
        db.query(Creature)
        .filter(
            Creature.is_hidden == False,
            Creature.is_boss == False,
        )
        .all()
    )

    categorized = sum(
        1
        for row in rows
        if resolve_creature_category(
            bestiary_class=row.bestiary_class,
            creature_class=row.creature_class,
            classification=row.classification,
        )
        is not None
    )

    total = len(rows)

    return {
        "total": total,
        "categorized": categorized,
        "unresolved": total - categorized,
        "coverage_percent": (
            categorized / total * 100
            if total
            else 0.0
        ),
    }


def latest_creature_documents_by_name(
    db: Session,
) -> dict[str, str]:
    documents = (
        db.query(KnowledgeDocument)
        .filter(
            KnowledgeDocument.provider_id == "tibiawiki",
            KnowledgeDocument.provider_document_id.like(
                "creature:%"
            ),
        )
        .order_by(
            KnowledgeDocument.retrieved_at.desc()
        )
        .all()
    )

    result: dict[str, str] = {}

    for document in documents:
        external_id = (
            document.provider_document_id
            .split(":", 1)[-1]
            .strip()
        )

        if not external_id.isdigit():
            continue

        metadata = document.document_metadata or {}
        raw = (
            document.raw_json
            if isinstance(document.raw_json, dict)
            else {}
        )
        parsed = (
            raw.get("parse")
            if isinstance(raw.get("parse"), dict)
            else {}
        )

        title = str(
            metadata.get("page_title")
            or parsed.get("title")
            or ""
        ).strip()

        key = normalize_search_text(title)

        if key and key not in result:
            result[key] = external_id

    return result


def build_category_recovery_plan(
    db: Session,
) -> list[CreatureRecoveryCandidate]:
    documents = latest_creature_documents_by_name(db)

    result: list[CreatureRecoveryCandidate] = []

    for creature in list_unresolved_creatures(db):
        external_id = documents.get(
            normalize_search_text(creature.name)
        )

        if external_id:
            result.append(
                CreatureRecoveryCandidate(
                    creature_id=creature.id,
                    creature_name=creature.name,
                    mode="renormalize",
                    external_id=external_id,
                )
            )
        else:
            result.append(
                CreatureRecoveryCandidate(
                    creature_id=creature.id,
                    creature_name=creature.name,
                    mode="detail",
                )
            )

    return result


def enqueue_category_recovery(
    db: Session,
    plan: list[CreatureRecoveryCandidate],
) -> CreatureRecoveryEnqueueResult:
    job_ids: list[UUID] = []
    renormalize = 0
    detail = 0
    created = 0
    already_active = 0

    for candidate in plan:
        if candidate.mode == "renormalize":
            if not candidate.external_id:
                raise ValueError(
                    "Renormalization requires external_id"
                )

            job_type = "creature_renormalize"
            payload = {
                "external_id": candidate.external_id,
            }
            renormalize += 1
        elif candidate.mode == "detail":
            job_type = "creature_detail"
            payload = {
                "page_title": candidate.creature_name,
            }
            detail += 1
        else:
            raise ValueError(
                f"Unknown recovery mode {candidate.mode}"
            )

        result = KnowledgeJobService.enqueue(
            db,
            EnqueueKnowledgeJob(
                provider_id="tibiawiki",
                job_type=job_type,
                entity_type="creature",
                payload=payload,
                priority=120,
                max_attempts=5,
                trigger="manual",
                allow_completed_recreate=True,
            ),
        )

        job_ids.append(result.job.id)

        if result.created:
            created += 1
        else:
            already_active += 1

    return CreatureRecoveryEnqueueResult(
        job_ids=tuple(job_ids),
        total=len(plan),
        renormalize=renormalize,
        detail=detail,
        created=created,
        already_active=already_active,
    )


def hide_non_creature_catalog_rows(
    db: Session,
) -> int:
    rows = (
        db.query(Creature)
        .filter(
            Creature.source_name == "tibiawiki",
            Creature.is_hidden == False,
        )
        .all()
    )

    changed = 0

    for row in rows:
        if not is_non_creature_catalog_title(
            row.name
        ):
            continue

        if "is_hidden" in set(
            row.protected_fields or []
        ):
            continue

        row.is_hidden = True
        changed += 1

    return changed


def clear_legacy_beast_classifications(
    db: Session,
) -> int:
    rows = (
        db.query(Creature)
        .filter(
            Creature.source_name == "tibiawiki",
            Creature.classification.isnot(None),
        )
        .all()
    )

    changed = 0

    for row in rows:
        if (
            str(row.classification or "")
            .strip()
            .casefold()
            != "beast"
        ):
            continue

        if str(row.bestiary_class or "").strip():
            continue

        if "classification" in set(
            row.protected_fields or []
        ):
            continue

        row.classification = None

        if isinstance(row.raw_data, dict):
            raw = dict(row.raw_data)

            if (
                str(raw.get("classification") or "")
                .strip()
                .casefold()
                == "beast"
            ):
                raw["classification"] = None
                row.raw_data = raw

        changed += 1

    return changed


def malformed_loot_rows(
    db: Session,
) -> list[Loot]:
    provider_host = urlparse(
        settings.TIBIAWIKI_BASE_PAGE_URL
    ).hostname

    malformed: list[Loot] = []

    for row in db.query(Loot).all():
        name = str(row.item_name or "").strip()

        if not AMOUNT_TOKEN_RE.fullmatch(name):
            continue

        source_host = urlparse(
            row.source_url or ""
        ).hostname
        image_host = urlparse(
            row.item_image_url or ""
        ).hostname

        raw = (
            row.raw_data
            if isinstance(row.raw_data, dict)
            else {}
        )

        if (
            (
                source_host == provider_host
                or image_host == provider_host
            )
            and (
                not raw
                or str(
                    raw.get("item_name") or ""
                ).strip()
                == name
            )
        ):
            malformed.append(row)

    return malformed


def remove_malformed_loot(
    db: Session,
) -> tuple[int, int]:
    rows = malformed_loot_rows(db)

    affected_creatures = {
        row.creature_id
        for row in rows
    }

    for row in rows:
        db.delete(row)

    return len(rows), len(affected_creatures)
