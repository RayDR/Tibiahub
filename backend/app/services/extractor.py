import httpx
import mwparserfromhell
import asyncio
import re
from typing import List, Dict, Any, Optional

class TibiaWikiExtractor:
    BASE_URL = "https://tibia.fandom.com/api.php"
    
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        await self.client.aclose()

    async def get_creature_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        content = await self.get_page_content(name)
        if content:
            return self.parse_creature(content)
        return None

    async def get_category_members(self, category: str, limit: int = 500) -> List[str]:
        """Fetch regular pages from a category."""
        params = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": f"Category:{category}",
            "cmlimit": limit,
            "cmtype": "page",
            "format": "json"
        }
        response = await self.client.get(self.BASE_URL, params=params)
        data = response.json()
        members = data.get("query", {}).get("categorymembers", [])
        return [m["title"] for m in members]

    async def get_page_content(self, title: str) -> Optional[str]:
        """Fetch raw wikitext of a page."""
        params = {
            "action": "parse",
            "page": title,
            "prop": "wikitext",
            "format": "json"
        }
        try:
            response = await self.client.get(self.BASE_URL, params=params)
            data = response.json()
            return data.get("parse", {}).get("wikitext", {}).get("*")
        except Exception as e:
            print(f"Error fetching {title}: {e}")
            return None

    def parse_creature(self, wikitext: str) -> Dict[str, Any]:
        """Parse Creature Infobox."""
        wikicode = mwparserfromhell.parse(wikitext)
        templates = wikicode.filter_templates()
        creature_data = {}
        
        for template in templates:
            if template.name.matches("Infobox Creature"):
                # Basic stats
                creature_data["name"] = str(template.get("name").value).strip() if template.has("name") else ""
                creature_data["hp"] = self._clean_number(template.get("hp").value) if template.has("hp") else 0
                creature_data["exp"] = self._clean_number(template.get("exp").value) if template.has("exp") else 0
                creature_data["armor"] = self._clean_number(template.get("armor").value) if template.has("armor") else 0
                creature_data["speed"] = self._clean_number(template.get("speed").value) if template.has("speed") else 0
                creature_data["max_damage"] = self._clean_number(template.get("maxdmg").value) if template.has("maxdmg") else 0
                creature_data["summon_cost"] = self._clean_number(template.get("summon").value) if template.has("summon") else None
                creature_data["convince_cost"] = self._clean_number(template.get("convince").value) if template.has("convince") else None
                
                # Image
                if template.has("image"):
                    img_name = str(template.get("image").value).strip()
                    if img_name:
                        # Construct direct file path URL
                        creature_data["image_url"] = f"https://tibia.fandom.com/wiki/Special:FilePath/{img_name.replace(' ', '_')}"

            # Parse Loot
            if template.name.matches("Loot Table") or template.name.matches("Loot List"):
                 loot_items = []
                 for param in template.params:
                     # Check if param value contains Loot Item template
                     if "Loot Item" in str(param.value):
                         # Recursively parse the param value to find Loot Item templates
                         inner_code = mwparserfromhell.parse(str(param.value))
                         for inner_tpl in inner_code.filter_templates():
                             if inner_tpl.name.matches("Loot Item"):
                                 item_name = str(inner_tpl.get(1).value).strip() if inner_tpl.has(1) else "Unknown"
                                 chance = str(inner_tpl.get(2).value).strip() if inner_tpl.has(2) else "Unknown"
                                 loot_items.append({"name": item_name, "chance": chance})
                 creature_data["loot"] = loot_items

                
        return creature_data

    def _clean_number(self, value) -> int:
        """Extract first number from string, ignore commas."""
        text = str(value).strip()
        # Handle ranges like "0-100" -> take max? or avg? Let's take max for safety or simple first number
        # Often it comes like "1000" or "1,000" or "Unknown"
        match = re.search(r'[\d,]+', text)
        if match:
            return int(match.group(0).replace(",", ""))
        return 0

    async def get_all_creatures(self, limit: int = 10) -> List[Dict[str, Any]]:
        titles = await self.get_category_members("Creatures", 500) # Fetch more to skip meta pages
        results = []
        count = 0
        for title in titles:
            if count >= limit:
                break
            # Skip lists and meta pages
            if any(x in title for x in ["List of", "Creatures", "Bestiary", "Category", "Sounds", "Update", "History", "Tibia"]):
                continue
                
            print(f"Fetching {title}...")
            content = await self.get_page_content(title)
            if content:
                data = self.parse_creature(content)
                if data.get("name"):
                    results.append(data)
                    count += 1
        return results

if __name__ == "__main__":
    async def main():
        extractor = TibiaWikiExtractor()
        data = await extractor.get_all_creatures(5)
        print(data)
        await extractor.close()
        
    asyncio.run(main())
