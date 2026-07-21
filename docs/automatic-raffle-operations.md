# Automatic raffle operations

The modern automatic subsystem (`run_mode=automatic`, purpose `test` or
`real`) is authoritative. Legacy event raffles remain readable for history but
are never discovered or executed by this scheduler.

## Architecture and configuration

The scheduler is a dedicated process (`python -m app.workers.raffle_scheduler`),
not a FastAPI timer. It polls UTC schedules, claims one due row, and delegates
selection to the Stage 1 transactional engine. PostgreSQL uses `FOR UPDATE SKIP
LOCKED`; SQLite supports one development worker through an optimistic version
claim. Production concurrency guarantees require PostgreSQL.

| Setting | Default |
| --- | ---: |
| `RAFFLE_SCHEDULER_ENABLED` | `false` |
| `RAFFLE_SCHEDULER_POLL_SECONDS` | `30` |
| `RAFFLE_SCHEDULER_LEASE_SECONDS` | `300` |
| `RAFFLE_SCHEDULER_MAX_RETRIES` | `5` |
| `RAFFLE_SCHEDULER_INITIAL_RETRY_SECONDS` | `60` |
| `RAFFLE_SCHEDULER_WORKER_ID` | `raffle-scheduler-1` |

PM2 defines one `tibiahub-raffle-scheduler` instance with separate output and
error logs. Do not increase instances on SQLite. Enable it only after migration
and staging rehearsal.

## Migration and staging rehearsal

1. Back up and rehearse on a recent isolated PostgreSQL copy.
2. Run `cd backend && alembic upgrade raffle_operations_20260721`.
3. Confirm `alembic heads` reports `raffle_operations_20260721`.
4. Start one enabled scheduler in staging.
5. Create a test raffle, freeze eligibility, let the due time pass, and verify
   one successful private run, notifications, and delivery deadlines.
6. Restart during a claim and verify recovery only after lease expiry. Rehearse
   publication, unpublication, delivery updates, and position reruns.

Never run migration experiments or test fixtures against production data.

## Recovery and emergency reruns

Claims and attempts are durable. Only expired `claimed` or `running` rows are
recovered. Overdue pending raffles execute after restart. Provider/network
failures use bounded exponential backoff capped at one hour. Invalid prizes,
snapshots, modes, and configuration fail permanently. Historical attempts and
superseded results remain intact.

Global admins can inspect heartbeat and aggregate counts through the protected
health endpoint. Public responses never expose worker details, claim tokens,
provider exceptions, or internal user IDs.

For reruns, select second, first, or both; enter a reason; review delivery
impact; and confirm positions. Delivered prizes require a global-admin override
and separate reason. Reruns return results to private review. Only the Guild
Leader or global admin publishes. Record delivered, disputed, or cancelled
prizes with appropriate notes.

## Test raffle runbook

Create a `test` raffle using authenticated local accounts, a near-future
schedule, guild-only access, five-day eligibility, and fixed 100/250 TC prizes.
Preview, refresh stale source data, freeze, and let the real scheduler execute.
Check normal and reduced-motion presentation; rerun each position and both;
update delivery; publish/unpublish; then soft-delete or archive only the test
raffle. Test cleanup never deletes accounts or guild membership. Test raffles
are visibly labelled, never achievements, and cannot become real raffles.

## Real raffle preparation checklist

The requested example is Friday, July 24, 2026 at 8:00 PM
`America/Chicago`, stored as July 25, 2026 at 01:00 UTC: second 100 TC, first
250 TC, five calendar days of activity, private results, and delivery within 24
hours. This date is documentation only and is not a permanent default. Select
the intended Friday and explicitly confirm each real raffle.

Verify guild, IANA timezone/DST conversion, UTC equivalent, membership and
activity freshness, fixed prizes, private state, and scheduler health. Do not
create or execute the production raffle during deployment.

## Notifications and multilingual maintenance

Notifications are internal database records only; no email or Discord is sent.
Recipient ownership and deduplication are enforced. Winner notifications stay
private until publication.

Future visible raffle strings must use i18n and include matching English and
Spanish entries with equivalent interpolation/pluralization. Character and
guild names, identifiers, timestamps, numbers, and `TC` are not translated.
