#!/usr/bin/env python3
"""ezy_manager.py: replaced by install.sh and the ezyspeech command.

It installed EzySpeech as two systemd services and updated it with git pull. Installing is now one command, natively (system services under an
"ezyspeech" account) or in Docker:

    curl -fsSL https://github.com/gahingwoo/ezy_speech_translate/releases/latest/download/install.sh | sudo bash

and an install is run with `ezyspeech` (status, update, restart, password,
logs, backup, uninstall), from Cockpit, or from the installer's menu. An
install made by ezy_manager.py is found and its settings, password and
transcripts brought over.

This file only points there, and passes `manage <command>` on to ezyspeech.
"""
import os
import shutil
import sys

ARGS = sys.argv[1:]
MANAGE = {'start': 'start', 'stop': 'stop', 'restart': 'restart', 'status': 'status',
          'logs': 'logs', 'logs:user': 'logs', 'logs:admin': 'logs'}
if len(ARGS) >= 2 and ARGS[0] == 'manage' and ARGS[1] in MANAGE and shutil.which('ezyspeech'):
    os.execvp('ezyspeech', ['ezyspeech', MANAGE[ARGS[1]], *ARGS[2:]])

print(__doc__.split("\n\n", 1)[1].rsplit("\n\nThis file", 1)[0], file=sys.stderr)
sys.exit(1)
