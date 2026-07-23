#!/usr/bin/env python3
"""Execute a libpq command with credentials supplied only through its environment."""
from __future__ import annotations

import os
import sys

from app.core.config import settings


def postgres_environment() -> dict[str, str]:
    url = settings.database_url
    if url.get_backend_name() != "postgresql":
        raise SystemExit("TibiaHub PostgreSQL command refused a non-PostgreSQL target")
    environment = os.environ.copy()
    values = {
        "PGHOST": url.host or "localhost",
        "PGPORT": str(url.port or 5432),
        "PGUSER": url.username or "",
        "PGPASSWORD": url.password or "",
        "PGDATABASE": url.database or "",
    }
    if not values["PGUSER"] or not values["PGDATABASE"]:
        raise SystemExit("TibiaHub PostgreSQL command requires a database and application role")
    environment.update(values)
    return environment


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: postgres-command.py command [argument ...]")
    os.execvpe(sys.argv[1], sys.argv[1:], postgres_environment())


if __name__ == "__main__":
    main()
