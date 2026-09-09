#!/usr/bin/env python
"""Complete admin login test"""

import os
import sys
import json
import hashlib

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, BASE_DIR)

# Import after path setup
from app.admin.server import app, ADMIN_USERNAME, ADMIN_PASSWORD, hash_password, login

print("=" * 80)
print("ADMIN SERVER LOGIN TEST")
print("=" * 80)

print(f"\n1. Credentials Configuration:")
print(f"   ADMIN_USERNAME: '{ADMIN_USERNAME}'")
print(f"   ADMIN_PASSWORD: '{ADMIN_PASSWORD}'")
print(f"   ADMIN_PASSWORD hash: {hash_password(ADMIN_PASSWORD)}")

# Test the hash_password function with actual credentials. From the
# environment, not from this file: it is in a public repository.
#   EZY_TEST_PASSWORD=... python3 tools/tests_legacy/test_admin_full_login.py
test_user = os.environ.get("EZY_TEST_USERNAME", "admin")
test_pass = os.environ.get("EZY_TEST_PASSWORD", "")
if not test_pass:
    sys.exit("set EZY_TEST_PASSWORD to the admin password before running this")

print(f"\n2. Test Login Simulation:")
print(f"   Input username: '{test_user}'")
print(f"   Input password: '{test_pass}'")
print(f"   Username matches: {test_user == ADMIN_USERNAME}")
print(f"   Password matches: {hash_password(test_pass) == hash_password(ADMIN_PASSWORD)}")

if test_user == ADMIN_USERNAME and hash_password(test_pass) == hash_password(ADMIN_PASSWORD):
    print(f"   ✅ CREDENTIALS ARE CORRECT!")
else:
    print(f"   ❌ CREDENTIALS MISMATCH!")

# Try with app test client
print(f"\n3. Testing with Flask Test Client:")
with app.test_client() as client:
    response = client.post(
        '/api/login',
        data=json.dumps({
            'username': test_user,
            'password': test_pass
        }),
        content_type='application/json'
    )
    
    print(f"   Status Code: {response.status_code}")
    print(f"   Response: {response.get_json()}")
    
    if response.status_code == 200:
        data = response.get_json()
        if data.get('success'):
            print(f"   ✅ LOGIN SUCCESSFUL!")
            print(f"   Token received: {data.get('token')[:50]}..." if data.get('token') else "   ❌ No token in response")
        else:
            print(f"   ❌ Success=false: {data.get('error')}")
    else:
        print(f"   ❌ Login failed with status {response.status_code}")

print("\n" + "=" * 80)
