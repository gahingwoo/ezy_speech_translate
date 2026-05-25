"""Thread-safe TTS audio cache.

Replaces the previous module-level ``SYNTHESIS_REQUEST_CACHE`` /
``SYNTHESIS_CACHE_TIME`` dict pair, which had a TOCTOU race between read and
write under eventlet/threaded access and never enforced its limits.

The cache is bounded by both item-count and total byte-size; expired or
over-quota entries are evicted oldest-first on insert (LRU-by-insert-time).
"""

from __future__ import annotations

import threading
import time
from typing import Dict, Optional, Tuple


class TTSCache:
    """Bounded, TTL-aware audio cache safe for concurrent use."""

    def __init__(
        self,
        ttl_seconds: int = 3600,
        max_items: int = 1000,
        max_bytes: int = 1000 * 1024 * 1024,  # 1 GB
    ) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_items = max_items
        self.max_bytes = max_bytes
        self._lock = threading.RLock()
        self._store: Dict[str, bytes] = {}
        self._ts: Dict[str, float] = {}
        self._total_bytes = 0

    # ── public API ────────────────────────────────────────────────────────

    def get(self, key: str) -> Optional[bytes]:
        """Return cached audio for `key` if present and not expired."""
        with self._lock:
            audio = self._store.get(key)
            if audio is None:
                return None
            if time.time() - self._ts.get(key, 0) >= self.ttl_seconds:
                self._evict(key)
                return None
            return audio

    def set(self, key: str, audio: bytes) -> None:
        """Insert or update an entry, evicting old ones to honour limits."""
        if not audio:
            return
        with self._lock:
            if key in self._store:
                self._total_bytes -= len(self._store[key])
            self._store[key] = audio
            self._ts[key] = time.time()
            self._total_bytes += len(audio)
            self._enforce_limits_locked()

    def clear(self) -> Tuple[int, int]:
        """Drop every entry. Returns (items_removed, bytes_freed)."""
        with self._lock:
            items = len(self._store)
            freed = self._total_bytes
            self._store.clear()
            self._ts.clear()
            self._total_bytes = 0
            return items, freed

    def stats(self) -> dict:
        with self._lock:
            return {
                "cache_items": len(self._store),
                "cache_size_bytes": self._total_bytes,
                "cache_size_mb": round(self._total_bytes / (1024 * 1024), 2),
                "cache_ttl_seconds": self.ttl_seconds,
                "max_cache_items": self.max_items,
                "max_cache_size_mb": round(self.max_bytes / (1024 * 1024), 2),
            }

    def __contains__(self, key: str) -> bool:  # convenience
        return self.get(key) is not None

    def __len__(self) -> int:
        with self._lock:
            return len(self._store)

    # ── internals ─────────────────────────────────────────────────────────

    def _evict(self, key: str) -> None:
        audio = self._store.pop(key, None)
        self._ts.pop(key, None)
        if audio is not None:
            self._total_bytes -= len(audio)

    def _enforce_limits_locked(self) -> None:
        # Evict oldest entries until we're within both limits.
        while (
            (self._total_bytes > self.max_bytes or len(self._store) > self.max_items)
            and self._ts
        ):
            oldest = min(self._ts, key=self._ts.get)  # type: ignore[arg-type]
            self._evict(oldest)


# Process-wide singleton; configuration knobs can be overridden by the server
# at startup (see app/user/server.py).
tts_cache = TTSCache()
