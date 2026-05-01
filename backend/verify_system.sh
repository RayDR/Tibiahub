#!/bin/bash
# Verification script for Multi-Source Sync System

echo "=================================================="
echo "🔍 Tibia Hub - Multi-Source Sync System Verification"
echo "=================================================="

cd /forge/tibiahub/backend

echo ""
echo "📂 Checking file structure..."
echo "   ✓ external_apis.py: $([ -f app/services/external_apis.py ] && echo 'EXISTS' || echo 'MISSING')"
echo "   ✓ external_sync_service.py: $([ -f app/services/external_sync_service.py ] && echo 'EXISTS' || echo 'MISSING')"
echo "   ✓ external_data.py: $([ -f app/models/external_data.py ] && echo 'EXISTS' || echo 'MISSING')"
echo "   ✓ sync_admin.py: $([ -f app/api/v1/endpoints/sync_admin.py ] && echo 'EXISTS' || echo 'MISSING')"
echo "   ✓ test_sync_system.py: $([ -f test_sync_system.py ] && echo 'EXISTS' || echo 'MISSING')"

echo ""
echo "📊 Testing system components..."
/forge/.venv/bin/python3 << 'EOF'
import sys
import asyncio

# Test imports
try:
    from app.services.external_apis import get_creatures, APISource, APIResponse
    print("   ✓ External APIs service: OK")
except Exception as e:
    print(f"   ✗ External APIs service: {e}")
    sys.exit(1)

try:
    from app.services.external_sync_service import ExternalSyncService
    print("   ✓ Sync service: OK")
except Exception as e:
    print(f"   ✗ Sync service: {e}")
    sys.exit(1)

try:
    from app.models.external_data import Item, HuntingPlace, TibiaWikiQuest, APISync
    print("   ✓ Data models: OK")
except Exception as e:
    print(f"   ✗ Data models: {e}")
    sys.exit(1)

try:
    from app.db.database import SessionLocal
    db = SessionLocal()
    db.close()
    print("   ✓ Database connection: OK")
except Exception as e:
    print(f"   ✗ Database connection: {e}")
    sys.exit(1)

# Test API responses
async def test_apis():
    try:
        response = await get_creatures()
        assert response.data is not None, "Creatures data is None"
        assert response.source in [APISource.TIBIAWIKI, APISource.TIBIADATA, APISource.LOCAL]
        print("   ✓ API responses: OK")
    except Exception as e:
        print(f"   ✗ API responses: {e}")
        sys.exit(1)

asyncio.run(test_apis())

print("")
print("✅ All components verified successfully!")
EOF

echo ""
echo "🗄️  Checking database tables..."
/forge/.venv/bin/python3 << 'EOF'
import sqlalchemy
from app.db.database import engine

inspector = sqlalchemy.inspect(engine)
tables = inspector.get_table_names()

required_tables = ['api_syncs', 'tibiawiki_items', 'tibiawiki_hunting_places', 'tibiawiki_quests']
for table in required_tables:
    if table in tables:
        print(f"   ✓ {table}: EXISTS")
    else:
        print(f"   ✗ {table}: MISSING")
EOF

echo ""
echo "🚀 Running full test suite..."
/forge/.venv/bin/python3 test_sync_system.py 2>&1 | tail -20

echo ""
echo "=================================================="
echo "✅ Verification complete!"
echo "=================================================="
echo ""
echo "📝 Documentation files:"
echo "   - SYNC_SYSTEM_STATUS.md"
echo "   - QUICK_REFERENCE.md"
echo "   - IMPLEMENTATION_COMPLETE.md"
echo ""
echo "🎯 Next steps:"
echo "   1. Start the server: python3 main.py"
echo "   2. Access admin endpoints: POST /admin/sync/*"
echo "   3. Monitor progress: GET /admin/sync/logs"
echo ""
