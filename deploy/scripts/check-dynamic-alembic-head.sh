#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DEPLOY_SCRIPT="$ROOT/deploy/scripts/deploy.sh"

bash -n "$DEPLOY_SCRIPT"

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

echo "Dynamic Alembic deploy target and frontend dependency checks passed."
