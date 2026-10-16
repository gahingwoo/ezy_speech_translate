"""
Translation Service with Rate Limiting and Caching
解决 Google Translate 的 Rate Limit 和 CORS 问题

Features:
- Server-side translation proxy (no CORS issues)
- Request caching to avoid duplicate translations
- Request queue with delays (prevent rate limiting)
- Error recovery with exponential backoff
- Support for multiple translation engines
"""

from __future__ import annotations

import requests
import time
import hashlib
import logging
import re
from functools import lru_cache
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple
from queue import Queue, Empty
from threading import Thread, Lock, Event
import json

from .backends import GoogleWebBackend, build_backends

logger = logging.getLogger(__name__)

class TranslationCache:
    """Simple LRU cache for translations"""
    
    def __init__(self, max_size: int = 1000, ttl_hours: int = 24):
        self.cache = {}
        self.max_size = max_size
        self.ttl = timedelta(hours=ttl_hours)
        self.lock = Lock()
    
    def _make_key(self, text: str, target_lang: str) -> str:
        """Generate cache key from text and target language"""
        combined = f"{text}_{target_lang}"
        return hashlib.md5(combined.encode(), usedforsecurity=False).hexdigest()
    
    def get(self, text: str, target_lang: str) -> Optional[str]:
        """Get cached translation if exists and not expired"""
        key = self._make_key(text, target_lang)
        with self.lock:
            if key in self.cache:
                cached_text, timestamp = self.cache[key]
                # Check if expired
                if datetime.now() - timestamp < self.ttl:
                    logger.info(f"Cache hit for {target_lang}: {text[:50]}...")
                    return cached_text
                else:
                    # Remove expired entry
                    del self.cache[key]
        return None
    
    def set(self, text: str, target_lang: str, translation: str):
        """Cache a translation"""
        key = self._make_key(text, target_lang)
        with self.lock:
            # Remove oldest items if cache is full
            if len(self.cache) >= self.max_size:
                # Remove oldest entry (simple FIFO)
                oldest_key = next(iter(self.cache))
                del self.cache[oldest_key]
                logger.warning(f"Cache full, removed oldest entry")
            
            self.cache[key] = (translation, datetime.now())
    
    def clear(self):
        """Clear all cache"""
        with self.lock:
            self.cache.clear()


class TranslationQueue:
    """Request queue to control rate limiting"""
    
    def __init__(self, min_delay: float = 0.5, max_concurrent: int = 3):
        """
        Args:
            min_delay: Minimum delay between requests in seconds
            max_concurrent: Maximum concurrent request handlers
        """
        self.queue = Queue()
        self.min_delay = min_delay
        self.max_concurrent = max_concurrent
        self.last_request_time = {}  # Per-language timing
        self.lock = Lock()
        self.active_requests = 0
        self.is_running = True
    
    def add_request(self, text: str, target_lang: str, callback):
        """Add translation request to queue"""
        self.queue.put((text, target_lang, callback))
    
    def wait_for_rate_limit(self, target_lang: str):
        """Wait if necessary to respect rate limiting"""
        with self.lock:
            now = time.time()
            last_time = self.last_request_time.get(target_lang, 0)
            elapsed = now - last_time
            
            if elapsed < self.min_delay:
                wait_time = self.min_delay - elapsed
                logger.debug(f"Rate limiting: waiting {wait_time:.2f}s for {target_lang}")
                time.sleep(wait_time)
            
            self.last_request_time[target_lang] = time.time()
    
    def start_workers(self, worker_func, num_workers: int = 2):
        """Start background workers to process queue"""
        for i in range(num_workers):
            worker = Thread(
                target=self._worker_loop,
                args=(worker_func,),
                daemon=True,
                name=f"TranslationWorker-{i}"
            )
            worker.start()
            logger.info(f"Started translation worker {i}")
    
    def _worker_loop(self, worker_func):
        """Worker loop to process queue items"""
        while self.is_running:
            try:
                # Get item with timeout
                text, target_lang, callback = self.queue.get(timeout=1)
                
                # Wait for rate limiting
                self.wait_for_rate_limit(target_lang)
                
                # Process the translation
                try:
                    with self.lock:
                        self.active_requests += 1
                    
                    result = worker_func(text, target_lang)
                    callback(result, None)  # Success
                    
                except Exception as e:
                    logger.error(f"Translation failed: {e}")
                    callback(None, str(e))  # Error
                
                finally:
                    with self.lock:
                        self.active_requests -= 1
                    self.queue.task_done()
            
            except Empty:
                continue
            except Exception as e:
                logger.error(f"Worker error: {e}")


