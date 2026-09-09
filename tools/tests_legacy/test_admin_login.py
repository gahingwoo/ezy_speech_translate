#!/usr/bin/env python
"""Test admin login credentials"""

import os
import sys
import hashlib

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, BASE_DIR)

from app.admin.server import ADMIN_USERNAME, ADMIN_PASSWORD, hash_password

print("=" * 60)
print("Admin Login Credentials Test")
print("=" * 60)

print(f"\n1. Loaded Configuration:")
print(f"   ADMIN_USERNAME: {ADMIN_USERNAME}")
print(f"   ADMIN_PASSWORD: {ADMIN_PASSWORD}")
print(f"   ADMIN_PASSWORD type: {type(ADMIN_PASSWORD)}")
print(f"   ADMIN_PASSWORD length: {len(ADMIN_PASSWORD) if ADMIN_PASSWORD else 0}")

# Test hash function
test_password = ADMIN_PASSWORD
test_hash = hash_password(test_password)
print(f"\n2. Hash Test (password='admin123'):")
print(f"   hash_password('admin123'): {hash_password('admin123')}")

print(f"\n3. Actual Password Hash:")
print(f"   hash_password(ADMIN_PASSWORD): {test_hash}")
print(f"   Expected match: {hash_password('admin123') == test_hash}")

print(f"\n4. Login Logic Test:")
username_match = "admin" == ADMIN_USERNAME
password_match = hash_password("admin123") == hash_password(ADMIN_PASSWORD)
print(f"   Username 'admin' == '{ADMIN_USERNAME}': {username_match}")
print(f"   Password 'admin123' hash matches: {password_match}")
print(f"   Both match: {username_match and password_match}")

print("\n5. Try different passwords:")
test_passwords = ["admin123", "admin", "password", ADMIN_PASSWORD]
for pwd in test_passwords:
    match = hash_password(pwd) == hash_password(ADMIN_PASSWORD)
    print(f"   '{pwd}' -> hash match: {match}")

print("\n" + "=" * 60)
