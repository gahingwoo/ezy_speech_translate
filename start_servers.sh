#!/bin/bash

# EzySpeechTranslate - Start Both Servers Script

cd "$(dirname "$0")" || exit 1

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}EzySpeechTranslate - Server Startup${NC}"
echo -e "${BLUE}========================================${NC}\n"

# Load Python environment
if [ -d "venv/bin" ]; then
    echo -e "${YELLOW}Activating Python environment...${NC}"
    source venv/bin/activate
else
    echo -e "${RED}❌ Virtual environment not found at venv/bin${NC}"
    exit 1
fi

# Verify both servers can be imported
echo -e "\n${YELLOW}Verifying server imports...${NC}"

python -c "from app.user.server import app; print('✓ User server imports OK')" 2>&1 | head -5
if [ ${PIPESTATUS[0]} -ne 0 ]; then
    echo -e "${RED}❌ User server import failed${NC}"
    exit 1
fi

python -c "from app.admin.server import app; print('✓ Admin server imports OK')" 2>&1 | head -5
if [ ${PIPESTATUS[0]} -ne 0 ]; then
    echo -e "${RED}❌ Admin server import failed${NC}"
    exit 1
fi

echo -e "\n${GREEN}✓ All imports successful${NC}"

# Display configuration
echo -e "\n${BLUE}========== Configuration ==========${NC}"
echo -e "User Server:  ${GREEN}http://localhost:1915${NC}"
echo -e "Admin Panel:  ${GREEN}http://localhost:1916/admin${NC}"
echo -e "Login Page:   ${GREEN}http://localhost:1916/login${NC}"
echo -e "${BLUE}===================================${NC}\n"

# Start user server in background
echo -e "${YELLOW}Starting User Server on port 1915...${NC}"
nohup python -m app.user.server > logs/user_server.log 2>&1 &
USER_PID=$!
disown $USER_PID
echo -e "${GREEN}✓ User Server PID: $USER_PID${NC}"
sleep 2

# Start admin server in background
echo -e "${YELLOW}Starting Admin Server on port 1916...${NC}"
nohup python -m app.admin.server > logs/admin_server.log 2>&1 &
ADMIN_PID=$!
disown $ADMIN_PID
echo -e "${GREEN}✓ Admin Server PID: $ADMIN_PID${NC}"
sleep 2

# Verify servers are running
echo -e "\n${BLUE}========== Status Check ==========${NC}"

if ps -p $USER_PID > /dev/null; then
    echo -e "${GREEN}✓ User Server is running (PID: $USER_PID)${NC}"
else
    echo -e "${RED}❌ User Server failed to start${NC}"
    echo -e "${YELLOW}Check logs/user_server.log for details${NC}"
fi

if ps -p $ADMIN_PID > /dev/null; then
    echo -e "${GREEN}✓ Admin Server is running (PID: $ADMIN_PID)${NC}"
else
    echo -e "${RED}❌ Admin Server failed to start${NC}"
    echo -e "${YELLOW}Check logs/admin_server.log for details${NC}"
fi

echo -e "${BLUE}===================================${NC}\n"

# Instructions
echo -e "${BLUE}📝 Next Steps:${NC}"
echo -e "1. Open ${GREEN}http://localhost:1916/login${NC} in your browser"
echo -e "2. Login with credentials from your config"
echo -e "3. Open ${GREEN}http://localhost:1915${NC} for the user/client interface\n"

echo -e "${YELLOW}Server logs are saved to:${NC}"
echo -e "  - User:  logs/user_server.log"
echo -e "  - Admin: logs/admin_server.log"
echo -e "  - Security: logs/security.log\n"

echo -e "${YELLOW}To stop servers:${NC} kill $(lsof -ti :1915 :1916) 2>/dev/null${NC}\n"

echo -e "${GREEN}✓ Both servers are running in background (nohup — survive terminal close)${NC}\n"

