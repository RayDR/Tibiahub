from app.db.database import SessionLocal
from app.models.creature import Creature
from app.models.loot import Loot

db = SessionLocal()
c = db.query(Creature).get(1)
print(f"Creature: {c.name}")
print(f"HP: {c.hitpoints} (Type: {type(c.hitpoints)})")
print(f"Exp: {c.experience} (Type: {type(c.experience)})")

print("Loot:")
for loot in c.loot_items:
    print(f" - {loot.item_name}: Min={loot.min_amount} ({type(loot.min_amount)}), Max={loot.max_amount} ({type(loot.max_amount)}), Chance={loot.percentage} ({type(loot.percentage)})")
