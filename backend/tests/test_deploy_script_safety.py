from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy-postgres-cutover.sh"
ROLLBACK = ROOT / "scripts" / "rollback-postgres-cutover.sh"
ENV_EXAMPLE = ROOT / "backend" / ".env.example"
README = ROOT / "README.md"
BACKEND_README = ROOT / "backend" / "README.md"
GENERATE_SECRETS = ROOT / "scripts" / "generate-tibiahub-secrets.sh"
PROVISION = ROOT / "scripts" / "provision-tibiahub-postgres.sh"
BACKUP = ROOT / "scripts" / "backup-tibiahub-postgres.sh"
RESTORE = ROOT / "scripts" / "restore-tibiahub-postgres.sh"
VERIFY = ROOT / "scripts" / "verify-postgres-cutover.sh"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_runtime_configuration_has_no_embedded_production_passwords():
    env_example = _text(ENV_EXAMPLE)
    readme = _text(README)
    backend_readme = _text(BACKEND_README)

    for text in (env_example, readme, backend_readme):
        assert "REDACTED" not in text
        assert "your_password" not in text
        assert "T1b1a" not in text
        assert "postgresql://postgres:" not in text
        assert "postgresql+psycopg2://postgres:" not in text


def test_provisioning_is_tibiahub_scoped_and_secret_file_driven():
    generate = _text(GENERATE_SECRETS)
    provision = _text(PROVISION)

    assert "/forge/tibiahub-secrets" in generate
    assert "/forge/tibiahub-secrets" in provision
    assert "TIBIAHUB_DB_PASSWORD" in provision
    assert "TIBIAHUB_DATABASE_NAME" in provision
    assert "TIBIAHUB_DATABASE_ROLE" in provision
    assert "TIBIAHUB_POSTGRES_ADMIN_MODE" in provision
    assert "credential_file" in provision
    assert "peer" in provision
    assert "createdb" not in provision
    assert "ALTER USER postgres" not in provision
    assert "ALTER ROLE postgres" not in provision
    assert "ALTER SYSTEM" not in provision
    assert "CREATE ROLE" in provision
    assert "LOGIN PASSWORD" in provision
    assert "CREATE DATABASE" in provision
    assert "WITH TEMPLATE template0 OWNER" in provision
    assert "FROM pg_database" in provision
    assert "FROM pg_roles" in provision
    assert "IF NOT EXISTS" not in provision
    assert "ALL PRIVILEGES ON DATABASE" in provision
    assert "ALTER DEFAULT PRIVILEGES" in provision
    assert "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public" in provision
    assert "GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public" in provision
    assert "OWNER TO" in provision
    assert "CREATE ON SCHEMA public" in provision
    assert "sslmode=require" not in provision
    assert "127.0.0.1" in provision


def test_secret_generation_never_prints_generated_credentials():
    generate = _text(GENERATE_SECRETS)

    assert "openssl rand" in generate
    assert "chmod 600" in generate
    assert "Created TibiaHub runtime, provisioning, and bootstrap secret files" in generate
    assert "echo \"Database password:" not in generate
    assert "echo \"Application secret:" not in generate
    assert "echo \"Bootstrap admin password:" not in generate
    assert "TIBIAHUB_POSTGRES_ADMIN_USER" in generate
    assert "TIBIAHUB_POSTGRES_ADMIN_PASSWORD" in generate
    assert "TIBIAHUB_POSTGRES_ADMIN_MODE" in generate
    assert "PGUSER" in generate
    assert "PGPASSWORD" in generate


def test_backup_and_restore_are_scoped_and_validated():
    backup = _text(BACKUP)
    restore = _text(RESTORE)

    assert "pg_dump" in backup
    assert "--format=custom" in backup
    assert "--file=\"$tmp_file\"" in backup
    assert "TIBIAHUB_BACKUP_DIR" in backup
    assert "tibiahub" in backup
    assert "postgres" not in backup.split("pg_dump", 1)[1].split("\n", 1)[0]
    assert "umask 077" in backup
    assert "chmod 700" in backup
    assert "chmod 600" in backup
    assert "TIBIAHUB_POSTGRES_ADMIN_MODE" in backup
    assert "credential_file" in backup
    assert "peer" in backup
    assert "sudo -u \"$peer_user\" pg_dump" in backup

    assert "pg_restore --list" in restore
    assert "--clean" in restore
    assert "--if-exists" in restore
    assert "--no-owner" in restore
    assert "--no-privileges" in restore
    assert "TIBIAHUB_RESTORE_CONFIRMATION" in restore
    assert "RESTORE_TIBIAHUB_DATABASE" in restore
    assert "TIBIAHUB_POSTGRES_ADMIN_MODE" in restore
    assert "credential_file" in restore
    assert "peer" in restore
    assert "sudo -u \"$peer_user\" pg_restore" in restore


