#!/usr/bin/env bash

# Compatibility shim. New scripts should source scripts/lib/postgres.sh directly.

_postgres_common_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/postgres.sh
source "$_postgres_common_root/lib/postgres.sh"
