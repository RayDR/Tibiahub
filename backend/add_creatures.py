#!/usr/bin/env python3
"""
Script para agregar criaturas reales de Tibia a la base de datos
"""
import sys
import os

# Agregar el directorio backend al path
sys.path.insert(0, os.path.dirname(__file__))

from app.db.database import SessionLocal
from app.models import Creature

def add_real_creatures():
    """Agregar criaturas reales de Tibia con datos precisos"""
    db = SessionLocal()
    
    creatures_data = [
        {
            'name': 'Amazon',
            'hitpoints': 110,
            'experience': 60,
            'armor': 10,
            'speed': 110,
            'difficulty': 'Easy',
            'description': 'Amazons are strong warrior women living on the Isle of the Kings.',
            'behavior': 'Aggressive, melee fighter',
            'image_url': 'https://static.tibia.com/images/library/amazon.gif'
        },
        {
            'name': 'Cyclops',
            'hitpoints': 260,
            'experience': 150,
            'armor': 20,
            'speed': 80,
            'difficulty': 'Easy',
            'description': 'One-eyed giants that dwell in mountains and hills.',
            'behavior': 'Aggressive, slow melee fighter',
            'image_url': 'https://static.tibia.com/images/library/cyclops.gif'
        },
        {
            'name': 'Dragon',
            'hitpoints': 1000,
            'experience': 700,
            'armor': 25,
            'speed': 100,
            'difficulty': 'Medium',
            'description': 'Mighty fire-breathing lizards that guard treasures in caves.',
            'behavior': 'Very aggressive, breathes fire',
            'image_url': 'https://static.tibia.com/images/library/dragon.gif'
        },
        {
            'name': 'Dragon Lord',
            'hitpoints': 1900,
            'experience': 2100,
            'armor': 40,
            'speed': 110,
            'difficulty': 'Hard',
            'description': 'The most powerful of all dragons, masters of fire magic.',
            'behavior': 'Extremely aggressive, powerful magic attacks',
            'image_url': 'https://static.tibia.com/images/library/dragon_lord.gif'
        },
        {
            'name': 'Demon',
            'hitpoints': 8200,
            'experience': 6000,
            'armor': 50,
            'speed': 118,
            'difficulty': 'Extreme',
            'description': 'Ancient evil creatures from the depths of hell.',
            'behavior': 'Extremely dangerous, uses powerful magic',
            'image_url': 'https://static.tibia.com/images/library/demon.gif'
        },
        {
            'name': 'Orc',
            'hitpoints': 70,
            'experience': 25,
            'armor': 5,
            'speed': 96,
            'difficulty': 'Trivial',
            'description': 'Green-skinned humanoids living in tribes.',
            'behavior': 'Aggressive, weak melee fighter',
            'image_url': 'https://static.tibia.com/images/library/orc.gif'
        },
        {
            'name': 'Orc Warrior',
            'hitpoints': 125,
            'experience': 50,
            'armor': 12,
            'speed': 100,
            'difficulty': 'Easy',
            'description': 'Stronger orcs trained in combat.',
            'behavior': 'Aggressive melee fighter',
            'image_url': 'https://static.tibia.com/images/library/orc_warrior.gif'
        },
        {
            'name': 'Vampire',
            'hitpoints': 475,
            'experience': 305,
            'armor': 16,
            'speed': 127,
            'difficulty': 'Medium',
            'description': 'Undead bloodsuckers that drain life from their victims.',
            'behavior': 'Fast and aggressive, life drain attacks',
            'image_url': 'https://static.tibia.com/images/library/vampire.gif'
        },
        {
            'name': 'Rotworm',
            'hitpoints': 65,
            'experience': 40,
            'armor': 12,
            'speed': 60,
            'difficulty': 'Easy',
            'description': 'Giant worms living in the sewers.',
            'behavior': 'Aggressive but slow',
            'image_url': 'https://static.tibia.com/images/library/rotworm.gif'
        },
        {
            'name': 'Hydra',
            'hitpoints': 2350,
            'experience': 2100,
            'armor': 40,
            'speed': 110,
            'difficulty': 'Hard',
            'description': 'Multi-headed serpents that regenerate their heads.',
            'behavior': 'Aggressive, poison attacks',
            'image_url': 'https://static.tibia.com/images/library/hydra.gif'
        }
    ]
    
    print("📦 Importando criaturas reales de Tibia...")
    print(f"{'='*60}")
    
    added = 0
    updated = 0
    
    for data in creatures_data:
        existing = db.query(Creature).filter(Creature.name == data['name']).first()
        
        if existing:
            # Actualizar
            for key, value in data.items():
                setattr(existing, key, value)
            print(f"🔄 {data['name']} actualizada")
            updated += 1
        else:
            # Crear nueva
            creature = Creature(**data)
            db.add(creature)
            print(f"✅ {data['name']} creada")
            added += 1
    
    db.commit()
    
    print(f"{'='*60}")
    print(f"✅ Proceso completado!")
    print(f"   Creadas: {added}")
    print(f"   Actualizadas: {updated}")
    print(f"   Total: {len(creatures_data)}")
    print(f"{'='*60}")
    
    db.close()

if __name__ == "__main__":
    add_real_creatures()
