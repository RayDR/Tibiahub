"""Audited, idempotent activation of the canonical TibiaWiki seed pipeline."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.knowledge.adapters.registry import KnowledgeAdapterRegistry
from app.knowledge.models import KnowledgeDocument, KnowledgeJob, KnowledgeProvider
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
    ("hunt_zone_catalog", "hunt_zone"),
)


@dataclass(frozen=True, slots=True)
class KnowledgeFullSyncRoot:
    provider_id: str
    entity_type: str
    job_type: str
    mode: str
    reason: str


# Character and guild are name-addressed detail lookups and TibiaMaps is a
# staged dataset import, so neither has a truthful provider-wide catalog root.
KNOWLEDGE_FULL_SYNC_ROOTS = (
    *(KnowledgeFullSyncRoot("tibiawiki", entity_type, job_type, "catalog", "bounded MediaWiki category")
      for job_type, entity_type in TIBIAWIKI_CATALOGS),
    KnowledgeFullSyncRoot("tibiadata", "world", "world_catalog", "catalog", "bounded TibiaData world list"),
    KnowledgeFullSyncRoot("tibiadata", "creature", "creature_catalog", "catalog", "bounded TibiaData official creature list"),
    KnowledgeFullSyncRoot("tibiadata", "spell", "spell_catalog", "catalog", "bounded TibiaData official spell list"),
    KnowledgeFullSyncRoot("tibiadata", "boss", "boosted_bosses_current", "observation", "current boosted-boss observation; not a semantic boss catalog"),
)

# These are executable but require an explicit current scope; inventing a list
# of character names, worlds, towns, highscore categories, or pages would make
# a supposedly deterministic full sync misleading.
TIBIADATA_PARAMETERIZED_ROOTS = (
    KnowledgeFullSyncRoot("tibiadata", "character", "character_detail", "parameterized", "requires character name"),
    KnowledgeFullSyncRoot("tibiadata", "guild", "guild_catalog", "parameterized", "requires world"),
    KnowledgeFullSyncRoot("tibiadata", "guild", "guild_detail", "parameterized", "requires guild name"),
    KnowledgeFullSyncRoot("tibiadata", "world", "world_detail", "parameterized", "requires world name"),
    KnowledgeFullSyncRoot("tibiadata", "world", "highscores_current", "parameterized", "requires world/category/vocation/page"),
    KnowledgeFullSyncRoot("tibiadata", "world", "killstatistics_current", "parameterized", "requires world"),
    KnowledgeFullSyncRoot("tibiadata", "town", "house_catalog", "parameterized", "requires world and town"),
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


@dataclass(frozen=True, slots=True)
class KnowledgeFullSyncResult:
    jobs: tuple[KnowledgeJob, ...]
    created_count: int
    skipped_count: int


class KnowledgeFullSyncService:
    """Deterministic, provider-isolated root planning and raw replay."""

    @staticmethod
    def roots() -> tuple[KnowledgeFullSyncRoot, ...]:
        return KNOWLEDGE_FULL_SYNC_ROOTS

    @staticmethod
    def enqueue(
        db: Session,
        *,
        batch_limit: int,
        repair_existing: bool = False,
        provider_ids: set[str] | None = None,
        enable_provider_ids: set[str] | None = None,
        adapters: KnowledgeAdapterRegistry | None = None,
    ) -> KnowledgeFullSyncResult:
        if not 1 <= batch_limit <= 50:
            raise ValueError("full_sync_batch_limit_invalid")
        registry = adapters or KnowledgeAdapterRegistry()
        jobs: list[KnowledgeJob] = []
        created = skipped = 0
        for root in KNOWLEDGE_FULL_SYNC_ROOTS:
            if provider_ids is not None and root.provider_id not in provider_ids:
                continue
            provider = db.get(KnowledgeProvider, root.provider_id)
            if provider is not None and root.provider_id in (enable_provider_ids or set()):
                provider.enabled = True
                if provider.health == "disabled":
                    provider.health = "unknown"
                provider.cooldown_until = None
                db.flush()
            if provider is None or not provider.enabled or provider.health == "disabled":
                skipped += 1
                continue
            scope = {"batch_limit": batch_limit} if (
                root.mode == "catalog" and (
                    root.provider_id == "tibiawiki" or root.entity_type in {"creature", "spell"}
                )
            ) else {}
            registry.validate_enqueue(root.provider_id, root.job_type, root.entity_type, scope, {})
            result = KnowledgeJobService.enqueue(db, EnqueueKnowledgeJob(
                provider_id=root.provider_id,
                job_type=root.job_type,
                entity_type=root.entity_type,
                scope=scope,
                payload={},
                priority=TIBIAWIKI_ROOT_CATALOG_PRIORITY,
                trigger="retry" if repair_existing else "manual",
                # Completed roots are refreshable; active roots remain idempotent.
                # The trigger distinguishes an explicitly requested repair pass.
                allow_completed_recreate=True,
            ))
            jobs.append(result.job)
            created += int(result.created)
            skipped += int(not result.created)
        return KnowledgeFullSyncResult(tuple(jobs), created, skipped)

    @staticmethod
    def enqueue_renormalization(
        db: Session,
        *,
        provider_id: str,
        entity_type: str,
        limit: int,
        normalization_root: str | None = None,
        document_prefix: str | None = None,
        adapters: KnowledgeAdapterRegistry | None = None,
    ) -> KnowledgeFullSyncResult:
        if not 1 <= limit <= 100:
            raise ValueError("renormalize_limit_invalid")
        registry = adapters or KnowledgeAdapterRegistry()
        root = normalization_root or entity_type
        job_type = f"{root}_renormalize"
        prefix = document_prefix or root
        documents = db.query(KnowledgeDocument).filter(
            KnowledgeDocument.provider_id == provider_id,
            KnowledgeDocument.provider_document_id.like(f"{prefix}:%"),
        ).order_by(KnowledgeDocument.retrieved_at.desc()).limit(limit * 4).all()
        jobs: list[KnowledgeJob] = []
        seen: set[str] = set()
        created = skipped = 0
        for document in documents:
            external_id = document.provider_document_id.split(":", 1)[1]
            if external_id in seen:
                continue
            seen.add(external_id)
            payload = {"external_id": external_id}
            registry.validate_enqueue(provider_id, job_type, entity_type, {}, payload)
            result = KnowledgeJobService.enqueue(db, EnqueueKnowledgeJob(
                provider_id=provider_id,
                job_type=job_type,
                entity_type=entity_type,
                payload=payload,
                trigger="renormalize",
                allow_completed_recreate=True,
            ))
            jobs.append(result.job)
            created += int(result.created)
            skipped += int(not result.created)
            if len(jobs) >= limit:
                break
        return KnowledgeFullSyncResult(tuple(jobs), created, skipped)