def test_cutover_requires_backup_and_explicit_confirmation():
    deploy = _text(DEPLOY)

    assert "TIBIAHUB_CUTOVER_CONFIRMATION" in deploy
    assert "MIGRATE_TIBIAHUB_TO_POSTGRES" in deploy
    assert "060-backup-current-production" in deploy
    assert "backup_source_database" in deploy
    assert "verify_schema_not_empty" in deploy
    assert "sync_jobs" in deploy
    assert "070-restore-postgresql-target" in deploy
    assert "restore-postgres-cutover" in deploy
    assert "100-alembic-baseline-current" in deploy
    assert "120-verify-data-counts" in deploy
    assert "check_named_table_count" in deploy
    assert "tables_with_rows" in deploy
    assert "test -s \"$backup_artifact\"" in deploy
    assert "TIBIAHUB_POSTGRES_ADMIN_MODE" in deploy
    assert "load_provision_env" in deploy
    assert """if [[ "$postgres_admin_mode" == "peer" ]]""" in deploy
    assert "sudo -u \"$postgres_peer_user\" pg_restore" in deploy
    assert "bootstrap_check=" in deploy
    assert "fail_closed_with_maintenance" in deploy
    assert "TIBIAHUB_BOOTSTRAP_ADMIN_MODE" in deploy
    assert "180-bootstrap-admin" in deploy
    assert "create-admin.py" in deploy
    assert "already_has_app_tables" in deploy
    assert "allow_existing_target" in deploy
    assert "live_cutover_requested" in deploy
    assert "development-only" in deploy
    assert "runtime-only" in deploy


def test_cutover_stops_services_before_final_restore_and_starts_after_verification():
    deploy = _text(DEPLOY)

    stop_idx = deploy.index("200-stop-services")
    final_restore_idx = deploy.index("230-final-backup-and-restore")
    verify_idx = deploy.index("250-final-verification")
    start_idx = deploy.index("270-start-services")

    assert stop_idx < final_restore_idx < verify_idx < start_idx


def test_cutover_has_rollback_and_failure_maintenance_paths():
    deploy = _text(DEPLOY)
    rollback = _text(ROLLBACK)

    assert "activate_maintenance" in deploy
    assert "rollback_runtime" in deploy
    assert "trap on_exit EXIT" in deploy
    assert "pm2 start" in deploy
    assert "restart_api_readiness" in deploy
    assert "api_database_mode" in deploy
    assert "api_connection_source" in deploy
    assert "api_connection_fingerprint" in deploy

    assert "TIBIAHUB_ROLLBACK_CONFIRMATION" in rollback
    assert "ROLLBACK_TIBIAHUB_POSTGRES_CUTOVER" in rollback
    assert "activate_maintenance" in rollback
    assert "rollback_runtime" in rollback
    assert "040-restore-sqlite" in rollback


def test_verification_is_postgresql_specific_and_checks_user_flows():
    verify = _text(VERIFY)

    assert "database_mode" in verify
    assert "postgresql" in verify
    assert "sqlite" not in verify.lower().split("database_mode", 1)[1].split("\n", 3)[0]
    assert "/api/v1/health/ready" in verify
    assert "api_database_mode" in verify
    assert "api_connection_source" in verify
    assert "api_connection_fingerprint" in verify
    assert "DATABASE_URL" in verify
    assert "reset-password" in verify
    assert "register" in verify
    assert "login" in verify
    assert "profile" in verify


def test_backend_runtime_is_versioned_activated_and_rollback_safe():
    deploy = _text(DEPLOY)
    rollback = _text(ROLLBACK)
    ecosystem = _text(
        ROOT / "ecosystem.config.js"
    )
    postgres = _text(
        ROOT / "scripts" / "lib" / "postgres.sh"
    )
    requirements = _text(
        ROOT / "backend" / "requirements.txt"
    )

    assert "TIBIAHUB_RUNTIME_ROOT" in deploy
    assert "015-preflight-backend-runtime" in deploy
    assert "python3 -m venv" in deploy
    assert "pip check" in deploy
    assert ".requirements.sha256" in deploy
    assert "205-activate-backend-runtime" in deploy
    assert "previous_runtime" in deploy

    assert (
        deploy.index("015-preflight-backend-runtime")
        < deploy.index("200-stop-services")
    )
    assert (
        deploy.index("200-stop-services")
        < deploy.index("205-activate-backend-runtime")
        < deploy.index("210-alembic-upgrade")
    )

    assert "045-restore-backend-runtime" in rollback
    assert "previous_runtime" in rollback
    assert "runtime-current" in rollback

    # API plus raffle, knowledge, email, sync, and localization workers all run
    # from the versioned runtime symlink so cutover/rollback remains atomic.
    assert (
        ecosystem.count(
            "script: 'runtime-current/bin/python'"
        )
        == 6
    )
    assert "tibiahub-localization-worker" in ecosystem

    assert "tibiahub_runtime_dir" in postgres
    assert "TIBIAHUB_PYTHON_RUNTIME" in postgres
    assert "runtime-current/bin/python" in postgres

    assert "PyJWT[crypto]==2.13.0" in requirements
    assert "python-jose" not in requirements
