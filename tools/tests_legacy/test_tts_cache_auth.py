#!/usr/bin/env python3
"""
Test script to verify TTS cache authentication and authorization.
Tests that cache clearing endpoints require proper admin authentication.
"""

import requests
import json
from datetime import datetime, timedelta
import jwt

# Configuration
USER_SERVER_URL = "http://localhost:1915"
ADMIN_SERVER_URL = "http://localhost:1916"
JWT_SECRET = "your-secret-key-here"  # Should match server config
ADMIN_USERNAME = "admin"

# Test constants
TEST_RESULTS = []

def log_test(test_name, passed, message=""):
    """Log test result"""
    status = "✅ PASS" if passed else "❌ FAIL"
    result = f"{status}: {test_name}"
    if message:
        result += f" - {message}"
    TEST_RESULTS.append((test_name, passed, message))
    print(result)

def generate_valid_admin_token():
    """Generate a valid admin JWT token"""
    payload = {
        'username': ADMIN_USERNAME,
        'type': 'api',
        'exp': datetime.utcnow() + timedelta(hours=1)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm='HS256')

def generate_invalid_token():
    """Generate an invalid token"""
    return "invalid.token.here"

def generate_non_admin_token():
    """Generate a token for non-admin user"""
    payload = {
        'username': 'regular_user',
        'type': 'api',
        'exp': datetime.utcnow() + timedelta(hours=1)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm='HS256')

def test_cache_stats_without_auth():
    """Test: Accessing cache stats without authentication should be rejected"""
    print("\n" + "="*60)
    print("TEST 1: Access cache stats WITHOUT authentication")
    print("="*60)
    
    try:
        response = requests.get(
            f"{USER_SERVER_URL}/api/tts/cache-stats",
            timeout=5
        )
        
        # Should return 401 Unauthorized
        passed = response.status_code == 401
        log_test(
            "Cache stats requires authentication",
            passed,
            f"Got status {response.status_code}, expected 401"
        )
    except Exception as e:
        log_test("Cache stats requires authentication", False, str(e))

def test_cache_stats_with_invalid_token():
    """Test: Accessing cache stats with invalid token should be rejected"""
    print("\n" + "="*60)
    print("TEST 2: Access cache stats WITH INVALID token")
    print("="*60)
    
    try:
        response = requests.get(
            f"{USER_SERVER_URL}/api/tts/cache-stats",
            headers={'Authorization': f'Bearer {generate_invalid_token()}'},
            timeout=5
        )
        
        # Should return 401 Unauthorized
        passed = response.status_code == 401
        log_test(
            "Invalid token is rejected",
            passed,
            f"Got status {response.status_code}, expected 401"
        )
    except Exception as e:
        log_test("Invalid token is rejected", False, str(e))

def test_cache_stats_with_valid_token():
    """Test: Accessing cache stats with valid admin token should succeed"""
    print("\n" + "="*60)
    print("TEST 3: Access cache stats WITH VALID admin token")
    print("="*60)
    
    try:
        token = generate_valid_admin_token()
        response = requests.get(
            f"{USER_SERVER_URL}/api/tts/cache-stats",
            headers={'Authorization': f'Bearer {token}'},
            timeout=5
        )
        
        # Should return 200 OK
        passed = response.status_code == 200
        log_test(
            "Valid admin token grants access",
            passed,
            f"Got status {response.status_code}, expected 200"
        )
        
        if passed:
            data = response.json()
            print(f"Cache stats: {json.dumps(data, indent=2)}")
    except Exception as e:
        log_test("Valid admin token grants access", False, str(e))

def test_cache_stats_with_non_admin_token():
    """Test: Non-admin token should be rejected"""
    print("\n" + "="*60)
    print("TEST 4: Access cache stats WITH non-admin token")
    print("="*60)
    
    try:
        token = generate_non_admin_token()
        response = requests.get(
            f"{USER_SERVER_URL}/api/tts/cache-stats",
            headers={'Authorization': f'Bearer {token}'},
            timeout=5
        )
        
        # Should return 403 Forbidden (admin access required)
        passed = response.status_code == 403
        log_test(
            "Non-admin token is rejected",
            passed,
            f"Got status {response.status_code}, expected 403 (Forbidden)"
        )
    except Exception as e:
        log_test("Non-admin token is rejected", False, str(e))

def test_cache_clear_without_auth():
    """Test: Clearing cache without authentication should be rejected"""
    print("\n" + "="*60)
    print("TEST 5: Clear cache WITHOUT authentication")
    print("="*60)
    
    try:
        response = requests.post(
            f"{USER_SERVER_URL}/api/tts/cache-clear",
            timeout=5
        )
        
        # Should return 401 Unauthorized
        passed = response.status_code == 401
        log_test(
            "Cache clear requires authentication",
            passed,
            f"Got status {response.status_code}, expected 401"
        )
    except Exception as e:
        log_test("Cache clear requires authentication", False, str(e))

def test_cache_clear_with_valid_token():
    """Test: Clearing cache with valid admin token should succeed"""
    print("\n" + "="*60)
    print("TEST 6: Clear cache WITH VALID admin token")
    print("="*60)
    
    try:
        token = generate_valid_admin_token()
        response = requests.post(
            f"{USER_SERVER_URL}/api/tts/cache-clear",
            headers={'Authorization': f'Bearer {token}'},
            timeout=5
        )
        
        # Should return 200 OK
        passed = response.status_code == 200
        log_test(
            "Valid admin token can clear cache",
            passed,
            f"Got status {response.status_code}, expected 200"
        )
        
        if passed:
            data = response.json()
            print(f"Clear response: {json.dumps(data, indent=2)}")
    except Exception as e:
        log_test("Valid admin token can clear cache", False, str(e))

def test_admin_cache_clear_requires_auth():
    """Test: Admin panel cache clear requires admin session"""
    print("\n" + "="*60)
    print("TEST 7: Admin panel cache clear requires authentication")
    print("="*60)
    
    try:
        response = requests.post(
            f"{ADMIN_SERVER_URL}/api/tts/cache-clear",
            timeout=5
        )
        
        # Should return 401 Unauthorized
        passed = response.status_code == 401
        log_test(
            "Admin cache clear requires authentication",
            passed,
            f"Got status {response.status_code}, expected 401"
        )
    except Exception as e:
        log_test("Admin cache clear requires authentication", False, str(e))

def print_summary():
    """Print test summary"""
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    total = len(TEST_RESULTS)
    passed = sum(1 for _, p, _ in TEST_RESULTS if p)
    
    for test_name, passed_status, message in TEST_RESULTS:
        status = "✅" if passed_status else "❌"
        print(f"{status} {test_name}")
        if message:
            print(f"   → {message}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed!")
    else:
        print(f"⚠️  {total - passed} test(s) failed")

def main():
    """Run all tests"""
    print("\n" + "🔐 TTS Cache Authentication Tests")
    print("Testing admin-only access to TTS cache management endpoints")
    
    try:
        # Run all tests
        test_cache_stats_without_auth()
        test_cache_stats_with_invalid_token()
        test_cache_stats_with_valid_token()
        test_cache_stats_with_non_admin_token()
        test_cache_clear_without_auth()
        test_cache_clear_with_valid_token()
        test_admin_cache_clear_requires_auth()
        
        print_summary()
        
    except KeyboardInterrupt:
        print("\n\nTests interrupted by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")

if __name__ == "__main__":
    main()
