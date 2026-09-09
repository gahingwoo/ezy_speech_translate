#!/usr/bin/env python
"""Diagnose login issues with CF Tunnel"""

import os
import sys
import json

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, BASE_DIR)

from app.admin.server import app, ADMIN_USERNAME, ADMIN_PASSWORD

print("=" * 80)
print("ADMIN SERVER DIAGNOSIS")
print("=" * 80)

print(f"\n1. Configuration Check:")
print(f"   ✓ ADMIN_USERNAME: {ADMIN_USERNAME}")
print(f"   ✓ ADMIN_PASSWORD set: {bool(ADMIN_PASSWORD)}")
print(f"   ✓ ADMIN_PASSWORD length: {len(ADMIN_PASSWORD)}")

print(f"\n2. Login Endpoint Check:")
with app.test_client() as client:
    # Test valid login
    response = client.post(
        '/api/login',
        data=json.dumps({
            'username': ADMIN_USERNAME,
            'password': ADMIN_PASSWORD
        }),
        content_type='application/json'
    )
    
    if response.status_code == 200:
        data = response.get_json()
        if data.get('success'):
            print(f"   ✓ Backend login works! Token generated")
        else:
            print(f"   ✗ Backend login failed: {data.get('error')}")
    else:
        print(f"   ✗ Unexpected status {response.status_code}: {response.get_json()}")

print(f"\n3. Config Endpoint Check:")
with app.test_client() as client:
    response = client.get('/api/config')
    if response.status_code == 200:
        data = response.get_json()
        print(f"   ✓ Config endpoint works")
        print(f"   - mainServerUrl: {data.get('mainServerUrl', 'NOT SET')}")
        print(f"   - mainServerPort: {data.get('mainServerPort')}")
        print(f"   - mainServerProtocol: {data.get('mainServerProtocol')}")
    else:
        print(f"   ✗ Config endpoint failed: {response.status_code}")

print(f"\n4. Debug Endpoint Check:")
with app.test_client() as client:
    response = client.get('/api/debug/login-info')
    if response.status_code == 200:
        data = response.get_json()
        print(f"   ✓ Debug endpoint works")
        for key, val in data.items():
            if key != "status":
                print(f"   - {key}: {val}")

print("\n" + "=" * 80)
print("\nTo test with curl (replace YOUR_DOMAIN with your actual CF Tunnel domain):")
print("  curl -X POST https://YOUR_DOMAIN/api/debug/login-info")
print("  curl -X POST https://YOUR_DOMAIN/api/config")
print("=" * 80)
