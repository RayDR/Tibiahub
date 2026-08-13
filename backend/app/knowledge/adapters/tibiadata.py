"""Executable TibiaData v4 ingestion for canonical facts and live observations."""

from __future__ import annotations

import asyncio
from typing import Any, Protocol
from urllib.parse import quote

from app.core.config import settings
from app.knowledge.adapters.protocol import (
    CanonicalEntityCandidate,
    KnowledgeChildJobRequest,
    KnowledgeDocumentDTO,
    KnowledgeFetchRequest,
    KnowledgeFetchResult,
    KnowledgeNormalizationContext,
    KnowledgeNormalizationResult,
    KnowledgeValidationResult,
)
from app.services import tibia_api

MAX_TIBIADATA_DOCUMENTS = 1000


class TibiaDataKnowledgeClient(Protocol):
    def character(self, name: str) -> dict[str, Any]: ...
    def guild(self, name: str) -> dict[str, Any]: ...
    def guilds(self, world: str) -> dict[str, Any]: ...
    def worlds(self) -> dict[str, Any]: ...
    def world(self, name: str) -> dict[str, Any]: ...
    def highscores(self, world: str, category: str, vocation: str, page: int) -> dict[str, Any]: ...
    def killstatistics(self, world: str) -> dict[str, Any]: ...
    def houses(self, world: str, town: str) -> dict[str, Any]: ...
    def creatures(self) -> dict[str, Any]: ...
    def creature(self, race: str) -> dict[str, Any]: ...
    def spells(self) -> dict[str, Any]: ...
    def spell(self, spell_id: str) -> dict[str, Any]: ...
    def boostable_bosses(self) -> dict[str, Any]: ...


class HttpTibiaDataKnowledgeClient:
    """Synchronous worker facade over the application's resilient HTTP client."""

    @staticmethod
    def _request(path: str) -> dict[str, Any]:
        return asyncio.run(tibia_api._get_json(f"{settings.TIBIADATA_BASE_URL}/{path}"))

    @staticmethod
    def _part(value: str) -> str:
        return quote(value, safe="")

    def character(self, name: str) -> dict[str, Any]: return self._request(f"character/{self._part(name)}")
    def guild(self, name: str) -> dict[str, Any]: return self._request(f"guild/{self._part(name)}")
    def guilds(self, world: str) -> dict[str, Any]: return self._request(f"guilds/{self._part(world)}")
    def worlds(self) -> dict[str, Any]: return self._request("worlds")
    def world(self, name: str) -> dict[str, Any]: return self._request(f"world/{self._part(name)}")
    def highscores(self, world: str, category: str, vocation: str, page: int) -> dict[str, Any]:
        return self._request(f"highscores/{self._part(world)}/{self._part(category)}/{self._part(vocation)}/{page}")
    def killstatistics(self, world: str) -> dict[str, Any]: return self._request(f"killstatistics/{self._part(world)}")
    def houses(self, world: str, town: str) -> dict[str, Any]:
        return self._request(f"houses/{self._part(world)}/{self._part(town)}")
    def creatures(self) -> dict[str, Any]: return self._request("creatures")
    def creature(self, race: str) -> dict[str, Any]: return self._request(f"creature/{self._part(race)}")
    def spells(self) -> dict[str, Any]: return self._request("spells")
    def spell(self, spell_id: str) -> dict[str, Any]: return self._request(f"spell/{self._part(spell_id)}")
    def boostable_bosses(self) -> dict[str, Any]: return self._request("boostablebosses")


_ENTITY_JOB_TYPES = {
    "character": {"character_detail", "character_renormalize"},
    "guild": {"guild_catalog", "guild_catalog_renormalize", "guild_detail", "guild_renormalize"},
    "world": {
        "world_catalog", "world_catalog_renormalize", "world_detail", "world_renormalize",
        "highscores_current", "highscores_renormalize",
        "killstatistics_current", "killstatistics_renormalize",
    },
    "town": {"house_catalog", "house_renormalize"},
    "creature": {"creature_catalog", "creature_catalog_renormalize", "creature_detail", "creature_renormalize"},
    "spell": {"spell_catalog", "spell_catalog_renormalize", "spell_detail", "spell_renormalize"},
    "boss": {"boosted_bosses_current", "boosted_bosses_renormalize"},
}

