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

import requests
import time
import hashlib
import logging
from functools import lru_cache
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple
from queue import Queue, Empty
from threading import Thread, Lock
import json

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
        return hashlib.md5(combined.encode()).hexdigest()
    
    def get(self, text: str, target_lang: str) -> Optional[str]:
        """Get cached translation if exists and not expired"""
        key = self._make_key(text, target_lang)
        with self.lock:
            if key in self.cache:
                cached_text, timestamp = self.cache[key]
                # Check if expired
                if datetime.now() - timestamp < self.ttl:
                    logger.info(f"📦 Cache hit for {target_lang}: {text[:50]}...")
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
                logger.debug(f"⏳ Rate limiting: waiting {wait_time:.2f}s for {target_lang}")
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
                    logger.error(f"❌ Translation failed: {e}")
                    callback(None, str(e))  # Error
                
                finally:
                    with self.lock:
                        self.active_requests -= 1
                    self.queue.task_done()
            
            except Empty:
                continue
            except Exception as e:
                logger.error(f"Worker error: {e}")


class GoogleTranslateService:
    """Google Translate API service with rate limiting and caching"""
    
    # API endpoint (using the gtx client, no authentication needed)
    API_URL = "https://translate.googleapis.com/translate_a/single"
    
    # Language code mapping
    LANG_MAP = {
        'zh': 'zh-CN',      # Simplified Chinese
        'zh-tw': 'zh-TW',   # Traditional Chinese
        'yue': 'yue',       # Cantonese
        'ja': 'ja',
        'ko': 'ko',
        'es': 'es',
        'fr': 'fr',
        'de': 'de',
        'ru': 'ru',
        'ar': 'ar',
        'pt': 'pt',
        'it': 'it',
        'nl': 'nl',
        'pl': 'pl',
        'tr': 'tr',
        'vi': 'vi',
        'th': 'th',
        'id': 'id',
        'ms': 'ms',
        'hi': 'hi',
        'ta': 'ta',
        'te': 'te',
        'bn': 'bn',
        'kn': 'kn',
        'ml': 'ml',
        'mr': 'mr',
        'ur': 'ur',
    }
    
    def __init__(self, cache_size: int = 1000, cache_ttl_hours: int = 24):
        self.cache = TranslationCache(max_size=cache_size, ttl_hours=cache_ttl_hours)
        self.queue = TranslationQueue(min_delay=0.5, max_concurrent=3)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.retry_attempts = 3
        self.retry_backoff = 2  # Exponential backoff factor
    
    def translate(self, text: str, target_lang: str) -> Tuple[bool, str, bool]:
        """
        Translate text to target language
        
        Args:
            text: Text to translate
            target_lang: Target language code
        
        Returns:
            (success, result, from_cache) - Tuple of (success bool, translated text, from_cache bool)
        """
        if not text or not text.strip():
            return True, text, False
        
        # Check cache first
        cached = self.cache.get(text, target_lang)
        if cached:
            logger.debug(f"📦 Cache hit for {target_lang}: {text[:30]}...")
            return True, cached, True  # Return True for from_cache flag
        
        # Normalize language code
        target_lang = self.LANG_MAP.get(target_lang, target_lang)
        
        # Attempt translation with retries
        for attempt in range(self.retry_attempts):
            try:
                result = self._translate_with_timeout(text, target_lang)
                if result:
                    # Cache successful translation
                    self.cache.set(text, target_lang, result)
                    logger.info(f"✅ Translated to {target_lang}: {text[:50]}... → {result[:50]}...")
                    return True, result, False  # Return False for from_cache (just created cache)
            
            except requests.exceptions.Timeout:
                logger.warning(f"⏱️ Request timeout (attempt {attempt + 1}/{self.retry_attempts})")
                wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                if attempt < self.retry_attempts - 1:
                    time.sleep(wait_time)
            
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429:  # Rate limited
                    logger.warning(f"⚠️ Rate limited (attempt {attempt + 1}/{self.retry_attempts})")
                    wait_time = (2 ** attempt) * 10  # Longer wait: 10s, 20s, 40s
                    if attempt < self.retry_attempts - 1:
                        logger.info(f"⏳ Waiting {wait_time}s before retry...")
                        time.sleep(wait_time)
                else:
                    raise
            
            except Exception as e:
                logger.error(f"❌ Translation error (attempt {attempt + 1}): {e}")
                if attempt < self.retry_attempts - 1:
                    wait_time = 2 ** attempt
                    time.sleep(wait_time)
        
        # All retries failed, return original text
        logger.error(f"❌ Translation failed after {self.retry_attempts} attempts")
        return False, text, False
    
    def _translate_with_timeout(self, text: str, target_lang: str, timeout: int = 10) -> Optional[str]:
        """Make translation request with timeout"""
        params = {
            'client': 'gtx',
            'sl': 'auto',
            'tl': target_lang,
            'dt': 't',
            'q': text
        }
        
        response = self.session.get(
            self.API_URL,
            params=params,
            timeout=timeout
        )
        response.raise_for_status()
        
        data = response.json()
        return self._extract_translation(data)
    
    @staticmethod
    def _extract_translation(data) -> Optional[str]:
        """Extract translation from Google API response"""
        if not data or not isinstance(data, list) or len(data) < 1:
            return None
        
        if not data[0] or not isinstance(data[0], list):
            return None
        
        # Combine all translation segments
        result = []
        for item in data[0]:
            if isinstance(item, list) and len(item) > 0:
                if isinstance(item[0], str):
                    result.append(item[0])
        
        return ''.join(result) if result else None
    
    def clear_cache(self):
        """Clear translation cache"""
        self.cache.clear()
        logger.info("🗑️ Translation cache cleared")


# Global instance
_translation_service = None

def get_translation_service() -> GoogleTranslateService:
    """Get or create global translation service instance"""
    global _translation_service
    if _translation_service is None:
        _translation_service = GoogleTranslateService()
    return _translation_service
