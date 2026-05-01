"""
Seed database with example Tibia bestiary data
"""
from sqlalchemy.orm import Session
from app.db.database import SessionLocal, init_db
from app.models import Creature, Element, Loot, HuntZone, SpawnLocation


def seed_elements(db: Session):
    """Seed damage elements"""
    elements_data = [
        {"name": "Physical", "color": "#8B4513", "icon_url": "/icons/physical.png"},
        {"name": "Fire", "color": "#FF4500", "icon_url": "/icons/fire.png"},
        {"name": "Ice", "color": "#00CED1", "icon_url": "/icons/ice.png"},
        {"name": "Energy", "color": "#9370DB", "icon_url": "/icons/energy.png"},
        {"name": "Earth", "color": "#32CD32", "icon_url": "/icons/earth.png"},
        {"name": "Holy", "color": "#FFD700", "icon_url": "/icons/holy.png"},
        {"name": "Death", "color": "#8B0000", "icon_url": "/icons/death.png"},
    ]
    
    elements = []
    for elem_data in elements_data:
        element = Element(**elem_data)
        db.add(element)
        elements.append(element)
    
    db.commit()
    return elements


def seed_creatures(db: Session, elements: list):
    """Seed example creatures"""
    
    # Get elements by name for easy reference
    physical = next(e for e in elements if e.name == "Physical")
    fire = next(e for e in elements if e.name == "Fire")
    ice = next(e for e in elements if e.name == "Ice")
    energy = next(e for e in elements if e.name == "Energy")
    earth = next(e for e in elements if e.name == "Earth")
    holy = next(e for e in elements if e.name == "Holy")
    death = next(e for e in elements if e.name == "Death")
    
    creatures_data = [
        {
            "name": "Rat",
            "article": "a",
            "plural": "Rats",
            "hitpoints": 20,
            "experience": 5,
            "armor": 1,
            "speed": 134,
            "max_damage": 8,
            "difficulty": "Trivial",
            "occurrence": "Common",
            "loot_value": 2.5,
            "description": "Rats can be found in sewers and cellars everywhere in Tibia.",
            "behavior": "Rats run in low health.",
            "image_url": "/creatures/rat.gif"
        },
        {
            "name": "Rotworm",
            "article": "a",
            "plural": "Rotworms",
            "hitpoints": 65,
            "experience": 40,
            "armor": 10,
            "speed": 60,
            "max_damage": 35,
            "difficulty": "Easy",
            "occurrence": "Common",
            "loot_value": 45.0,
            "description": "Rotworms live in the tunnels and sewers below many cities.",
            "behavior": "Rotworms fight until death.",
            "image_url": "/creatures/rotworm.gif"
        },
        {
            "name": "Dragon",
            "article": "a",
            "plural": "Dragons",
            "hitpoints": 1000,
            "experience": 700,
            "armor": 25,
            "speed": 200,
            "max_damage": 300,
            "difficulty": "Medium",
            "occurrence": "Common",
            "loot_value": 280.0,
            "description": "Dragons are among the most powerful monsters.",
            "behavior": "Dragons fight until death. They can breathe fire.",
            "image_url": "/creatures/dragon.gif"
        },
        {
            "name": "Dragon Lord",
            "article": "a",
            "plural": "Dragon Lords",
            "hitpoints": 1900,
            "experience": 2100,
            "armor": 38,
            "speed": 220,
            "max_damage": 650,
            "difficulty": "Hard",
            "occurrence": "Uncommon",
            "loot_value": 650.0,
            "description": "Dragon Lords are the most powerful of all dragons.",
            "behavior": "Dragon Lords fight until death. They can breathe massive fire waves.",
            "image_url": "/creatures/dragon_lord.gif"
        },
        {
            "name": "Demon",
            "article": "a",
            "plural": "Demons",
            "hitpoints": 8200,
            "experience": 6000,
            "armor": 50,
            "speed": 280,
            "max_damage": 850,
            "difficulty": "Hard",
            "occurrence": "Rare",
            "is_boss": False,
            "loot_value": 4500.0,
            "description": "Demons are the most dangerous creatures in Tibia.",
            "behavior": "Demons fight until death and summon fire elementals.",
            "image_url": "/creatures/demon.gif"
        }
    ]
    
    creatures = []
    for creature_data in creatures_data:
        creature = Creature(**creature_data)
        
        # Add weaknesses and resistances
        if creature.name == "Dragon" or creature.name == "Dragon Lord":
            creature.weaknesses.append(ice)
            creature.resistances.append(fire)
        elif creature.name == "Demon":
            creature.weaknesses.append(ice)
            creature.weaknesses.append(holy)
            creature.resistances.append(fire)
            creature.resistances.append(death)
        
        db.add(creature)
        creatures.append(creature)
    
    db.commit()
    return creatures


