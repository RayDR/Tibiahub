"""Exact retained-document evidence for NPC and Location media."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
import re
from typing import Iterable
from urllib.parse import quote

from sqlalchemy.orm import Session

from app.core.config import settings
from app.knowledge.models import KnowledgeDocument
from app.models.external_data import TibiaWikiLocation, TibiaWikiNpc
from app.services.bestiary_source import _extract_infobox_param_map
from app.services.text_utils import normalize_search_text


MEDIA_EVIDENCE_STATES = (
    "eligible",
    "no_source_evidence",
    "malformed_source",
    "unresolved_source",
)
_ALLOWED_IMAGE_FIELDS = frozenset({"image", "imagefile", "image file", "sprite", "picture", "photo"})
_DISALLOWED_LOCATION_FIELDS = frozenset({"map", "map2", "map3", "minimap"})
_ALLOWED_EXTENSIONS = frozenset({".gif", ".png", ".jpg", ".jpeg", ".webp"})
_PRIMARY_TEMPLATE = {
    "npc": re.compile(r"^\s*\{\{\s*Infobox\s+NPC\b", re.IGNORECASE),
    "location": re.compile(r"^\s*\{\{\s*Infobox\s+(?:Geography|Location)\b", re.IGNORECASE),
}


@dataclass(frozen=True, slots=True)
class EntityMediaEvidence:
    state: str
    source_url: str | None = None
    field_name: str | None = None
    explicit_reference: bool = False
    rejected_unrelated_reference: bool = False
    moving_or_variant: bool = False

    @property
    def eligible(self) -> bool:
        return self.state == "eligible" and bool(self.source_url)


def _document_parts(document: KnowledgeDocument) -> tuple[str, str, str] | None:
    raw = document.raw_json if isinstance(document.raw_json, dict) else {}
    parsed = raw.get("parse")
    if not isinstance(parsed, dict):
        return None
    external_id = str(parsed.get("pageid") or "").strip()
    title = str(parsed.get("title") or "").strip()
    node = parsed.get("wikitext")
    wikitext = node.get("*") if isinstance(node, dict) else None
    if not external_id.isdigit() or not title or not isinstance(wikitext, str) or not wikitext.strip():
        return None
    return external_id, title, wikitext


def _primary_template(wikitext: str, entity_type: str) -> str | None:
    matcher = _PRIMARY_TEMPLATE[entity_type]
    lines = wikitext.splitlines()
    start = next((index for index, line in enumerate(lines) if matcher.match(line)), None)
    if start is None:
        return None
    selected: list[str] = []
    for line in lines[start:]:
        selected.append(line)
        if len(selected) > 1 and line.strip() == "}}":
            return "\n".join(selected)
    return None


def _file_name(raw_value: str) -> str | None:
    value = (raw_value or "").strip()
    if not value or "{{" in value or "<" in value or ">" in value:
        return None
    wrapped = re.match(r"^\[\[(?:File|Image):([^\]]+)\]\]$", value, re.IGNORECASE)
    if wrapped:
        value = wrapped.group(1)
    value = value.split("|", 1)[0].strip()
    value = re.sub(r"^(?:File|Image):", "", value, flags=re.IGNORECASE).strip()
    if not value or "/" in value or "\\" in value or any(ord(character) < 32 for character in value):
        return None
    if PurePosixPath(value).suffix.casefold() not in _ALLOWED_EXTENSIONS:
        return None
    return value


def explicit_provider_media_reference(wikitext: str, entity_type: str) -> EntityMediaEvidence:
    """Accept only a file named by the primary entity infobox.

    Location map/minimap fields and arbitrary body links are deliberately not
    representative-media evidence.
    """
    template = _primary_template(wikitext, entity_type)
    if template is None:
        return EntityMediaEvidence("no_source_evidence")
    params = _extract_infobox_param_map(template)
    rejected = entity_type == "location" and any(
        key.casefold() in _DISALLOWED_LOCATION_FIELDS and bool(value.strip())
        for key, value in params.items()
    )
    supplied = next(
        ((key, value) for key, value in params.items() if key.casefold() in _ALLOWED_IMAGE_FIELDS),
        None,
    )
    if supplied is None:
        return EntityMediaEvidence(
            "no_source_evidence",
            rejected_unrelated_reference=rejected,
        )
    field_name, raw_value = supplied
    file_name = _file_name(raw_value)
    if file_name is None:
        return EntityMediaEvidence(
            "malformed_source",
            field_name=field_name,
            explicit_reference=True,
            rejected_unrelated_reference=rejected,
        )
    encoded = quote(file_name.replace(" ", "_"), safe="_.-()")
    source_url = f"{settings.TIBIAWIKI_BASE_PAGE_URL}/Special:FilePath/{encoded}"
    return EntityMediaEvidence(
        "eligible",
        source_url=source_url,
        field_name=field_name,
        explicit_reference=True,
        rejected_unrelated_reference=rejected,
    )


def evidence_for_entities(
    db: Session,
    entity_type: str,
    rows: Iterable[TibiaWikiNpc | TibiaWikiLocation],
) -> dict[int, EntityMediaEvidence]:
    """Resolve evidence with exact page IDs or one exact normalized page title."""
    values = list(rows)
    if not values:
        return {}
    documents = (
        db.query(KnowledgeDocument)
        .filter(
            KnowledgeDocument.provider_id == "tibiawiki",
            KnowledgeDocument.provider_document_id.like(f"{entity_type}:%"),
        )
        .order_by(KnowledgeDocument.retrieved_at.desc(), KnowledgeDocument.uuid.desc())
        .all()
    )
    latest_by_id: dict[str, KnowledgeDocument] = {}
    documents_by_title: dict[str, list[KnowledgeDocument]] = {}
    for document in documents:
        latest_by_id.setdefault(document.provider_document_id, document)
    for document in latest_by_id.values():
        parts = _document_parts(document)
        if parts is not None:
            documents_by_title.setdefault(normalize_search_text(parts[1]), []).append(document)

    result: dict[int, EntityMediaEvidence] = {}
    for row in values:
        moving = entity_type == "npc" and (row.provider_metadata or {}).get("location_mode") in {
            "moving",
            "multiple",
        }
        document = None
        external_id = str(row.external_id or "").strip()
        if external_id.isdigit():
            document = latest_by_id.get(f"{entity_type}:{external_id}")
        else:
            matches = documents_by_title.get(normalize_search_text(row.name), [])
            if len(matches) == 1:
                document = matches[0]
        if document is None:
            result[row.id] = EntityMediaEvidence("unresolved_source", moving_or_variant=moving)
            continue
        parts = _document_parts(document)
        if parts is None:
            result[row.id] = EntityMediaEvidence("malformed_source", moving_or_variant=moving)
            continue
        document_external_id, title, wikitext = parts
        exact_id = external_id.isdigit() and document_external_id == external_id
        exact_title = normalize_search_text(title) == normalize_search_text(row.name)
        if not exact_id and not exact_title:
            result[row.id] = EntityMediaEvidence("unresolved_source", moving_or_variant=moving)
            continue
        evidence = explicit_provider_media_reference(wikitext, entity_type)
        result[row.id] = EntityMediaEvidence(
            state=evidence.state,
            source_url=evidence.source_url,
            field_name=evidence.field_name,
            explicit_reference=evidence.explicit_reference,
            rejected_unrelated_reference=evidence.rejected_unrelated_reference,
            moving_or_variant=moving,
        )
    return result
