#!/usr/bin/env python3
"""Print a single non-secret component of TibiaHub's configured database."""
from __future__ import annotations

import sys

from app.core.config import settings


COMPONENTS = {
    "dialect": settings.database_url.get_backend_name(),
    "host": settings.database_url.host or "localhost",
    "name": settings.database_name,
    "port": str(settings.database_url.port or 5432),
    "user": settings.database_url.username or "",
}

if len(sys.argv) != 2 or sys.argv[1] not in COMPONENTS:
    raise SystemExit("usage: postgres-target.py dialect|host|name|port|user")
print(COMPONENTS[sys.argv[1]])
