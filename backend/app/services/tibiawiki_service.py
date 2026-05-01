"""
TibiaWiki API Integration Service

Data source: https://tibia.fandom.com/api.php
Documentation: https://www.mediawiki.org/wiki/API:Main_page

This service fetches creature data, hunt zones, and other information
from the official TibiaWiki API.
"""

import requests
from typing import Dict, List, Optional, Any
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

TIBIAWIKI_API_URL = "https://tibia.fandom.com/api.php"
USER_AGENT = "TibiaBestiary/2.0 (Educational Project)"


class TibiaWikiService:
    """Service for fetching data from TibiaWiki API"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': USER_AGENT,
            'Accept': 'application/json'
        })
    
    def _make_request(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Make a request to TibiaWiki API"""
        try:
            params['format'] = 'json'
            response = self.session.get(TIBIAWIKI_API_URL, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"TibiaWiki API request failed: {e}")
            return {}
    
    @lru_cache(maxsize=128)
    def get_creature_data(self, creature_name: str) -> Optional[Dict[str, Any]]:
        """
        Fetch creature data from TibiaWiki
        
        Args:
            creature_name: Name of the creature
            
        Returns:
            Dictionary with creature data including:
            - hitpoints
            - experience
            - armor
            - speed
            - loot
            - locations
            - immunities
            - weaknesses
        """
        params = {
            'action': 'parse',
            'page': creature_name,
            'prop': 'wikitext',
        }
        
        data = self._make_request(params)
        
        if 'parse' not in data:
            logger.warning(f"Creature not found: {creature_name}")
            return None
        
        # Parse the wikitext to extract creature data
        wikitext = data['parse'].get('wikitext', {}).get('*', '')
        return self._parse_creature_wikitext(wikitext)
    
    def _parse_creature_wikitext(self, wikitext: str) -> Dict[str, Any]:
        """Parse creature infobox from wikitext"""
        creature_data = {}
        
        # Extract data from Infobox_Creature template
        lines = wikitext.split('\n')
        for line in lines:
            line = line.strip()
            
            if '|hitpoints' in line.lower():
                hp = self._extract_number(line)
                if hp:
                    creature_data['hitpoints'] = hp
            
            elif '|experience' in line.lower():
                exp = self._extract_number(line)
                if exp:
                    creature_data['experience'] = exp
            
            elif '|armor' in line.lower():
                armor = self._extract_number(line)
                if armor:
                    creature_data['armor'] = armor
            
            elif '|speed' in line.lower():
                speed = self._extract_number(line)
                if speed:
                    creature_data['speed'] = speed
        
        return creature_data
    
    def _extract_number(self, line: str) -> Optional[int]:
        """Extract number from a wikitext line"""
        import re
        match = re.search(r'=\s*(\d+)', line)
        if match:
            return int(match.group(1))
        return None
    
    def search_creatures(self, query: str, limit: int = 10) -> List[str]:
        """
        Search for creatures by name
        
        Args:
            query: Search query
            limit: Maximum number of results
            
        Returns:
            List of creature names
        """
        params = {
            'action': 'opensearch',
            'search': query,
            'limit': limit,
            'namespace': 0,  # Main namespace
        }
        
        data = self._make_request(params)
        
        if len(data) >= 2:
            return data[1]  # Returns list of page titles
        
        return []
    
    def get_hunt_zones(self) -> List[Dict[str, Any]]:
        """
        Fetch hunting places from TibiaWiki
        
        Returns:
            List of hunt zones with data
        """
        params = {
            'action': 'query',
            'list': 'categorymembers',
            'cmtitle': 'Category:Hunting_Places',
            'cmlimit': 100,
        }
        
        data = self._make_request(params)
        
        zones = []
        if 'query' in data and 'categorymembers' in data['query']:
            for member in data['query']['categorymembers']:
                zone_name = member.get('title', '')
                if zone_name:
                    zones.append({
                        'name': zone_name,
                        'page_id': member.get('pageid'),
                    })
        
        return zones
    
    def get_zone_details(self, zone_name: str) -> Optional[Dict[str, Any]]:
        """
        Fetch detailed information about a hunting zone
        
        Args:
            zone_name: Name of the hunting zone
            
        Returns:
            Dictionary with zone details including:
            - location
            - level_range
            - recommended_vocations
            - creatures
            - exp_rate
            - profit_rate
        """
        params = {
            'action': 'parse',
            'page': zone_name,
            'prop': 'wikitext',
        }
        
        data = self._make_request(params)
        
        if 'parse' not in data:
            return None
        
        wikitext = data['parse'].get('wikitext', {}).get('*', '')
        return self._parse_zone_wikitext(wikitext)
    
    def _parse_zone_wikitext(self, wikitext: str) -> Dict[str, Any]:
        """Parse hunting place infobox from wikitext"""
        zone_data = {}
        
        lines = wikitext.split('\n')
        for line in lines:
            line = line.strip()
            
            if '|location' in line.lower():
                zone_data['location'] = line.split('=', 1)[1].strip() if '=' in line else ''
            
            elif '|lvl' in line.lower() or '|level' in line.lower():
                zone_data['level_range'] = line.split('=', 1)[1].strip() if '=' in line else ''
            
            elif '|exp' in line.lower():
                zone_data['exp_rate'] = line.split('=', 1)[1].strip() if '=' in line else ''
            
            elif '|profit' in line.lower():
                zone_data['profit_rate'] = line.split('=', 1)[1].strip() if '=' in line else ''
        
        return zone_data
    
    def get_weekly_bosses(self) -> List[Dict[str, Any]]:
        """
        Fetch information about world bosses and weeklies
        
        Returns:
            List of world bosses with spawn information
        """
        params = {
            'action': 'query',
            'list': 'categorymembers',
            'cmtitle': 'Category:World_Bosses',
            'cmlimit': 50,
        }
        
        data = self._make_request(params)
        
        bosses = []
        if 'query' in data and 'categorymembers' in data['query']:
            for member in data['query']['categorymembers']:
                boss_name = member.get('title', '')
                if boss_name:
                    bosses.append({
                        'name': boss_name,
                        'page_id': member.get('pageid'),
                    })
        
        return bosses


# Singleton instance
tibiawiki_service = TibiaWikiService()
