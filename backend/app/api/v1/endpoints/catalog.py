"""
Unified Catalog Endpoints (Hunts, Quests, Custom)
"""
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session
from sqlalchemy import case, desc, or_
from typing import List, Optional
from datetime import UTC, datetime

from app.db.database import get_db
from app.knowledge.models import KnowledgeEntity
from app.models.catalog import Catalog
from app.models.creature import Creature
from app.models.entity_metadata import EntityMetadata
from app.models.external_data import Item as ExternalItem, TibiaWikiQuest
from app.models.hunt_zone import HuntZone
from app.models.media_asset import MediaAsset
from app.models.user import User
from app.api.v1.endpoints.auth import get_current_user, get_current_admin_user

router = APIRouter()


@router.get("/category-visuals")
def cyclopedia_category_visuals(response: Response, db: Session = Depends(get_db)):
    """Stable, local-only visual identities for the five Cyclopedia sections."""
    gif_first = case((MediaAsset.content_type.ilike("%gif%"), 0), else_=1)
    creature = db.query(Creature).join(MediaAsset, Creature.image_asset_id == MediaAsset.id).filter(
        Creature.is_hidden.is_(False),
        Creature.is_boss.is_(False),
        MediaAsset.status == "cached",
    ).order_by(gif_first, Creature.id.asc()).first()
    boss = db.query(Creature).join(MediaAsset, Creature.image_asset_id == MediaAsset.id).filter(
        Creature.is_hidden.is_(False),
        Creature.is_boss.is_(True),
        MediaAsset.status == "cached",
    ).order_by(gif_first, Creature.id.asc()).first()
    item_candidates = db.query(ExternalItem).filter(
        ExternalItem.knowledge_entity_id.isnot(None),
    ).order_by(ExternalItem.id.asc()).limit(40).all()
    quest_candidates = db.query(ExternalItem).filter(
        ExternalItem.knowledge_entity_id.isnot(None),
        or_(
            ExternalItem.normalized_name.contains("tome"),
            ExternalItem.normalized_name.contains("book"),
            ExternalItem.normalized_name.contains("scroll"),
        ),
    ).order_by(ExternalItem.normalized_name == "tome of knowledge", ExternalItem.id.asc()).limit(40).all()
    item_keys = {f"item:knowledge:{row.knowledge_entity_id}" for row in [*item_candidates, *quest_candidates]}
    assets = db.query(MediaAsset).filter(MediaAsset.asset_key.in_(item_keys), MediaAsset.status == "cached").all() if item_keys else []
    assets_by_key = {row.asset_key: row for row in assets}
    def choose_item(candidates):
        available = [row for row in candidates if f"item:knowledge:{row.knowledge_entity_id}" in assets_by_key]
        return min(available, key=lambda row: ("gif" not in (assets_by_key[f"item:knowledge:{row.knowledge_entity_id}"].content_type or "").lower(), row.id), default=None)
    item = choose_item(item_candidates)
    quest_item = choose_item(quest_candidates)
    zone = db.query(HuntZone).join(MediaAsset, HuntZone.map_asset_id == MediaAsset.id).filter(
        MediaAsset.status == "cached",
    ).order_by(gif_first, HuntZone.id.asc()).first()

    response.headers["Cache-Control"] = "public, max-age=3600, stale-while-revalidate=86400"
    return {
        "creatures": f"/api/v1/creatures/{creature.id}/image?placeholder=false" if creature else None,
        "bosses": f"/api/v1/creatures/{boss.id}/image?placeholder=false" if boss else None,
        "items": f"/api/v1/items/{item.id}/image?placeholder=false" if item else None,
        "quests": f"/api/v1/items/{quest_item.id}/image?placeholder=false" if quest_item else None,
        "zones": f"/api/v1/hunt-zones/{zone.id}/map-image?placeholder=false" if zone else None,
    }


@router.get("/discovery")
def cyclopedia_discovery(db: Session = Depends(get_db)):
    """Content-first local Cyclopedia landing data; never calls a provider."""
    featured_ids = [row.entity_id for row in db.query(EntityMetadata).filter(
        EntityMetadata.entity_type == "creature", EntityMetadata.is_featured.is_(True),
        EntityMetadata.entity_id.isnot(None),
    ).order_by(EntityMetadata.updated_at.desc()).limit(6).all()]
    featured_query = db.query(Creature).filter(Creature.is_hidden.is_(False), Creature.is_boss.is_(False))
    featured = featured_query.filter(Creature.id.in_(featured_ids)).all() if featured_ids else featured_query.order_by(Creature.updated_at.desc()).limit(6).all()
    hunt_ids = [row.entity_id for row in db.query(EntityMetadata).filter(
        EntityMetadata.entity_type == "hunt_zone", EntityMetadata.entity_id.isnot(None),
    ).order_by(EntityMetadata.search_count.desc(), EntityMetadata.last_viewed_at.desc()).limit(6).all()]
    hunts = db.query(HuntZone).filter(HuntZone.id.in_(hunt_ids)).all() if hunt_ids else db.query(HuntZone).order_by(HuntZone.updated_at.desc()).limit(6).all()
    quests = db.query(TibiaWikiQuest).order_by(TibiaWikiQuest.updated_at.desc()).limit(6).all()
    latest = db.query(KnowledgeEntity).filter(
        KnowledgeEntity.visibility == "public", KnowledgeEntity.status == "active",
    ).order_by(KnowledgeEntity.updated_at.desc()).limit(8).all()
    trending = db.query(EntityMetadata).filter(EntityMetadata.search_count > 0).order_by(
        EntityMetadata.search_count.desc(), EntityMetadata.last_viewed_at.desc(),
    ).limit(8).all()
    return {
        "featured_creatures": [
            {
                "id": row.id,
                "name": row.name,
                "slug": row.slug,
                "image_url": f"/api/v1/creatures/{row.id}/image",
                "experience": row.experience,
                "hitpoints": row.hitpoints,
            }
            for row in featured
        ],
        "popular_hunts": [{"id": row.id, "name": row.name, "slug": row.slug, "city": row.city, "recommended_level": row.recommended_level or row.min_level} for row in hunts],
        "recent_quests": [{"id": row.external_id or str(row.id), "name": row.name, "slug": row.slug, "summary": row.summary, "updated_at": row.updated_at} for row in quests],
        "latest_knowledge": [{"id": str(row.uuid), "name": row.canonical_name, "slug": row.slug, "entity_type": row.entity_type, "updated_at": row.updated_at} for row in latest],
        "trending": [{"id": f"{row.entity_type}:{row.entity_id or row.entity_key}", "entity_type": row.entity_type, "entity_id": row.entity_id, "name": row.display_name, "search_count": row.search_count} for row in trending],
        "boosted_creature": None,
        "boosted_boss": None,
        "boosted_state": "awaiting_official_sync",
    }


