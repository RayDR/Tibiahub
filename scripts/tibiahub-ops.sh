#!/usr/bin/env bash

if [[ "${BASH_SOURCE[0]}" != "$0" ]]; then
  echo "scripts/tibiahub-ops.sh must be executed, not sourced." >&2
  return 1 2>/dev/null || exit 1
fi

set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/ops-common.sh
source "$ROOT/scripts/lib/ops-common.sh"
# shellcheck source=lib/postgres.sh
source "$ROOT/scripts/lib/postgres.sh"

print_help() {
  cat <<'HELP'
Usage: scripts/tibiahub-ops.sh <command> [subcommand] [options]

General:
  help
  status
  health
  diagnose

Database:
  db status
  db verify [--dry-run]
  db revision [current|heads|history|check]
  db migrate [--dry-run | --confirm-migrate-tibiahub]
  db backup [backup_path]
  db restore [--dry-run <backup.dump> | --confirm-restore-tibiahub <backup.dump>]
  db reset [--dry-run | --confirm-reset-tibiahub]
  db provision [--dry-run | --confirm-provision-tibiahub]

Spatial:
  spatial verify --dry-run
  spatial rebuild [--dry-run | --execute --confirm-rebuild-spatial-links]

Services:
  services status
  services logs <service_name>
  services restart [--dry-run <service_name> | --confirm-restart-tibiahub <service_name>]

Admin:
  admin bootstrap --confirm-bootstrap-admin

Secrets:
  secrets verify
  secrets generate --confirm-generate-secrets

Deploy:
  deploy [--confirm-deploy] [--previous-commit <sha40>]
  deploy dry-run [--confirm-deploy]
  deploy status
  deploy history
  deploy rollback [<deployment-dir>] [--confirm-rollback]

Notes:
  --confirm-deploy only bypasses the non-standard branch approval guard.
  Normal deploys from an allowed branch do not require a confirmation flag.
  Rollback without a deployment directory uses the snapshot for the current deployment.

Media:
  media test --item-id <id> [--concurrency <n>] [--base-url <url>]
HELP
}

run_child() {
  local dry_run="$1"
  shift
  if [[ "$dry_run" == 1 ]]; then
    echo "[dry-run] $(ops_safe_command_name "$@")"
    return 0
  fi
  "$@"
}

require_confirm() {
  local expected="$1"
  local actual="${2:-}"
  if [[ "$actual" != "$expected" ]]; then
    ops_error "Missing confirmation flag: $expected"
    return 2
  fi
  return 0
}

cmd_help() {
  print_help
}

cmd_status() {
  echo "Branch: $(git -C "$ROOT" branch --show-current 2>/dev/null || echo unknown)"
  echo "Git status:"
  git -C "$ROOT" status -sb
  echo
  echo "Services:"
  pm2 jlist | jq -r '.[] | select(.name | startswith("tibiahub-")) | [.name, (.pm2_env.status // "unknown"), (.pid // 0)] | @tsv' | sed -e 's/\t/ | /g'
}

cmd_health() {
  local urls=(
    "http://127.0.0.1:8001/api/v1/health"
    "http://127.0.0.1:8001/api/v1/ready"
    "https://tibiahub.domoforge.com/api/v1/health"
    "https://tibiahub.domoforge.com/api/v1/ready"
  )
  local url
  for url in "${urls[@]}"; do
    echo "Checking $url"
    curl --silent --show-error --fail --max-time 10 "$url" >/dev/null
    echo "ok"
  done
}

cmd_diagnose() {
  cmd_status
  echo
  cmd_health
  echo
  bash "$ROOT/scripts/verify-postgres.sh"
}