_RENORMALIZE_PREFIXES = {
    "character_renormalize": ("character", "character"),
    "guild_renormalize": ("guild", "guild"),
    "guild_catalog_renormalize": ("guild_catalog", "guild_catalog"),
    "world_renormalize": ("world", "world"),
    "world_catalog_renormalize": ("catalog", "world_catalog"),
    "creature_renormalize": ("creature", "creature"),
    "creature_catalog_renormalize": ("catalog", "creature_catalog"),
    "spell_renormalize": ("spell", "spell"),
    "spell_catalog_renormalize": ("catalog", "spell_catalog"),
    "highscores_renormalize": ("highscores", "highscores"),
    "killstatistics_renormalize": ("killstatistics", "killstatistics"),
    "house_renormalize": ("houses", "houses"),
    "boosted_bosses_renormalize": ("boosted_bosses", "boosted_bosses"),
}


def _safe_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 255:
        raise ValueError(f"TibiaData {field} must be a non-empty string no longer than 255 characters")
    cleaned = value.strip()
    if any(ord(char) < 32 for char in cleaned):
        raise ValueError(f"TibiaData {field} contains control characters")
    return cleaned


def _nested(raw: dict[str, Any], *paths: tuple[str, ...]) -> Any:
    for path in paths:
        value: Any = raw
        for key in path:
            value = value.get(key) if isinstance(value, dict) else None
        if value is not None:
            return value
    return None


def _list(raw: dict[str, Any], *paths: tuple[str, ...]) -> list[dict[str, Any]]:
    value = _nested(raw, *paths)
    return [row for row in value if isinstance(row, dict)] if isinstance(value, list) else []


def _detail_payload(raw: dict[str, Any], entity_type: str) -> dict[str, Any]:
    paths = {
        "character": (("character", "character"),),
        "guild": (("guild",),),
        "world": (("world",), ("worlds",)),
        "creature": (("creature",),),
        "spell": (("spell",),),
    }
    value = _nested(raw, *paths.get(entity_type, ()))
    return value if isinstance(value, dict) else raw


def _name(payload: dict[str, Any], entity_type: str) -> str:
    for field in (("race", "name") if entity_type == "creature" else ("name", "spell_id")):
        value = payload.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _source(path: str) -> str:
    return f"{settings.TIBIADATA_BASE_URL}/{path}"


