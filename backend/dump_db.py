
import json
import os
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.models import Creature, HuntZone, Loot, SpawnLocation

def dump_data():
    db: Session = SessionLocal()
    data = {
        "creatures": [],
        "hunt_zones": [],
        "loot": [],
        "spawns": []
    }

    print("Fetching Creatures...")
    creatures = db.query(Creature).all()
    for c in creatures:
        data["creatures"].append({
            "id": c.id,
            "name": c.name,
            "hitpoints": c.hitpoints,
            "experience": c.experience,
            "armor": c.armor,
            "speed": c.speed,
            "max_damage": c.max_damage,
            "difficulty": c.difficulty,
            "image_url": c.image_url,
            "description": c.description,
            "behavior": c.behavior,
            "weaknesses": [w.name for w in c.weaknesses],
            "resistances": [r.name for r in c.resistances]
        })

    print("Fetching Hunt Zones...")
    zones = db.query(HuntZone).all()
    for z in zones:
        data["hunt_zones"].append({
            "id": z.id,
            "name": z.name,
            "city": z.city,
            "min_level": z.min_level,
            "max_level": z.max_level,
            "avg_exp_hour": z.avg_exp_hour,
            "avg_profit_hour": z.avg_profit_hour,
            "monks_recommended": z.monks_recommended
        })

    print("Fetching Loot...")
    loot_items = db.query(Loot).all()
    for l in loot_items:
        data["loot"].append({
            "id": l.id,
            "creature_id": l.creature_id,
            "item_name": l.item_name,
            "percentage": l.percentage,
            "item_value": l.item_value
        })

    print(f"Exporting {len(data['creatures'])} creatures, {len(data['hunt_zones'])} zones, {len(data['loot'])} loot items.")
    
    with open("tibia_data.json", "w") as f:
        json.dump(data, f, indent=4)
        
    print("Success! Data saved to tibia_data.json")

if __name__ == "__main__":
    dump_data()
