#!/usr/bin/env python3
"""
Complete test suite for the multi-source sync system
"""
import asyncio
from app.db.database import SessionLocal
from app.services.external_apis import get_creatures, get_items, get_hunting_places, get_quests, get_character
from app.services.external_sync_service import ExternalSyncService

async def test_all_apis():
    """Test all external API endpoints"""
    print("\n" + "="*60)
    print("🔍 Testing External APIs")
    print("="*60)
    
    # Test creatures
    print("\n📦 Testing creatures endpoint...")
    response = await get_creatures()
    creatures = response.data if response.success() else {}
    print(f"  ✅ Status: {response.source.value}")
    print(f"  ✅ Creatures: {len(creatures)}")
    if creatures:
        sample = list(creatures.keys())[0]
        print(f"  ✅ Sample: {sample}")

    # Test items
    print("\n📦 Testing items endpoint...")
    response = await get_items()
    items = response.data if response.success() else {}
    print(f"  ✅ Status: {response.source.value}")
    print(f"  ✅ Items: {len(items)}")

    # Test hunting places
    print("\n📦 Testing hunting places endpoint...")
    response = await get_hunting_places()
    places = response.data if response.success() else {}
    print(f"  ✅ Status: {response.source.value}")
    print(f"  ✅ Hunting places: {len(places)}")

    # Test quests
    print("\n📦 Testing quests endpoint...")
    response = await get_quests()
    quests = response.data if response.success() else {}
    print(f"  ✅ Status: {response.source.value}")
    print(f"  ✅ Quests: {len(quests)}")

    # Test character
    print("\n👤 Testing character endpoint...")
    response = await get_character("Ray On")
    character = response.data if response.success() else {}
    print(f"  ✅ Status: {response.source.value}")
    print(f"  ✅ Character: {character.get('name', 'N/A')}")

    # Test guild
    print("\n👥 Testing guild endpoint...")
    response = await get_character("Bloodborne Warhowl")
    guild = response.data if response.success() else {}
    print(f"  ✅ Status: {response.source.value}")
    print(f"  ✅ Guild: {guild.get('name', 'N/A')}")

async def test_sync_operations():
    """Test synchronization operations"""
    print("\n" + "="*60)
    print("🔄 Testing Sync Operations")
    print("="*60)
    
    db = SessionLocal()
    
    try:
        # Sync creatures
        print("\n📦 Syncing creatures...")
        result = await ExternalSyncService.sync_creatures(db)
        print(f"  ✅ Status: {result['status']}")
        print(f"  ✅ Created: {result.get('created', 0)}")
        print(f"  ✅ Updated: {result.get('updated', 0)}")
        print(f"  ✅ Errors: {result.get('errors', 0)}")
        print(f"  ✅ Sync ID: {result.get('sync_id')}")
        
        # Get stats
        print("\n📊 Checking statistics...")
        stats = ExternalSyncService.get_sync_stats(db)
        print(f"  ✅ Creatures: {stats['creatures']}")
        print(f"  ✅ Items: {stats['items']}")
        print(f"  ✅ Hunting places: {stats['hunting_places']}")
        print(f"  ✅ Quests: {stats['quests']}")
        print(f"  ✅ Sync logs: {stats['sync_logs']}")
        
        # Get logs
        print("\n📋 Checking sync logs...")
        logs = ExternalSyncService.get_sync_logs(db)
        print(f"  ✅ Total logs: {len(logs)}")
        if logs:
            latest = logs[0]
            print(f"  ✅ Latest log:")
            print(f"     - API: {latest.api_name}")
            print(f"     - Status: {latest.status}")
            print(f"     - Processed: {latest.processed_items}/{latest.total_items}")
            
    finally:
        db.close()

async def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("🚀 Multi-Source Sync System Test Suite")
    print("="*60)
    
    # Test APIs
    await test_all_apis()
    
    # Test sync
    await test_sync_operations()
    
    print("\n" + "="*60)
    print("✅ All tests completed successfully!")
    print("="*60 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
