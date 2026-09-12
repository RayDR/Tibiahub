#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import shutil
import stat
import struct
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath


REPO = Path(__file__).resolve().parents[1]

EXPECTED_ROOT_HINTS = {
    "page-titles",
    "logos",
    "icons",
    "module-assets",
    "ui-concepts",
    "docs",
}

MAPPINGS = [
    (
        "page-titles",
        "frontend/src/assets/brand/page-titles",
    ),
    (
        "logos/main",
        "frontend/src/assets/brand/logo/main",
    ),
    (
        "logos/alternates",
        "frontend/src/assets/brand/logo/alternates",
    ),
    (
        "icons/navigation",
        "frontend/src/assets/brand/navigation",
    ),
    (
        "icons/sections",
        "frontend/src/assets/brand/sections",
    ),
    (
        "module-assets",
        "frontend/src/assets/brand/modules",
    ),
    (
        "ui-concepts",
        "docs/brand/reference-boards/ui-concepts",
    ),
    (
        "docs",
        "docs/brand/source-kit",
    ),
]

ALLOWED_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".svg",
    ".gif",
    ".avif",
    ".ico",
    ".txt",
    ".md",
    ".json",
}

MAX_UNCOMPRESSED_SIZE = 2 * 1024 * 1024 * 1024
MAX_FILE_SIZE = 200 * 1024 * 1024


def sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def png_dimensions(path: Path):
    if path.suffix.lower() != ".png":
        return None

    try:
        with path.open("rb") as handle:
            signature = handle.read(8)

            if signature != b"\x89PNG\r\n\x1a\n":
                return None

            length = struct.unpack(">I", handle.read(4))[0]
            chunk_type = handle.read(4)

            if chunk_type != b"IHDR" or length < 8:
                return None

            width, height = struct.unpack(">II", handle.read(8))
            return width, height
    except Exception:
        return None


def safe_extract(zip_path: Path, destination: Path) -> None:
    with zipfile.ZipFile(zip_path) as archive:
        total = sum(info.file_size for info in archive.infolist())

        if total > MAX_UNCOMPRESSED_SIZE:
            raise RuntimeError(
                f"ZIP expands to {total / 1024 / 1024:.1f} MB; "
                "automatic extraction refused."
            )

        for info in archive.infolist():
            member = PurePosixPath(info.filename)

            if member.is_absolute() or ".." in member.parts:
                raise RuntimeError(
                    f"Unsafe ZIP path: {info.filename}"
                )

            file_type = (info.external_attr >> 16) & 0o170000

            if file_type == stat.S_IFLNK:
                raise RuntimeError(
                    f"Symlinks are not accepted: {info.filename}"
                )

            target = destination.joinpath(*member.parts)

            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue

            if info.file_size > MAX_FILE_SIZE:
                raise RuntimeError(
                    f"File exceeds safety limit: {info.filename}"
                )

            target.parent.mkdir(parents=True, exist_ok=True)

            with archive.open(info) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output)


def locate_kit_root(extracted: Path) -> Path:
    candidates = []

    for path in [extracted, *extracted.rglob("*")]:
        if not path.is_dir():
            continue

        children = {
            child.name
            for child in path.iterdir()
            if child.is_dir()
        }

        score = len(children & EXPECTED_ROOT_HINTS)

        if score >= 4:
            candidates.append((score, len(path.parts), path))

    if not candidates:
        raise RuntimeError(
            "Could not identify TibiaHub Brand Kit root."
        )

    candidates.sort(
        key=lambda row: (-row[0], row[1])
    )

    return candidates[0][2]


def should_ignore(path: Path) -> bool:
    ignored = {
        "__MACOSX",
        ".DS_Store",
        "Thumbs.db",
        "desktop.ini",
    }

    return any(
        part in ignored or part.startswith("._")
        for part in path.parts
    )


def copy_directory(
    kit_root: Path,
    source_relative: str,
    destination_relative: str,
):
    source = kit_root / source_relative
    destination = REPO / destination_relative

    imported = []
    skipped = []

    if not source.exists():
        return imported, skipped, False

    for item in sorted(source.rglob("*")):
        if not item.is_file():
            continue

        relative = item.relative_to(source)

        if should_ignore(relative):
            continue

        extension = item.suffix.lower()

        if extension not in ALLOWED_EXTENSIONS:
            skipped.append(
                (
                    str(Path(source_relative) / relative),
                    f"unsupported extension {extension}",
                )
            )
            continue

        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)

        shutil.copy2(item, target)

        dimensions = png_dimensions(target)

        imported.append(
            {
                "source": str(
                    Path(source_relative) / relative
                ),
                "destination": str(
                    Path(destination_relative) / relative
                ),
                "size": target.stat().st_size,
                "dimensions": (
                    f"{dimensions[0]}×{dimensions[1]}"
                    if dimensions
                    else "—"
                ),
                "sha256": sha256(target),
            }
        )

    return imported, skipped, True


