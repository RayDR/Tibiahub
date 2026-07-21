# Workspace and content scope model

TibiaHub separates five UI contexts: public, personal, a user's own guild, global administration, and explicit admin guild assistance. The frontend provider derives context from the authenticated account and route for presentation only. Backend dependencies and centralized capability helpers remain authoritative.

`/guild` always resolves the authenticated user's `guild_name`; ordinary requests cannot select another guild. Global administrators use `/admin/guilds` to select a registered guild. Opening `/admin/guilds/{key}` records a focused `WorkspaceAudit`, does not alter the administrator's membership, and displays a persistent assistance banner.

Guild leaders manage members, announcements, and events in their own guild. Viceleaders may manage announcements and events but not members. Members have read/participation access. Existing raffle manager grants remain narrower, explicit grants and do not confer leadership. Global administration is restricted to superusers.

Activity scopes are normalized in application policy as `guild`, `server`, `global`, and future `coalition`. Historical `guild_only`, `world_only`, and `public` access modes remain readable through a compatibility adapter. Server and global creation are global-admin-only until a durable policy grant exists. Coalition is represented for forward compatibility but rejected by current creation policy and is not exposed in the UI.

The `workspace_foundation_20260723` Alembic migration adds only the focused assistance audit table. Deploy it in staging first, verify the current Alembic head and backup plan, then run the same versioned migration in production. It does not rewrite historical events or raffles.
