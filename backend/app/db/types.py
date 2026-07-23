"""Database column types shared by all models."""
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB


# PostgreSQL stores queryable application payloads as JSONB. The generic JSON
# variant remains available solely for isolated SQLite unit tests.
JSONBType = JSON().with_variant(JSONB(), "postgresql")