@router.get("/", response_model=List[dict])
def get_catalog_items(
    type: Optional[str] = None,
    level_min: Optional[int] = None,
    level_max: Optional[int] = None,
    vocation: Optional[str] = None,
    location: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get catalog items with optional filtering"""
    query = db.query(Catalog).filter(Catalog.is_active == True)
    
    if type:
        query = query.filter(Catalog.type == type)
    
    if level_min is not None:
        query = query.filter(Catalog.level_min >= level_min)
    
    if level_max is not None:
        query = query.filter(Catalog.level_max <= level_max)
    
    if vocation:
        query = query.filter(or_(
            Catalog.vocation == vocation,
            Catalog.vocation == 'All',
            Catalog.vocation == None
        ))
    
    if location:
        query = query.filter(Catalog.location.ilike(f'%{location}%'))
    
    items = query.order_by(desc(Catalog.created_at)).offset(skip).limit(limit).all()
    
    return [
        {
            "id": item.id,
            "type": item.type,
            "name": item.name,
            "location": item.location,
            "level_min": item.level_min,
            "level_max": item.level_max,
            "vocation": item.vocation,
            "exp_per_hour": item.exp_per_hour,
            "profit_per_hour": item.profit_per_hour,
            "creatures": item.creatures,
            "quest_reward": item.quest_reward,
            "quest_requirements": item.quest_requirements,
            "strategy": item.strategy,
            "notes": item.notes,
            "difficulty": item.difficulty,
            "is_active": item.is_active,
            "created_at": item.created_at,
            "updated_at": item.updated_at
        }
        for item in items
    ]


@router.get("/{catalog_id}", response_model=dict)
def get_catalog_item(
    catalog_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific catalog item"""
    item = db.query(Catalog).filter(Catalog.id == catalog_id, Catalog.is_active == True).first()
    if not item:
        raise HTTPException(status_code=404, detail="Catalog item not found")
    
    return {
        "id": item.id,
        "type": item.type,
        "name": item.name,
        "location": item.location,
        "level_min": item.level_min,
        "level_max": item.level_max,
        "vocation": item.vocation,
        "exp_per_hour": item.exp_per_hour,
        "profit_per_hour": item.profit_per_hour,
        "creatures": item.creatures,
        "quest_reward": item.quest_reward,
        "quest_requirements": item.quest_requirements,
        "strategy": item.strategy,
        "notes": item.notes,
        "difficulty": item.difficulty,
        "is_active": item.is_active,
        "created_at": item.created_at,
        "updated_at": item.updated_at
    }


@router.post("/", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_catalog_item(
    item_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Create a new catalog item (admin only)"""
    new_item = Catalog(**item_data)
    
    db.add(new_item)
    db.commit()
    db.refresh(new_item)
    
    return {
        "id": new_item.id,
        "type": new_item.type,
        "name": new_item.name,
        "location": new_item.location,
        "level_min": new_item.level_min,
        "level_max": new_item.level_max,
        "vocation": new_item.vocation,
        "exp_per_hour": new_item.exp_per_hour,
        "profit_per_hour": new_item.profit_per_hour,
        "creatures": new_item.creatures,
        "quest_reward": new_item.quest_reward,
        "quest_requirements": new_item.quest_requirements,
        "strategy": new_item.strategy,
        "notes": new_item.notes,
        "difficulty": new_item.difficulty,
        "is_active": new_item.is_active,
        "created_at": new_item.created_at,
        "updated_at": new_item.updated_at
    }


@router.put("/{catalog_id}", response_model=dict)
def update_catalog_item(
    catalog_id: int,
    item_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Update a catalog item (admin only)"""
    item = db.query(Catalog).filter(Catalog.id == catalog_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Catalog item not found")
    
    for key, value in item_data.items():
        if hasattr(item, key):
            setattr(item, key, value)
    
    item.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(item)
    
    return get_catalog_item(catalog_id, db, current_user)


@router.delete("/{catalog_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_catalog_item(
    catalog_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Delete a catalog item (admin only)"""
    item = db.query(Catalog).filter(Catalog.id == catalog_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Catalog item not found")
    
    item.is_active = False
    db.commit()
    return
