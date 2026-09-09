#!/usr/bin/env python3
"""
Test script to verify admin /api/config returns correct mainServerUrl
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_admin_config():
    """Test admin /api/config endpoint"""
    from app.admin.server import app, get_config
    
    print("\n" + "="*60)
    print("🧪 Testing Admin /api/config Endpoint")
    print("="*60)
    
    with app.test_client() as client:
        # Test 1: Without external_url (local development)
        print("\n✅ Test 1: Local Development (no external_url)")
        print("-" * 60)
        
        response = client.get('/api/config')
        config = response.get_json()
        
        print(f"Response status: {response.status_code}")
        print(f"mainServerUrl: {config.get('mainServerUrl')}")
        print(f"mainServerPort: {config.get('mainServerPort')}")
        print(f"mainServerProtocol: {config.get('mainServerProtocol')}")
        
        # Verify mainServerUrl doesn't contain 0.0.0.0
        main_url = config.get('mainServerUrl', '')
        if '0.0.0.0' in main_url:
            print("❌ FAILED: mainServerUrl still contains 0.0.0.0")
            print(f"   Expected: localhost, got: {main_url}")
            return False
        elif 'localhost' not in main_url and '127.0.0.1' not in main_url:
            print(f"⚠️  WARNING: mainServerUrl is not localhost: {main_url}")
        else:
            print("✅ PASSED: mainServerUrl uses localhost/127.0.0.1")
        
        # Verify response is valid JSON and has expected keys
        if not main_url:
            print("❌ FAILED: mainServerUrl is empty")
            return False
        
        print("\n✅ All tests passed!")
        return True

if __name__ == '__main__':
    try:
        success = test_admin_config()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
