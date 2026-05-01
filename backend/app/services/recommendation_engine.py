"""
Advanced Recommendation Engine for Hunt Zones

This service provides intelligent recommendations based on:
- Character level
- Vocation
- Party composition
- Goal (exp, profit, both)
- Player skill level

Algorithm considers multiple factors to suggest optimal hunting spots.
"""

from typing import List, Dict, Optional, Any
from sqlalchemy.orm import Session
from ..models.hunt_zone import HuntZone
from ..models.creature import Creature
from ..schemas import Vocation


class RecommendationEngine:
    """Advanced recommendation engine for hunt zones"""
    
    # Vocation characteristics
    VOCATION_PROFILES = {
        'knight': {
            'melee': True,
            'range': False,
            'magic': False,
            'healing': False,
            'tank': True,
            'preferred_spawns': ['close_range', 'crowded'],
        },
        'paladin': {
            'melee': False,
            'range': True,
            'magic': False,
            'healing': False,
            'tank': False,
            'preferred_spawns': ['ranged', 'open'],
        },
        'sorcerer': {
            'melee': False,
            'range': False,
            'magic': True,
            'healing': False,
            'tank': False,
            'preferred_spawns': ['area_magic', 'grouped'],
        },
        'druid': {
            'melee': False,
            'range': False,
            'magic': True,
            'healing': True,
            'tank': False,
            'preferred_spawns': ['area_magic', 'healing_safe'],
        },
        'monk': {
            'melee': True,
            'range': False,
            'magic': True,
            'healing': True,
            'tank': False,
            'preferred_spawns': ['hybrid', 'versatile'],
        },
    }
    
    # Party synergies
    PARTY_SYNERGIES = {
        ('knight', 'druid'): 1.3,  # Classic tank + healer
        ('knight', 'sorcerer'): 1.2,  # Tank + damage
        ('knight', 'paladin'): 1.15,  # Mixed damage
        ('paladin', 'druid'): 1.2,  # Range + support
        ('sorcerer', 'druid'): 1.25,  # Double mage
        ('knight', 'sorcerer', 'druid'): 1.5,  # Full team hunt
        ('knight', 'paladin', 'sorcerer', 'druid'): 1.8,  # Optimal 4-man
    }
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_solo_recommendations(
        self,
        vocation: Vocation,
        level: int,
        goal: str = 'exp',  # 'exp', 'profit', 'balanced'
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get hunt zone recommendations for solo player
        
        Args:
            vocation: Player vocation
            level: Player level
            goal: Hunting goal (exp/profit/balanced)
            limit: Maximum number of recommendations
            
        Returns:
            List of recommended zones with scores
        """
        # Get zones within appropriate level range
        level_min = max(1, level - 50)
        level_max = level + 20
        
        zones = self.db.query(HuntZone).filter(
            HuntZone.min_level >= level_min,
            HuntZone.min_level <= level_max
        ).all()
        
        recommendations = []
        
        for zone in zones:
            score = self._calculate_solo_score(zone, vocation, level, goal)
            
            if score > 0:
                recommendations.append({
                    'zone': zone,
                    'score': score,
                    'reasons': self._generate_reasons(zone, vocation, level, goal, is_party=False),
                    'estimated_exp': self._estimate_exp(zone, level, vocation),
                    'estimated_profit': self._estimate_profit(zone, level, vocation),
                })
        
        # Sort by score descending
        recommendations.sort(key=lambda x: x['score'], reverse=True)
        
        return recommendations[:limit]
    
    def get_party_recommendations(
        self,
        party_composition: List[Dict[str, Any]],  # [{'vocation': 'knight', 'level': 100}, ...]
        goal: str = 'exp',
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get hunt zone recommendations for party
        
        Args:
            party_composition: List of party members with vocation and level
            goal: Hunting goal
            limit: Maximum number of recommendations
            
        Returns:
            List of recommended zones optimized for party
        """
        if not party_composition:
            return []
        
        # Calculate average level
        avg_level = sum(member['level'] for member in party_composition) / len(party_composition)
        
        # Get vocations
        vocations = tuple(sorted([member['vocation'] for member in party_composition]))
        
        # Determine level range
        min_level = int(avg_level - 30)
        max_level = int(avg_level + 30)
        
        zones = self.db.query(HuntZone).filter(
            HuntZone.min_level >= min_level,
            HuntZone.min_level <= max_level
        ).all()
        
        recommendations = []
        
        for zone in zones:
            score = self._calculate_party_score(zone, party_composition, goal)
            
            if score > 0:
                recommendations.append({
                    'zone': zone,
                    'score': score,
                    'reasons': self._generate_party_reasons(zone, party_composition, goal),
                    'synergy_bonus': self._calculate_synergy(vocations),
                    'estimated_exp': self._estimate_party_exp(zone, party_composition),
                    'estimated_profit': self._estimate_party_profit(zone, party_composition),
                })
        
        recommendations.sort(key=lambda x: x['score'], reverse=True)
        
        return recommendations[:limit]
    
    def _calculate_solo_score(
        self,
        zone: HuntZone,
        vocation: Vocation,
        level: int,
        goal: str
    ) -> float:
        """Calculate recommendation score for solo hunting"""
        score = 0.0
        
        # Check if zone is recommended for vocation
        vocation_field = f"{vocation}s_recommended"
        if hasattr(zone, vocation_field) and getattr(zone, vocation_field):
            score += 50
        
        # Level appropriateness (bell curve)
        level_diff = abs(zone.min_level - level)
        if level_diff <= 10:
            score += 30
        elif level_diff <= 20:
            score += 20
        elif level_diff <= 30:
            score += 10
        
        # Goal-based scoring
        if goal == 'exp' and zone.avg_exp_hour:
            score += min(zone.avg_exp_hour / 10000, 20)
        elif goal == 'profit' and zone.avg_profit_hour:
            score += min(zone.avg_profit_hour / 1000, 20)
        elif goal == 'balanced':
            if zone.avg_exp_hour and zone.avg_profit_hour:
                score += min((zone.avg_exp_hour / 10000 + zone.avg_profit_hour / 1000) / 2, 20)
        
        # Difficulty consideration
        if zone.difficulty:
            difficulty_map = {
                'Trivial': -10,
                'Easy': 5,
                'Medium': 10,
                'Hard': 0,
                'Extreme': -20
            }
            score += difficulty_map.get(zone.difficulty, 0)
        
        return max(0, score)
    
    def _calculate_party_score(
        self,
        zone: HuntZone,
        party: List[Dict[str, Any]],
        goal: str
    ) -> float:
        """Calculate recommendation score for party hunting"""
        base_score = 0.0
        
        # Check vocations match
        vocation_matches = 0
        for member in party:
            vocation = member['vocation']
            vocation_field = f"{vocation}s_recommended"
            if hasattr(zone, vocation_field) and getattr(zone, vocation_field):
                vocation_matches += 1
        
        base_score += (vocation_matches / len(party)) * 40
        
        # Party synergy
        vocations = tuple(sorted([m['vocation'] for m in party]))
        synergy = self._calculate_synergy(vocations)
        base_score += synergy * 30
        
        # Level appropriateness
        avg_level = sum(m['level'] for m in party) / len(party)
        level_diff = abs(zone.min_level - avg_level)
        if level_diff <= 15:
            base_score += 30
        elif level_diff <= 30:
            base_score += 15
        
        return max(0, base_score)
    
    def _calculate_synergy(self, vocations: tuple) -> float:
        """Calculate party synergy bonus"""
        return self.PARTY_SYNERGIES.get(vocations, 1.0)
    
    def _generate_reasons(
        self,
        zone: HuntZone,
        vocation: Vocation,
        level: int,
        goal: str,
        is_party: bool = False
    ) -> List[str]:
        """Generate human-readable reasons for recommendation"""
        reasons = []
        
        vocation_field = f"{vocation}s_recommended"
        if hasattr(zone, vocation_field) and getattr(zone, vocation_field):
            reasons.append(f"Recommended for {vocation}s")
        
        level_diff = zone.min_level - level
        if level_diff <= 0:
            reasons.append("Suitable for your level")
        elif level_diff <= 10:
            reasons.append("Slightly challenging (good for exp)")
        
        if goal == 'exp' and zone.avg_exp_hour:
            reasons.append(f"High exp rate: {zone.avg_exp_hour:,}/h")
        
        if goal == 'profit' and zone.avg_profit_hour:
            reasons.append(f"Good profit: {zone.avg_profit_hour:,}k/h")
        
        if zone.size:
            reasons.append(f"{zone.size} spawn size")
        
        return reasons
    
    def _generate_party_reasons(
        self,
        zone: HuntZone,
        party: List[Dict[str, Any]],
        goal: str
    ) -> List[str]:
        """Generate reasons for party recommendations"""
        reasons = []
        
        vocations = [m['vocation'] for m in party]
        vocation_key = tuple(sorted(vocations))
        
        synergy = self._calculate_synergy(vocation_key)
        if synergy > 1.2:
            reasons.append(f"Excellent party synergy (+{int((synergy - 1) * 100)}%)")
        
        # Check if has tank
        if 'knight' in vocations:
            reasons.append("Tank available for blocking")
        
        # Check if has healer
        if 'druid' in vocations or 'monk' in vocations:
            reasons.append("Healer available for support")
        
        # Check for area damage
        if 'sorcerer' in vocations or 'druid' in vocations:
            reasons.append("Area damage dealers for efficiency")
        
        return reasons
    
    def _estimate_exp(self, zone: HuntZone, level: int, vocation: Vocation) -> Optional[int]:
        """Estimate experience per hour"""
        if zone.avg_exp_hour:
            # Adjust based on level difference
            level_factor = 1.0 + (level - zone.min_level) * 0.02
            return int(zone.avg_exp_hour * level_factor)
        return None
    
    def _estimate_profit(self, zone: HuntZone, level: int, vocation: Vocation) -> Optional[int]:
        """Estimate profit per hour"""
        if zone.avg_profit_hour:
            return zone.avg_profit_hour
        return None
    
    def _estimate_party_exp(self, zone: HuntZone, party: List[Dict[str, Any]]) -> Optional[int]:
        """Estimate party experience per hour"""
        if zone.avg_exp_hour:
            party_size = len(party)
            vocations = tuple(sorted([m['vocation'] for m in party]))
            synergy = self._calculate_synergy(vocations)
            
            # Party gets bonus exp with synergy
            return int(zone.avg_exp_hour * synergy * (1 + party_size * 0.1))
        return None
    
    def _estimate_party_profit(self, zone: HuntZone, party: List[Dict[str, Any]]) -> Optional[int]:
        """Estimate party profit per hour"""
        if zone.avg_profit_hour:
            return zone.avg_profit_hour
        return None


def get_recommendation_engine(db: Session) -> RecommendationEngine:
    """Get recommendation engine instance"""
    return RecommendationEngine(db)
