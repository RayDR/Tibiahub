"""
TibiaWiki Data Importer
Script para importar criaturas y datos desde TibiaWiki API

Uso:
    python import_tibiawiki.py --creatures 50  # Importar 50 criaturas
    python import_tibiawiki.py --all           # Importar todo
"""
import requests
import json
import time
from typing import List, Dict, Optional
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models import Creature, Element, Loot, HuntZone
from app.schemas import CreatureCreate, LootCreate


class TibiaWikiImporter:
    """Importador de datos de TibiaWiki"""
    
    BASE_URL = "https://tibiawiki.dev/api.php"
    
    def __init__(self, db: Session):
        self.db = db
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'TibiaBestiary/1.0 (Educational Project)'
        })
    
    def get_creature_list(self, limit: int = 100) -> List[str]:
        """Obtiene lista de nombres de criaturas"""
        params = {
            'action': 'query',
            'format': 'json',
            'list': 'categorymembers',
            'cmtitle': 'Category:Creatures',
            'cmlimit': limit
        }
        
        response = self.session.get(self.BASE_URL, params=params)
        data = response.json()
        
        creatures = []
        if 'query' in data and 'categorymembers' in data['query']:
            creatures = [item['title'] for item in data['query']['categorymembers']]
        
        return creatures
    
    def get_creature_data(self, creature_name: str) -> Optional[Dict]:
        """Obtiene datos detallados de una criatura"""
        params = {
            'action': 'parse',
            'format': 'json',
            'page': creature_name,
            'prop': 'wikitext'
        }
        
        try:
            response = self.session.get(self.BASE_URL, params=params)
            data = response.json()
            
            if 'parse' not in data:
                return None
            
            # Parsear wikitext (simplificado)
            wikitext = data['parse']['wikitext']['*']
            
            # Extraer datos básicos (esto es simplificado, necesita mejorar parsing)
            creature_data = self._parse_wikitext(wikitext, creature_name)
            
            return creature_data
        except Exception as e:
            print(f"Error obteniendo datos de {creature_name}: {e}")
            return None
    
    def _parse_wikitext(self, wikitext: str, name: str) -> Dict:
        """Parse wikitext para extraer datos de criatura (simplificado)"""
        # Este es un parser muy básico, se puede mejorar con expresiones regulares
        data = {
            'name': name,
            'hitpoints': 100,
            'experience': 50,
            'armor': 10,
            'speed': 100,
            'difficulty': 'Medium'
        }
        
        # Buscar HP
        if 'hp' in wikitext.lower():
            # Extraer HP (esto es muy simplificado)
            pass
        
        return data
    
    def import_creature(self, creature_name: str) -> bool:
        """Importa una criatura a la base de datos"""
        # Verificar si ya existe
        existing = self.db.query(Creature).filter(Creature.name == creature_name).first()
        if existing:
            print(f"⚠️  {creature_name} ya existe")
            return False
        
        # Obtener datos
        data = self.get_creature_data(creature_name)
        if not data:
            print(f"❌ No se pudieron obtener datos de {creature_name}")
            return False
        
        # Crear criatura
        try:
            creature = Creature(**data)
            self.db.add(creature)
            self.db.commit()
            print(f"✅ {creature_name} importada exitosamente")
            return True
        except Exception as e:
            self.db.rollback()
            print(f"❌ Error importando {creature_name}: {e}")
            return False
    
    def import_creatures_batch(self, limit: int = 50):
        """Importa múltiples criaturas"""
        print(f"🔍 Obteniendo lista de criaturas (límite: {limit})...")
        creature_names = self.get_creature_list(limit)
        
        print(f"📦 Encontradas {len(creature_names)} criaturas")
        print(f"📥 Iniciando importación...\n")
        
        success = 0
        failed = 0
        
        for i, name in enumerate(creature_names, 1):
            print(f"[{i}/{len(creature_names)}] Importando {name}...")
            
            if self.import_creature(name):
                success += 1
            else:
                failed += 1
            
            # Rate limiting
            time.sleep(0.5)
        
        print(f"\n{'='*50}")
        print(f"✅ Importadas: {success}")
        print(f"❌ Fallidas: {failed}")
        print(f"📊 Total: {len(creature_names)}")
        print(f"{'='*50}")