def write_inventory(
    zip_path: Path,
    kit_root: Path,
    imported,
    skipped,
    missing,
):
    destination = REPO / "docs/brand/asset-inventory.md"
    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    lines = [
        "# TibiaHub Brand Asset Inventory",
        "",
        "Generated by `scripts/import-brand-kit.py`.",
        "",
        f"Source ZIP: `{zip_path.name}`",
        f"Detected kit root: `{kit_root.name}`",
        "",
        f"Imported assets: **{len(imported)}**",
        "",
        "## Imported files",
        "",
        "| Destination | Source | Dimensions | Size | SHA-256 |",
        "| --- | --- | ---: | ---: | --- |",
    ]

    for row in imported:
        lines.append(
            f"| `{row['destination']}` "
            f"| `{row['source']}` "
            f"| {row['dimensions']} "
            f"| {row['size']} B "
            f"| `{row['sha256']}` |"
        )

    if skipped:
        lines += [
            "",
            "## Skipped",
            "",
        ]

        for filename, reason in skipped:
            lines.append(
                f"- `{filename}` — {reason}"
            )

    if missing:
        lines += [
            "",
            "## Missing expected directories",
            "",
        ]

        for directory in missing:
            lines.append(
                f"- `{directory}`"
            )

    lines += [
        "",
        "## Runtime asset groups",
        "",
        "- `frontend/src/assets/brand/page-titles/`",
        "- `frontend/src/assets/brand/logo/`",
        "- `frontend/src/assets/brand/navigation/`",
        "- `frontend/src/assets/brand/sections/`",
        "- `frontend/src/assets/brand/modules/`",
        "",
        "## Reference-only material",
        "",
        "- `docs/brand/reference-boards/ui-concepts/`",
        "- `docs/brand/source-kit/`",
        "",
        "No existing application references are modified by the importer.",
        "",
    ]

    destination.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def main() -> int:
    if len(sys.argv) != 2:
        print(
            "Usage: scripts/import-brand-kit.py "
            "/path/to/TibiaHub_Brand_Kit.zip"
        )
        return 2

    zip_path = Path(
        sys.argv[1]
    ).expanduser().resolve()

    if not zip_path.is_file():
        print(
            f"ERROR: ZIP not found: {zip_path}"
        )
        return 2

    imported = []
    skipped = []
    missing = []

    with tempfile.TemporaryDirectory(
        prefix="tibiahub-brand-import-"
    ) as temp:
        extracted = Path(temp) / "extracted"
        extracted.mkdir()

        print(
            f"Validating and extracting: {zip_path}"
        )

        safe_extract(
            zip_path,
            extracted,
        )

        kit_root = locate_kit_root(
            extracted
        )

        print(
            f"Detected Brand Kit root: {kit_root.name}"
        )
        print()

        for (
            source_relative,
            destination_relative,
        ) in MAPPINGS:
            copied, ignored, exists = copy_directory(
                kit_root,
                source_relative,
                destination_relative,
            )

            if not exists:
                missing.append(
                    source_relative
                )
                print(
                    f"MISS  {source_relative}"
                )
                continue

            imported.extend(copied)
            skipped.extend(ignored)

            print(
                f"OK    {source_relative:<24} "
                f"-> {destination_relative} "
                f"({len(copied)} files)"
            )

        write_inventory(
            zip_path,
            kit_root,
            imported,
            skipped,
            missing,
        )

    print()
    print(
        "=== TibiaHub Brand Kit import complete ==="
    )
    print(
        f"Imported: {len(imported)}"
    )
    print(
        f"Skipped:  {len(skipped)}"
    )
    print(
        f"Missing:  {len(missing)}"
    )
    print()
    print(
        "Inventory: docs/brand/asset-inventory.md"
    )
    print()
    print(
        "No existing application source file was modified."
    )
    print(
        "No git add, commit, push, or branch operation was performed."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