class TranslationHealth:
    """How translation has gone lately, for the console to see: the last few
    minutes of attempts, which provider answered each, and why one did not."""

    WINDOW = 300                        # seconds looked back over

    def __init__(self):
        self._lock = Lock()
        self._events = []               # (time, answered_by or None, refusals: [(provider, why)])

    def record(self, answered_by: Optional[str], refusals: list):
        now = time.time()
        with self._lock:
            self._events.append((now, answered_by, list(refusals)))
            cut = now - self.WINDOW
            while self._events and self._events[0][0] < cut:
                self._events.pop(0)

    def summary(self, first_provider: str) -> dict:
        """state: ok; degraded (the first provider refuses, another answers);
        failing (half or more of three or more attempts got nothing)."""
        cut = time.time() - self.WINDOW
        with self._lock:
            recent = [e for e in self._events if e[0] >= cut]
        tried = len(recent)
        failed = sum(1 for e in recent if e[1] is None)
        answered = {}
        for e in recent:
            if e[1]:
                answered[e[1]] = answered.get(e[1], 0) + 1
        last_why = next((r[-1][1] for e in reversed(recent) for r in [e[2]] if r), None)
        if tried >= 3 and failed * 2 >= tried:
            state = 'failing'
        elif any(p != first_provider for p in answered):
            state = 'degraded'
        else:
            state = 'ok'
        return {'state': state, 'tried': tried, 'failed': failed, 'answered_by': answered,
                'first': first_provider, 'reason': last_why, 'window': self.WINDOW}


