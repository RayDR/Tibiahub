"""Audited, idempotent activation of the canonical TibiaWiki seed pipeline."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.knowledge.adapters.registry import KnowledgeAdapterRegistry
from app.knowledge.models import KnowledgeJob, KnowledgeProvider
from app.knowledge.services.jobs import EnqueueKnowledgeJob, KnowledgeJobService
from app.models.workspace_audit import WorkspaceAudit


TIBIAWIKI_BOOTSTRAP_CONFIRMATION = "ENABLE TIBIAWIKI FULL SYNC"
TIBIAWIKI_ROOT_CATALOG_PRIORITY = 200
TIBIAWIKI_CATALOGS = (
    ("creature_catalog", "creature"),
    ("item_catalog", "item"),
    ("quest_catalog", "quest"),
    ("npc_catalog", "npc"),
    ("location_catalog", "location"),
    ("route_catalog", "route"),
)


@dataclass(frozen=True, slots=True)
class KnowledgeBootstrapResult:
    provider: KnowledgeProvider
    jobs: tuple[KnowledgeJob, ...]
    created_count: int


class KnowledgeBootstrapService:
    """Enable and seed a provider through its registered durable adapters only."""

    @staticmethod
    def activate_tibiawiki(
        db: Session,
        *,
        actor_id: int,
        confirmation: str,
        batch_limit: int = 50,
        adapters: KnowledgeAdapterRegistry | None = None,
    ) -> KnowledgeBootstrapResult:
        if confirmation != TIBIAWIKI_BOOTSTRAP_CONFIRMATION:
            raise ValueError("bootstrap_confirmation_required")
        if not 1 <= batch_limit <= 50:
            raise ValueError("bootstrap_batch_limit_invalid")
        provider = db.get(KnowledgeProvider, "tibiawiki")
        if provider is None:
            raise ValueError("bootstrap_provider_missing")

        registry = adapters or KnowledgeAdapterRegistry()
        for job_type, entity_type in TIBIAWIKI_CATALOGS:
            registry.validate_enqueue("tibiawiki", job_type, entity_type, {"batch_limit": batch_limit}, {})

        provider.enabled = True
        if provider.health == "disabled":
            provider.health = "unknown"
        provider.cooldown_until = None
        db.flush()

        jobs: list[KnowledgeJob] = []
        created_count = 0
        for job_type, entity_type in TIBIAWIKI_CATALOGS:
            result = KnowledgeJobService.enqueue(
                db,
                EnqueueKnowledgeJob(
                    provider_id="tibiawiki",
                    job_type=job_type,
                    entity_type=entity_type,
                    scope={"batch_limit": batch_limit},
                    payload={},
                    # Seed every entity family before detail expansion. Detail
                    # jobs use priority 100, so a lower root priority lets the
                    # first large catalog starve all other catalog roots.
                    priority=TIBIAWIKI_ROOT_CATALOG_PRIORITY,
                    max_attempts=5,
                    created_by_id=actor_id,
                    trigger="bootstrap",
                    allow_completed_recreate=True,
                ),
            )
            jobs.append(result.job)
            # Existing active idempotent roots keep their original priority;
            # promote them as part of a repeated bootstrap as well.
            result.job.priority = max(result.job.priority, TIBIAWIKI_ROOT_CATALOG_PRIORITY)
            created_count += int(result.created)

        db.add(WorkspaceAudit(
            actor_id=actor_id,
            workspace_type="admin",
            action="knowledge_tibiawiki_bootstrap_started",
            target_type="knowledge_provider",
            target_id="tibiawiki",
            assisted=False,
            safe_metadata={
                "batch_limit": batch_limit,
                "catalogs": [entity_type for _job_type, entity_type in TIBIAWIKI_CATALOGS],
                "jobs_created": created_count,
            },
        ))
        return KnowledgeBootstrapResult(provider, tuple(jobs), created_count)
