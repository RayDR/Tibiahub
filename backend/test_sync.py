#!/usr/bin/env python3
"""
Test script to verify event sync functionality
"""
import sys
sys.path.append('/forge/tibiahub/backend')

from app.services.tibia_api import get_active_guild_members, get_guild_info
import asyncio

async def test_sync():
    print("=" * 60)
    print("Testing Guild Sync")
    print("=" * 60)
    
    guild_name = "Bloodborne Warhowl"
    active_days = 10
    
    print(f"\n1. Testing get_guild_info for: {guild_name}")
    try:
        guild_info = await get_guild_info(guild_name)
        if guild_info:
            print(f"   ✅ Guild found: {guild_info['name']}")
            print(f"   World: {guild_info.get('world', 'Unknown')}")
            print(f"   Members: {len(guild_info.get('members', []))}")
        else:
            print("   ❌ Guild not found")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    print(f"\n2. Testing get_active_guild_members (last {active_days} days)")
    try:
        active_members = await get_active_guild_members(guild_name, active_days)
        print(f"   ✅ Found {len(active_members)} active members:")
        for i, member in enumerate(active_members[:5], 1):
            print(f"      {i}. {member['name']} - Lvl {member.get('level', '?')} - {member.get('vocation', '?')}")
        if len(active_members) > 5:
            print(f"      ... and {len(active_members) - 5} more")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    asyncio.run(test_sync())
