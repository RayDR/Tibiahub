"""Public SEO discovery documents generated only from local canonical knowledge."""

from __future__ import annotations

from xml.etree.ElementTree import Element, SubElement, tostring

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import get_db
from app.models.creature import Creature
from app.models.external_data import Item, TibiaWikiLocation, TibiaWikiNpc, TibiaWikiQuest
from app.models.hunt_zone import HuntZone
from app.services.text_utils import normalize_search_text


router = APIRouter(prefix="/seo", tags=["SEO"])
SITEMAP_ENTITY_LIMIT = 5000


def _slug(value: str | None, name: str) -> str:
    return value or normalize_search_text(name).replace(" ", "-")


def canonical_public_paths(db: Session) -> list[str]:
    paths = ["/", "/cyclopedia", "/map"]
    paths.extend(
        f"/creatures/{_slug(row.slug, row.name)}"
        for row in db.query(Creature).filter(Creature.is_hidden.is_(False)).order_by(Creature.id).limit(SITEMAP_ENTITY_LIMIT).all()
    )
    paths.extend(
        f"/items/{_slug(row.slug, row.name)}"
        for row in db.query(Item).filter(Item.knowledge_entity_id.isnot(None)).order_by(Item.id).limit(SITEMAP_ENTITY_LIMIT).all()
    )
    paths.extend(
        f"/quests/{_slug(row.slug, row.name)}"
        for row in db.query(TibiaWikiQuest).filter(TibiaWikiQuest.is_group.is_(False)).order_by(TibiaWikiQuest.id).limit(SITEMAP_ENTITY_LIMIT).all()
    )
    paths.extend(
        f"/hunt-zones/{_slug(row.slug, row.name)}"
        for row in db.query(HuntZone).order_by(HuntZone.id).limit(SITEMAP_ENTITY_LIMIT).all()
    )
    paths.extend(f"/npcs/{row.slug}" for row in db.query(TibiaWikiNpc).filter(TibiaWikiNpc.slug.isnot(None)).order_by(TibiaWikiNpc.id).limit(SITEMAP_ENTITY_LIMIT).all())
    paths.extend(f"/locations/{row.slug}" for row in db.query(TibiaWikiLocation).filter(TibiaWikiLocation.slug.isnot(None)).order_by(TibiaWikiLocation.id).limit(SITEMAP_ENTITY_LIMIT).all())
    return list(dict.fromkeys(paths))


@router.get("/sitemap.xml", include_in_schema=False)
def sitemap(db: Session = Depends(get_db)) -> Response:
    origin = f"https://{settings.PUBLIC_DOMAIN.strip().lower()}"
    root = Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
    for path in canonical_public_paths(db):
        node = SubElement(root, "url")
        SubElement(node, "loc").text = f"{origin}{path}"
    return Response(
        content=tostring(root, encoding="utf-8", xml_declaration=True),
        media_type="application/xml",
        headers={"Cache-Control": "public, max-age=900"},
    )


@router.get("/robots.txt", include_in_schema=False)
def robots() -> Response:
    origin = f"https://{settings.PUBLIC_DOMAIN.strip().lower()}"
    content = f"User-agent: *\nAllow: /\nDisallow: /admin/\nDisallow: /guild/\nDisallow: /profile\nSitemap: {origin}/sitemap.xml\n"
    return Response(content=content, media_type="text/plain", headers={"Cache-Control": "public, max-age=3600"})
