"""
Hunt recommendation service - Recommends hunting zones based on vocation and level
"""
from sqlalchemy.orm import Session
from typing import List, Optional
from app.models import HuntZone, Creature, SpawnLocation
from app.schemas import HuntRecommendation, HuntZone as HuntZoneSchema, CreatureSimple


class HuntRecommendationService:
    """Service for recommending hunt zones"""
    
    VOCATION_MAP = {
        "knight": "knights_recommended",
        "paladin": "paladins_recommended",
        "sorcerer": "sorcerers_recommended",
        "druid": "druids_recommended",
        "monk": "monks_recommended"
    }
    
    @staticmethod
    def get_recommendations(
        db: Session,
        vocation: str,
        level: int,
        limit: int = 10
    ) -> List[HuntRecommendation]:
        """
        Get hunt zone recommendations based on vocation and level
        
        Args:
            db: Database session
            vocation: Player vocation (knight, paladin, sorcerer, druid, monk)
            level: Player level
            limit: Maximum number of recommendations
            
        Returns:
            List of hunt zone recommendations sorted by score
        """
        vocation_lower = vocation.lower()
        
        if vocation_lower not in HuntRecommendationService.VOCATION_MAP:
            raise ValueError(f"Invalid vocation: {vocation}. Must be one of: knight, paladin, sorcerer, druid, monk")
        
        vocation_field = HuntRecommendationService.VOCATION_MAP[vocation_lower]
        
        # Query zones within level range and recommended for vocation
        query = db.query(HuntZone).filter(
            HuntZone.min_level <= level
        )
        
        # Add max level filter if set
        query = query.filter(
            (HuntZone.max_level.is_(None)) | (HuntZone.max_level >= level)
        )
        
        zones = query.all()
        
        recommendations = []
        
        for zone in zones:
            score, reasons = HuntRecommendationService._calculate_score(
                zone, vocation_field, level
            )
            
            if score > 0:
                # Get creatures in this zone
                creatures = HuntRecommendationService._get_zone_creatures(db, zone.id)
                
                recommendations.append(
                    HuntRecommendation(
                        zone=HuntZoneSchema.from_orm(zone),
                        score=score,
                        reasons=reasons,
                        creatures=creatures
                    )
                )
        
        # Sort by score descending
        recommendations.sort(key=lambda x: x.score, reverse=True)
        
        return recommendations[:limit]
    
    @staticmethod
    def _calculate_score(zone: HuntZone, vocation_field: str, level: int) -> tuple[float, List[str]]:
        """Calculate recommendation score for a zone"""
        score = 0.0
        reasons = []
        
        # Base score for vocation match
        if getattr(zone, vocation_field):
            score += 40
            reasons.append(f"Recommended for this vocation")
        
        # Level match scoring
        if zone.recommended_level:
            level_diff = abs(level - zone.recommended_level)
            if level_diff == 0:
                score += 30
                reasons.append("Perfect level match")
            elif level_diff <= 10:
                score += 20 - level_diff
                reasons.append("Good level match")
            elif level_diff <= 20:
                score += 10 - (level_diff - 10) * 0.5
        elif zone.min_level is not None:
            # Use min/max levels if no recommended level
            mid_level = zone.min_level + ((zone.max_level or zone.min_level + 50) - zone.min_level) / 2
            level_diff = abs(level - mid_level)
            if level_diff <= 15:
                score += 15 - level_diff * 0.5
        
        # Exp and profit bonuses
        if zone.avg_exp_hour:
            exp_score = min(zone.avg_exp_hour / 50000, 15)  # Max 15 points
            score += exp_score
            if zone.avg_exp_hour > 100000:
                reasons.append("Excellent experience rate")
            elif zone.avg_exp_hour > 50000:
                reasons.append("Good experience rate")
        
        if zone.avg_profit_hour:
            if zone.avg_profit_hour > 0:
                profit_score = min(zone.avg_profit_hour / 30000, 10)  # Max 10 points
                score += profit_score
                if zone.avg_profit_hour > 50000:
                    reasons.append("High profit potential")
                elif zone.avg_profit_hour > 20000:
                    reasons.append("Good profit potential")
        
        # Penalty for quest requirement
        if zone.requires_quest:
            score -= 5
            reasons.append(f"Requires quest: {zone.quest_name or 'Unknown'}")
        
        # Size bonus (larger zones generally better)
        size_bonus = {"Small": 0, "Medium": 2, "Large": 5, "Huge": 8}
        score += size_bonus.get(zone.size, 0)
        
        return score, reasons
    
    @staticmethod
    def _get_zone_creatures(db: Session, zone_id: int, limit: int = 5) -> List[CreatureSimple]:
        """Get main creatures in a zone"""
        spawns = db.query(SpawnLocation).filter(
            SpawnLocation.hunt_zone_id == zone_id
        ).limit(limit).all()
        
        creatures = []
        for spawn in spawns:
            if spawn.creature:
                creatures.append(CreatureSimple(
                    id=spawn.creature.id,
                    name=spawn.creature.name,
                    hitpoints=spawn.creature.hitpoints,
                    experience=spawn.creature.experience,
                    difficulty=spawn.creature.difficulty,
                    image_url=spawn.creature.image_url
                ))
        
        return creatures
