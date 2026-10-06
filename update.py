#!/usr/bin/env python3
"""update.py: replaced by install.sh and the ezyspeech command.

It updated EzySpeech with git pull, whatever the remote's main branch held. Installing is now one command, natively (system services under an
"ezyspeech" account) or in Docker:

    curl -fsSL https://github.com/gahingwoo/ezy_speech_translate/releases/latest/download/install.sh | sudo bash

and an install is run with `ezyspeech` (status, update, restart, password,
logs, backup, uninstall), from Cockpit, or from the installer's menu. An
install made by ezy_manager.py is found and its settings, password and
transcripts brought over.

This file only points there, and runs `ezyspeech update` where that is installed.
"""
import os
import shutil
import sys

ARGS = sys.argv[1:]
if shutil.which('ezyspeech'):
    os.execvp('ezyspeech', ['ezyspeech', 'update', *ARGS])

print(__doc__.split("\n\n", 1)[1].rsplit("\n\nThis file", 1)[0], file=sys.stderr)
sys.exit(1)
