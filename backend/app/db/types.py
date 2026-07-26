"""Database column types shared by all models."""
from sqlalchemy import JSON, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import UserDefinedType


# PostgreSQL stores queryable application payloads as JSONB. The generic JSON
# variant remains available solely for isolated SQLite unit tests.
JSONBType = JSON().with_variant(JSONB(), "postgresql")


class PostGISGeometry(UserDefinedType):
    """PostGIS type declaration without requiring runtime geometry decoding."""

    cache_ok = True

    def __init__(self, geometry_type: str):
        self.geometry_type = geometry_type

    def get_col_spec(self, **_kw) -> str:
        return f"geometry({self.geometry_type},0)"


def geometry_column_type(geometry_type: str):
    """Use PostGIS in PostgreSQL and inert text in isolated SQLite unit tests."""
    return PostGISGeometry(geometry_type).with_variant(Text(), "sqlite")
