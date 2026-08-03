"""Transactional synchronization of the canonical TibiaData guild roster."""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import Awaitable, Callable

from sqlalchemy.orm import Session, selectinload

from app.models.guild_management import GuildRosterCharacter
from app.models.user import User
from app.models.user_character import UserCharacter
from app.services.character_ownership_service import normalize_character_name
from app.services.tibia_api import get_character_info, get_guild_info


def normalize_guild_identity(value: str) -> str:
    return " ".join((value or "").split()).casefold()


def parse_activity_timestamp(value) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


@dataclass(frozen=True)
class GuildRosterSyncResult:
    guild_name: str
    world_name: str
    total: int
    inserted: int
    updated: int
    departed: int
    linked: int
    unlinked: int
    synchronized_at: datetime

    def to_dict(self) -> dict:
        return asdict(self)


class GuildRosterSyncError(RuntimeError):
    """Raised before any roster mutation when the authoritative fetch fails."""


class GuildRosterService:
    ENRICH_CONCURRENCY = 8
    ENRICH_TTL = timedelta(hours=6)

    @classmethod
    async def synchronize(
        cls,
        db: Session,
        guild_name: str,
        *,
        guild_fetcher: Callable[[str], Awaitable[dict | None]] = get_guild_info,
        character_fetcher: Callable[[str], Awaitable[dict | None]] = get_character_info,
    ) -> GuildRosterSyncResult:
        """Fetch completely, then update the roster in one caller-owned transaction."""
        try:
            guild = await guild_fetcher(guild_name)
        except Exception as exc:
            raise GuildRosterSyncError("TibiaData guild roster is temporarily unavailable") from exc
        if not guild or not guild.get("name") or not guild.get("world") or not isinstance(guild.get("members"), list):
            raise GuildRosterSyncError("TibiaData returned an incomplete guild roster")

        canonical_guild = str(guild["name"]).strip()
        world = str(guild["world"]).strip()
        guild_key = normalize_guild_identity(canonical_guild)
        world_key = normalize_guild_identity(world)
        raw_members = [member for member in guild["members"] if str(member.get("name") or "").strip()]
        now = datetime.now(UTC)

        existing = db.query(GuildRosterCharacter).filter(
            GuildRosterCharacter.normalized_guild_name == guild_key,
            GuildRosterCharacter.normalized_world_name == world_key,
        ).all()
        existing_by_name = {row.normalized_character_name: row for row in existing}

        semaphore = asyncio.Semaphore(cls.ENRICH_CONCURRENCY)

        async def enrich(member: dict) -> tuple[dict, dict | None]:
            name = str(member.get("name") or "").strip()
            old = existing_by_name.get(normalize_character_name(name))
            direct_activity = member.get("last_login") or member.get("lastlogin")
            previous_sync = parse_activity_timestamp(old.last_synchronized_at) if old else None
            recently_enriched = bool(previous_sync and now - previous_sync < cls.ENRICH_TTL)
            if direct_activity or recently_enriched:
                return member, None
            try:
                async with semaphore:
                    return member, await character_fetcher(name)
            except Exception:
                # Membership data remains authoritative; retain last good activity.
                return member, None

        enriched = await asyncio.gather(*(enrich(member) for member in raw_members))
        names = {normalize_character_name(str(member.get("name") or "")) for member, _ in enriched}
        verified = db.query(UserCharacter).filter(
            UserCharacter.normalized_name.in_(names),
            UserCharacter.ownership_status == "verified",
        ).all() if names else []
        verified_by_name = {row.normalized_name: row for row in verified}

        inserted = updated = linked = unlinked = 0
        current_names: set[str] = set()
        for member, detail in enriched:
            name = str(member.get("name") or "").strip()
            normalized_name = normalize_character_name(name)
            current_names.add(normalized_name)
            row = existing_by_name.get(normalized_name)
            if row is None:
                row = GuildRosterCharacter(
                    guild_name=canonical_guild,
                    normalized_guild_name=guild_key,
                    world_name=world,
                    normalized_world_name=world_key,
                    character_name=name,
                    normalized_character_name=normalized_name,
                    first_synchronized_at=now,
                )
                db.add(row)
                inserted += 1
            else:
                updated += 1

            activity = parse_activity_timestamp(
                member.get("last_login") or member.get("lastlogin")
                or (detail or {}).get("last_login_at") or (detail or {}).get("last_login")
            )
            verified_character = verified_by_name.get(normalized_name)
            row.character_name = str((detail or {}).get("name") or name).strip()
            row.guild_rank = member.get("rank") or member.get("title") or member.get("position")
            row.level = member.get("level") or (detail or {}).get("level") or row.level
            row.vocation = member.get("vocation") or (detail or {}).get("vocation") or row.vocation
            row.last_activity_at = activity or row.last_activity_at
            if bool(member.get("online")):
                row.last_online_seen_at = now
            row.last_synchronized_at = now
            row.is_current = True
            row.source = "tibiadata"
            row.source_metadata = {"provider": "tibiadata", "activity_enriched": bool(detail)}
            row.linked_user_character_id = verified_character.id if verified_character else None
            row.linked_user_id = verified_character.user_id if verified_character else None
            if verified_character:
                linked += 1
                verified_character.guild_name = canonical_guild
                verified_character.guild_rank = row.guild_rank
                verified_character.world_name = world
                verified_character.level = row.level
                verified_character.vocation = row.vocation
                verified_character.last_login_at = row.last_activity_at or verified_character.last_login_at
                verified_character.last_seen = now
            else:
                unlinked += 1

        departed = 0
        for row in existing:
            if row.normalized_character_name not in current_names and row.is_current:
                row.is_current = False
                row.last_synchronized_at = now
                departed += 1

        # Keep legacy profile caches coherent for display/backward compatibility;
        # these fields are never used as the authoritative grant policy.
        roster_by_name = {**existing_by_name}
        roster_by_name.update({
            row.normalized_character_name: row
            for row in db.new
            if isinstance(row, GuildRosterCharacter)
        })
        all_characters = db.query(UserCharacter).options(
            selectinload(UserCharacter.user).selectinload(User.characters),
        ).filter(UserCharacter.guild_name.isnot(None)).all()
        for character in all_characters:
            same_guild = normalize_guild_identity(character.guild_name or "") == guild_key
            if not same_guild:
                continue
            roster_row = roster_by_name.get(character.normalized_name or normalize_character_name(character.character_name))
            if roster_row and roster_row.is_current:
                character.guild_name = canonical_guild
                character.guild_rank = roster_row.guild_rank
                character.world_name = world
                character.level = roster_row.level
                character.vocation = roster_row.vocation
                if character.user:
                    character.user.guild_name = canonical_guild
                    character.user.guild_rank = roster_row.guild_rank or "Member"
                    character.user.world_name = world
            else:
                character.guild_name = None
                character.guild_rank = None
                if character.user and not any(
                    normalize_guild_identity(other.guild_name or "") == guild_key
                    for other in character.user.characters if other is not character
                ):
                    character.user.guild_name = None
                    character.user.guild_rank = "Unranked"

        db.flush()
        return GuildRosterSyncResult(
            guild_name=canonical_guild, world_name=world, total=len(enriched),
            inserted=inserted, updated=updated, departed=departed,
            linked=linked, unlinked=unlinked, synchronized_at=now,
        )
