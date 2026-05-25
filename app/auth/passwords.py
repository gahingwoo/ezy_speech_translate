"""Password hashing helpers."""

from __future__ import annotations

import hashlib


def hash_password(password: str) -> str:
    """Return the SHA-256 hex digest of `password`.

    NOTE: SHA-256 alone is not ideal for password storage. This matches the
    existing behaviour of the legacy code; migration to bcrypt/argon2 should
    be a follow-up change.
    """
    if password is None:
        password = ""
    return hashlib.sha256(str(password).encode("utf-8")).hexdigest()
