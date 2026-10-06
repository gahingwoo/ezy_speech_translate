"""The version of EzySpeech, read from the VERSION file at the root.

That file is the one place the number is written. The servers put it in
every page and in /api/health, the Docker image and the release package
are named by it, and the ezyspeech command compares it with the latest
release to offer an update.
"""
from pathlib import Path

_FILE = Path(__file__).resolve().parent.parent.parent / 'VERSION'

try:
    VERSION = _FILE.read_text(encoding='utf-8').strip() or '0.0.0'
except OSError:
    VERSION = '0.0.0'
