#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DEPLOY_SCRIPT="$ROOT/deploy/scripts/deploy.sh"
ROLLBACK_SCRIPT="$ROOT/deploy/scripts/rollback.sh"

bash -n "$DEPLOY_SCRIPT"
bash -n "$ROLLBACK_SCRIPT"

grep -Fq 'EXPECTED_REVISION=""' "$DEPLOY_SCRIPT"
! grep -Eq '^EXPECTED_REVISION="[A-Za-z0-9_]+"$' "$DEPLOY_SCRIPT"
grep -Fq 'Deployment requires exactly one Alembic HEAD' "$DEPLOY_SCRIPT"
grep -Fq 'EXPECTED_REVISION="${migration_heads[0]}"' "$DEPLOY_SCRIPT"
grep -Fq 'Resolved Alembic target revision: $EXPECTED_REVISION' "$DEPLOY_SCRIPT"

grep -Fq 'frontend_dependency_fingerprint()' "$DEPLOY_SCRIPT"
grep -Fq 'cd "$FRONTEND_DIR"' "$DEPLOY_SCRIPT"
grep -Fq 'sha256sum package.json package-lock.json' "$DEPLOY_SCRIPT"
grep -Fq 'Preparing frontend dependencies with npm ci.' "$DEPLOY_SCRIPT"
grep -Fq 'npm ci --prefer-offline --no-audit --no-fund' "$DEPLOY_SCRIPT"
grep -Fq '085-preflight-frontend-dependencies' "$DEPLOY_SCRIPT"
grep -Fq '.tibiahub-dependency-inputs.sha256' "$DEPLOY_SCRIPT"
! grep -Fq 'ln -s "$ROOT/frontend/node_modules" "$previous_worktree/frontend/node_modules"' "$DEPLOY_SCRIPT"

grep -Fq 'previous_commit_source="explicit"' "$DEPLOY_SCRIPT"
grep -Fq 'using the explicit value.' "$DEPLOY_SCRIPT"
grep -Fq "printf 'previous_commit_source=%s\\n'" "$DEPLOY_SCRIPT"
grep -Fq "printf 'recorded_previous_commit=%s\\n'" "$DEPLOY_SCRIPT"
! grep -Fq 'Provided previous commit does not match recorded deployment state.' "$DEPLOY_SCRIPT"

grep -Fq 'wait_for_worker_readiness()' "$DEPLOY_SCRIPT"
grep -Fq 'for attempt in $(seq 1 30)' "$DEPLOY_SCRIPT"
grep -Fq 'sleep 2' "$DEPLOY_SCRIPT"
grep -Fq 'pm2_state="$(pm2 jlist)"' "$DEPLOY_SCRIPT"
grep -Fq '.pm2_env.status == "online"' "$DEPLOY_SCRIPT"
grep -Fq 'worker_readiness_not_before="$(date -u' "$DEPLOY_SCRIPT"
readiness_timestamp_line="$(grep -nF 'worker_readiness_not_before="$(date -u' "$DEPLOY_SCRIPT" | cut -d: -f1)"
service_start_line="$(grep -nF 'for service in "${SERVICES[@]}"; do' "$DEPLOY_SCRIPT" | tail -n 1 | cut -d: -f1)"
[[ "$service_start_line" -eq $((readiness_timestamp_line + 1)) ]]
grep -Fq -- '-v readiness_not_before="$worker_readiness_not_before"' "$DEPLOY_SCRIPT"
grep -Fq "WHEN last_heartbeat IS NULL THEN 'missing'" "$DEPLOY_SCRIPT"
grep -Fq "WHEN last_heartbeat < :'readiness_not_before'::timestamptz THEN 'predeploy'" "$DEPLOY_SCRIPT"
grep -Fq "WHEN last_heartbeat < now() - interval '5 minutes' THEN 'stale'" "$DEPLOY_SCRIPT"
grep -Fq 'Worker readiness timed out after 60 seconds; heartbeats must be at or after $worker_readiness_not_before.' "$DEPLOY_SCRIPT"
grep -Fq 'last heartbeat=${last_heartbeat[$worker]:-missing}' "$DEPLOY_SCRIPT"
grep -Fq 'heartbeat age=${heartbeat_age[$worker]:-unknown}s' "$DEPLOY_SCRIPT"
grep -Fq 'freshness=${heartbeat_freshness[$worker]:-missing}' "$DEPLOY_SCRIPT"

grep -Fq 'git switch --detach "$previous_commit"' "$ROLLBACK_SCRIPT"
grep -Fq 'git switch develop' "$ROLLBACK_SCRIPT"
grep -Fq 'git pull --ff-only origin develop' "$ROLLBACK_SCRIPT"

echo "Dynamic Alembic, frontend dependency, deploy reconciliation, worker readiness, and rollback checks passed."
