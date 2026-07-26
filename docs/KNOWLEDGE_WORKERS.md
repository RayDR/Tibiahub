# Knowledge workers

Stage 2A-2 adds a durable execution layer to the Knowledge Platform. PostgreSQL is the source of truth for jobs, attempts, leases, heartbeats, provider cursors, and active-job idempotency. Redis and process-local state are not used for correctness.

The production worker is disabled by default. Enabling it does not enqueue work: jobs must be created through the controlled admin API or the enqueue script.

## Execution model

The worker executes this sequence:

1. Recover a bounded batch of expired leases.
2. Claim one due job in a short transaction using `FOR UPDATE SKIP LOCKED`.
3. Commit the claim and create a numbered attempt.
4. Resolve the registered provider adapter and perform provider work outside the claim transaction.
5. Validate the adapter result.
6. Store an immutable raw `KnowledgeDocument` and invoke the provider-neutral normalization boundary.
7. Update metrics, provider health, cursor, and domain events in the completion transaction.
8. Complete the job or classify the failure and schedule a bounded retry.

Jobs move through `pending`, `claimed`, `running`, `retrying`, and one of the terminal states `succeeded`, `partially_succeeded`, `failed`, or `cancelled`. Only `pending` and `retrying` jobs whose schedule is due and whose provider is enabled and outside cooldown can be claimed. Priority sorts descending, then scheduled and creation time sort ascending.

A claim records the worker and a configurable lease expiry. Completion locks the job and verifies the current worker, running state, unexpired lease, and attempt ownership. Expired claims are changed to `retrying` (or `failed` at the attempt limit), and a stale worker cannot finish a reassigned job. Retries add an attempt to the same job rather than cloning job identity.

## Idempotency policy

The deterministic key is the SHA-256 digest of canonical JSON containing:

- provider code;
- job type;
- entity type;
- normalized scope;
- normalized request payload;
- an optional time bucket only for intentionally bucketed scheduled work.

Object keys are sorted, surrounding string whitespace is normalized, and non-finite numbers or non-JSON input are rejected. Job type separates full and incremental synchronization semantics. PostgreSQL enforces a partial unique index for the active states (`pending`, `claimed`, `running`, and `retrying`), so concurrent enqueue requests cannot create duplicate active work. A completed job can be recreated only with the explicit recreation option. Manual retry changes the existing failed job to `retrying` and cannot create multiple active jobs.

## Failure and retry policy

Timeouts, connection and temporary DNS failures, HTTP 429/502/503/504 responses, database connection interruptions, and expired leases are retryable. Invalid provider configuration, unsupported work, malformed or oversized responses, missing authorization, invalid normalization contracts, cancellation, and unknown exceptions are permanent unless explicitly classified otherwise.

Backoff is exponential, bounded to one hour by default, includes bounded jitter, honors a safe bounded `Retry-After`, and stops at `max_attempts`. Stored and API-visible errors are fixed safe summaries. Logs include job and correlation identifiers but not payloads, credentials, environment dumps, stack traces, or provider error envelopes.

Transient provider failures increment `consecutive_failures`, set health to `degraded` and then `unavailable`, and impose a bounded cooldown. Success resets the failure count and cooldown. Disabled providers remain disabled. Existing canonical data and raw documents stay available regardless of provider health.

## Adapter and normalization boundaries

`KnowledgeProviderAdapter` receives dataclass DTOs, never SQLAlchemy models. Its request/result contracts reserve pagination cursors, list/detail job types, language, metadata, media references, partial results, and child jobs. The adapter registry is the foundation for provider-specific support and concurrency policy. Stage 2A-2 registers only the deterministic `reference` adapter; it performs no network calls and is disabled in migrated environments.

Each validated document is content-addressed by provider, provider document ID, and canonical JSON hash. Identical content is deduplicated while unknown JSON fields are retained. Every newly stored document is immutable; failed or invalid results never replace an earlier valid document. Safe metadata links a stored document to its job, attempt, and correlation identifiers. Provider-import events record storage or deduplication, while normalization events are emitted only when canonical data was created or changed.

Normalization currently supports no-op and canonical test-entity upsert contracts. It reports documents received, entities created/updated/unchanged, aliases created, warnings, and child jobs enqueued. Entity-specific production rules remain deferred.

## Configuration and operations

The PM2 process is named `tibiahub-knowledge-worker`. It runs one forked instance with the backend virtual-environment Python, a fixed backend working directory, independent logs, restart delay, and graceful kill timeout. PM2 receives only the database secret-file path; the credential itself is never embedded in the ecosystem file or saved process configuration.

Configuration:

- `KNOWLEDGE_WORKER_ENABLED` defaults to `false`.
- `KNOWLEDGE_WORKER_ID` is the safe logical worker identifier.
- `KNOWLEDGE_WORKER_POLL_SECONDS` controls bounded idle polling.
- `KNOWLEDGE_WORKER_LEASE_SECONDS` controls ownership duration.
- `KNOWLEDGE_WORKER_MAX_IDLE_SECONDS` caps database-failure and idle backoff.

Before enabling the production process, confirm all of the following:

1. The API is using the TibiaHub PostgreSQL database.
2. Alembic is at `knowledge_workers_20260723`.
3. No unintended provider jobs exist.
4. The worker flag is explicitly enabled through operational configuration.
5. A registered production adapter is enabled intentionally.

The worker verifies connectivity and schema head but never runs migrations. It handles SIGTERM and SIGINT, writes a stopping heartbeat where possible, has no busy loop, and never performs a full sync at startup.

Safe operator scripts are available at:

- `scripts/enqueue-knowledge-job.py`
- `scripts/verify-knowledge-worker.py`
- `scripts/recover-expired-knowledge-jobs.py`

They use shared settings, require the database name to be exactly `tibiahub`, do not print credentials, and provide dry-run or confirmation behavior where state can change. The admin API under `/api/v1/admin/knowledge` supplies paginated safe operational data and audited enqueue, retry, and cancel actions. It accepts registered provider/job/entity combinations only and does not expose provider URLs, raw documents, unrestricted payloads, or secrets.

## Deferred to Stage 2A-3

Real Creature, Item, Quest, Guild, Character, map, media, and search adapters; entity-specific normalization; provider-specific concurrency enforcement; AI, embeddings, and pgvector; raw-document administration; and automatic schedules are intentionally not part of this stage.
