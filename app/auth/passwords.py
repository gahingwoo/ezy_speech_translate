"""Password checking.

The browser sends SHA-256 of what was typed (client_hash). The server keeps
a PBKDF2-SHA256 verifier of that, made by make_verifier, in config/secrets.key;
see secure_loader.py, where it is made and where an older install's password
is converted.
"""

from __future__ import annotations

import os
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from secure_loader import (  # noqa: E402,F401
    client_hash, make_verifier, is_verifier, check_verifier, store_admin_password,
)


def hash_password(password: str) -> str:
    """What the browser sends for a password. Kept under its old name."""
    return client_hash(password)


def verify(client_hex: str, verifier: str | None) -> bool:
    """Whether what the browser sent matches the verifier.

    The hash takes a fifth of a second of CPU by design, and the servers run
    on one thread: done in place, every sign-in would stop live captions for
    everyone for that long. Under eventlet it runs on a real thread instead.
    """
    if not verifier or not isinstance(client_hex, str) or len(client_hex) != 64:
        return False
    try:
        from eventlet import tpool
        return bool(tpool.execute(check_verifier, client_hex, verifier))
    except Exception:
        return check_verifier(client_hex, verifier)