cmd_db() {
  local sub="${1:-}"
  shift || true
  case "$sub" in
    status)
      load_tibiahub_environment
      TIBIAHUB_DATABASE_NAME=tibiahub require_local_tibiahub_target
      postgres_exec psql -X -A -t -c 'SELECT current_database(), current_user'
      ;;
    verify)
      local dry=0
      [[ "${1:-}" == "--dry-run" ]] && dry=1
      run_child "$dry" bash "$ROOT/scripts/verify-postgres.sh"
      ;;
    revision)
      local operation="${1:-current}"
      if [[ $# -gt 1 ]]; then
        ops_error "Usage: db revision [current|heads|history|check]"
        return 2
      fi
      case "$operation" in
        current|heads|history|check)
          run_alembic_read_only "$operation"
          ;;
        *)
          ops_error "Unknown db revision operation: $operation"
          ops_error "Usage: db revision [current|heads|history|check]"
          return 2
          ;;
      esac
      ;;
    migrate)
      if [[ "${1:-}" == "--dry-run" ]]; then
        [[ $# -eq 1 ]] || { ops_error "Usage: db migrate --dry-run | --confirm-migrate-tibiahub"; return 2; }
        run_child 1 run_alembic upgrade head
        return 0
      fi
      require_confirm "--confirm-migrate-tibiahub" "${1:-}" || return $?
      [[ $# -eq 1 ]] || { ops_error "Usage: db migrate --dry-run | --confirm-migrate-tibiahub"; return 2; }
      run_alembic upgrade head
      ;;
    backup)
      if [[ $# -ge 1 ]]; then
        bash "$ROOT/scripts/backup-postgres.sh" "$1"
      else
        bash "$ROOT/scripts/backup-postgres.sh"
      fi
      ;;
    restore)
      if [[ "${1:-}" == "--dry-run" ]]; then
        [[ $# -eq 2 ]] || { ops_error "Usage: db restore --dry-run <backup.dump> | --confirm-restore-tibiahub <backup.dump>"; return 2; }
        run_child 1 bash "$ROOT/scripts/restore-postgres.sh" --confirm-restore-tibiahub "$2"
        return 0
      fi
      require_confirm "--confirm-restore-tibiahub" "${1:-}" || return $?
      [[ $# -eq 2 ]] || { ops_error "Usage: db restore --confirm-restore-tibiahub <backup.dump>"; return 2; }
      bash "$ROOT/scripts/restore-postgres.sh" --confirm-restore-tibiahub "$2"
      ;;
    reset)
      if [[ "${1:-}" == "--dry-run" ]]; then
        [[ $# -eq 1 ]] || { ops_error "Usage: db reset --dry-run | --confirm-reset-tibiahub"; return 2; }
        run_child 1 bash "$ROOT/scripts/reset-postgres.sh" --confirm-reset-tibiahub
        return 0
      fi
      require_confirm "--confirm-reset-tibiahub" "${1:-}" || return $?
      [[ $# -eq 1 ]] || { ops_error "Usage: db reset --dry-run | --confirm-reset-tibiahub"; return 2; }
      bash "$ROOT/scripts/reset-postgres.sh" --confirm-reset-tibiahub
      ;;
    provision)
      if [[ "${1:-}" == "--dry-run" ]]; then
        [[ $# -eq 1 ]] || { ops_error "Usage: db provision --dry-run | --confirm-provision-tibiahub"; return 2; }
        run_child 1 bash "$ROOT/scripts/provision-postgres.sh" --confirm-provision-tibiahub
        return 0
      fi
      require_confirm "--confirm-provision-tibiahub" "${1:-}" || return $?
      [[ $# -eq 1 ]] || { ops_error "Usage: db provision --dry-run | --confirm-provision-tibiahub"; return 2; }
      bash "$ROOT/scripts/provision-postgres.sh" --confirm-provision-tibiahub
      ;;
    *)
      ops_error "Unknown db subcommand: $sub"
      return 2
      ;;
  esac
}

cmd_spatial() {
  local sub="${1:-}"
  shift || true
  case "$sub" in
    verify)
      [[ "${1:-}" == "--dry-run" ]] || { ops_error "Usage: spatial verify --dry-run"; return 2; }
      bash "$ROOT/scripts/verify-spatial-consistency.sh" --dry-run
      ;;
    rebuild)
      if [[ "${1:-}" == "--dry-run" ]]; then
        bash "$ROOT/scripts/rebuild-spatial-links.sh" --dry-run
      else
        [[ "${1:-}" == "--execute" && "${2:-}" == "--confirm-rebuild-spatial-links" ]] || {
          ops_error "Usage: spatial rebuild --dry-run | --execute --confirm-rebuild-spatial-links"
          return 2
        }
        bash "$ROOT/scripts/rebuild-spatial-links.sh" --execute --confirm-rebuild-spatial-links
      fi
      ;;
    *)
      ops_error "Unknown spatial subcommand: $sub"
      return 2
      ;;
  esac
}

cmd_services() {
  local sub="${1:-}"
  shift || true
  case "$sub" in
    status)
      pm2 jlist | jq -r '.[] | select(.name | startswith("tibiahub-")) | [.name, (.pm2_env.status // "unknown"), (.pid // 0)] | @tsv' | sed -e 's/\t/ | /g'
      ;;
    logs)
      [[ $# -eq 1 ]] || { ops_error "Usage: services logs <service_name>"; return 2; }
      pm2 logs "$1" --lines 100
      ;;
    restart)
      if [[ "${1:-}" == "--dry-run" ]]; then
        [[ $# -eq 2 ]] || { ops_error "Usage: services restart --dry-run <service_name> | --confirm-restart-tibiahub <service_name>"; return 2; }
        run_child 1 pm2 restart "$2"
        return 0
      fi
      [[ "${1:-}" == "--confirm-restart-tibiahub" && $# -eq 2 ]] || {
        ops_error "Usage: services restart --dry-run <service_name> | --confirm-restart-tibiahub <service_name>"
        return 2
      }
      pm2 restart "$2"
      ;;
    *)
      ops_error "Unknown services subcommand: $sub"
      return 2
      ;;
  esac
}

cmd_admin() {
  local sub="${1:-}"
  shift || true
  case "$sub" in
    bootstrap)
      require_confirm "--confirm-bootstrap-admin" "${1:-}" || return $?
      bash "$ROOT/scripts/bootstrap-admin.sh"
      ;;
    *)
      ops_error "Unknown admin subcommand: $sub"
      return 2
      ;;
  esac
}

cmd_secrets() {
  local sub="${1:-}"
  shift || true
  case "$sub" in
    verify)
      load_secure_file "$TIBIAHUB_RUNTIME_SECRETS_FILE" "TibiaHub runtime secret file"
      load_secure_file "$TIBIAHUB_PROVISION_SECRETS_FILE" "TibiaHub provisioning secret file"
      local bootstrap_file="${TIBIAHUB_BOOTSTRAP_SECRETS_FILE:-/forge/tibiahub-secrets/bootstrap.env}"
      load_secure_file "$bootstrap_file" "TibiaHub bootstrap secret file"
      echo "Secret files are present and secured."
      ;;
    generate)
      if [[ "${1:-}" == "--dry-run" ]]; then
        [[ $# -eq 1 ]] || { ops_error "Usage: secrets generate --dry-run | --confirm-generate-secrets"; return 2; }
        run_child 1 bash "$ROOT/scripts/generate-tibiahub-secrets.sh" --confirm-create-tibiahub-secrets
        return 0
      fi
      require_confirm "--confirm-generate-secrets" "${1:-}" || return $?
      [[ $# -eq 1 ]] || { ops_error "Usage: secrets generate --dry-run | --confirm-generate-secrets"; return 2; }
      bash "$ROOT/scripts/generate-tibiahub-secrets.sh" --confirm-create-tibiahub-secrets
      ;;
    *)
      ops_error "Unknown secrets subcommand: $sub"
      return 2
      ;;
  esac
}

deploy_root_dir() {
  printf '%s' "${TIBIAHUB_DEPLOY_ROOT:-/forge/tibiahub-backups/deployments}"
}

deploy_status() {
  local root_dir
  root_dir="$(deploy_root_dir)"
  [[ -d "$root_dir" ]] || { ops_error "Deploy root missing: $root_dir"; return 1; }
  echo "Deploy root: $root_dir"
  echo "Recent deployment evidence:"
  find "$root_dir" -mindepth 1 -maxdepth 1 -type d -name '20*' | sort | tail -n 5
  if [[ -f "$root_dir/current.env" ]]; then
    echo
    echo "Current deployment:"
    sed -n '1,100p' "$root_dir/current.env"
  fi
}

deploy_history() {
  local root_dir dir status target branch previous started
  root_dir="$(deploy_root_dir)"
  [[ -d "$root_dir" ]] || { ops_error "Deploy root missing: $root_dir"; return 1; }
  printf '%-36s %-10s %-14s %-12s %s\n' "DEPLOYMENT" "STATUS" "BRANCH" "COMMIT" "PREVIOUS"
  while IFS= read -r dir; do
    status="unknown"
    [[ -f "$dir/SUCCEEDED" ]] && status="succeeded"
    [[ -f "$dir/FAILED" ]] && status="failed"
    [[ -f "$dir/ROLLBACK_SUCCEEDED" || -f "$dir/rollback.env" ]] && status="rolledback"
    target="$(awk -F= '$1 == "target_commit" {print $2}' "$dir/metadata.env" 2>/dev/null || true)"
    branch="$(awk -F= '$1 == "target_branch" {print $2}' "$dir/metadata.env" 2>/dev/null || true)"
    previous="$(awk -F= '$1 == "previous_commit" {print $2}' "$dir/metadata.env" 2>/dev/null || true)"
    started="$(basename "$dir")"
    printf '%-36s %-10s %-14s %-12s %s\n' "$started" "$status" "${branch:-unknown}" "${target:0:12}" "${previous:0:12}"
  done < <(find "$root_dir" -mindepth 1 -maxdepth 1 -type d -name '20*' | sort -r | head -n 20)
}

deploy_run() {
  local dry_run="$1"
  shift
  local args=()
  local confirm_branch=0
  local previous_commit=""

  while (($#)); do
    case "$1" in
      --confirm-deploy)
        confirm_branch=1
        shift
        ;;
      --confirm-deploy-tibiahub)
        ops_warn "--confirm-deploy-tibiahub is deprecated; use --confirm-deploy only for non-standard branch approval."
        confirm_branch=1
        shift
        ;;
      --previous-commit)
        [[ $# -ge 2 ]] || { ops_error "--previous-commit requires a 40-character commit."; return 2; }
        previous_commit="$2"
        shift 2
        ;;
      --dry-run)
        dry_run=1
        shift
        ;;
      *)
        ops_error "Unknown deploy option: $1"
        return 2
        ;;
    esac
  done

  [[ "$dry_run" == 1 ]] && args+=(--dry-run)
  [[ "$confirm_branch" == 1 ]] && args+=(--confirm-deploy)
  [[ -n "$previous_commit" ]] && args+=(--previous-commit "$previous_commit")
  bash "$ROOT/deploy/scripts/deploy.sh" "${args[@]}"
}

deploy_rollback() {
  local root_dir evidence="" confirm=0 answer
  root_dir="$(deploy_root_dir)"

  while (($#)); do
    case "$1" in
      --confirm-rollback)
        confirm=1
        shift
        ;;
      --confirm-rollback-tibiahub)
        ops_warn "--confirm-rollback-tibiahub is deprecated; use --confirm-rollback."
        confirm=1
        shift
        ;;
      -* )
        ops_error "Unknown rollback option: $1"
        return 2
        ;;
      *)
        [[ -z "$evidence" ]] || { ops_error "Rollback accepts at most one deployment directory."; return 2; }
        evidence="$1"
        shift
        ;;
    esac
  done

  if [[ -z "$evidence" ]]; then
    [[ -f "$root_dir/current.env" ]] || {
      ops_error "No current deployment state exists. Pass a deployment directory from 'deploy history'."
      return 2
    }
    evidence="$(awk -F= '$1 == "snapshot_dir" {print $2}' "$root_dir/current.env")"
  elif [[ "$evidence" != /* ]]; then
    evidence="$root_dir/$evidence"
  fi

  [[ -n "$evidence" && -d "$evidence" ]] || {
    ops_error "Rollback deployment evidence not found: ${evidence:-unknown}"
    return 2
  }

  if [[ "$confirm" != 1 ]]; then
    if [[ -t 0 && -t 1 ]]; then
      ops_warn "Rollback will restore database, frontend, runtime and PM2 state from: $evidence"
      read -r -p "Continue with rollback? [y/N] " answer
      case "$answer" in
        y|Y|yes|YES) ;;
        *) ops_warn "Rollback cancelled."; return 1 ;;
      esac
    else
      ops_error "Rollback requires interactive approval or --confirm-rollback."
      return 2
    fi
  fi

  bash "$ROOT/deploy/scripts/rollback.sh" --confirm-rollback-tibiahub "$evidence"
}

cmd_deploy() {
  local action="${1:-}"
  case "$action" in
    "")
      deploy_run 0
      ;;
    dry-run)
      shift
      deploy_run 1 "$@"
      ;;
    status)
      shift
      [[ $# -eq 0 ]] || { ops_error "Usage: deploy status"; return 2; }
      deploy_status
      ;;
    history)
      shift
      [[ $# -eq 0 ]] || { ops_error "Usage: deploy history"; return 2; }
      deploy_history
      ;;
    rollback)
      shift
      deploy_rollback "$@"
      ;;
    preflight)
      shift
      [[ "${1:-}" == "--dry-run" ]] && shift
      ops_warn "'deploy preflight --dry-run' is deprecated; use 'deploy dry-run'."
      deploy_run 1 "$@"
      ;;
    run)
      shift
      ops_warn "'deploy run' is deprecated; use 'deploy'."
      deploy_run 0 "$@"
      ;;
    *)
      deploy_run 0 "$@"
      ;;
  esac
}

cmd_media() {
  local sub="${1:-}"
  shift || true
  case "$sub" in
    test)
      local item_id=""
      local concurrency=20
      local base_url="http://127.0.0.1:8001"
      while (($#)); do
        case "$1" in
          --item-id)
            item_id="$2"
            shift 2
            ;;
          --concurrency)
            concurrency="$2"
            shift 2
            ;;
          --base-url)
            base_url="$2"
            shift 2
            ;;
          *)
            ops_error "Unknown media test option: $1"
            return 2
            ;;
        esac
      done
      [[ -n "$item_id" ]] || { ops_error "media test requires --item-id <id>"; return 2; }
      seq 1 "$concurrency" | xargs -I{} -P"$concurrency" curl --silent --show-error --output /dev/null --write-out "%{http_code}\n" "$base_url/api/v1/items/$item_id/image"
      ;;
    *)
      ops_error "Unknown media subcommand: $sub"
      return 2
      ;;
  esac
}

main() {
  local command="${1:-help}"
  shift || true
  case "$command" in
    help|-h|--help) cmd_help ;;
    status) cmd_status ;;
    health) cmd_health ;;
    diagnose) cmd_diagnose ;;
    db) cmd_db "$@" ;;
    spatial) cmd_spatial "$@" ;;
    services) cmd_services "$@" ;;
    admin) cmd_admin "$@" ;;
    secrets) cmd_secrets "$@" ;;
    deploy) cmd_deploy "$@" ;;
    rollback) cmd_deploy rollback "$@" ;;
    media) cmd_media "$@" ;;
    *)
      ops_error "Unknown command: $command"
      print_help
      return 2
      ;;
  esac
}

main "$@"
