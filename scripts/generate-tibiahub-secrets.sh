#!/usr/bin/env bash
set -Eeuo pipefail

TIBIAHUB_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
secrets_dir="${TIBIAHUB_SECRETS_DIR:-/forge/tibiahub-secrets}"
database_name="${TIBIAHUB_DATABASE_NAME:-tibiahub}"
database_role="${TIBIAHUB_DATABASE_ROLE:-tibiahub_app}"
database_host="${TIBIAHUB_DATABASE_HOST:-127.0.0.1}"
database_port="${TIBIAHUB_DATABASE_PORT:-5432}"
postgres_admin_user="${TIBIAHUB_POSTGRES_ADMIN_USER:-}"
postgres_admin_password="${TIBIAHUB_POSTGRES_ADMIN_PASSWORD:-}"

if [[ "${1:-}" != "--confirm-create-tibiahub-secrets" || $# -ne 1 ]]; then
  echo "Usage: $0 --confirm-create-tibiahub-secrets" >&2
  exit 2
fi

if [[ "$database_name" != "tibiahub" || "$database_role" != "tibiahub_app" ]]; then
  echo "Secret generation is restricted to database tibiahub and role tibiahub_app." >&2
  exit 2
fi
if [[ "$database_host" != "127.0.0.1" && "$database_host" != "localhost" && "$database_host" != "::1" ]]; then
  echo "Secret generation is restricted to localhost PostgreSQL." >&2
  exit 2
fi
if [[ ! "$database_port" =~ ^[0-9]+$ ]]; then
  echo "TibiaHub PostgreSQL port must be numeric." >&2
  exit 2
fi

resolved_dir="$(realpath -m "$secrets_dir")"
case "$resolved_dir/" in
  "$TIBIAHUB_ROOT/"*)
    echo "TibiaHub secrets must be created outside the repository." >&2
    exit 2
    ;;
esac

runtime_file="$resolved_dir/runtime.env"
provision_file="$resolved_dir/provision.env"
bootstrap_file="$resolved_dir/bootstrap.env"
for secret_file in "$runtime_file" "$provision_file" "$bootstrap_file"; do
  if [[ -e "$secret_file" || -L "$secret_file" ]]; then
    echo "Refusing to overwrite existing secret file: $secret_file" >&2
    exit 2
  fi
done

install -d -m 700 "$resolved_dir"
chmod 700 "$resolved_dir"
chmod g-s "$resolved_dir"
umask 077

database_password="$(openssl rand -hex 32)"
application_secret="$(openssl rand -hex 48)"
bootstrap_password="$(openssl rand -hex 24)"
database_scheme="postgresql+psycopg2"
database_url_host="$database_host"
if [[ "$database_url_host" == "::1" ]]; then
  database_url_host="[::1]"
fi
database_authority="${database_role}:${database_password}@${database_url_host}:${database_port}"
database_url="${database_scheme}://${database_authority}/${database_name}"

runtime_tmp="$(mktemp "$resolved_dir/.runtime.env.XXXXXX")"
provision_tmp="$(mktemp "$resolved_dir/.provision.env.XXXXXX")"
bootstrap_tmp="$(mktemp "$resolved_dir/.bootstrap.env.XXXXXX")"
cleanup() {
  rm -f -- "$runtime_tmp" "$provision_tmp" "$bootstrap_tmp"
}
trap cleanup EXIT

{
  printf "APP_ENV='production'\n"
  printf "DATABASE_URL='%s'\n" "$database_url"
  printf "SECRET_KEY='%s'\n" "$application_secret"
  printf "API_HOST='127.0.0.1'\n"
  printf "API_PORT='8001'\n"
  printf "RAFFLE_SCHEDULER_ENABLED='true'\n"
  printf "RAFFLE_SCHEDULER_WORKER_ID='raffle-scheduler-1'\n"
} >"$runtime_tmp"

{
  printf "# Fill PGUSER and PGPASSWORD with an elevated local PostgreSQL identity.\n"
  printf "PGHOST='%s'\n" "$database_host"
  printf "PGPORT='%s'\n" "$database_port"
  printf "PGDATABASE='postgres'\n"
  printf "PGUSER=%q\n" "$postgres_admin_user"
  printf "PGPASSWORD=%q\n" "$postgres_admin_password"
  printf "TIBIAHUB_DB_PASSWORD='%s'\n" "$database_password"
  printf "TIBIAHUB_DATABASE_NAME='%s'\n" "$database_name"
  printf "TIBIAHUB_DATABASE_ROLE='%s'\n" "$database_role"
  printf "TIBIAHUB_DATABASE_HOST='%s'\n" "$database_host"
  printf "TIBIAHUB_DATABASE_PORT='%s'\n" "$database_port"
} >"$provision_tmp"

{
  printf "BOOTSTRAP_ADMIN_USERNAME='admin'\n"
  printf "BOOTSTRAP_ADMIN_EMAIL='admin@tibiahub.local'\n"
  printf "BOOTSTRAP_ADMIN_PASSWORD='%s'\n" "$bootstrap_password"
} >"$bootstrap_tmp"

chmod 600 "$runtime_tmp" "$provision_tmp" "$bootstrap_tmp"
mv "$runtime_tmp" "$runtime_file"
mv "$provision_tmp" "$provision_file"
mv "$bootstrap_tmp" "$bootstrap_file"
trap - EXIT

echo "Created TibiaHub runtime, provisioning, and bootstrap secret files in $resolved_dir."
if [[ -z "$postgres_admin_user" || -z "$postgres_admin_password" ]]; then
  echo "Provisioning credentials are intentionally blank and must be supplied securely before cutover."
else
  echo "Provisioning credentials were stored without being printed."
fi
