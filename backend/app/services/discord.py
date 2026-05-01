"""
Discord Integration Service
"""
import httpx
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class DiscordService:
    """Service for sending messages to Discord via webhooks"""
    
    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url
        
    async def send_announcement(
        self,
        title: str,
        content: str,
        announcement_type: str = "general",
        author: str = "Guild System",
        url: Optional[str] = None
    ) -> bool:
        """
        Send an announcement to Discord channel
        
        Args:
            title: Announcement title
            content: Announcement content
            announcement_type: Type of announcement (general, hunt, contest)
            author: Author name
            url: Optional URL to the announcement
            
        Returns:
            True if successful, False otherwise
        """
        if not self.webhook_url:
            logger.warning("Discord webhook URL not configured")
            return False
            
        # Color mapping for different announcement types
        color_map = {
            "general": 0x6B7280,  # Gray
            "hunt": 0xEF4444,      # Red
            "contest": 0xA855F7    # Purple
        }
        
        embed = {
            "title": f"📢 {title}",
            "description": content[:4000],  # Discord limit
            "color": color_map.get(announcement_type, 0x6B7280),
            "author": {
                "name": author,
                "icon_url": "https://static.wikia.nocookie.net/tibia/images/f/f0/Guild_Icon.gif"
            },
            "footer": {
                "text": f"Type: {announcement_type.upper()}"
            }
        }
        
        if url:
            embed["url"] = url
            
        payload = {
            "embeds": [embed],
            "username": "Bloodborne Warhowl",
            "avatar_url": "https://static.wikia.nocookie.net/tibia/images/f/f0/Guild_Icon.gif"
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.webhook_url,
                    json=payload,
                    timeout=10.0
                )
                
                if response.status_code == 204:
                    logger.info(f"Successfully sent announcement to Discord: {title}")
                    return True
                else:
                    logger.error(f"Failed to send to Discord. Status: {response.status_code}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error sending to Discord: {str(e)}")
            return False
            
    async def send_event_notification(
        self,
        event_name: str,
        event_date: str,
        description: str,
        participants: int = 0,
        rewards: Optional[str] = None
    ) -> bool:
        """Send event notification to Discord"""
        
        if not self.webhook_url:
            return False
            
        embed = {
            "title": f"🎮 {event_name}",
            "description": description,
            "color": 0xF59E0B,  # Amber
            "fields": [
                {
                    "name": "📅 Date",
                    "value": event_date,
                    "inline": True
                }
            ]
        }
        
        if participants > 0:
            embed["fields"].append({
                "name": "👥 Participants",
                "value": str(participants),
                "inline": True
            })
            
        if rewards:
            embed["fields"].append({
                "name": "🏆 Rewards",
                "value": rewards,
                "inline": False
            })
            
        payload = {
            "embeds": [embed],
            "username": "Bloodborne Warhowl Events",
            "avatar_url": "https://static.wikia.nocookie.net/tibia/images/f/f0/Guild_Icon.gif"
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.webhook_url,
                    json=payload,
                    timeout=10.0
                )
                return response.status_code == 204
        except Exception as e:
            logger.error(f"Error sending event to Discord: {str(e)}")
            return False

# Global instance
discord_service = DiscordService()

def set_discord_webhook(url: str):
    """Update the Discord webhook URL"""
    global discord_service
    discord_service.webhook_url = url
    logger.info("Discord webhook URL updated")
