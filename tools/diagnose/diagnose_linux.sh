#!/bin/bash
# Quick diagnostics for Linux login issue

echo "=== EzySpeechTranslate Linux Diagnostics ==="
echo ""

# Check Python version
echo "1. Python Version:"
python3 --version
echo ""

# Check if required packages are installed
echo "2. Checking required packages:"
python3 -c "
import sys
packages = ['cryptography', 'flask', 'yaml']
for pkg in packages:
    try:
        __import__(pkg)
        print(f'   ✓ {pkg}')
    except ImportError:
        print(f'   ✗ {pkg} MISSING')
        sys.exit(1)
"
echo ""

# Run the diagnostic script
echo "3. Running detailed configuration diagnostic:"
python3 test_config_loading.py
echo ""

# Try a test login simulation
echo "4. Testing password hashing:"
python3 << 'PYEOF'
import hashlib

# Load the actual password from config
import sys
import os
sys.path.insert(0, os.getcwd())

try:
    from secure_loader import SecureConfig
    config = SecureConfig('config/config.yaml')
    password = config.get('authentication', 'admin_password')
    
    if password:
        hashed = hashlib.sha256(password.encode()).hexdigest()
        print(f"   ✓ Password loaded: {password}")
        print(f"   ✓ Hash: {hashed[:32]}...")
    else:
        print("   ✗ Password is None or empty!")
except Exception as e:
    print(f"   ✗ Error: {e}")
PYEOF

echo ""
echo "=== Diagnostics Complete ==="
