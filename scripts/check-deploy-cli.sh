#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

fail() {
  echo "deploy CLI check failed: $*" >&2
  exit 1
}

bash -n "$ROOT/scripts/tibiahub-ops.sh"
bash -n "$ROOT/deploy/scripts/deploy.sh"
bash -n "$ROOT/deploy/scripts/rollback.sh"

help_output="$(bash "$ROOT/scripts/tibiahub-ops.sh" help)"

grep -Fq 'deploy [--confirm-deploy] [--previous-commit <sha40>]' <<<"$help_output" || fail "new deploy command missing from help"
grep -Fq 'deploy dry-run [--confirm-deploy]' <<<"$help_output" || fail "dry-run command missing from help"
grep -Fq 'deploy status' <<<"$help_output" || fail "deploy status missing from help"
grep -Fq 'deploy history' <<<"$help_output" || fail "deploy history missing from help"
grep -Fq 'deploy rollback [<deployment-dir>] [--confirm-rollback]' <<<"$help_output" || fail "rollback command missing from help"

if grep -Fq 'deploy run --confirm-deploy-tibiahub' <<<"$help_output"; then
  fail "legacy redundant deploy confirmation is still advertised"
fi

# Static safety contracts. These deliberately check operator-facing invariants
# without attempting to touch PM2, PostgreSQL, the network, or deployment state.
grep -Fq 'refs/tibiahub/deploy-snapshots/' "$ROOT/deploy/scripts/deploy.sh" || fail "previous commit snapshot ref is not created"
grep -Fq 'git fetch --quiet origin "$target_branch"' "$ROOT/deploy/scripts/deploy.sh" || fail "current branch remote parity is not checked"
grep -Fq 'approve_nonstandard_branch' "$ROOT/deploy/scripts/deploy.sh" || fail "non-standard branch approval guard is missing"
grep -Fq 'snapshot_dir' "$ROOT/scripts/tibiahub-ops.sh" || fail "automatic rollback snapshot resolution is missing"
grep -Fq -- '--confirm-rollback' "$ROOT/scripts/tibiahub-ops.sh" || fail "non-interactive rollback confirmation is missing"

echo "Deploy CLI contracts passed."