def seed_loot(db: Session, creatures: list):
    """Seed loot items"""
    
    # Get creatures by name
    rat = next(c for c in creatures if c.name == "Rat")
    rotworm = next(c for c in creatures if c.name == "Rotworm")
    dragon = next(c for c in creatures if c.name == "Dragon")
    dragon_lord = next(c for c in creatures if c.name == "Dragon Lord")
    demon = next(c for c in creatures if c.name == "Demon")
    
    loot_data = [
        # Rat loot
        {"creature_id": rat.id, "item_name": "Gold Coin", "rarity": "Common", "percentage": 50.0, 
         "min_amount": 0, "max_amount": 4, "item_value": 1, "item_type": "Gold"},
        {"creature_id": rat.id, "item_name": "Cheese", "rarity": "Common", "percentage": 30.0, 
         "item_value": 2, "item_type": "Food"},
        
        # Rotworm loot
        {"creature_id": rotworm.id, "item_name": "Gold Coin", "rarity": "Common", "percentage": 55.0,
         "min_amount": 1, "max_amount": 17, "item_value": 1, "item_type": "Gold"},
        {"creature_id": rotworm.id, "item_name": "Lump of Dirt", "rarity": "Always", "percentage": 100.0,
         "item_value": 10, "item_type": "Resource"},
        {"creature_id": rotworm.id, "item_name": "Sword", "rarity": "Semi-rare", "percentage": 15.0,
         "item_value": 85, "item_type": "Equipment"},
        
        # Dragon loot
        {"creature_id": dragon.id, "item_name": "Gold Coin", "rarity": "Common", "percentage": 90.0,
         "min_amount": 1, "max_amount": 110, "item_value": 1, "item_type": "Gold"},
        {"creature_id": dragon.id, "item_name": "Dragon Ham", "rarity": "Always", "percentage": 100.0,
         "item_value": 60, "item_type": "Food"},
        {"creature_id": dragon.id, "item_name": "Steel Shield", "rarity": "Uncommon", "percentage": 25.0,
         "item_value": 240, "item_type": "Equipment"},
        {"creature_id": dragon.id, "item_name": "Dragon Scale Mail", "rarity": "Rare", "percentage": 2.5,
         "item_value": 40000, "item_type": "Equipment"},
        
        # Dragon Lord loot
        {"creature_id": dragon_lord.id, "item_name": "Gold Coin", "rarity": "Common", "percentage": 100.0,
         "min_amount": 1, "max_amount": 250, "item_value": 1, "item_type": "Gold"},
        {"creature_id": dragon_lord.id, "item_name": "Dragon Ham", "rarity": "Always", "percentage": 100.0,
         "min_amount": 1, "max_amount": 3, "item_value": 60, "item_type": "Food"},
        {"creature_id": dragon_lord.id, "item_name": "Royal Helmet", "rarity": "Semi-rare", "percentage": 8.0,
         "item_value": 30000, "item_type": "Equipment"},
        
        # Demon loot
        {"creature_id": demon.id, "item_name": "Gold Coin", "rarity": "Always", "percentage": 100.0,
         "min_amount": 1, "max_amount": 250, "item_value": 1, "item_type": "Gold"},
        {"creature_id": demon.id, "item_name": "Platinum Coin", "rarity": "Always", "percentage": 100.0,
         "min_amount": 1, "max_amount": 12, "item_value": 100, "item_type": "Gold"},
        {"creature_id": demon.id, "item_name": "Magic Sword", "rarity": "Rare", "percentage": 1.5,
         "item_value": 320000, "item_type": "Equipment"},
        {"creature_id": demon.id, "item_name": "Demon Shield", "rarity": "Very Rare", "percentage": 0.5,
         "item_value": 30000, "item_type": "Equipment"},
    ]
    
    for loot_item in loot_data:
        loot = Loot(**loot_item)
        db.add(loot)
    
    db.commit()


