"""Thin JWT helpers (HS256). Keep them stateless so both servers can share."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Optional

import jwt

_log = logging.getLogger("security")


def encode_jwt(payload: dict, secret: str, exp_seconds: Optional[int] = None) -> str:
    """Encode `payload` as a JWT signed with HS256.

    If `exp_seconds` is provided, sets `exp` and `iat` claims automatically
    (existing values in `payload` are preserved).
    """
    body = dict(payload)
    if exp_seconds is not None:
        body.setdefault("iat", datetime.utcnow())
        body.setdefault("exp", datetime.utcnow() + timedelta(seconds=exp_seconds))
    return jwt.encode(body, secret, algorithm="HS256")


def decode_jwt(token: Optional[str], secret: str) -> Optional[dict[str, Any]]:
    """Verify+decode a JWT. Returns the payload, or None on any failure."""
    if not token:
        return None
    try:
        return jwt.decode(token, secret, algorithms=["HS256"], options={"verify_exp": True})
    except jwt.ExpiredSignatureError:
        _log.info("Expired JWT presented")
        return None
    except jwt.InvalidTokenError as exc:
        _log.warning("Invalid JWT: %s", exc)
        return None
