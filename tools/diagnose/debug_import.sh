#!/bin/bash
# Quick debug script to check import issues

echo "Starting admin server with debug output..."
echo "==============================================="

cd ~/ezy_speech_translate
python3 app/admin/server.py 2>&1 &
SERVER_PID=$!

# Wait a bit for startup
sleep 5

# Show which process is running
echo "Server PID: $SERVER_PID"
ps aux | grep $SERVER_PID | grep -v grep

# Kill the server
kill $SERVER_PID 2>/dev/null || true
wait $SERVER_PID 2>/dev/null || true

echo "==============================================="
echo "Debug output complete"
