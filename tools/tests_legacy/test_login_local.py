#!/usr/bin/env python3
"""
Test the login process locally
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import hashlib
from secure_loader import SecureConfig

print("=" * 60)
print("Login Process Test")
print("=" * 60)

# Load config
config = SecureConfig('config/config.yaml')

admin_username = config.get('authentication', 'admin_username', default='admin')
admin_password = config.get('authentication', 'admin_password', default='admin123')

print(f"\n1. Loaded Credentials:")
print(f"   USERNAME: {admin_username}")
print(f"   PASSWORD: {admin_password}")
print(f"   PASSWORD TYPE: {type(admin_password)}")
print(f"   PASSWORD EMPTY: {not admin_password}")

# Simulate login. The password comes from the environment: this file is in a
# public repository, and a working password written into it is a published one.
#   EZY_TEST_PASSWORD=... python3 tools/tests_legacy/test_login_local.py
test_username = os.environ.get("EZY_TEST_USERNAME", "admin")
test_password = os.environ.get("EZY_TEST_PASSWORD", "")
if not test_password:
    sys.exit("set EZY_TEST_PASSWORD to the admin password before running this")

def hash_password(password):
    """Hash password with SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

expected_hash = hash_password(admin_password)
provided_hash = hash_password(test_password)

print(f"\n2. Password Verification:")
print(f"   Expected hash: {expected_hash}")
print(f"   Provided hash: {provided_hash}")
print(f"   Hashes match: {expected_hash == provided_hash}")

print(f"\n3. Username Verification:")
print(f"   Expected: {admin_username}")
print(f"   Provided: {test_username}")
print(f"   Usernames match: {admin_username == test_username}")

print(f"\n4. Final Result:")
if (test_username == admin_username) and (provided_hash == expected_hash):
    print(f"   ✓ LOGIN WOULD SUCCEED")
else:
    print(f"   ✗ LOGIN WOULD FAIL")
    print(f"   Reasons:")
    if test_username != admin_username:
        print(f"     - Username mismatch")
    if provided_hash != expected_hash:
        print(f"     - Password mismatch")

print("\n" + "=" * 60)