def import_manual_creatures():
    """Importa criaturas manualmente con datos reales de Tibia"""
    db = SessionLocal()
    
    # Datos reales de criaturas populares de Tibia
    creatures_data = [
        {
            'name': 'Dragon',
            'hitpoints': 1000,
            'experience': 700,
            'armor': 25,
            'speed': 100,
            'difficulty': 'Medium',
            'level_min': 50,
            'level_max': 80,
            'mana': 0,
            'summonable': False,
            'convinceable': False,
            'illusionable': False,
            'pushable': False,
            'paralyzable': True,
            'attacks_physical': True,
            'attacks_fire': True,
            'attacks_earth': False,
            'attacks_energy': False,
            'attacks_ice': False,
            'attacks_holy': False,
            'attacks_death': False,
            'description': 'Dragons are fearsome creatures that live in caves and mountains.',
            'behavior': 'Aggressive. Attacks from distance.',
            'image_url': 'https://tibiawiki.dev/images/Dragon.gif'
        },
        {
            'name': 'Demon',
            'hitpoints': 8200,
            'experience': 6000,
            'armor': 50,
            'speed': 118,
            'difficulty': 'Hard',
            'level_min': 150,
            'level_max': 300,
            'mana': 0,
            'summonable': False,
            'convinceable': False,
            'illusionable': False,
            'pushable': False,
            'paralyzable': False,
            'attacks_physical': True,
            'attacks_fire': True,
            'attacks_earth': False,
            'attacks_energy': True,
            'attacks_ice': False,
            'attacks_holy': False,
            'attacks_death': False,
            'description': 'Demons are among the most powerful creatures in Tibia.',
            'behavior': 'Very aggressive. Uses powerful spells.',
            'image_url': 'https://tibiawiki.dev/images/Demon.gif'
        },
        {
            'name': 'Cyclops',
            'hitpoints': 260,
            'experience': 150,
            'armor': 20,
            'speed': 80,
            'difficulty': 'Easy',
            'level_min': 25,
            'level_max': 50,
            'mana': 0,
            'summonable': False,
            'convinceable': False,
            'illusionable': False,
            'pushable': False,
            'paralyzable': True,
            'attacks_physical': True,
            'attacks_fire': False,
            'attacks_earth': False,
            'attacks_energy': False,
            'attacks_ice': False,
            'attacks_holy': False,
            'attacks_death': False,
            'description': 'One-eyed giants that live in mountains.',
            'behavior': 'Aggressive. Melee fighter.',
            'image_url': 'https://tibiawiki.dev/images/Cyclops.gif'
        }
    ]
    
    print("📦 Importando criaturas con datos reales...")
    
    for data in creatures_data:
        # Verificar si existe
        existing = db.query(Creature).filter(Creature.name == data['name']).first()
        if existing:
            print(f"⚠️  {data['name']} ya existe, actualizando...")
            for key, value in data.items():
                setattr(existing, key, value)
        else:
            creature = Creature(**data)
            db.add(creature)
            print(f"✅ {data['name']} creada")
    
    db.commit()
    print("\n✅ Criaturas importadas exitosamente!")
    db.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Importar datos de TibiaWiki')
    parser.add_argument('--creatures', type=int, help='Número de criaturas a importar')
    parser.add_argument('--manual', action='store_true', help='Importar criaturas manuales con datos reales')
    parser.add_argument('--all', action='store_true', help='Importar todo')
    
    args = parser.parse_args()
    
    if args.manual:
        import_manual_creatures()
    elif args.creatures:
        db = SessionLocal()
        importer = TibiaWikiImporter(db)
        importer.import_creatures_batch(args.creatures)
        db.close()
    elif args.all:
        db = SessionLocal()
        importer = TibiaWikiImporter(db)
        importer.import_creatures_batch(500)
        db.close()
    else:
        print("❌ Especifica una opción: --creatures N, --manual, o --all")
        parser.print_help()
