#!/usr/bin/env python3
"""
User Server Launcher
Run the user server from project root
"""

import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import and run
from app.user.server import app, socketio

if __name__ == "__main__":
    socketio.run(app, debug=True)
