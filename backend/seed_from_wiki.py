
import asyncio
from app.db.database import SessionLocal, verify_connection_and_schema
from app.models import Creature, Loot, HuntZone, User, Quest
from app.services.extractor import TibiaWikiExtractor

async def seed_data():
    # Schema creation is exclusively managed by Alembic.
    verify_connection_and_schema()
    db = SessionLocal()

    # Fetch Creatures
    extractor = TibiaWikiExtractor()
    creatures_to_fetch = ["Dragon", "Dragon Lord", "Demon", "Cyclops", "Rat", "Monk (Creature)"]
    
    print("Fetching creatures from Wiki...")
    for name in creatures_to_fetch:
        try:
            data = await extractor.get_creature_by_name(name)
            if not data or not data.get("name"):
                print(f"Failed to fetch {name}")
                continue

            # Check if exists
            existing = db.query(Creature).filter(Creature.name == data["name"]).first()
            if existing:
                print(f"Updating {data['name']}...")
                # Update logic here if needed
                creature = existing
            else:
                print(f"Creating {data['name']}...")
                creature = Creature(
                    name=data["name"],
                    hitpoints=data.get("hp", 0),
                    experience=data.get("exp", 0),
                    armor=data.get("armor", 0),
                    speed=data.get("speed", 0),
                    max_damage=data.get("max_damage", 0),
                    summon_cost=data.get("summon_cost"),
                    convince_cost=data.get("convince_cost"),
                    image_url=data.get("image_url"),
                    difficulty="Medium" # Placeholder
                )
                db.add(creature)
                db.flush() # Get ID

            # clear old loot
            db.query(Loot).filter(Loot.creature_id == creature.id).delete()
            
            # Add Loot
            for item in data.get("loot", []):
                loot = Loot(
                    creature_id=creature.id,
                    item_name=item["name"],
                    percentage=0.0, # Need parsing
                    rarity=item["chance"]
                )
                db.add(loot)
            
            db.commit()
            
        except Exception as e:
            print(f"Error processing {name}: {e}")
            db.rollback()

    await extractor.close()
    db.close()
    print("Seeding complete!")

if __name__ == "__main__":
    asyncio.run(seed_data())
