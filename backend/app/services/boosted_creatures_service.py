"""Current TibiaData boosted names projected onto exact local Creatures."""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Lock
from typing import Literal

from sqlalchemy.orm import Session

from app.models.creature import Creature
from app.models.media_asset import MediaAsset
from app.services import media_asset_service, tibia_api
from app.services.text_utils import normalize_search_text


logger = logging.getLogger(__name__)
BOOSTED_CACHE_TTL_SECONDS = 300
BoostedKind = Literal["creature", "boss"]


@dataclass(frozen=True)
class _CachedObservation:
    source_name: str
    observed_at: datetime
    expires_at: float


_CACHE_LOCK = Lock()
_BOOSTED_CACHE: dict[BoostedKind, _CachedObservation] = {}


def _reset_boosted_cache_for_tests() -> None:
    """Deterministically clear the bounded process cache for tests."""
    with _CACHE_LOCK:
        _BOOSTED_CACHE.clear()


async def _current_name(
    kind: BoostedKind,
    *,
    monotonic_now: float,
) -> tuple[str | None, datetime | None, bool]:
    with _CACHE_LOCK:
        cached = _BOOSTED_CACHE.get(kind)
        if cached and cached.expires_at > monotonic_now:
            return cached.source_name, cached.observed_at, True
        _BOOSTED_CACHE.pop(kind, None)

    fetch = (
        tibia_api.get_boosted_creature_name
        if kind == "creature"
        else tibia_api.get_boosted_boss_name
    )
    try:
        source_name = await fetch()
    except Exception:
        logger.warning("tibiadata_boosted_unavailable kind=%s", kind)
        return None, None, False

    observed_at = datetime.now(UTC)
    observation = _CachedObservation(
        source_name=source_name,
        observed_at=observed_at,
        expires_at=monotonic_now + BOOSTED_CACHE_TTL_SECONDS,
    )
    with _CACHE_LOCK:
        _BOOSTED_CACHE[kind] = observation
    return source_name, observed_at, True


def _unavailable_side() -> dict:
    return {
        "source_name": None,
        "resolution_state": "unavailable",
        "id": None,
        "canonical_id": None,
        "slug": None,
        "name": None,
        "media": {"status": "unavailable", "url": None},
    }


def _resolve_local(db: Session, source_name: str, *, is_boss: bool) -> dict:
    normalized_name = normalize_search_text(source_name)
    matches = (
        db.query(Creature)
        .filter(
            Creature.normalized_name == normalized_name,
            Creature.is_hidden.is_(False),
            Creature.is_boss.is_(is_boss),
        )
        .order_by(Creature.id.asc())
        .limit(2)
        .all()
    )
    if len(matches) != 1:
        return {
            **_unavailable_side(),
            "source_name": source_name,
            "resolution_state": "unresolved",
        }

    creature = matches[0]
    asset_key = media_asset_service.build_creature_asset_key(creature)
    asset = db.query(MediaAsset).filter(MediaAsset.asset_key == asset_key).first()
    media_available = bool(
        asset
        and asset.status == "cached"
        and asset.file_exists()
    )
    return {
        "source_name": source_name,
        "resolution_state": "resolved",
        "id": creature.id,
        "canonical_id": creature.knowledge_entity_id,
        "slug": creature.slug,
        "name": creature.name,
        "media": {
            "status": "available" if media_available else "unavailable",
            "url": (
                f"/api/v1/creatures/{creature.id}/image?placeholder=false"
                if media_available
                else None
            ),
        },
    }


async def get_boosted_projection(db: Session) -> dict:
    """Fetch both current facts independently and resolve exact local records."""
    monotonic_now = time.monotonic()
    creature_result, boss_result = await asyncio.gather(
        _current_name("creature", monotonic_now=monotonic_now),
        _current_name("boss", monotonic_now=monotonic_now),
    )
    creature_name, creature_observed_at, creature_current = creature_result
    boss_name, boss_observed_at, boss_current = boss_result

    creature = (
        _resolve_local(db, creature_name, is_boss=False)
        if creature_current and creature_name
        else _unavailable_side()
    )
    boss = (
        _resolve_local(db, boss_name, is_boss=True)
        if boss_current and boss_name
        else _unavailable_side()
    )
    successful_observations = [
        value
        for value in (creature_observed_at, boss_observed_at)
        if value is not None
    ]
    if not successful_observations:
        status = "unavailable"
    elif (
        creature_current
        and boss_current
        and creature["resolution_state"] == "resolved"
        and boss["resolution_state"] == "resolved"
    ):
        status = "available"
    else:
        status = "partial"

    return {
        "status": status,
        "source": "tibiadata",
        "observed_at": max(successful_observations) if successful_observations else None,
        "creature": creature,
        "boss": boss,
    }