class TibiaDataKnowledgeAdapter:
    provider_code = "tibiadata"
    job_types = tuple(sorted(set().union(*_ENTITY_JOB_TYPES.values())))

    def __init__(self, client: TibiaDataKnowledgeClient | None = None):
        self.client = client or HttpTibiaDataKnowledgeClient()

    def supports(self, job_type: str, entity_type: str | None) -> bool:
        return entity_type in _ENTITY_JOB_TYPES and job_type in _ENTITY_JOB_TYPES[entity_type]

    def validate_enqueue(self, job_type: str, scope: dict, payload: dict) -> None:
        if job_type in {"world_catalog", "boosted_bosses_current"}:
            if scope or payload:
                raise ValueError("This TibiaData root does not accept scope or payload")
            return
        if job_type in {"creature_catalog", "spell_catalog"}:
            if payload or set(scope) - {"batch_limit"}:
                raise ValueError("TibiaData catalogs accept only an optional batch_limit scope")
            limit = scope.get("batch_limit", 50)
            if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 100:
                raise ValueError("TibiaData batch_limit must be between 1 and 100")
            return
        if job_type.endswith("_renormalize"):
            if scope or set(payload) != {"external_id"}:
                raise ValueError("TibiaData renormalization requires only external_id")
            _safe_string(payload.get("external_id"), "external_id")
            return
        required = {
            "character_detail": {"name"}, "guild_detail": {"name"}, "guild_catalog": {"world"},
            "world_detail": {"name"}, "creature_detail": {"name"}, "spell_detail": {"spell_id"},
            "highscores_current": {"world", "category", "vocation", "page"},
            "killstatistics_current": {"world"}, "house_catalog": {"world", "town"},
        }.get(job_type)
        if scope or required is None or set(payload) != required:
            raise ValueError("TibiaData job payload has unexpected fields")
        for key in required - {"page"}:
            _safe_string(payload.get(key), key)
        if "page" in required:
            page = payload.get("page")
            if not isinstance(page, int) or isinstance(page, bool) or not 1 <= page <= 1000:
                raise ValueError("TibiaData highscore page must be between 1 and 1000")

    def _stored(self, request: KnowledgeFetchRequest) -> KnowledgeFetchResult:
        raw = request.payload.get("_stored_document")
        if not isinstance(raw, dict):
            raise ValueError("TibiaData renormalization requires a stored raw document")
        prefix, kind = _RENORMALIZE_PREFIXES[request.job_type]
        external_id = str(request.payload.get("external_id") or "").strip()
        stored_metadata = request.payload.get("_stored_metadata")
        source_url = stored_metadata.get("source_url") if isinstance(stored_metadata, dict) else None
        return KnowledgeFetchResult((KnowledgeDocumentDTO(
            self.provider_code, f"{prefix}:{external_id}", raw,
            version=str(request.payload.get("_stored_version") or "v4"),
            metadata={"document_kind": kind, "external_id": external_id, "source_url": source_url},
        ),), provider_metadata={"source": "stored_document"})

    def fetch(self, request: KnowledgeFetchRequest) -> KnowledgeFetchResult:
        if request.job_type.endswith("_renormalize"):
            return self._stored(request)
        payload = request.payload
        if request.job_type == "world_catalog":
            raw = self.client.worlds()
            entries = [*_list(raw, ("worlds", "regular_worlds")), *_list(raw, ("worlds", "tournament_worlds"))]
            return self._catalog(raw, "world", entries, "name", request, source_path="worlds")
        if request.job_type == "creature_catalog":
            raw = self.client.creatures()
            entries = _list(raw, ("creatures", "creature_list"), ("creatures", "creatures"), ("creatures",))
            return self._catalog(raw, "creature", entries, "race", request, source_path="creatures")
        if request.job_type == "spell_catalog":
            raw = self.client.spells()
            entries = _list(raw, ("spells", "spell_list"), ("spells", "spells"), ("spells",))
            return self._catalog(raw, "spell", entries, "spell_id", request, source_path="spells")
        if request.job_type == "character_detail":
            name = _safe_string(payload["name"], "name"); raw = self.client.character(name)
            return self._detail(raw, "character", name, f"character/{quote(name, safe='')}")
        if request.job_type == "guild_detail":
            name = _safe_string(payload["name"], "name"); raw = self.client.guild(name)
            return self._detail(raw, "guild", name, f"guild/{quote(name, safe='')}")
        if request.job_type == "world_detail":
            name = _safe_string(payload["name"], "name"); raw = self.client.world(name)
            return self._detail(raw, "world", name, f"world/{quote(name, safe='')}")
        if request.job_type == "creature_detail":
            name = _safe_string(payload["name"], "name"); raw = self.client.creature(name)
            return self._detail(raw, "creature", name, f"creature/{quote(name, safe='')}")
        if request.job_type == "spell_detail":
            name = _safe_string(payload["spell_id"], "spell_id"); raw = self.client.spell(name)
            return self._detail(raw, "spell", name, f"spell/{quote(name, safe='')}")
        if request.job_type == "guild_catalog":
            world = _safe_string(payload["world"], "world"); raw = self.client.guilds(world)
            return self._observation(raw, "guild_catalog", world.casefold(), f"guilds/{quote(world, safe='')}")
        if request.job_type == "highscores_current":
            world, category, vocation, page = payload["world"], payload["category"], payload["vocation"], payload["page"]
            raw = self.client.highscores(world, category, vocation, page)
            key = f"{world.casefold()}:{category.casefold()}:{vocation.casefold()}:{page}"
            return self._observation(raw, "highscores", key, f"highscores/{quote(world, safe='')}/{quote(category, safe='')}/{quote(vocation, safe='')}/{page}")
        if request.job_type == "killstatistics_current":
            world = payload["world"]; raw = self.client.killstatistics(world)
            return self._observation(raw, "killstatistics", world.casefold(), f"killstatistics/{quote(world, safe='')}")
        if request.job_type == "house_catalog":
            world, town = payload["world"], payload["town"]; raw = self.client.houses(world, town)
            return self._observation(raw, "houses", f"{world.casefold()}:{town.casefold()}", f"houses/{quote(world, safe='')}/{quote(town, safe='')}")
        if request.job_type == "boosted_bosses_current":
            return self._observation(self.client.boostable_bosses(), "boosted_bosses", "global", "boostablebosses")
        raise ValueError("Unsupported TibiaData job")

    def _catalog(self, raw, entity_type, entries, name_field, request, *, source_path):
        entries = entries[:MAX_TIBIADATA_DOCUMENTS]
        limit = request.scope.get("batch_limit", 100)
        documents = [KnowledgeDocumentDTO(
            self.provider_code, f"catalog:{entity_type}", raw, version="v4",
            metadata={"document_kind": f"{entity_type}_catalog", "source_url": _source(source_path)},
        )]
        children = []
        for entry in entries[:limit]:
            external = str(entry.get(name_field) or entry.get("name") or "").strip()
            if not external:
                continue
            documents.append(KnowledgeDocumentDTO(
                self.provider_code, f"{entity_type}:{external.casefold()}", entry, version="v4",
                metadata={"document_kind": entity_type, "external_id": external.casefold(), "source_url": _source(source_path)},
            ))
            if entity_type in {"creature", "spell"}:
                children.append(KnowledgeChildJobRequest(
                    job_type=f"{entity_type}_detail", entity_type=entity_type,
                    payload={"name" if entity_type == "creature" else "spell_id": external},
                ))
        return KnowledgeFetchResult(
            tuple(documents), partial=len(entries) > limit,
            provider_metadata={"discovered": len(entries)}, child_jobs=tuple(children),
        )

    def _detail(self, raw, entity_type, external, path):
        return KnowledgeFetchResult((KnowledgeDocumentDTO(
            self.provider_code, f"{entity_type}:{external.casefold()}", raw, version="v4",
            metadata={"document_kind": entity_type, "external_id": external.casefold(), "source_url": _source(path)},
        ),))

    def _observation(self, raw, kind, key, path):
        return KnowledgeFetchResult((KnowledgeDocumentDTO(
            self.provider_code, f"{kind}:{key}", raw, version="v4",
            metadata={"document_kind": kind, "external_id": key, "source_url": _source(path)},
        ),))

    def validate(self, result: KnowledgeFetchResult) -> KnowledgeValidationResult:
        if not result.documents:
            return KnowledgeValidationResult(False, classification="empty", safe_errors=("empty_response",))
        for document in result.documents:
            if not isinstance(document.raw_json, dict) or not document.raw_json:
                return KnowledgeValidationResult(False, classification="invalid", safe_errors=("invalid_envelope",))
            kind = str(document.metadata.get("document_kind") or "")
            if kind.endswith("_catalog") or kind in {"highscores", "killstatistics", "houses", "boosted_bosses"}:
                continue
            payload = _detail_payload(document.raw_json, kind)
            if not isinstance(payload, dict) or not _name(payload, kind):
                return KnowledgeValidationResult(False, classification="invalid", safe_errors=("required_fields",))
        return KnowledgeValidationResult(True)

    def normalize(self, document: KnowledgeDocumentDTO, context: KnowledgeNormalizationContext) -> KnowledgeNormalizationResult:
        kind = str(document.metadata.get("document_kind") or "")
        source_url = str(document.metadata.get("source_url") or "") or None
        external_id = str(document.metadata.get("external_id") or document.provider_document_id.split(":", 1)[-1])
        if kind.endswith("_catalog") or kind in {"highscores", "killstatistics", "houses", "boosted_bosses"}:
            observation_type = kind.removesuffix("_catalog") + "_catalog" if kind.endswith("_catalog") else kind
            return KnowledgeNormalizationResult(
                action="noop", provider_code=self.provider_code,
                observation_type=observation_type, observation_key=external_id,
                observation_data=document.raw_json, observation_source_url=source_url,
            )
        entity_type = kind
        if entity_type not in {"character", "guild", "world", "creature", "spell"}:
            return KnowledgeNormalizationResult(action="noop", warnings=("unsupported_tibiadata_document",))
        payload = _detail_payload(document.raw_json, entity_type)
        name = _name(payload, entity_type)
        supplied_fields = sorted(key for key, value in payload.items() if value is not None)
        external_id = external_id.casefold()
        return KnowledgeNormalizationResult(
            action="upsert",
            candidate=CanonicalEntityCandidate(
                entity_type=entity_type, canonical_name=name,
                language_neutral_id=f"{entity_type}:tibiadata:{external_id}", source_priority=10,
                identity_strategy="exact_unique_or_create" if entity_type in {"creature", "spell"} else "provider_identity",
            ),
            provider_code=self.provider_code, external_id=external_id,
            canonical_data={
                "fields": payload, "supplied_fields": supplied_fields,
                "source_url": source_url, "data_version": 1,
                "knowledge_role": "current_official_observation",
            },
            observation_type=entity_type,
            observation_key=external_id,
            observation_data=payload,
            observation_source_url=source_url,
        )
