"""Input sanitisation utilities (defence-in-depth)."""

from __future__ import annotations

import logging
import re
from typing import Callable, Optional

_log = logging.getLogger("security")

DANGEROUS_PATTERNS = [
    r"<script[^>]*>.*?</script>",
    r"javascript\s*:",
    r"vbscript\s*:",
    r"on\w+\s*=",
    r"<iframe[^>]*>",
    r"<embed[^>]*>",
    r"<object[^>]*>",
    r"<svg[^>]*>",
    r"<img[^>]+onerror",
    r"data\s*:\s*text/html",
    r"expression\s*\(",
]

_CTRL_CHARS = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")

# HTML escape map (used by admin server).
# IMPORTANT: '&' MUST be first so it is replaced before the other entries
# whose replacements contain '&' (e.g. '<' → '&lt;').  If '&' were
# processed last, pre-existing '&' characters would be double-encoded.
_HTML_ESCAPES = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#x27;",
    "/": "&#x2F;",
}


def sanitize_text(
    text: str,
    max_length: int = 5000,
    ip_provider: Optional[Callable[[], str]] = None,
) -> str:
    """Strip control chars, dangerous HTML/JS patterns, and truncate length."""
    if not text or not isinstance(text, str):
        return ""

    text = _CTRL_CHARS.sub("", text)[:max_length]

    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            try:
                ip = ip_provider() if ip_provider else "?"
            except Exception:
                ip = "?"
            _log.warning("Dangerous pattern detected from %s", ip)
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

    return text.strip()


def sanitize_html(text: str) -> str:
    """HTML-escape angle brackets / quotes / slashes (admin server variant)."""
    if not isinstance(text, str):
        return text
    for ch, esc in _HTML_ESCAPES.items():
        text = text.replace(ch, esc)
    return text


def validate_path(path: str) -> bool:
    """Refuse paths that try to traverse upwards or are absolute."""
    if not isinstance(path, str):
        return False
    return ".." not in path and not path.startswith("/")
