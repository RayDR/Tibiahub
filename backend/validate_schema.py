import sys
from app.db.database import SessionLocal
from app.models.creature import Creature as CreatureModel
from app.schemas import Creature as CreatureSchema

try:
    db = SessionLocal()
    c = db.query(CreatureModel).get(1)
    if not c:
        print("Creature 1 not found")
        sys.exit(1)

    print(f"Validating Creature: {c.name}")
    try:
        # Use model_validate (Pydantic V2) or from_orm (Pydantic V1)
        # Attempting standard pydantic v2 validation since I saw model_validate not available?
        # Check schemas/__init__.py for imported pydantic version... assumed v2
        # But wait, looking at imports 'from pydantic import BaseModel'.
        # Let's try from_orm first as it's common.
        
        # If schema defines Config with from_attributes=True, it's V2.
        # If schema defines Config with orm_mode=True, it's V1.
        # The code showed 'from_attributes = True', so it is Pydantic V2.
        # Method is model_validate.
        
        pydantic_obj = CreatureSchema.model_validate(c)
        print("Validation Successful!")
        print(pydantic_obj.model_dump_json(indent=2))
        
    except Exception as e:
        print("\n--- VALIDATION ERROR ---")
        print(e)
        import traceback
        traceback.print_exc()

except Exception as e:
    print(e)
