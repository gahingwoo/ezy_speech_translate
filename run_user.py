#!/usr/bin/env python3
"""
User Server Launcher
Run the user server from project root

Copyright (C) 2025-2026 Ga Hing Woo (Jiaxing Hu)

This file is part of EzySpeech.

EzySpeech is free software: you can redistribute it and/or modify it under
the terms of the GNU Affero General Public License as published by the Free
Software Foundation, either version 3 of the License, or (at your option)
any later version. Two additional terms apply under section 7: the author
attribution in the about dialog must be preserved, and no trademark rights
are granted. See LICENSE and TRADEMARK.md.

EzySpeech is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE. See the GNU Affero General Public License for more
details.
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
