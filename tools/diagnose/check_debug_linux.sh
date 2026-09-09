#!/bin/bash
# ============================================================
# Linux Server Debug - Run this to see import debug output
# ============================================================

echo "Starting Admin Server with debug output..."
echo "Check for [DEBUG PATH] and [DEBUG IMPORT] messages"
echo "============================================================"
echo ""

cd ~/ezy_speech_translate

# Run server and capture stderr (that's where debug output goes)
python3 app/admin/server.py 2>&1 | head -100

echo ""
echo "============================================================"
echo "If you see '[DEBUG IMPORT] ✓ SecureConfig imported' -> GOOD!"
echo "If you see '[DEBUG IMPORT] ✗ ImportError' -> Need to fix"
echo "============================================================"
