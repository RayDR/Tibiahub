#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.creature_category_service import (
    CANONICAL_CREATURE_CATEGORIES,
)


def category_key(value: str) -> str:
    result = []
    separator = False

    for char in value.strip().lower():
        if char.isalnum():
            result.append(char)
            separator = False
        elif not separator:
            result.append("_")
            separator = True

    return "".join(result).strip("_")


def fetch_json(
    base_url: str,
    path: str,
    *,
    params: dict | None = None,
    timeout: float = 10,
):
    url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"

    if params:
        url += "?" + urlencode(params)

    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "tibiahub-cyclopedia-smoke/1.0",
        },
    )

    with urlopen(request, timeout=timeout) as response:
        if response.status != 200:
            raise RuntimeError(
                f"{url} returned HTTP {response.status}"
            )

        return json.loads(
            response.read().decode("utf-8")
        )


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8001/api/v1",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10,
    )
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    timeout = args.timeout

    print(f"base_url={base_url}")

    health = fetch_json(
        base_url,
        "health",
        timeout=timeout,
    )
    require(
        isinstance(health, dict),
        "Health response is not an object",
    )
    print("health=ok")

    ready = fetch_json(
        base_url,
        "ready",
        timeout=timeout,
    )
    require(
        isinstance(ready, dict),
        "Readiness response is not an object",
    )
    print("ready=ok")

    counts = fetch_json(
        base_url,
        "creatures/category-counts",
        timeout=timeout,
    )
    require(
        isinstance(counts, dict),
        "Category counts response is not an object",
    )

    canonical_keys = {
        category_key(category)
        for category in CANONICAL_CREATURE_CATEGORIES
    }
    expected_count_keys = canonical_keys | {"all"}
    returned_count_keys = set(counts)

    missing = expected_count_keys - returned_count_keys
    extra = returned_count_keys - expected_count_keys

    require(
        not missing,
        f"Missing category count keys: {sorted(missing)}",
    )
    require(
        not extra,
        f"Unexpected category count keys: {sorted(extra)}",
    )
    require(
        "beast" not in counts,
        "Legacy Beast category leaked into counts",
    )

    total = int(counts["all"])
    categorized = sum(
        int(counts[key])
        for key in canonical_keys
    )
    unresolved = total - categorized

    require(
        unresolved >= 0,
        "Category counts exceed visible creature total",
    )

    print(
        f"creatures_total={total} "
        f"categorized={categorized} "
        f"unresolved={unresolved}"
    )

    images = fetch_json(
        base_url,
        "creatures/category-images",
        timeout=timeout,
    )
    require(
        isinstance(images, dict),
        "Category images response is not an object",
    )
    require(
        set(images).issubset(canonical_keys),
        "Category images contain non-canonical keys: "
        f"{sorted(set(images) - canonical_keys)}",
    )
    require(
        "beast" not in images,
        "Legacy Beast category leaked into media",
    )
    print(f"category_images={len(images)}")

    previews = fetch_json(
        base_url,
        "creatures/category-previews",
        timeout=timeout,
    )
    require(
        isinstance(previews, dict),
        "Category previews response is not an object",
    )
    require(
        set(previews).issubset(canonical_keys),
        "Category previews contain non-canonical keys: "
        f"{sorted(set(previews) - canonical_keys)}",
    )
    print(f"category_previews={len(previews)}")

    checked_categories = 0

    for category in CANONICAL_CREATURE_CATEGORIES:
        key = category_key(category)

        if int(counts[key]) <= 0:
            continue

        rows = fetch_json(
            base_url,
            "creatures/",
            params={
                "category": category,
                "is_boss": "false",
                "skip": 0,
                "limit": 1,
            },
            timeout=timeout,
        )

        require(
            isinstance(rows, list) and len(rows) > 0,
            f"{category} has count but no query result",
        )

        checked_categories += 1

    print(
        f"category_filters_checked={checked_categories}"
    )

    probes = (
        (
            "creatures",
            "creatures/",
            {
                "is_boss": "false",
                "skip": 0,
                "limit": 1,
            },
        ),
        (
            "bosses",
            "creatures/bosses",
            {
                "skip": 0,
                "limit": 1,
            },
        ),
        (
            "items",
            "items/",
            {
                "skip": 0,
                "limit": 1,
            },
        ),
        (
            "quests",
            "quests/",
            {
                "skip": 0,
                "limit": 1,
            },
        ),
        (
            "hunt_zones",
            "hunt-zones/",
            {
                "skip": 0,
                "limit": 1,
            },
        ),
    )

    for name, path, params in probes:
        payload = fetch_json(
            base_url,
            path,
            params=params,
            timeout=timeout,
        )

        require(
            isinstance(payload, list),
            f"{name} response is not a list",
        )

        print(
            f"{name}=ok sample_count={len(payload)}"
        )

    print("cyclopedia_smoke=passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
