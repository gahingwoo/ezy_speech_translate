#!/bin/bash
# Complete Linux Login Diagnostics Guide

echo "╔════════════════════════════════════════════════════════════╗"
echo "║  EzySpeechTranslate Linux Login Issue - Full Diagnostic    ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# Step 1: Check basic prerequisites
echo "STEP 1: Checking Prerequisites..."
echo "─────────────────────────────"
python3 --version || { echo "❌ Python 3 not found!"; exit 1; }
echo "✓ Python 3 available"
echo ""

# Step 2: Test configuration loading
echo "STEP 2: Testing Configuration Loading..."
echo "────────────────────────────────────"
python3 << 'PYEOF'
import sys
import os
sys.path.insert(0, os.getcwd())

try:
    from secure_loader import SecureConfig
    config = SecureConfig('config/config.yaml')
    
    admin_pw = config.get('authentication', 'admin_password')
    jwt_sec = config.get('authentication', 'jwt_secret')
    
    print(f"✓ SecureConfig loaded successfully")
    print(f"  - admin_password: {'LOADED' if admin_pw else 'MISSING'} (length: {len(admin_pw) if admin_pw else 0})")
    print(f"  - jwt_secret: {'LOADED' if jwt_sec else 'MISSING'} (length: {len(jwt_sec) if jwt_sec else 0})")
    
    if not admin_pw:
        print(f"❌ ERROR: admin_password is not loaded!")
        sys.exit(1)
    
except Exception as e:
    print(f"❌ Error loading config: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
PYEOF

if [ $? -ne 0 ]; then
    echo "❌ Configuration loading failed!"
    exit 1
fi
echo ""

# Step 3: Test login simulation
echo "STEP 3: Testing Login Simulation..."
echo "─────────────────────────────"
python3 test_login_local.py || {
    echo "❌ Login test failed!"
    exit 1
}
echo ""

# Step 4: Check server startup
echo "STEP 4: Starting Admin Server (for 10 seconds)..."
echo "─────────────────────────────────────────"
timeout 10 python3 -u app/admin/server.py 2>&1 | head -50 &
SERVER_PID=$!
sleep 3

# Step 5: Test server connectivity
echo ""
echo "STEP 5: Testing Server Connectivity..."
echo "──────────────────────────────────"
if curl -s http://localhost:1916/api/debug/config > /dev/null 2>&1; then
    echo "✓ Server is responding"
    echo ""
    echo "Server config response:"
    curl -s http://localhost:1916/api/debug/config | python3 -m json.tool || echo "Response not JSON"
else
    echo "⚠ Server not responding (expected if not running)"
fi

# Step 6: Test login endpoint
echo ""
echo "STEP 6: Testing Login Endpoint..."
echo "────────────────────────────"
echo "Sending login request..."
# From the environment, not from this file: it is in a public repository.
#   EZY_TEST_PASSWORD=... sh tools/diagnose/run_full_diagnostic.sh
if [ -z "$EZY_TEST_PASSWORD" ]; then
  echo "  skipped: set EZY_TEST_PASSWORD to test the login endpoint"
  RESPONSE=""
else
  RESPONSE=$(curl -s -X POST http://localhost:1916/api/login \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"${EZY_TEST_USERNAME:-admin}\",\"password\":\"${EZY_TEST_PASSWORD}\"}")
fi

echo "Response: $RESPONSE"

if echo "$RESPONSE" | grep -q '"success":true'; then
    echo "✓ LOGIN SUCCESSFUL!"
else
    echo "❌ LOGIN FAILED"
fi

# Kill the server
kill $SERVER_PID 2>/dev/null || true
wait $SERVER_PID 2>/dev/null || true

echo ""
echo "════════════════════════════════════════════════════════════"
echo "Diagnostics Complete!"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "Next steps:"
echo "1. Check the responses above for any errors"
echo "2. If login test succeeded but browser login fails, check browser console"
echo "3. If login test failed, check server startup errors above"
echo ""