def seed_hunt_zones(db: Session, creatures: list):
    """Seed hunt zones"""
    zones_data = [
        {
            "name": "Rookgaard Sewers",
            "city": "Rookgaard",
            "min_level": 1,
            "max_level": 8,
            "recommended_level": 5,
            "knights_recommended": True,
            "paladins_recommended": True,
            "sorcerers_recommended": True,
            "druids_recommended": True,
            "size": "Small",
            "difficulty": "Trivial",
            "avg_exp_hour": 2000,
            "avg_profit_hour": 500,
            "requires_quest": False,
            "requires_premium": False,
            "description": "Perfect for new players. Contains rats and other weak creatures.",
            "tips": "Bring some health potions. The sewers are safe for beginners.",
            "map_image_url": "/maps/rookgaard_sewers.png"
        },
        {
            "name": "Fibula Rotworm Cave",
            "city": "Fibula",
            "min_level": 8,
            "max_level": 25,
            "recommended_level": 15,
            "knights_recommended": True,
            "paladins_recommended": True,
            "sorcerers_recommended": False,
            "druids_recommended": False,
            "size": "Medium",
            "difficulty": "Easy",
            "avg_exp_hour": 8000,
            "avg_profit_hour": 2000,
            "requires_quest": False,
            "requires_premium": False,
            "description": "A good place to hunt rotworms and carrion worms.",
            "tips": "Knights and Paladins can hunt here efficiently. Loot the lump of dirt!",
            "map_image_url": "/maps/fibula_rotworm.png"
        },
        {
            "name": "Darashia Dragon Lair",
            "city": "Darashia",
            "min_level": 40,
            "max_level": 100,
            "recommended_level": 60,
            "knights_recommended": True,
            "paladins_recommended": True,
            "sorcerers_recommended": True,
            "druids_recommended": True,
            "size": "Large",
            "difficulty": "Medium",
            "avg_exp_hour": 120000,
            "avg_profit_hour": 15000,
            "requires_quest": False,
            "requires_premium": True,
            "description": "Classic dragon hunting ground with good experience and profit.",
            "tips": "Bring fire protection. Dragons deal heavy fire damage. Ice weapons work well.",
            "map_image_url": "/maps/darashia_dragons.png"
        },
        {
            "name": "Mintwallin Dragon Lords",
            "city": "Mintwallin",
            "min_level": 80,
            "max_level": 150,
            "recommended_level": 100,
            "knights_recommended": True,
            "paladins_recommended": True,
            "sorcerers_recommended": True,
            "druids_recommended": True,
            "size": "Medium",
            "difficulty": "Hard",
            "avg_exp_hour": 280000,
            "avg_profit_hour": 35000,
            "requires_quest": False,
            "requires_premium": True,
            "description": "Dragon Lords spawn here. Dangerous but profitable.",
            "tips": "Team hunting recommended. Bring fire protection and ice damage.",
            "map_image_url": "/maps/mintwallin.png"
        },
        {
            "name": "Goroma Demons",
            "city": "Goroma",
            "min_level": 150,
            "max_level": None,
            "recommended_level": 200,
            "knights_recommended": False,
            "paladins_recommended": True,
            "sorcerers_recommended": True,
            "druids_recommended": True,
            "size": "Large",
            "difficulty": "Extreme",
            "avg_exp_hour": 800000,
            "avg_profit_hour": 100000,
            "requires_quest": True,
            "quest_name": "The Shattered Isles Quest",
            "requires_premium": True,
            "description": "One of the most dangerous places. Demons spawn here.",
            "tips": "Only for experienced players. Team hunting highly recommended. Bring holy damage.",
            "map_image_url": "/maps/goroma_demons.png"
        }
    ]
    
    zones = []
    for zone_data in zones_data:
        zone = HuntZone(**zone_data)
        db.add(zone)
        zones.append(zone)
    
    db.commit()
    return zones


def seed_spawn_locations(db: Session, creatures: list, zones: list):
    """Seed spawn locations"""
    
    # Get entities by name
    rat = next(c for c in creatures if c.name == "Rat")
    rotworm = next(c for c in creatures if c.name == "Rotworm")
    dragon = next(c for c in creatures if c.name == "Dragon")
    dragon_lord = next(c for c in creatures if c.name == "Dragon Lord")
    demon = next(c for c in creatures if c.name == "Demon")
    
    rookgaard = next(z for z in zones if z.name == "Rookgaard Sewers")
    fibula = next(z for z in zones if z.name == "Fibula Rotworm Cave")
    darashia = next(z for z in zones if z.name == "Darashia Dragon Lair")
    mintwallin = next(z for z in zones if z.name == "Mintwallin Dragon Lords")
    goroma = next(z for z in zones if z.name == "Goroma Demons")
    
    spawns_data = [
        {"creature_id": rat.id, "hunt_zone_id": rookgaard.id, "quantity": "Many"},
        {"creature_id": rotworm.id, "hunt_zone_id": fibula.id, "quantity": "Plenty"},
        {"creature_id": dragon.id, "hunt_zone_id": darashia.id, "quantity": "Many"},
        {"creature_id": dragon_lord.id, "hunt_zone_id": mintwallin.id, "quantity": "Some"},
        {"creature_id": dragon.id, "hunt_zone_id": mintwallin.id, "quantity": "Few"},
        {"creature_id": demon.id, "hunt_zone_id": goroma.id, "quantity": "Some"},
    ]
    
    for spawn_data in spawns_data:
        spawn = SpawnLocation(**spawn_data)
        db.add(spawn)
    
    db.commit()


def seed_database():
    """Main function to seed the database"""
    print("Initializing database...")
    init_db()
    
    db = SessionLocal()
    
    try:
        # Check if already seeded
        existing_elements = db.query(Element).count()
        if existing_elements > 0:
            print("Database already contains data. Skipping seed.")
            return
        
        print("Seeding elements...")
        elements = seed_elements(db)
        
        print("Seeding creatures...")
        creatures = seed_creatures(db, elements)
        
        print("Seeding loot...")
        seed_loot(db, creatures)
        
        print("Seeding hunt zones...")
        zones = seed_hunt_zones(db, creatures)
        
        print("Seeding spawn locations...")
        seed_spawn_locations(db, creatures, zones)
        
        print("✅ Database seeded successfully!")
        
    except Exception as e:
        print(f"❌ Error seeding database: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
