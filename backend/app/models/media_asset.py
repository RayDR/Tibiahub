"""MediaAsset — locally-cached media files with deduplication by asset_key."""
from pathlib import Path
from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from app.db.database import Base


class MediaAsset(Base):
    """
    Content-addressed media cache.

    Multiple creatures/items can reference the same MediaAsset via asset_key.
    For example, "Angry Demon" and "Demon Outcast" both use asset_key
    "creature:demon" when their image_alias is set to "Demon".

    asset_key format:
        creature:{normalized_name_or_alias}
        item:{normalized_name_or_alias}
        zone:{normalized_name}
    """
    __tablename__ = "media_assets"

    id = Column(Integer, primary_key=True, index=True)
    # Unique deduplication key.  Multiple entities share the same key → same file.
    asset_key = Column(String(255), unique=True, nullable=False, index=True)
    source_url = Column(String(1024), nullable=True)
    resolved_url = Column(String(1024), nullable=True)
    local_path = Column(String(1024), nullable=True)
    content_type = Column(String(100), nullable=True)
    size_bytes = Column(Integer, nullable=True)
    sha256_hash = Column(String(64), nullable=True)
    width = Column(Integer, nullable=True)   # future: image dimensions
    height = Column(Integer, nullable=True)
    # cached | missing | failed | pending
    status = Column(String(20), nullable=False, default="pending")
    error_message = Column(Text, nullable=True)
    last_fetched_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # ── helpers ──────────────────────────────────────────────────────────────

    def file_exists(self) -> bool:
        if not self.local_path:
            return False
        return Path(self.local_path).exists()

    def read_bytes(self) -> bytes | None:
        if not self.file_exists():
            return None
        try:
            return Path(self.local_path).read_bytes()
        except OSError:
            return None
