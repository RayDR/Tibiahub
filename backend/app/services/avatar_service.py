"""Validated, metadata-free account avatar processing outside the source tree."""

from __future__ import annotations

import io
import os
import re
import secrets
from pathlib import Path

from PIL import Image, ImageOps

from app.core.config import settings
from app.services.media_asset_service import UnsafeMediaError, validate_raster_image


_KEY = re.compile(r"^[A-Za-z0-9_-]{32,80}$")


class AvatarService:
    @staticmethod
    def root() -> Path:
        root = Path(settings.AVATAR_STORAGE_ROOT)
        if not root.is_absolute() or root.is_symlink():
            raise UnsafeMediaError("Avatar storage is unavailable")
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(root, 0o700)
        return root.resolve()

    @staticmethod
    def process(content: bytes, declared_content_type: str | None) -> tuple[str, dict[int, bytes]]:
        if len(content) > settings.AVATAR_MAX_BYTES:
            raise UnsafeMediaError("The image exceeds the maximum allowed size")
        validate_raster_image(content, declared_content_type)
        try:
            with Image.open(io.BytesIO(content)) as source:
                oriented = ImageOps.exif_transpose(source)
                if oriented.mode not in {"RGB", "RGBA"}:
                    oriented = oriented.convert("RGBA")
                if oriented.mode == "RGBA":
                    background = Image.new("RGB", oriented.size, (15, 23, 42))
                    background.paste(oriented, mask=oriented.getchannel("A"))
                    oriented = background
                else:
                    oriented = oriented.convert("RGB")
                outputs: dict[int, bytes] = {}
                for size in (256, 64):
                    square = ImageOps.fit(oriented, (size, size), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
                    buffer = io.BytesIO()
                    square.save(buffer, format="WEBP", quality=86, method=6, exif=b"", icc_profile=None)
                    outputs[size] = buffer.getvalue()
        except (OSError, ValueError, Image.DecompressionBombError) as exc:
            raise UnsafeMediaError("Invalid image data") from exc
        return secrets.token_urlsafe(32), outputs

    @staticmethod
    def store(key: str, outputs: dict[int, bytes]) -> None:
        if not _KEY.fullmatch(key):
            raise UnsafeMediaError("Invalid avatar key")
        root = AvatarService.root()
        created: list[Path] = []
        try:
            for size, content in outputs.items():
                temporary = root / f".{key}-{size}-{secrets.token_hex(6)}.tmp"
                target = root / f"{key}-{size}.webp"
                temporary.write_bytes(content)
                os.chmod(temporary, 0o600)
                os.replace(temporary, target)
                created.append(target)
        except Exception:
            for path in created:
                path.unlink(missing_ok=True)
            raise

    @staticmethod
    def path(key: str, size: int) -> Path | None:
        if size not in {64, 256} or not _KEY.fullmatch(key):
            return None
        root = AvatarService.root()
        target = (root / f"{key}-{size}.webp").resolve()
        if target.parent != root:
            return None
        return target if target.is_file() else None

    @staticmethod
    def remove(key: str | None) -> None:
        if not key or not _KEY.fullmatch(key):
            return
        root = AvatarService.root()
        for size in (64, 256):
            target = (root / f"{key}-{size}.webp").resolve()
            if target.parent == root:
                target.unlink(missing_ok=True)

    @staticmethod
    def url(key: str | None, size: int = 256) -> str | None:
        return f"/api/v1/profile/avatars/{key}/{size}.webp" if key and _KEY.fullmatch(key) else None
