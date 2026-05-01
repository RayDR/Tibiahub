"""
Test admin endpoints
"""
import requests
import json

BASE_URL = "http://localhost:8001/api/v1"

def get_admin_token():
    """Get admin token"""
    response = requests.post(
        f"{BASE_URL}/auth/login",
        data={"username": "admin", "password": "admin123"}
    )
    if response.status_code == 200:
        return response.json()["access_token"]
    return None

def test_tibia_api_status(token):
    """Test Tibia API status endpoint"""
    print("\n" + "=" * 60)
    print("TEST: Tibia API Status")
    print("=" * 60)
    
    response = requests.get(
        f"{BASE_URL}/guild-management/tibia-api-status",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(json.dumps(data, indent=2))
        print(f"\n✅ Tibia API Status: {data['status']}")
        if data.get('latency_ms'):
            print(f"   Latency: {data['latency_ms']} ms")
    else:
        print(f"❌ Failed: {response.text}")

def test_get_users(token):
    """Test get users endpoint"""
    print("\n" + "=" * 60)
    print("TEST: Get All Users")
    print("=" * 60)
    
    response = requests.get(
        f"{BASE_URL}/guild-management/users",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        users = response.json()
        print(f"\n✅ Found {len(users)} users:")
        for user in users:
            print(f"\n  - ID: {user['id']}")
            print(f"    Username: {user['username']}")
            print(f"    Email: {user.get('email', 'N/A')}")
            print(f"    Guild Rank: {user.get('guild_rank', 'N/A')}")
            print(f"    Is Superuser: {user['is_superuser']}")
            print(f"    Characters: {len(user['characters'])}")
            for char in user['characters']:
                char_info = f"      • {char['character_name']}"
                if char.get('level'):
                    char_info += f" (Level {char['level']}"
                if char.get('vocation'):
                    char_info += f" - {char['vocation']}"
                if char.get('level'):
                    char_info += ")"
                print(char_info)
    else:
        print(f"❌ Failed: {response.text}")

def test_get_stats(token):
    """Test stats endpoint"""
    print("\n" + "=" * 60)
    print("TEST: Get System Stats")
    print("=" * 60)
    
    response = requests.get(
        f"{BASE_URL}/guild-management/stats",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        stats = response.json()
        print("\n✅ System Statistics:")
        print(json.dumps(stats, indent=2))
    else:
        print(f"❌ Failed: {response.text}")

def test_get_settings(token):
    """Test get settings endpoint"""
    print("\n" + "=" * 60)
    print("TEST: Get System Settings")
    print("=" * 60)
    
    response = requests.get(
        f"{BASE_URL}/guild-management/settings",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        settings = response.json()
        print("\n✅ Current Settings:")
        print(json.dumps(settings, indent=2))
        return settings
    else:
        print(f"❌ Failed: {response.text}")
        return None

def test_update_settings(token):
    """Test update settings endpoint"""
    print("\n" + "=" * 60)
    print("TEST: Update System Settings")
    print("=" * 60)
    print("Setting tibia_validation_strict = False")
    
    response = requests.put(
        f"{BASE_URL}/guild-management/settings",
        headers={"Authorization": f"Bearer {token}"},
        json={"tibia_validation_strict": False}
    )
    
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        settings = response.json()
        print("\n✅ Settings Updated:")
        print(json.dumps(settings, indent=2))
    else:
        print(f"❌ Failed: {response.text}")

def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("GUILD MANAGEMENT ENDPOINTS TEST SUITE")
    print("=" * 60)
    
    # Get admin token
    print("\nGetting admin token...")
    token = get_admin_token()
    
    if not token:
        print("❌ Failed to get admin token")
        return
    
    print("✅ Admin token obtained")
    
    # Run tests
    test_tibia_api_status(token)
    test_get_users(token)
    test_get_stats(token)
    test_get_settings(token)
    test_update_settings(token)
    
    print("\n" + "=" * 60)
    print("✅ ALL TESTS COMPLETED")
    print("=" * 60)
    print("\nAdmin Dashboard Endpoints:")
    print(f"  - GET  {BASE_URL}/guild-management/tibia-api-status")
    print(f"  - GET  {BASE_URL}/guild-management/users")
    print(f"  - GET  {BASE_URL}/guild-management/users/{{user_id}}")
    print(f"  - GET  {BASE_URL}/guild-management/stats")
    print(f"  - GET  {BASE_URL}/guild-management/settings")
    print(f"  - PUT  {BASE_URL}/guild-management/settings")

if __name__ == "__main__":
    main()
