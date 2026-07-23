"""
Tibia Character Validation Service
Handles validation of Tibia characters using the official Tibia Data API
"""
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class TibiaValidationService:
    """Service for validating Tibia characters and checking API status"""
    
    API_BASE_URL = "https://api.tibiadata.com/v4"
    TIMEOUT = 10  # seconds
    CONNECT_TIMEOUT = 3
    RETRY_ATTEMPTS = 2
    
    # Cache for API status checks
    _last_status_check: Optional[datetime] = None
    _cached_status: bool = True
    _cache_duration = timedelta(minutes=5)

    @classmethod
    def _session(cls) -> requests.Session:
        session = requests.Session()
        retry = Retry(
            total=cls.RETRY_ATTEMPTS,
            connect=cls.RETRY_ATTEMPTS,
            read=cls.RETRY_ATTEMPTS,
            backoff_factor=0.4,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session
    
    @classmethod
    def check_api_status(cls) -> Dict[str, Any]:
        """
        Check if Tibia API is available and responsive
        Returns status information including latency
        """
        # Check cache first
        if cls._last_status_check and datetime.now() - cls._last_status_check < cls._cache_duration:
            return {
                "status": "online" if cls._cached_status else "offline",
                "latency_ms": None,
                "cached": True,
                "last_check": cls._last_status_check.isoformat(),
                "message": "Using cached status"
            }
        
        start_time = datetime.now()
        try:
            # Try to fetch a known character (or worlds list) to test API
            with cls._session() as session:
                response = session.get(
                    f"{cls.API_BASE_URL}/worlds",
                    timeout=(cls.CONNECT_TIMEOUT, cls.TIMEOUT)
                )
            
            latency = (datetime.now() - start_time).total_seconds() * 1000  # ms
            
            if response.status_code == 200:
                data = response.json()
                # Check if response has expected structure
                if "worlds" in data and "worlds" in data["worlds"]:
                    cls._cached_status = True
                    cls._last_status_check = datetime.now()
                    return {
                        "status": "online",
                        "latency_ms": round(latency, 2),
                        "cached": False,
                        "last_check": cls._last_status_check.isoformat(),
                        "message": "Tibia API is operational"
                    }
            
            cls._cached_status = False
            cls._last_status_check = datetime.now()
            return {
                "status": "degraded",
                "latency_ms": round(latency, 2),
                "cached": False,
                "last_check": cls._last_status_check.isoformat(),
                "message": f"Tibia API returned status {response.status_code}"
            }
            
        except requests.exceptions.Timeout:
            cls._cached_status = False
            cls._last_status_check = datetime.now()
            logger.warning("Tibia API timeout")
            return {
                "status": "offline",
                "cached": False,
                "last_check": cls._last_status_check.isoformat(),
                "message": "Tibia API timeout - request took too long"
            }
            
        except requests.exceptions.RequestException as e:
            cls._cached_status = False
            cls._last_status_check = datetime.now()
            logger.error(f"Tibia API error: {e}")
            return {
                "status": "offline",
                "cached": False,
                "last_check": cls._last_status_check.isoformat(),
                "message": f"Tibia API error: {str(e)}"
            }
    
    @classmethod
    def validate_character(cls, character_name: str, strict: bool = True) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """
        Validate a Tibia character exists and return its data
        
        Args:
            character_name: Name of the character to validate
            strict: If True, fail when API is down. If False, allow without validation
        
        Returns:
            Tuple of (is_valid, character_data, error_message)
        """
        try:
            with cls._session() as session:
                response = session.get(
                    f"{cls.API_BASE_URL}/character/{character_name}",
                    timeout=(cls.CONNECT_TIMEOUT, cls.TIMEOUT)
                )
            
            if response.status_code == 200:
                data = response.json()
                
                # Check if character exists
                if "character" in data and "character" in data["character"]:
                    char_data = data["character"]["character"]
                    
                    # Character not found
                    if "name" not in char_data:
                        return False, None, "Character not found in Tibia"
                    
                    # Character found - extract useful data
                    guild_data = char_data.get("guild") or {}
                    character_info = {
                        "name": char_data.get("name"),
                        "level": char_data.get("level"),
                        "vocation": char_data.get("vocation"),
                        "world": char_data.get("world"),
                        "sex": char_data.get("sex"),
                        "residence": char_data.get("residence"),
                        "guild_name": guild_data.get("name") if isinstance(guild_data, dict) else guild_data,
                        "guild_rank": guild_data.get("rank") if isinstance(guild_data, dict) else None,
                    }
                    
                    return True, character_info, None
                else:
                    return False, None, "Character not found in Tibia"
            
            elif response.status_code == 404:
                return False, None, "Character not found in Tibia"
            
            else:
                error_msg = f"Tibia API returned status {response.status_code}"
                logger.warning(error_msg)
                
                if strict:
                    return False, None, error_msg
                else:
                    # Allow registration without validation
                    logger.info(f"Allowing registration without validation (non-strict mode)")
                    return True, None, None
        
        except requests.exceptions.Timeout:
            error_msg = "Tibia API timeout"
            logger.warning(error_msg)
            
            if strict:
                return False, None, f"{error_msg} - Please try again later"
            else:
                logger.info("Allowing registration without validation (API timeout)")
                return True, None, None
        
        except requests.exceptions.RequestException as e:
            error_msg = f"Tibia API error: {str(e)}"
            logger.error(error_msg)
            
            if strict:
                return False, None, f"Could not validate character - {str(e)}"
            else:
                logger.info("Allowing registration without validation (API error)")
                return True, None, None
