"""
Advanced API Endpoints for Hunt Recommendations

Implements:
- Solo hunt recommendations
- Party hunt recommendations  
- Weekly bosses information
- Profit optimization
- EXP optimization

Data sourced from TibiaWiki API: https://tibia.fandom.com/api.php
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.db.database import get_db
from app.services.recommendation_engine import get_recommendation_engine
from app.schemas import Vocation
from app.models import Creature, HuntZone
from app.models.external_data import Item, TibiaWikiQuest
from app.services.text_utils import normalize_search_text

router = APIRouter()


def _zone_payload(rec, engine=None, player_level=None):
    zone = rec['zone']
    location_x = zone.location_x if zone.location_x is not None else zone.map_x
    location_y = zone.location_y if zone.location_y is not None else zone.map_y
    profile = engine.recommendation_profile(zone, player_level) if engine and player_level is not None else {}
    return {
        "zone_id": zone.id, "zone_name": zone.name, "zone_slug": zone.slug,
        "score": round(rec['score'], 2), "reasons": rec['reasons'],
        "is_preselected": bool(rec.get("is_preselected")),
        "avg_exp_hour": zone.avg_exp_hour, "avg_profit_hour": zone.avg_profit_hour,
        "rate_basis": "stored_local_average" if zone.avg_exp_hour or zone.avg_profit_hour else None,
        "min_level": zone.min_level, "max_level": zone.max_level, "difficulty": zone.difficulty,
        "requires_premium": zone.requires_premium, "requires_quest": zone.requires_quest,
        "quest_name": zone.quest_name, "city": zone.city, "region": zone.region, "size": zone.size,
        "recommended_party_size": zone.recommended_party_size,
        "suggested_level": profile.get("suggested_level") or zone.recommended_level,
        "effective_min_level": profile.get("minimum_level") or zone.min_level,
        "level_fit": profile.get("level_fit"), "danger": profile.get("danger"),
        "raw_creature_exp": profile.get("raw_experience"),
        "profile_basis": profile.get("profile_basis"),
        "map_image_url": None,
        "map_bounds": zone.map_bounds, "location_x": location_x,
        "location_y": location_y, "location_z": zone.location_z if zone.location_z is not None else zone.map_z,
        "creatures": [{
            "id": spawn.creature.id, "name": spawn.creature.name, "slug": spawn.creature.slug,
            "is_boss": bool(spawn.creature.is_boss), "image_url": f"/api/v1/creatures/{spawn.creature.id}/image",
            "hitpoints": spawn.creature.hitpoints, "experience": spawn.creature.experience,
            "max_damage": spawn.creature.max_damage,
            "weaknesses": [element.name for element in spawn.creature.weaknesses],
            "resistances": [element.name for element in spawn.creature.resistances],
            "valuable_loot": [{"name": loot.item_name, "value": loot.item_value, "image_url": f"/api/v1/items/{loot.id}/image"} for loot in sorted(spawn.creature.loot_items, key=lambda item: item.item_value or 0, reverse=True)[:5] if loot.item_value],
        } for spawn in zone.creature_spawns[:8] if spawn.creature],
    }


@router.get("/solo")
async def get_solo_recommendations(
    vocation: Vocation = Query(..., description="Player vocation"),
    level: int = Query(..., ge=8, le=2000, description="Player level"),
    goal: str = Query("exp", pattern="^(exp|profit|balanced)$", description="Hunting goal"),
    limit: int = Query(10, ge=1, le=50, description="Maximum results"),
    skip: int = Query(0, ge=0, le=500, description="Pagination offset"),
    zone: Optional[str] = Query(None, max_length=150, description="Optional zone identifier to inspect in context"),
    db: Session = Depends(get_db)
):
    """
    Get personalized hunt zone recommendations for solo players
    
    **Algorithm considers:**
    - Character level vs zone level range
    - Vocation suitability
    - Goal optimization (exp/profit/balanced)
    - Zone difficulty
    - Estimated rates
    
    **Data Sources:**
    - Zone database (curated from TibiaWiki)
    - Community exp/profit rates
    - Vocation characteristics analysis
    """
    engine = get_recommendation_engine(db)
    recommendations = engine.get_solo_recommendations(
        vocation=vocation,
        level=level,
        goal=goal,
        limit=limit + 1,
        skip=skip,
        preferred_zone=zone,
    )
    
    return {
        "vocation": vocation,
        "level": level,
        "goal": goal,
        "skip": skip, "limit": limit, "has_more": len(recommendations) > limit,
        "recommendations": [
            _zone_payload(rec, engine, level)
            for rec in recommendations[:limit]
        ]
    }


@router.post("/party")
async def get_party_recommendations(
    party_composition: List[dict],  # [{"vocation": "knight", "level": 100}, ...]
    goal: str = Query("exp", pattern="^(exp|profit|balanced)$"),
    limit: int = Query(10, ge=1, le=50),
    skip: int = Query(0, ge=0, le=500),
    db: Session = Depends(get_db)
):
    """
    Get optimized hunt zone recommendations for party hunting
    
    **Party Synergies Considered:**
    - Knight + Druid: Tank + Healer (+30% efficiency)
    - Knight + Sorcerer + Druid: Full team (+50% efficiency)
    - Knight + Paladin + Sorcerer + Druid: Optimal 4-man (+80% efficiency)
    
    **Algorithm Features:**
    - Analyzes party composition
    - Calculates synergy bonuses
    - Suggests zones with good spawn density
    - Considers level distribution
    - Optimizes for party goal
    
    **Example Party:**
    ```json
    [
        {"vocation": "knight", "level": 250},
        {"vocation": "druid", "level": 240},
        {"vocation": "sorcerer", "level": 245}
    ]
    ```
    
    **Data Sources:**
    - Zone spawn density (TibiaWiki)
    - Party exp rates (community data)
    - Synergy calculations (game mechanics)
    """
    allowed_vocations = {"knight", "paladin", "sorcerer", "druid", "monk"}
    if not party_composition or len(party_composition) > 4:
        raise HTTPException(status_code=422, detail="Party must contain between one and four members")
    normalized_party = []
    for member in party_composition:
        vocation = str(member.get("vocation", "")).lower()
        try:
            level = int(member.get("level"))
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail="Each party member requires a numeric level")
        if vocation not in allowed_vocations or level < 8 or level > 2000:
            raise HTTPException(status_code=422, detail="Invalid party vocation or level")
        normalized_party.append({"vocation": vocation, "level": level})
    engine = get_recommendation_engine(db)
    recommendations = engine.get_party_recommendations(
        party_composition=normalized_party,
        goal=goal,
        limit=limit + 1,
        skip=skip,
    )
    
    return {
        "party_size": len(normalized_party),
        "avg_level": sum(m['level'] for m in normalized_party) / len(normalized_party),
        "vocations": [m['vocation'] for m in normalized_party],
        "goal": goal,
        "skip": skip, "limit": limit, "has_more": len(recommendations) > limit,
        "recommendations": [
            {**_zone_payload(rec, engine, int(sum(m['level'] for m in normalized_party) / len(normalized_party))), "composition_fit": rec['synergy_bonus']}
            for rec in recommendations[:limit]
        ]
    }


@router.get("/weekly-bosses")
def get_weekly_bosses(db: Session = Depends(get_db)):
    """
    Get information about world bosses and weekly spawns
    
    **Provides:**
    - World boss names
    - Spawn schedules
    - Minimum recommended level
    - Required team composition
    
    Reads only locally synchronized canonical boss records.
    """
    rows = db.query(Creature).filter(
        Creature.is_boss.is_(True), Creature.is_hidden.is_(False),
    ).order_by(Creature.name.asc()).limit(100).all()
    bosses = [{
        "id": row.id, "name": row.name, "slug": row.slug,
        "canonical_id": row.knowledge_entity_id, "external_id": row.external_id,
        "source_provider": row.source_name, "source_url": row.source_url,
        "supplied_fields": list(row.supplied_fields or []),
        "missing_fields": list(row.missing_fields or []),
        "data_version": row.data_version, "last_synced_at": row.last_synced_at,
        "hitpoints": row.hitpoints, "experience": row.experience,
        "locations": list(row.locations or []), "related_tasks": list(row.related_tasks or []),
    } for row in rows]
    
    return {
        "source": "local canonical Knowledge",
        "total_bosses": len(bosses),
        "bosses": bosses,
        "note": "Spawn times and mechanics sourced from community wiki"
    }


@router.get("/profit-zones")
async def get_profit_zones(
    min_level: int = Query(..., ge=8, le=2000),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """
    Get zones optimized for profit (gold per hour)
    
    **Returns zones with:**
    - High valuable loot
    - Good creature drop rates
    - Efficient farming routes
    
    **Factors Considered:**
    - Average gold per hour
    - Waste (supply costs)
    - Loot value
    - Spawn respawn rate
    
    **Data Sources:**
    - Community profit rates
    - Loot tables from TibiaWiki
    - Supply cost estimates
    """
    engine = get_recommendation_engine(db)
    
    # Get zones and sort by profit
    from app.models.hunt_zone import HuntZone
    
    zones = db.query(HuntZone).filter(
        HuntZone.min_level <= min_level,
        HuntZone.avg_profit_hour.isnot(None)
    ).order_by(
        HuntZone.avg_profit_hour.desc()
    ).limit(limit).all()
    
    return {
        "min_level": min_level,
        "zones": [
            {
                "id": zone.id,
                "name": zone.name,
                "min_level": zone.min_level,
                "avg_profit_hour": zone.avg_profit_hour,
                "difficulty": zone.difficulty,
                "requires_premium": zone.requires_premium,
                "city": zone.city,
            }
            for zone in zones
        ],
        "note": "Profit rates are community averages and may vary"
    }


@router.get("/exp-zones")
async def get_exp_zones(
    min_level: int = Query(..., ge=8, le=2000),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """
    Get zones optimized for maximum experience per hour
    
    **Returns zones with:**
    - High experience rates
    - Fast spawn respawn
    - Efficient routes
    
    **Best for:**
    - Power leveling
    - Rapid advancement
    - Event grinding
    
    **Data Sources:**
    - Community exp rates
    - Creature experience values (official)
    - Spawn density analysis (TibiaWiki)
    """
    from app.models.hunt_zone import HuntZone
    
    zones = db.query(HuntZone).filter(
        HuntZone.min_level <= min_level,
        HuntZone.avg_exp_hour.isnot(None)
    ).order_by(
        HuntZone.avg_exp_hour.desc()
    ).limit(limit).all()
    
    return {
        "min_level": min_level,
        "zones": [
            {
                "id": zone.id,
                "name": zone.name,
                "min_level": zone.min_level,
                "avg_exp_hour": zone.avg_exp_hour,
                "difficulty": zone.difficulty,
                "recommended_vocations": [
                    v for v in ['knight', 'paladin', 'sorcerer', 'druid', 'monk']
                    if getattr(zone, f"{v}s_recommended", False)
                ],
            }
            for zone in zones
        ],
        "note": "Experience rates based on community data and may vary by skill level"
    }


@router.get("/tibiawiki/search")
def search_tibiawiki(
    query: str = Query(..., min_length=3, description="Search query"),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """
    Search TibiaWiki for creatures, zones, and items
    
    Compatibility endpoint backed only by local canonical records.
    
    Useful for:
    - Finding creature information
    - Locating hunt zones
    - Item lookups
    
    **Data Source:** local Knowledge storage
    """
    normalized = normalize_search_text(query)
    matches: list[dict] = []
    sources = (
        ("creature", Creature, Creature.normalized_name),
        ("hunt_zone", HuntZone, HuntZone.normalized_name),
        ("item", Item, Item.normalized_name),
        ("quest", TibiaWikiQuest, TibiaWikiQuest.normalized_name),
    )
    for entity_type, model, name_column in sources:
        rows = db.query(model).filter(name_column.contains(normalized)).order_by(model.name.asc()).limit(limit).all()
        matches.extend({
            "entity_type": entity_type, "id": row.id, "name": row.name,
            "slug": getattr(row, "slug", None),
            "canonical_id": getattr(row, "knowledge_entity_id", None),
            "external_id": getattr(row, "external_id", None),
            "source_provider": getattr(row, "source_name", None) or getattr(row, "source_provider", None),
            "source_url": getattr(row, "source_url", None),
            "data_version": getattr(row, "data_version", 1),
            "last_synced_at": getattr(row, "last_synced_at", None),
        } for row in rows)
    results = sorted(matches, key=lambda value: (normalize_search_text(value["name"]) != normalized, value["name"].casefold()))[:limit]
    
    return {
        "query": query,
        "source": "local canonical Knowledge",
        "results": results,
        "total": len(results)
    }


@router.get("/tibiawiki/creature/{creature_name}")
def get_creature_from_wiki(creature_name: str, db: Session = Depends(get_db)):
    """
    Read locally synchronized TibiaWiki creature data
    
    **Returns:**
    - Official stats (HP, EXP, Armor, Speed)
    - Loot table
    - Spawn locations
    - Immunities and weaknesses
    
    **Data Source:** local Knowledge storage
    **Attribution:** All creature data © CipSoft GmbH, compiled by TibiaWiki community
    """
    data = db.query(Creature).filter(
        Creature.normalized_name == normalize_search_text(creature_name),
        Creature.is_hidden.is_(False),
    ).first()
    
    if not data:
        return {
            "error": "Creature not found",
            "creature_name": creature_name,
            "suggestion": "Try searching first to get exact name"
        }
    
    return {
        "creature_name": creature_name,
        "source": "local canonical Knowledge",
        "data": {
            "id": data.id, "name": data.name, "slug": data.slug,
            "canonical_id": data.knowledge_entity_id, "external_id": data.external_id,
            "source_provider": data.source_name, "source_url": data.source_url,
            "supplied_fields": list(data.supplied_fields or []),
            "missing_fields": list(data.missing_fields or []),
            "data_version": data.data_version, "last_synced_at": data.last_synced_at,
            "hitpoints": data.hitpoints, "experience": data.experience,
            "armor": data.armor, "speed": data.speed,
            "description": data.description, "behavior": data.behavior,
            "locations": list(data.locations or []),
            "loot": [{"name": row.item_name, "chance": row.percentage, "rarity": row.rarity} for row in data.loot_items],
        },
        "attribution": "Tibia and all related content © CipSoft GmbH"
    }
