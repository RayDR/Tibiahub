#!/usr/bin/env bash

# Shared operational helpers.
# This file is intended to be sourced by entrypoint scripts.

if [[ "${_TIBIAHUB_OPS_COMMON_SH_LOADED:-0}" == "1" ]]; then
  return 0
fi
_TIBIAHUB_OPS_COMMON_SH_LOADED=1

ops_now_utc() {
  date -u +"%Y%m%dT%H%M%SZ"
}

ops_log() {
  local level="$1"
  shift
  printf '%s [%s] %s\n' "$(ops_now_utc)" "$level" "$*" >&2
}

ops_info() { ops_log INFO "$*"; }
ops_warn() { ops_log WARN "$*"; }
ops_error() { ops_log ERROR "$*"; }

ops_refuse_if_sourced_entrypoint() {
  local script_name="$1"
  if [[ "${BASH_SOURCE[1]}" != "$0" ]]; then
    ops_error "$script_name must be executed, not sourced."
    return 1
  fi
  return 0
}

ops_require_commands() {
  local missing=0
  local command_name
  for command_name in "$@"; do
    if ! command -v "$command_name" >/dev/null 2>&1; then
      ops_error "Required command is unavailable: $command_name"
      missing=1
    fi
  done
  if [[ "$missing" -ne 0 ]]; then
    return 2
  fi
  return 0
}

ops_safe_command_name() {
  local argv=()
  local arg
  for arg in "$@"; do
    argv+=("$(printf '%q' "$arg")")
  done
  printf '%s' "${argv[*]}"
}

ops_redact_text() {
  # Redact credentials in URL authority segments.
  sed -E 's#(postgresql(\+[a-z0-9_]+)?://)[^/@:]+(:[^/@]*)?@#\1***:***@#g'
}

ops_write_failure_record() {
  local failure_file="$1"
  local exit_code="$2"
  local failed_step="$3"
  local failed_line="$4"
  local failed_function="$5"
  local failed_command="$6"
  local stdout_log="$7"
  local stderr_log="$8"

  {
    printf 'failed_at=%s\n' "$(ops_now_utc)"
    printf 'exit_code=%s\n' "$exit_code"
    printf 'failed_step=%q\n' "$failed_step"
    printf 'failed_line=%s\n' "$failed_line"
    printf 'failed_function=%q\n' "$failed_function"
    printf 'failed_command=%q\n' "$failed_command"
    printf 'stdout_log=%q\n' "$stdout_log"
    printf 'stderr_log=%q\n' "$stderr_log"
  } >"$failure_file"
}

ops_run_deploy_step() {
  local evidence_dir="$1"
  local step_name="$2"
  shift 2

  if [[ $# -eq 0 ]]; then
    ops_error "ops_run_deploy_step requires a command"
    return 2
  fi

  local steps_dir="$evidence_dir/steps"
  mkdir -p "$steps_dir" || return 1

  local stdout_log="$steps_dir/${step_name}.out.log"
  local stderr_log="$steps_dir/${step_name}.err.log"
  local meta_log="$steps_dir/${step_name}.meta.env"
  local command_preview
  command_preview="$(ops_safe_command_name "$@")"

  local started_epoch
  started_epoch="$(date -u +%s)"
  local started_at
  started_at="$(ops_now_utc)"

  local status
  if "$@" >"$stdout_log" 2>"$stderr_log"; then
    status=0
  else
    status=$?
  fi

  local finished_epoch
  finished_epoch="$(date -u +%s)"
  local finished_at
  finished_at="$(ops_now_utc)"
  local duration_seconds=$((finished_epoch - started_epoch))

  {
    printf 'step_name=%q\n' "$step_name"
    printf 'started_at=%s\n' "$started_at"
    printf 'finished_at=%s\n' "$finished_at"
    printf 'duration_seconds=%s\n' "$duration_seconds"
    printf 'exit_status=%s\n' "$status"
    printf 'command=%q\n' "$command_preview"
    printf 'stdout_log=%q\n' "$stdout_log"
    printf 'stderr_log=%q\n' "$stderr_log"
  } >"$meta_log"

  OPS_LAST_STEP_NAME="$step_name"
  OPS_LAST_STEP_STATUS="$status"
  OPS_LAST_STEP_STDOUT="$stdout_log"
  OPS_LAST_STEP_STDERR="$stderr_log"

  return "$status"
}
