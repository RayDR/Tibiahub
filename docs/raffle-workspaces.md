# Raffle workspace runbook

## Routes and contexts

`/guild/raffles` is the single own-guild entry. The former `/guild/raffle` and `/guild/automatic-raffles` routes redirect to it. Historical records remain under **History** and public links remain `/raffles/{publicCode}`.

Global administrators create server and global contests from `/admin/activities`. Guild-specific administration begins in `/admin/guilds/{guildKey}` and continues at `/admin/guilds/{guildKey}/raffles`; the selected guild remains fixed and the assistance banner remains visible.

## Authority

- Members receive safe workspace summaries, published results, registration state, participant counts, and aggregate eligibility. Internal user and participant identifiers are not returned by the workspace or eligibility contracts.
- Viceleaders receive no automatic raffle-management authority. An active `RaffleManagerGrant` enables operational actions but not publication.
- Guild leaders create and operate automatic raffles for their own guild and may publish results.
- Global admins operate assisted guild raffles and create server/global contests. Assisted creates, snapshot freezes, executions, reruns, delivery updates, and publication are written to `workspace_audits`.

## Automatic guild raffle lifecycle

The UI represents draft, registration, eligibility review, frozen snapshot, scheduled, running, private review, publication, delivery, and completion. Eligibility defaults to five days. Automatic prizes are exactly 100 TC for second place and 250 TC for first place. Results remain private until a leader or global administrator publishes them. Delivery is due 24 hours after execution.

The backend remains authoritative for winners. The reveal component only presents already-returned results, honors reduced-motion preferences, and supports a replay that does not call the execution endpoint.

Reruns require selected positions and a reason, preserve history, return the raffle to private review, and protect delivered prizes. Only a global administrator can override that protection with an explicit reason.

## Deployment

Apply Alembic revision `raffle_scopes_20260724` in staging first. It adds normalized `scope_type` and `world_name` fields, derives scope from historical access modes, and adds append-only delivery transition audits. It does not remove or rewrite historical raffle/event records beyond populating the new normalized scope field.

Rehearse the migration against a recent PostgreSQL copy and follow the production backup plan before deployment.
