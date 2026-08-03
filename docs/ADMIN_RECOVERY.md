# Administrator recovery

Run administrator recovery from the repository root with the same environment
configuration used by the API. The command refuses a database whose configured
name is not `tibiahub`, displays only the database host and name, and verifies
the persisted password from a fresh session after commit.

Use a private password file inside a subshell so cleanup cannot terminate the
parent SSH or interactive shell:

```bash
(
  umask 077
  recovery_password_file=$(mktemp)
  trap 'rm -f -- "$recovery_password_file"' EXIT
  IFS= read -r -s -p 'New administrator password: ' recovery_password
  printf '\n'
  printf '%s\n' "$recovery_password" >"$recovery_password_file"
  unset recovery_password
  backend/venv/bin/python scripts/recover_admin.py \
    --identifier admin \
    --password-file "$recovery_password_file" \
    --confirm 'RECOVER TIBIAHUB ADMIN'
)
```

The password file must be an absolute, regular mode-0600 file. By default the
operation invalidates outstanding password-reset and email-verification tokens.
Use `--keep-one-time-tokens` only when that behavior is explicitly required.
The command returns nonzero if the update, activation, promotion, or fresh-session
password verification fails. It never prints a password or password hash.
