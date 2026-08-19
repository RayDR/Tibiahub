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

echo "Dynamic Alembic deploy target checks passed."