class GoogleTranslateService:
    """Translation with caching, glossary protection, and backends tried in
    order (see backends.py). The name is from when Google's web endpoint was
    the only one."""

    def __init__(self, cache_size: int = 1000, cache_ttl_hours: int = 24, backends=None):
        self.cache = TranslationCache(max_size=cache_size, ttl_hours=cache_ttl_hours)
        self.queue = TranslationQueue(min_delay=0.5, max_concurrent=3)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.backends = backends if backends is not None else [GoogleWebBackend(self.session)]
        self.timeout = 10
        self.health = TranslationHealth()
        # Lines being fetched right now, so a second asker waits for the first.
        self._inflight: Dict[Tuple[str, str], dict] = {}
        self._inflight_lock = Lock()

    def translate(self, text: str, target_lang: str,
                  glossary: list | None = None) -> Tuple[bool, str, bool]:
        """
        Translate text to target language

        Args:
            text: Text to translate
            target_lang: Target language code
            glossary: Optional list of dicts with keys:
                source_term, translation, case_sensitive (bool)
                Terms are protected with placeholders during translation
                and substituted back afterwards. Only entries whose
                target_lang matches (or is '*') should be supplied here.

        Returns:
            (success, result, from_cache) - Tuple of (success bool, translated text, from_cache bool)
        """
        if not text or not text.strip():
            return True, text, False

        # Build cache key including a glossary fingerprint so a glossary change
        # invalidates cached results for the same text+lang.
        glossary_sig = ""
        applicable_terms: list = []
        if glossary:
            for g in glossary:
                term = (g.get("source_term") or "").strip()
                trans = (g.get("translation") or "").strip()
                if not term or not trans:
                    continue
                applicable_terms.append({
                    "term": term, "translation": trans,
                    "case_sensitive": bool(g.get("case_sensitive")),
                })
            if applicable_terms:
                # Stable signature for cache invalidation
                sig_src = "|".join(
                    f"{t['term']}={t['translation']}:{int(t['case_sensitive'])}"
                    for t in sorted(applicable_terms, key=lambda x: x["term"])
                )
                glossary_sig = hashlib.md5(sig_src.encode("utf-8"), usedforsecurity=False).hexdigest()[:8]

        cache_lang_key = target_lang + (f"#{glossary_sig}" if glossary_sig else "")

        # Check cache first
        cached = self.cache.get(text, cache_lang_key)
        if cached:
            logger.debug(f"Cache hit for {target_lang}: {text[:30]}...")
            return True, cached, True

        # Every listener reading the same language asks for the same line at
        # the same moment, the instant it is spoken, so all of them miss the
        # cache together and each used to make its own request. One goes out;
        # the rest wait for its answer.
        key = (text, cache_lang_key)
        with self._inflight_lock:
            pending = self._inflight.get(key)
            leader = pending is None
            if leader:
                pending = self._inflight[key] = {'done': Event(), 'result': None}
        if not leader:
            # Longer than the leader can take: three attempts of ten seconds
            # with their backoff between.
            pending['done'].wait(timeout=40)
            result = pending['result']
            if result is None:
                return False, text, False
            success, translated, _ = result
            return success, translated, success
        try:
            pending['result'] = self._fetch(text, target_lang, cache_lang_key, applicable_terms)
            return pending['result']
        finally:
            with self._inflight_lock:
                self._inflight.pop(key, None)
            pending['done'].set()

    def _fetch(self, text: str, target_lang: str, cache_lang_key: str,
               applicable_terms: list) -> Tuple[bool, str, bool]:
        """Ask each backend in turn, and cache the first answer."""
        # Protect glossary terms with placeholders before translation
        protected_text, placeholders = self._apply_glossary_protect(
            text, applicable_terms
        )
        refusals = []
        for backend in self.backends:
            if not backend.supports(target_lang):
                continue
            # A timeout is worth one more try; anything else, the next backend.
            for attempt in range(2):
                try:
                    result = backend.translate(protected_text, target_lang, self.timeout)
                except requests.exceptions.Timeout:
                    logger.warning(f"{backend.name}: timed out (attempt {attempt + 1})")
                    if attempt == 0:
                        time.sleep(1)
                        continue
                    refusals.append((backend.name, 'timed out'))
                    break
                except requests.exceptions.HTTPError as e:
                    status = e.response.status_code if e.response is not None else '?'
                    # 429 from google_web: it refuses a server outright, and
                    # waiting changes nothing. The browser asks it directly
                    # when every backend here has said no.
                    logger.warning(f"{backend.name}: refused ({status})")
                    refusals.append((backend.name, f'refused ({status})'))
                    break
                except Exception as e:
                    logger.error(f"{backend.name}: {e}")
                    refusals.append((backend.name, type(e).__name__))
                    break
                if result:
                    final = self._apply_glossary_restore(result, placeholders)
                    self.cache.set(text, cache_lang_key, final)
                    self.health.record(backend.name, refusals)
                    logger.info(f"Translated to {target_lang} by {backend.name}: "
                                f"{text[:50]}...{final[:50]}...")
                    return True, final, False
                refusals.append((backend.name, 'no answer'))
                break
        self.health.record(None, refusals)
        logger.error(f"No translation backend answered for {target_lang}")
        return False, text, False

    # ── Glossary helpers ──────────────────────────────────────────────────
    # Placeholder format: zero-width-safe ASCII token that survives Google
    # Translate without alteration. Tested against zh/ja/ko/es/fr/de.
    _PH_PREFIX = "ZQX"
    _PH_SUFFIX = "QZ"

    def _apply_glossary_protect(self, text: str, terms: list) -> Tuple[str, dict]:
        """Replace glossary source terms with placeholders.

        Returns (modified_text, {placeholder -> target_translation}).
        Longer terms are matched first to avoid partial overlaps.
        If the source text already contains our placeholder pattern, we skip
        protection entirely to avoid corruption — translation proceeds without
        glossary substitution for this call.
        """
        if not terms:
            return text, {}
        # Collision check: if source already contains our placeholder pattern,
        # bail out rather than risk silently corrupting the user's text.
        if re.search(rf"{self._PH_PREFIX}\d{{3}}{self._PH_SUFFIX}", text):
            logger.warning("Glossary placeholder collision detected in source; skipping glossary")
            return text, {}
        placeholders: dict = {}
        # Sort by source term length descending so "Jesus Christ" wins over "Jesus"
        sorted_terms = sorted(terms, key=lambda t: len(t["term"]), reverse=True)
        result = text
        for idx, t in enumerate(sorted_terms):
            ph = f"{self._PH_PREFIX}{idx:03d}{self._PH_SUFFIX}"
            pattern = re.escape(t["term"])
            flags = 0 if t["case_sensitive"] else re.IGNORECASE
            new_result, n = re.subn(pattern, ph, result, flags=flags)
            if n > 0:
                result = new_result
                placeholders[ph] = t["translation"]
        return result, placeholders

    def _apply_glossary_restore(self, text: str, placeholders: dict) -> str:
        """Substitute placeholders back with their forced translations."""
        if not placeholders:
            return text
        result = text
        for ph, trans in placeholders.items():
            # Translation engines sometimes uppercase or add spaces; be lenient
            result = re.sub(
                re.escape(ph), trans.replace("\\", r"\\"),
                result, flags=re.IGNORECASE,
            )
        return result
    
    def health_summary(self) -> dict:
        return self.health.summary(self.backends[0].name if self.backends else 'none')

    def clear_cache(self):
        """Clear translation cache"""
        self.cache.clear()
        logger.info("Translation cache cleared")


# Global instance
_translation_service = None

def get_translation_service() -> GoogleTranslateService:
    """Get or create global translation service instance"""
    global _translation_service
    if _translation_service is None:
        service = GoogleTranslateService()
        try:
            from app.core.config import get_config
            service.backends = build_backends(
                service.session, lambda key, default=None: get_config('translation', key, default=default))
        except Exception as exc:          # no config to read: the default
            logger.warning(f"Translation providers from config unavailable ({exc}); using google_web")
        _translation_service = service
    return _translation_service
