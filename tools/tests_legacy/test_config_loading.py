#!/usr/bin/env python3
"""
Config Loading Diagnostic Script
Run this on the Linux system to debug configuration issues
"""

import os
import sys
import json
from pathlib import Path

# Add parent dir to path
sys.path.insert(0, os.path.dirname(__file__))

print("=" * 60)
print("Configuration Loading Diagnostic Tool")
print("=" * 60)

# Check file existence
config_path = Path(__file__).parent / "config" / "config.yaml"
secrets_path = Path(__file__).parent / "config" / "secrets.key"

print(f"\n1. File Existence Check:")
print(f"   config.yaml exists: {config_path.exists()}")
print(f"   secrets.key exists: {secrets_path.exists()}")

# Check file readability
if config_path.exists():
    print(f"\n2. config.yaml Details:")
    print(f"   Size: {config_path.stat().st_size} bytes")
    print(f"   Readable: {os.access(config_path, os.R_OK)}")

if secrets_path.exists():
    print(f"\n3. secrets.key Details:")
    print(f"   Size: {secrets_path.stat().st_size} bytes")
    print(f"   Readable: {os.access(secrets_path, os.R_OK)}")

# Try loading secrets.key
print(f"\n4. Loading secrets.key:")
try:
    raw = json.loads(secrets_path.read_text(encoding='utf-8'))
    print(f"   ✓ Successfully parsed JSON")
    print(f"   Fields: {list(raw.keys())}")
except Exception as e:
    print(f"   ✗ Failed to parse: {e}")
    sys.exit(1)

# Try Fernet decryption
print(f"\n5. Testing Fernet Decryption:")
try:
    from cryptography.fernet import Fernet
    
    fernet_key = raw.get('fernet_key')
    if not fernet_key:
        print(f"   ✗ No fernet_key in secrets.key")
        sys.exit(1)
    
    key_bytes = fernet_key.encode()
    f = Fernet(key_bytes)
    print(f"   ✓ Fernet initialized")
    
    # Try decrypting each field
    for field in ['admin_password', 'jwt_secret', 'server_secret_key']:
        token = raw.get(field, '')
        if not token:
            print(f"   ⚠ {field} is empty")
            continue
        
        try:
            decrypted = f.decrypt(token.encode()).decode()
            print(f"   ✓ {field}: {decrypted if field == 'admin_password' else decrypted[:30] + '...'}")
        except Exception as e:
            print(f"   ✗ {field}: {type(e).__name__}: {e}")

except ImportError:
    print(f"   ✗ cryptography library not installed")
    sys.exit(1)
except Exception as e:
    print(f"   ✗ Fernet error: {e}")
    sys.exit(1)

# Try loading via SecureConfig
print(f"\n6. Testing SecureConfig Loader:")
try:
    from secure_loader import SecureConfig
    config = SecureConfig('config/config.yaml', 'config/secrets.key')
    
    admin_pw = config.get('authentication', 'admin_password', default=None)
    jwt_sec = config.get('authentication', 'jwt_secret', default=None)
    
    print(f"   admin_password loaded: {bool(admin_pw)}")
    print(f"   jwt_secret loaded: {bool(jwt_sec)}")
    
    if admin_pw:
        print(f"   ✓ admin_password value: {admin_pw}")
    else:
        print(f"   ✗ admin_password is None or empty")
        
except Exception as e:
    print(f"   ✗ Error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

print(f"\n" + "=" * 60)
print("If everything is ✓, then configuration should work correctly!")
print("=" * 60)
