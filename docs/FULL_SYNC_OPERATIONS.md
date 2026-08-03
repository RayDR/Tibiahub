# Durable full synchronization and maintenance

`tibiahub-sync-worker` is the only production process that executes queued
`SyncJob` operations. The API creates durable job and phase rows and returns the
operation ID immediately. PostgreSQL row locks, worker ownership, leases, phase
checkpoints, and bounded provider-aware retries provide crash recovery without
depending on the browser or API process.

Full operations can include creatures, bosses, items, quests, hunt zones,
images/resources, Knowledge Platform jobs, and active guild rosters. Completed
phases are not repeated during resume. Failed optional phases remain visible and
resumable, and independent later phases continue when configured.

Maintenance is represented by persistent holds. Manual holds are released only
by an explicit administrator action. A sync hold belongs to one job and is
released for completed, completed-with-errors, failed, and cancelled terminal
states. API and worker startup reconciliation releases orphaned terminal-job
holds while preserving active and manual holds.

During maintenance, public API requests receive HTTP 503 with
`maintenance_mode` and `Retry-After`. Static assets, health/readiness, real login,
current-user authentication, password recovery, and authenticated global-admin
operations remain available. `Ctrl+Shift+A` only navigates to the real login
route; it grants no access and is not an authorization mechanism.
