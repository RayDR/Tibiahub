"""
Test authentication endpoints
"""
import requests
import json

BASE_URL = "http://localhost:8001/api/v1"

def test_admin_login():
    """Test admin login"""
    print("\n" + "=" * 60)
    print("TEST 1: Admin Login")
    print("=" * 60)
    
    response = requests.post(
        f"{BASE_URL}/auth/login",
        data={
            "username": "admin",
            "password": "admin123"
        }
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code == 200:
        print("✅ Admin login successful!")
        return response.json()["access_token"]
    else:
        print("❌ Admin login failed!")
        return None

def test_get_profile(token):
    """Test get profile"""
    print("\n" + "=" * 60)
    print("TEST 2: Get Admin Profile")
    print("=" * 60)
    
    response = requests.get(
        f"{BASE_URL}/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code == 200:
        print("✅ Get profile successful!")
        return True
    else:
        print("❌ Get profile failed!")
        return False

def test_register_with_tibia_character():
    """Test registration with Tibia character"""
    print("\n" + "=" * 60)
    print("TEST 3: Register User with Tibia Character")
    print("=" * 60)
    print("Using character: Bubble (a real Tibia character)")
    
    response = requests.post(
        f"{BASE_URL}/auth/register",
        json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "password123",
            "tibia_character_name": "Bubble"
        }
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code == 200:
        print("✅ Registration with Tibia character successful!")
        return True
    else:
        print("❌ Registration failed!")
        return False

def test_login_with_character():
    """Test login with character name"""
    print("\n" + "=" * 60)
    print("TEST 4: Login with Character Name")
    print("=" * 60)
    
    response = requests.post(
        f"{BASE_URL}/auth/login",
        data={
            "username": "Bubble",  # Login with character name
            "password": "password123"
        }
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code == 200:
        print("✅ Login with character name successful!")
        return True
    else:
        print("❌ Login with character name failed!")
        return False

def test_login_with_username():
    """Test login with username"""
    print("\n" + "=" * 60)
    print("TEST 5: Login with Username")
    print("=" * 60)
    
    response = requests.post(
        f"{BASE_URL}/auth/login",
        data={
            "username": "testuser",  # Login with username
            "password": "password123"
        }
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code == 200:
        print("✅ Login with username successful!")
        return True
    else:
        print("❌ Login with username failed!")
        return False

def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("TIBIA BESTIARY - AUTHENTICATION TESTS")
    print("=" * 60)
    
    try:
        # Test 1: Admin login
        token = test_admin_login()
        if not token:
            print("\n⚠️  Stopping tests - admin login failed")
            return
        
        # Test 2: Get profile
        test_get_profile(token)
        
        # Test 3: Register with Tibia character
        test_register_with_tibia_character()
        
        # Test 4: Login with character name
        test_login_with_character()
        
        # Test 5: Login with username
        test_login_with_username()
        
        print("\n" + "=" * 60)
        print("✅ ALL TESTS COMPLETED")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Error running tests: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
