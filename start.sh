#!/usr/bin/env bash
set -Eeuo pipefail

TIBIAHUB_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$TIBIAHUB_ROOT"

if [[ ! -f ecosystem.config.js ]]; then
  echo "ecosystem.config.js was not found in $TIBIAHUB_ROOT" >&2
  exit 1
fi

# This verifies connectivity and Alembic head; it never runs migrations.
scripts/verify-postgres.sh
pm2 start ecosystem.config.js --only tibiahub-api

ready=0
for _attempt in {1..20}; do
  if curl --fail --silent http://127.0.0.1:8001/api/v1/ready >/dev/null; then
    ready=1
    break
  fi
  sleep 1
done
if [[ "$ready" != "1" ]]; then
  echo "API readiness failed; scheduler and frontend were not started." >&2
  exit 1
fi

pm2 start ecosystem.config.js --only tibiahub-raffle-scheduler
pm2 start ecosystem.config.js --only tibiahub-frontend
pm2 list | grep tibiahub
