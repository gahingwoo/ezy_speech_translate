"""
EzySpeechTranslate User Server
Real-time speech recognition and translation system with security hardening
"""

import os
import sys
import yaml
import logging
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
import jwt
from functools import wraps
import hashlib
import eventlet
import eventlet.wsgi
# ⚠️ CRITICAL: Disable select AND socket monkeypatch BEFORE importing asyncio
# to avoid conflicts with asyncio's event loop
# We need asyncio's native socket and select modules, not eventlet's patched versions
eventlet.monkey_patch(select=False, socket=False)
import secrets
import re
from collections import defaultdict
import time
import io
import subprocess
import threading

# ── Optional persistence layer (SQLite) ───────────────────────────────────────
try:
    try:
        from . import db as _db_mod
    except ImportError:
        import importlib as _importlib, os as _os2
        _spec2 = _importlib.util.spec_from_file_location(
            "db", _os2.path.join(_os2.path.dirname(__file__), "..", "db.py")
        )
        _db_mod = _importlib.util.module_from_spec(_spec2)
        _spec2.loader.exec_module(_db_mod)
    db = _db_mod
except Exception as _db_err:
    db = None
    logging.getLogger(__name__).warning("DB module unavailable: %s", _db_err)

# ──────────────────────────────────────────
# Path Setup (BEFORE any app imports)
# ──────────────────────────────────────────
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Add base directory to sys.path for module imports
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# OEM Configuration - with fallback for direct script execution
try:
    # Try relative import (works when imported as module)
    from .oem_manager import init_oem_config
except ImportError:
    # Fallback for direct script execution
    from app.oem_manager import init_oem_config

# Now import Flask and other app modules
from flask import Flask, render_template, request, jsonify, session, Response
from flask_socketio import SocketIO, emit, disconnect
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman
from werkzeug.middleware.proxy_fix import ProxyFix
CONFIG_DIR = os.path.join(BASE_DIR, "config")
SSL_DIR = os.path.join(CONFIG_DIR, "ssl")

TEMPLATE_DIR = os.path.join(APP_DIR, "templates")
STATIC_DIR = os.path.join(APP_DIR, "static")

os.chdir(BASE_DIR)

# ──────────────────────────────────────────
# Configuration (shared loader)
# ──────────────────────────────────────────
sys.path.insert(0, BASE_DIR)
from app.core.config import get_config, config_loader  # noqa: E402

# ──────────────────────────────────────────
# Logging Setup with Security Logging
# ──────────────────────────────────────────
log_file = get_config('logging', 'file', default='logs/app.log')
log_dir = os.path.dirname(log_file) or 'logs'
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=get_config('logging', 'level', default='INFO'),
    format=get_config('logging', 'format',
                      default='%(asctime)s - %(name)s - %(levelname)s - %(message)s'),
    handlers=[
        RotatingFileHandler(
            log_file,
            maxBytes=get_config('logging', 'max_bytes', default=10 * 1024 * 1024),
            backupCount=get_config('logging', 'backup_count', default=5)
        ),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Separate security logger - ensure directory exists first
security_log_dir = 'logs'
os.makedirs(security_log_dir, exist_ok=True)
security_logger = logging.getLogger('security')
security_handler = RotatingFileHandler(
    os.path.join(security_log_dir, 'security.log'),
    maxBytes=10*1024*1024,
    backupCount=5
)
security_handler.setFormatter(logging.Formatter(
    "%(asctime)s [SECURITY] %(message)s"
))
security_logger.addHandler(security_handler)
security_logger.setLevel(logging.WARNING)

# ──────────────────────────────────────────
# Flask Initialization with Security
# ──────────────────────────────────────────
app = Flask(__name__,
            template_folder=TEMPLATE_DIR,
            static_folder=STATIC_DIR,
            static_url_path='/static')

# Secure configuration
secret_key = get_config('server', 'secret_key')
if not secret_key or secret_key == 'changeme':
    secret_key = secrets.token_hex(32)
    logger.warning("Using generated secret key. Set a permanent key in config!")

app.config['SECRET_KEY'] = secret_key
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Strict'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=2)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max request

# CORS with restrictions from config
cors_origins = get_config('advanced', 'security', 'cors_origins')
if cors_origins is None or cors_origins == '*':
    allowed_origins = '*'
else:
    allowed_origins = [cors_origins] if isinstance(cors_origins, str) else cors_origins
CORS(app, origins=allowed_origins, supports_credentials=True)

# Initialize OEM Configuration
try:
    init_oem_config(app, get_config)
    logger.info("✓ OEM configuration initialized successfully")
except Exception as e:
    logger.warning(f"⚠ OEM configuration initialization failed: {e}")

# Trust Cloudflare Tunnel / reverse proxy headers
# CF Tunnel acts as a proxy, so we need to unwrap the forwarded IP
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)


def get_real_ip():
    """Get real client IP, respecting CF-Connecting-IP and X-Forwarded-For headers.
    CF Tunnel sets CF-Connecting-IP to the actual visitor's IP.
    """
    # Cloudflare always sets this header with the true client IP
    cf_ip = request.headers.get('CF-Connecting-IP')
    if cf_ip:
        return cf_ip.strip()
    # Generic reverse proxy forwarded header (set by ProxyFix above)
    forwarded_for = request.headers.get('X-Forwarded-For')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    return request.remote_addr


def get_rate_limit_key():
    """Get unique identifier for rate limiting - always uses browser-specific client ID.

    Each browser gets a persistent unique ID in a cookie (_client_id).
    Chrome and Firefox on same WiFi will have DIFFERENT IDs and won't block each other.
    This never falls back to IP.
    """
    # Always check cookies first - works for both HTTP and Socket.IO
    client_id = request.cookies.get('_client_id')
    if client_id:
        return f"client:{client_id}"

    # If no cookie yet, check if request.client_id was set by before_request
    if hasattr(request, 'client_id'):
        return f"client:{request.client_id}"

    # For Socket.IO or other cases without cookies, generate temporary ID
    # This will be written to cookie in after_request
    return f"client:{secrets.token_hex(16)}"

socketio = SocketIO(
    app,
    cors_allowed_origins=allowed_origins,
    async_mode='eventlet',
    ping_timeout=get_config('advanced', 'websocket', 'ping_timeout', default=20),
    ping_interval=get_config('advanced', 'websocket', 'ping_interval', default=10),
    max_http_buffer_size=get_config('advanced', 'websocket', 'max_message_size', default=1048576)
)

# ──────────────────────────────────────────
# Bible reference detection (optional, opt-in)
# ──────────────────────────────────────────
BIBLE_DETECTION_ENABLED = bool(get_config('features', 'bible_detection', 'enabled', default=False))
BIBLE_SOURCE_TRANSLATION = get_config('features', 'bible_detection', 'source_translation', default='WEB')
BIBLE_TARGET_TRANSLATION = get_config('features', 'bible_detection', 'target_translation', default='')
BIBLE_MAX_VERSES = int(get_config('features', 'bible_detection', 'max_verses', default=10))
BIBLE_API_TIMEOUT = int(get_config('features', 'bible_detection', 'api_timeout', default=8))
bible_detector = None
if BIBLE_DETECTION_ENABLED:
    try:
        try:
            from . import bible_detector as _bible_mod   # module mode: python -m app.user.server
        except ImportError:
            import importlib, os as _os
            _spec = importlib.util.spec_from_file_location(
                "bible_detector",
                _os.path.join(_os.path.dirname(__file__), "bible_detector.py"),
            )
            _bible_mod = importlib.util.module_from_spec(_spec)
            _spec.loader.exec_module(_bible_mod)
        _bible_mod.init(
            source_translation=BIBLE_SOURCE_TRANSLATION,
            target_translation=BIBLE_TARGET_TRANSLATION,
            max_verses=BIBLE_MAX_VERSES,
            api_timeout=BIBLE_API_TIMEOUT,
        )
        bible_detector = _bible_mod
        logging.getLogger("bible").info(
            f"📖 Bible detection enabled (source={BIBLE_SOURCE_TRANSLATION}"
            + (f", target={BIBLE_TARGET_TRANSLATION}" if BIBLE_TARGET_TRANSLATION else "")
            + ")"
        )
    except Exception as e:
        logging.getLogger("bible").error(f"Failed to init bible_detector: {e}")
        bible_detector = None

# ──────────────────────────────────────────
# Protocol Configuration (HTTP/HTTPS)
# ──────────────────────────────────────────
USE_HTTPS = get_config('server', 'use_https', default=True)

# Security Headers - only apply for HTTPS
if USE_HTTPS:
    csp = {
        'default-src': ["'self'"],
        'script-src': ["'self'", "'unsafe-inline'", "https://cdnjs.cloudflare.com"],
        'style-src': ["'self'", "'unsafe-inline'", "https://fonts.googleapis.com"],
        'font-src': ["'self'", "https://fonts.gstatic.com"],
        'img-src': ["'self'", "data:", "https:"],
        'connect-src': ["'self'", "wss:", "https:", "https://translate.googleapis.com"]
    }

    Talisman(
        app,
        force_https=True,
        strict_transport_security=True,
        strict_transport_security_max_age=31536000,
        content_security_policy=csp,
        feature_policy={
            'geolocation': "'none'",
            'camera': "'none'",
            'microphone': "'none'"
        }
    )
else:
    # For HTTP mode, allow HTTPS resources (CDN scripts) and ws connections
    csp = {
        'default-src': ["'self'"],
        'script-src': ["'self'", "'unsafe-inline'", "https://cdnjs.cloudflare.com", "https:"],
        'style-src': ["'self'", "'unsafe-inline'", "https://fonts.googleapis.com"],
        'font-src': ["'self'", "https://fonts.gstatic.com"],
        'img-src': ["'self'", "data:", "https:"],
        'connect-src': ["'self'", "ws:", "wss:", "https:", "https://translate.googleapis.com"],
        'media-src': ["'self'", "blob:"]  # Allow blob URLs for audio playback
    }

    Talisman(
        app,
        force_https=False,
        strict_transport_security=False,
        content_security_policy=csp,
        feature_policy={
            'geolocation': "'none'",
            'camera': "'none'",
            'microphone': "'none'"
        }
    )

# Rate Limiting - check if enabled in config
rate_limit_enabled = get_config('advanced', 'security', 'rate_limit_enabled', default=True)
max_requests = get_config('advanced', 'security', 'max_requests_per_minute', default=60)

# Max simultaneous WebSocket connections allowed per IP
max_ws_connections = get_config('advanced', 'security', 'max_ws_connections', default=20)

if rate_limit_enabled:
    limiter = Limiter(
        app=app,
        key_func=get_rate_limit_key,
        default_limits=[f"{max_requests} per minute", "1000 per day"],
        storage_uri="memory://"
    )
else:
    # Create a no-op limiter when disabled
    class NoOpLimiter:
        def limit(self, *args, **kwargs):
            def decorator(f):
                return f
            return decorator
    limiter = NoOpLimiter()

# ──────────────────────────────────────────
# Security: Attack Prevention
# ──────────────────────────────────────────
blocked_clients = set()  # Store blocked session keys, not IPs
failed_login_attempts = defaultdict(list)  # Session key: [timestamps]
rate_limit_violations = defaultdict(int)  # Session key: count
suspicious_patterns = defaultdict(int)  # Session key: count
blocked_since = {}  # Session key: timestamp when blocked

MAX_LOGIN_ATTEMPTS = get_config('advanced', 'security', 'max_login_attempts', default=10)
login_window_min = get_config('advanced', 'security', 'login_attempt_window_minutes', default=15)
LOGIN_ATTEMPT_WINDOW = timedelta(minutes=login_window_min)
MAX_RATE_VIOLATIONS = get_config('advanced', 'security', 'max_rate_violations', default=100)  # Increased from 10
MAX_SUSPICIOUS_PATTERNS = get_config('advanced', 'security', 'max_suspicious_patterns', default=20)  # NEW: Increased from hardcoded 5
block_minutes = get_config('advanced', 'security', 'block_duration_minutes', default=60)
BLOCK_DURATION = timedelta(minutes=block_minutes)

def get_client_key():
    """Get unique client identifier for blocking (session-based, not IP-based).
    This prevents users on the same WiFi from blocking each other.
    """
    return get_rate_limit_key()

def is_client_blocked(client_key=None):
    """Check if client/session is blocked"""
    if client_key is None:
        client_key = get_client_key()

    if client_key not in blocked_clients:
        return False

    # Check if block has expired
    if client_key in blocked_since:
        if datetime.now() - blocked_since[client_key] > BLOCK_DURATION:
            blocked_clients.discard(client_key)
            blocked_since.pop(client_key, None)
            return False

    return True

def record_failed_login(client_key=None):
    """Record failed login attempt for a client/session"""
    if client_key is None:
        client_key = get_client_key()

    now = datetime.now()
    attempts = failed_login_attempts[client_key]

    # Clean old attempts
    attempts[:] = [t for t in attempts if now - t < LOGIN_ATTEMPT_WINDOW]
    attempts.append(now)

    if len(attempts) >= MAX_LOGIN_ATTEMPTS:
        blocked_clients.add(client_key)
        blocked_since[client_key] = now
        security_logger.critical(f"CLIENT BLOCKED due to failed login attempts: {client_key}")
        return True

    return False

def record_rate_violation(client_key=None):
    """Record rate limit violation for a client/session"""
    if client_key is None:
        client_key = get_client_key()

    rate_limit_violations[client_key] += 1

    if rate_limit_violations[client_key] >= MAX_RATE_VIOLATIONS:
        blocked_clients.add(client_key)
        blocked_since[client_key] = datetime.now()
        security_logger.critical(f"CLIENT BLOCKED due to rate limit violations: {client_key}")
        return True

    return False

def record_suspicious_activity(reason, client_key=None):
    """Record suspicious activity for a client/session"""
    if client_key is None:
        client_key = get_client_key()

    suspicious_patterns[client_key] += 1
    security_logger.warning(f"Suspicious activity from {client_key}: {reason}")

    if suspicious_patterns[client_key] >= MAX_SUSPICIOUS_PATTERNS:
        blocked_clients.add(client_key)
        blocked_since[client_key] = datetime.now()
        security_logger.critical(f"CLIENT BLOCKED due to suspicious patterns: {client_key}")
        return True

    return False

def check_client_access(f):
    """Decorator to check client/session access (not IP-based)"""
    @wraps(f)
    def decorated(*args, **kwargs):
        client_key = get_client_key()
        if is_client_blocked(client_key):
            security_logger.warning(f"Blocked client attempted access: {client_key}")
            return jsonify({'error': 'Access denied - too many failed attempts'}), 403
        return f(*args, **kwargs)
    return decorated

# ──────────────────────────────────────────
# Security: Input Validation (delegated to app.auth)
# ──────────────────────────────────────────
from app.auth import sanitize_text as _sanitize_text_core, decode_jwt as _decode_jwt  # noqa: E402


def sanitize_text(text, max_length=5000):
    """Sanitize text input (delegates to app.auth.sanitize)."""
    return _sanitize_text_core(text, max_length=max_length, ip_provider=get_real_ip)


def validate_jwt_token(token):
    """Validate JWT token (delegates to app.auth.jwt_utils)."""
    return _decode_jwt(token, get_config('authentication', 'jwt_secret', default='secret'))

# ──────────────────────────────────────────
# In-memory Storage with Limits from Config
# ──────────────────────────────────────────
MAX_HISTORY_SIZE = get_config('advanced', 'performance', 'cache_size', default=1000)

# ── Multi-room support ───────────────────────────────────────────────────────
# Each room has independent history, listener tracking, and ID counter.
# Backward compat: legacy single-room deployments use the default room "main".
DEFAULT_ROOM_ID = "main"
_VALID_ROOM_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_\-]{0,63}$')

# room_id -> {history: list, listeners: dict[client_key]=sid, next_id: int, display_name: str}
_rooms: dict = {}
# Guards lazy creation of room state to avoid two concurrent handlers
# clobbering each other's freshly-created entry. Dict mutations themselves
# are atomic in CPython, but the get-then-set sequence is not.
_rooms_lock = threading.Lock()

def normalize_room_id(rid) -> str:
    """Validate and normalize a room_id. Falls back to DEFAULT_ROOM_ID."""
    if not rid or not isinstance(rid, str):
        return DEFAULT_ROOM_ID
    rid = rid.strip()
    if not _VALID_ROOM_RE.match(rid):
        return DEFAULT_ROOM_ID
    return rid

def _room(rid: str) -> dict:
    """Get or lazily create the state dict for a room."""
    rid = normalize_room_id(rid)
    state = _rooms.get(rid)
    if state is None:
        with _rooms_lock:
            state = _rooms.get(rid)  # Re-check under lock
            if state is None:
                state = {
                    'history': [],
                    'listeners': {},   # client_key -> sid
                    'next_id': 0,
                    'display_name': rid.replace('_', ' ').title() if rid != DEFAULT_ROOM_ID else 'Main',
                    'recording': None,   # None or {'username': str, 'sid': str, 'started_at': iso}
                }
                _rooms[rid] = state
    return state

def _all_listener_count() -> int:
    """Total user listeners across all rooms."""
    return sum(len(s['listeners']) for s in _rooms.values())

def _all_history_count() -> int:
    return sum(len(s['history']) for s in _rooms.values())

# Ensure default room exists immediately
_room(DEFAULT_ROOM_ID)

# Legacy aliases — kept for compatibility with endpoints/code paths that
# implicitly mean "the default room". New code should use _room(rid).
translations_history = _room(DEFAULT_ROOM_ID)['history']
next_translation_id = 0  # legacy; per-room counters are authoritative
listener_clients = _room(DEFAULT_ROOM_ID)['listeners']

connected_clients = set()          # all socket SIDs
admin_sessions = {}                 # sid -> {'username': str, 'room_id': str}
api_session_tokens = {}             # Maps token -> {sid, created_at, expires_at}
# sid -> (client_key, client_type, room_id) for cleanup on disconnect
sid_to_client_key = {}
_sid_last_seen: dict = {}           # sid -> datetime of last heartbeat (user clients only)

# ──────────────────────────────────────────
# Session Analytics (Feature 9)
# ──────────────────────────────────────────
_session_start_time = datetime.now()
_peak_clients       = 0             # peak concurrent user-type listeners
_total_words        = 0             # running word count across all final transcriptions
_total_bible_refs   = 0             # running count of bible references detected
_total_tts_plays    = 0             # incremented by /api/tts/synthesize
_total_translations = 0             # incremented by /api/translate

ANALYTICS_ENABLED = get_config('features', 'session_analytics', 'enabled', default=True)

# ──────────────────────────────────────────
# Multi-account auth (Feature 6)
# Build a dict  username -> {password_hash, role, channel, display_name}
# Falls back to single admin_username / admin_password if no accounts list.
# ──────────────────────────────────────────
_accounts: dict = {}

from app.auth import hash_password as _hash_password  # noqa: E402


def _build_accounts():
    raw_accounts = get_config('authentication', 'accounts', default=None)
    if raw_accounts and isinstance(raw_accounts, list):
        for acct in raw_accounts:
            uname = acct.get('username', '')
            raw_pwd = acct.get('password') or get_config(
                'authentication', 'admin_password', default='admin123'
            )
            if uname:
                _accounts[uname] = {
                    'password_hash': _hash_password(raw_pwd),
                    'role':         acct.get('role', 'operator'),
                    'channel':      acct.get('channel', 'main'),
                    'display_name': acct.get('display_name', uname),
                }
    # Always ensure the legacy admin account is present
    if not _accounts:
        uname = get_config('authentication', 'admin_username', default='admin')
        pwd   = get_config('authentication', 'admin_password', default='admin123')
        _accounts[uname] = {
            'password_hash': _hash_password(pwd),
            'role':         'admin',
            'channel':      'main',
            'display_name': uname,
        }

_build_accounts()


# ── Admin-session helpers ─────────────────────────────────────────────────────

def _admin_username(sid: str) -> str:
    """Extract username from admin_sessions entry (handles both dict and legacy str forms)."""
    info = admin_sessions.get(sid)
    if isinstance(info, dict):
        return info.get('username', 'admin')
    return info or 'admin'


def _admin_room(sid: str) -> str:
    """Get the room_id an admin SID is currently broadcasting to."""
    info = admin_sessions.get(sid)
    if isinstance(info, dict):
        return normalize_room_id(info.get('room_id'))
    return DEFAULT_ROOM_ID


def _sid_room(sid: str) -> str:
    """Get the room a user/admin SID is currently in. Falls back to default."""
    mapping = sid_to_client_key.get(sid)
    if mapping and len(mapping) >= 3:
        return normalize_room_id(mapping[2])
    return _admin_room(sid) if sid in admin_sessions else DEFAULT_ROOM_ID


def add_translation(data, room_id: str = DEFAULT_ROOM_ID):
    """Add translation to the given room with size limit, DB persistence, and session stats."""
    global _total_words, _total_bible_refs
    room_id = normalize_room_id(room_id)
    state = _room(room_id)

    # Assign stable ID (independent of history size) — per-room counter
    if 'id' not in data or data['id'] is None:
        data['id'] = state['next_id']
        state['next_id'] += 1
    else:
        # Keep counter ahead of any imported IDs to avoid collisions
        try:
            state['next_id'] = max(state['next_id'], int(data['id']) + 1)
        except (TypeError, ValueError):
            pass

    # Tag the record with its room so DB / clients can filter
    data['room_id'] = room_id

    # Bible reference detection — opt-in via config.
    if bible_detector is not None and 'bible_refs' not in data:
        try:
            scan_text = data.get('corrected') or data.get('original') or ''
            results = bible_detector.detect_and_lookup(scan_text)
            if results:
                data['bible_refs'] = results
        except Exception as e:
            logger.warning(f"Bible detection failed: {e}")

    state['history'].append(data)

    # ── Session analytics ──────────────────────────────────────────
    if ANALYTICS_ENABLED:
        text_for_stats = data.get('corrected') or data.get('original') or ''
        _total_words    += len(text_for_stats.split())
        _total_bible_refs += len(data.get('bible_refs') or [])

    # ── SQLite persistence ─────────────────────────────────────────
    if db is not None:
        db.persist(data)

    # Limit history size (per room)
    if len(state['history']) > MAX_HISTORY_SIZE:
        state['history'][:] = state['history'][-MAX_HISTORY_SIZE:]
        logger.info(
            f"History trimmed to {MAX_HISTORY_SIZE} items for room '{room_id}'. "
            f"Total IDs generated: {state['next_id']}"
        )


def _get_glossary_for(room_id: str, target_lang: str) -> list:
    """Fetch glossary entries that apply to (room_id, target_lang).

    Returns a list of dicts in the form expected by translation_service:
        [{source_term, translation, case_sensitive}, ...]
    Includes both global (room_id IS NULL) and room-specific entries.
    Room-specific entries override global ones for the same source_term.
    """
    if db is None:
        return []
    try:
        rows = db.glossary_list(room_id=room_id, include_global=True)
    except Exception as exc:
        logger.warning(f"glossary_list failed: {exc}")
        return []
    # Filter by language + enabled, and de-dupe (room-specific wins)
    seen = {}
    target_lang_norm = (target_lang or '').lower()
    # Sort so global entries come first; room-specific overwrite them
    rows.sort(key=lambda r: 0 if r.get('room_id') is None else 1)
    for r in rows:
        if not r.get('enabled', True):
            continue
        entry_lang = (r.get('target_lang') or '').lower()
        if entry_lang != '*' and entry_lang != target_lang_norm:
            continue
        key = r['source_term'] if r.get('case_sensitive') else r['source_term'].lower()
        seen[key] = {
            'source_term':    r['source_term'],
            'translation':    r['translation'],
            'case_sensitive': bool(r.get('case_sensitive', False)),
        }
    return list(seen.values())


# ──────────────────────────────────────────
# Middleware
# ──────────────────────────────────────────
@app.before_request
def before_request():
    """Security checks before each request - auto-assign client ID if needed"""
    # Ensure every request has a unique client ID
    client_id = request.cookies.get('_client_id')
    if not client_id:
        client_id = f"browser_{secrets.token_hex(16)}"
    request.client_id = client_id

    client_key = f"client:{client_id}"

    # Check client/session blocking
    if is_client_blocked(client_key):
        return jsonify({'error': 'Access denied - too many failed attempts'}), 403

    # Check request size
    if request.content_length and request.content_length > app.config['MAX_CONTENT_LENGTH']:
        security_logger.warning(f"Large request from {client_key}: {request.content_length}")
        return jsonify({'error': 'Request too large'}), 413

    # Check for path traversal
    if '../' in request.path or '..\\' in request.path:
        record_suspicious_activity("Path traversal attempt", client_key)
        return jsonify({'error': 'Invalid request'}), 400

    # Check for SQL injection patterns
    sql_patterns = ['union select', 'drop table', 'insert into', '--', ';--']
    query_string = request.query_string.decode('utf-8', 'ignore').lower()
    if any(pattern in query_string for pattern in sql_patterns):
        record_suspicious_activity("SQL injection attempt", client_key)
        return jsonify({'error': 'Invalid request'}), 400

@app.after_request
def after_request(response):
    """Add security headers and set client ID cookie"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
    
    # ✅ Content Security Policy - dynamically include external URL if configured
    external_url = get_config('server', 'external_url', default='')
    
    # Build connect-src with local and external URLs
    connect_src_list = ["'self'", "http://localhost:*", "http://127.0.0.1:*", 
                       "ws://localhost:*", "ws://127.0.0.1:*",
                       "https://cdnjs.cloudflare.com", "https://translate.googleapis.com", 
                       "https://fonts.googleapis.com", "https://fonts.gstatic.com"]
    
    # Add external URL if configured (for CF Tunnel or reverse proxy)
    if external_url:
        # Add both https:// and wss:// versions
        if external_url.startswith('https://'):
            external_host = external_url.replace('https://', '').rstrip('/')
            connect_src_list.append(f"https://{external_host}")
            connect_src_list.append(f"wss://{external_host}")
        elif external_url.startswith('http://'):
            external_host = external_url.replace('http://', '').rstrip('/')
            connect_src_list.append(f"http://{external_host}")
            connect_src_list.append(f"ws://{external_host}")
    
    connect_src = ' '.join(connect_src_list)
    
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
        "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://fonts.googleapis.com; "
        "media-src 'self' blob:; "
        f"connect-src {connect_src}; "
        "img-src 'self' data:; "
        "font-src 'self' data: https://cdnjs.cloudflare.com https://fonts.gstatic.com"
    )

    # Set persistent client ID cookie if we generated a new one
    if hasattr(request, 'client_id') and not request.cookies.get('_client_id'):
        response.set_cookie(
            '_client_id',
            request.client_id,
            max_age=365*24*60*60,  # 1 year
            secure=USE_HTTPS,
            httponly=True,
            samesite='Strict'
        )

    return response

# ──────────────────────────────────────────
# Authentication with Security
# ──────────────────────────────────────────

def generate_api_session_token():
    """Generate a temporary API session token"""
    return secrets.token_urlsafe(32)

def create_api_token(sid):
    """Create a new API token for this WebSocket session"""
    token = generate_api_session_token()
    api_session_tokens[token] = {
        'sid': sid,
        'created_at': datetime.now(),
        'expires_at': datetime.now() + timedelta(hours=24)  # Valid for 24 hours
    }
    return token

def validate_api_token(token):
    """Validate and return session info if token is valid"""
    if token not in api_session_tokens:
        return None
    
    session_info = api_session_tokens[token]
    
    # Check if expired
    if datetime.now() > session_info['expires_at']:
        del api_session_tokens[token]
        return None
    
    return session_info

def require_api_token(f):
    """Decorator to validate API session token"""
    @wraps(f)
    def decorated(*args, **kwargs):
        # Try multiple locations for token
        token = None
        
        # 1. Authorization header (Bearer token)
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]
        
        # 2. X-API-Session-Token header
        if not token:
            token = request.headers.get('X-API-Session-Token', '')
        
        # 3. Query parameter (fallback)
        if not token:
            token = request.args.get('api_token', '')
        
        if not token:
            return jsonify({'error': 'No API token provided'}), 401
        
        session_info = validate_api_token(token)
        if not session_info:
            return jsonify({'error': 'Invalid or expired API token'}), 401
        
        request.session_info = session_info
        request.api_session = session_info  # Keep both for compatibility
        return f(*args, **kwargs)
    
    return decorated

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not get_config('authentication', 'enabled', default=True):
            return f(*args, **kwargs)

        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if not token:
            token = request.args.get('token', '')

        if not token:
            return jsonify({'error': 'No token provided'}), 401

        decoded = validate_jwt_token(token)
        if not decoded:
            return jsonify({'error': 'Invalid or expired token'}), 401

        request.user = decoded
        return f(*args, **kwargs)

    return decorated

def require_admin_auth(f):
    """Decorator to require admin authentication (JWT token)"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not get_config('authentication', 'enabled', default=True):
            return f(*args, **kwargs)

        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if not token:
            return jsonify({'success': False, 'error': 'No token provided'}), 401

        decoded = validate_jwt_token(token)
        if not decoded:
            security_logger.warning(f"Invalid token attempt for admin endpoint from {get_real_ip()}")
            return jsonify({'success': False, 'error': 'Invalid or expired token'}), 401

        # Accept users whose account role is 'admin'
        acct = _accounts.get(decoded.get('username', ''))
        if not acct or acct.get('role') != 'admin':
            security_logger.warning(f"Non-admin user '{decoded.get('username')}' attempted to access admin endpoint from {get_real_ip()}")
            return jsonify({'success': False, 'error': 'Admin access required'}), 403

        request.user = decoded
        return f(*args, **kwargs)

    return decorated

def is_admin(sid):
    """Check if session is authenticated admin"""
    if not get_config('authentication', 'enabled', default=True):
        return True
    return sid in admin_sessions

# ──────────────────────────────────────────
# Cache Control Middleware (prevent browser caching of JS/CSS)
# ──────────────────────────────────────────
@app.after_request
def set_cache_headers(response):
    """Set proper cache headers for static and dynamic content"""
    # ✅ Ensure CSP is always present with external URL support
    if 'Content-Security-Policy' not in response.headers:
        external_url = get_config('server', 'external_url', default='')
        
        # Build connect-src with local and external URLs
        connect_src_list = ["'self'", "http://localhost:*", "http://127.0.0.1:*", 
                           "ws://localhost:*", "ws://127.0.0.1:*",
                           "https://cdnjs.cloudflare.com", "https://translate.googleapis.com", 
                           "https://fonts.googleapis.com", "https://fonts.gstatic.com"]
        
        # Add external URL if configured (for CF Tunnel or reverse proxy)
        if external_url:
            # Add both https:// and wss:// versions
            if external_url.startswith('https://'):
                external_host = external_url.replace('https://', '').rstrip('/')
                connect_src_list.append(f"https://{external_host}")
                connect_src_list.append(f"wss://{external_host}")
            elif external_url.startswith('http://'):
                external_host = external_url.replace('http://', '').rstrip('/')
                connect_src_list.append(f"http://{external_host}")
                connect_src_list.append(f"ws://{external_host}")
        
        connect_src = ' '.join(connect_src_list)
        
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
            "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://fonts.googleapis.com; "
            "media-src 'self' blob:; "
            f"connect-src {connect_src}; "
            "img-src 'self' data:; "
            "font-src 'self' data: https://cdnjs.cloudflare.com https://fonts.gstatic.com"
        )
    
    # Disable caching for HTML pages (always fetch fresh version)
    if response.content_type and 'text/html' in response.content_type:
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, public, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    
    # Disable caching for API responses
    elif request.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, public, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    
    # For static files (JS, CSS, images) - use versioning strategy
    elif request.path.startswith('/static/'):
        # If URL has version/hash parameter (?v=...), cache forever (immutable)
        if request.args.get('v'):
            response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'  # 1 year
        else:
            # Without version, don't cache - forces browser to check for updates
            # This handles unversioned requests during development/debugging
            response.headers['Cache-Control'] = 'public, max-age=0, must-revalidate'
        
        # Add ETag for cache validation
        if not response.headers.get('ETag'):
            response.set_etag()
    
    return response

# ──────────────────────────────────────────
# Jinja2 Helpers - Static File Versioning
# ──────────────────────────────────────────
def get_static_file_version(filename):
    """
    Get file modification time as version string for cache busting
    Usage in templates: {{ url_for('static', filename='css/user.css') }}?v={{ 'css/user.css' | static_version }}
    """
    try:
        filepath = os.path.join(STATIC_DIR, filename)
        if os.path.exists(filepath):
            mtime = os.path.getmtime(filepath)
            return str(int(mtime))
        else:
            logger.warning(f"Static file not found for versioning: {filename}")
            return "1"
    except Exception as e:
        logger.error(f"Error getting static file version for {filename}: {e}")
        return "1"

# Register Jinja2 filter for static file versioning
app.jinja_env.filters['static_version'] = get_static_file_version

# ──────────────────────────────────────────
# Routes with Protection
# ──────────────────────────────────────────
@app.route('/')
@limiter.limit("60 per minute")
@check_client_access
def index():
    """Main client interface"""
    return render_template(
        'user.html',
        bible_detection_enabled=bool(BIBLE_DETECTION_ENABLED and bible_detector is not None),
    )

@app.route('/captions')
@limiter.limit("60 per minute")
@check_client_access
def captions():
    """OBS / streaming overlay — transparent caption renderer.

    Configurable via URL query params (see captions.html header for full list).
    Examples:
        /captions?mode=translated&size=64&pos=bottom
        /captions?mode=both&color=ffff00&strokew=6
    """
    return render_template('captions.html')

@app.route('/admin')
def admin_route():
    """Admin interface route"""
    return jsonify({'message': 'Use admin_server.py for admin interface'}), 404

@app.route('/api/login', methods=['POST'])
@limiter.limit("5 per minute")
@check_client_access
def login():
    """Admin login with brute force protection"""
    client_key = get_client_key()

    try:
        data = request.json or {}
    except Exception:
        security_logger.warning(f"Malformed JSON from {client_key}")
        return jsonify({'success': False, 'error': 'Invalid request'}), 400

    username = sanitize_text(data.get('username', ''), max_length=100)
    # Accept client-side pre-hashed password (SHA-256 hex) only
    password_hash = data.get('password_hash', '')

    if not username or not password_hash or len(password_hash) != 64:
        return jsonify({'success': False, 'error': 'Missing credentials'}), 400

    # Rate limiting check
    if len(username) > 100:
        record_suspicious_activity("Oversized credentials", client_key)
        return jsonify({'success': False, 'error': 'Invalid credentials'}), 400

    # Verify credentials against multi-account table
    # account['password_hash'] is sha256(config_password); client sends sha256(entered_password)
    account = _accounts.get(username)

    if account and account['password_hash'] == password_hash:
        acct_role    = account.get('role', 'operator')
        acct_channel = account.get('channel', 'main')
        acct_display = account.get('display_name', username)

        # Generate secure token
        token = jwt.encode(
            {
                'username': username,
                'role':     acct_role,
                'channel':  acct_channel,
                'display_name': acct_display,
                'exp': datetime.utcnow() + timedelta(
                    seconds=get_config('authentication', 'session_timeout', default=7200)
                ),
                'iat': datetime.utcnow(),
                'jti': secrets.token_hex(16)
            },
            get_config('authentication', 'jwt_secret', default='secret'),
            algorithm='HS256'
        )

        logger.info(f"✓ Login successful: {username} ({acct_role}/{acct_channel}) from {client_key}")
        return jsonify({
            'success':      True,
            'token':        token,
            'username':     username,
            'role':         acct_role,
            'channel':      acct_channel,
            'display_name': acct_display,
        })

    # Failed login
    logger.warning(f"✗ Failed login attempt: {username} from {client_key}")
    if record_failed_login(client_key):
        return jsonify({'success': False, 'error': 'Too many failed attempts. Session blocked.'}), 403

    return jsonify({'success': False, 'error': 'Invalid credentials'}), 401

@app.route('/api/config', methods=['GET'])
@limiter.limit("30 per minute")
@require_auth
@check_client_access
def get_runtime_config():
    """Get current configuration (filtered)"""
    # Only return non-sensitive config
    return jsonify({
        'audio': {
            'sample_rate': get_config('audio', 'sample_rate'),
            'channels': get_config('audio', 'channels')
        },
        'mainServerPort': get_config('server', 'port', default=1915)
    })

@app.route('/api/oem-config', methods=['GET'])
@limiter.limit("60 per minute")
@check_client_access
def get_oem_config():
    """Get OEM configuration for frontend"""
    return jsonify(app.config.get('OEM', {}))

@app.route('/api/features', methods=['GET'])
@limiter.limit("60 per minute")
def get_features():
    """Expose feature flags the client cares about.

    Used by user.js to decide whether to render optional UI like the
    Bible verse panel toggle. Public endpoint — only returns booleans
    plus inert config (translation id), no secrets.
    """
    return jsonify({
        'bible_detection': {
            'enabled': bool(BIBLE_DETECTION_ENABLED and bible_detector is not None),
            'source_translation': BIBLE_SOURCE_TRANSLATION,
            'target_translation': BIBLE_TARGET_TRANSLATION,
        },
    })

_VALID_TRANS_RE = re.compile(r'^[A-Za-z0-9_-]{1,20}$')

@app.route('/api/bible/lookup', methods=['POST'])
@limiter.limit("120 per minute")
def bible_lookup():
    """Fetch verse text from PrayerPulse API for a list of refs.

    Body (JSON):
      {
        "refs": [{book, chapter, verse_start, verse_end, display}, ...],
        "source_translation": "WEB",   // bolls.life translation code
        "target_translation": "CUV"    // optional; "" to disable
      }

    Returns the same list with source/target verse text attached.
    Results are cached server-side so repeated requests are cheap.
    """
    if bible_detector is None:
        return jsonify({'error': 'Bible detection not enabled'}), 404

    payload = request.get_json(silent=True) or {}
    refs = payload.get('refs')
    if not refs or not isinstance(refs, list) or len(refs) > 20:
        return jsonify({'error': 'refs must be a list of 1-20 items'}), 400

    src = str(payload.get('source_translation') or BIBLE_SOURCE_TRANSLATION)[:20]
    tgt = str(payload.get('target_translation', BIBLE_TARGET_TRANSLATION) or '')[:20]

    # Validate translation codes (alphanumeric + dash/underscore)
    if not _VALID_TRANS_RE.match(src):
        return jsonify({'error': 'invalid source_translation'}), 400
    if tgt and not _VALID_TRANS_RE.match(tgt):
        return jsonify({'error': 'invalid target_translation'}), 400

    # Allow only the expected keys in each ref to prevent injection
    clean_refs = []
    for r in refs:
        if not isinstance(r, dict):
            continue
        book = r.get('book', '')
        chapter = r.get('chapter')
        if not isinstance(book, str) or not isinstance(chapter, int):
            continue
        clean_refs.append({
            'book': book[:50],
            'chapter': int(chapter),
            'verse_start': int(r['verse_start']) if isinstance(r.get('verse_start'), int) else None,
            'verse_end':   int(r['verse_end'])   if isinstance(r.get('verse_end'), int)   else None,
            'display': str(r.get('display', ''))[:80],
        })

    if not clean_refs:
        return jsonify([])

    try:
        results = bible_detector.lookup(clean_refs, source_translation=src, target_translation=tgt)
        return jsonify(results)
    except Exception as e:
        logger.warning(f"bible_lookup endpoint failed: {e}")
        return jsonify({'error': 'lookup failed'}), 500


# ── In-process cache for the language list (large, rarely changes) ──
_bible_languages_cache: list = []
_bible_languages_cached_at: float = 0.0
_BIBLE_LANGUAGES_TTL = 3600  # re-fetch once per hour

@app.route('/api/bible/languages', methods=['GET'])
@limiter.limit("20 per minute")
def bible_languages():
    """Return available Bible translations grouped by language from PrayerPulse API.

    Proxied and cached server-side (1-hour TTL) so the browser never has
    to hit an external host directly.  Shape:
      [{"language": "English", "translations": [{"short_name": "KJV", "full_name": "..."}, ...]}, ...]
    """
    import time as _time
    global _bible_languages_cache, _bible_languages_cached_at
    if bible_detector is None:
        return jsonify([]), 404
    now = _time.time()
    if not _bible_languages_cache or (now - _bible_languages_cached_at) > _BIBLE_LANGUAGES_TTL:
        data = bible_detector.fetch_languages()
        if data:
            _bible_languages_cache = data
            _bible_languages_cached_at = now
    return jsonify(_bible_languages_cache)


@app.route('/api/bible/source-translation', methods=['GET', 'POST'])
@limiter.limit("30 per minute")
def bible_source_translation_endpoint():
    """GET: return the admin-configured source translation.
    POST (admin auth required): update the source translation live.

    POST body: {"source_translation": "KJV"}
    """
    global BIBLE_SOURCE_TRANSLATION
    if request.method == 'GET':
        return jsonify({'source_translation': BIBLE_SOURCE_TRANSLATION})

    # POST — require admin token
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({'error': 'Unauthorized'}), 401
    token = auth_header.split(' ', 1)[1]
    try:
        import jwt as _jwt
        decoded = _jwt.decode(token, get_config('authentication', 'jwt_secret', default=''), algorithms=['HS256'])
        admin_username = get_config('authentication', 'admin_username', default='admin')
        if decoded.get('username') != admin_username:
            return jsonify({'error': 'Admin access required'}), 403
    except Exception:
        return jsonify({'error': 'Invalid token'}), 401

    payload = request.get_json(silent=True) or {}
    new_src = str(payload.get('source_translation') or '')[:20].strip()
    if not new_src or not _VALID_TRANS_RE.match(new_src):
        return jsonify({'error': 'invalid source_translation'}), 400

    BIBLE_SOURCE_TRANSLATION = new_src
    if bible_detector is not None:
        bible_detector.init(
            source_translation=BIBLE_SOURCE_TRANSLATION,
            target_translation=BIBLE_TARGET_TRANSLATION,
        )
    logger.info("📖 Admin updated source translation to: %s", BIBLE_SOURCE_TRANSLATION)
    return jsonify({'source_translation': BIBLE_SOURCE_TRANSLATION, 'updated': True})


@app.route('/api/translations', methods=['GET'])
@limiter.limit("120 per minute")
@require_api_token
def get_translations():
    """
    Get translation history with pagination support
    
    Query parameters:
        offset (int): Starting index (default 0)
        limit (int): Number of items to return (default 100, max 1000)
    
    Response:
        {
            'translations': [...],
            'offset': 0,
            'limit': 100,
            'total': 1234,
            'has_more': true
        }
    """
    try:
        offset = int(request.args.get('offset', 0))
        limit = int(request.args.get('limit', 100))
    except (ValueError, TypeError):
        offset = 0
        limit = 100

    room_id = normalize_room_id(request.args.get('room'))
    history = _room(room_id)['history']

    # Validate parameters
    offset = max(0, min(offset, len(history)))
    limit = max(1, min(limit, 1000))  # Max 1000 items per request

    total = len(history)

    # Get slice of translations (newest first)
    start = max(0, total - offset - limit)
    end = max(0, total - offset)
    translations_slice = history[start:end]
    translations_slice = list(reversed(translations_slice))

    has_more = (offset + limit) < total

    return jsonify({
        'translations': translations_slice,
        'room_id': room_id,
        'offset': offset,
        'limit': limit,
        'total': total,
        'has_more': has_more
    })

@app.route('/api/translations/<int:translation_id>/translated', methods=['PATCH'])
@limiter.limit("300 per minute")
@require_api_token
def save_translated(translation_id):
    """
    Cache a client-side translation result back to the server so future clients
    skip the translate call for this item.

    Body: { "translated": "...", "lang": "zh" }
    """
    data = request.get_json(silent=True) or {}
    translated = data.get('translated', '').strip()
    lang = data.get('lang', '').strip()

    if not translated or not lang or len(translated) > 4000:
        return jsonify({'success': False, 'error': 'invalid'}), 400

    room_id = normalize_room_id(request.args.get('room') or (request.get_json(silent=True) or {}).get('room'))
    history = _room(room_id)['history']

    # Update in-memory history (scoped to room)
    for item in history:
        if item.get('id') == translation_id:
            if item.get('translated_lang') != lang:
                item['translated'] = translated
                item['translated_lang'] = lang
            break

    # Persist to DB
    if db is not None:
        db.update_translated(translation_id, translated, lang)

    return jsonify({'success': True})

@app.route('/api/translations/clear', methods=['POST'])
@limiter.limit("10 per minute")
@require_auth
@check_client_access
def clear_translations():
    """Clear translation history for the specified room (default room if omitted)."""
    room_id = normalize_room_id(request.args.get('room') or
                                (request.get_json(silent=True) or {}).get('room'))
    state = _room(room_id)
    state['history'].clear()
    state['next_id'] = 0
    socketio.emit('history_cleared', {'room_id': room_id}, room=f'room:{room_id}')
    socketio.emit('history_cleared', {'room_id': room_id}, room=f'admin:{room_id}')
    logger.info(f"Translation history cleared for room '{room_id}' by {request.user.get('username')}")
    return jsonify({'success': True, 'room_id': room_id})

@app.route('/favicon.ico', methods=['GET'])
def favicon():
    """Favicon endpoint - return empty response to prevent 404"""
    return '', 204

@app.route('/api/health', methods=['GET'])
@limiter.limit("120 per minute")
def health_check():
    """Health check endpoint. Accepts optional ?room= for room-scoped counts."""
    room_param = request.args.get('room')
    if room_param:
        room_id = normalize_room_id(room_param)
        room_state = _room(room_id)
        clients = len(room_state['listeners'])
        translations = len(room_state['history'])
    else:
        room_id = None
        clients = _all_listener_count()
        translations = _all_history_count()
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'clients': clients,
        'peak_clients': _peak_clients,
        'translations': translations,
        'rooms': len(_rooms),
        'room_id': room_id,
    })

@app.route('/api/history', methods=['GET'])
@limiter.limit("60 per minute")
@require_auth
def get_history():
    """Get all transcription history for the given room (default room if omitted)."""
    room_id = normalize_room_id(request.args.get('room'))
    history = _room(room_id)['history']
    return jsonify({
        'success': True,
        'room_id': room_id,
        'translations': history,
        'count': len(history),
    })

# ──────────────────────────────────────────
# Feature 9: Session Analytics API
# ──────────────────────────────────────────
@app.route('/api/analytics', methods=['GET'])
@limiter.limit("30 per minute")
@require_auth
def get_analytics():
    """Return per-session statistics for the admin dashboard."""
    now = datetime.now()
    elapsed = now - _session_start_time
    elapsed_sec = int(elapsed.total_seconds())
    hours, rem = divmod(elapsed_sec, 3600)
    minutes, seconds = divmod(rem, 60)
    duration_str = f"{hours}h {minutes}m {seconds}s" if hours else f"{minutes}m {seconds}s"

    db_stats = db.get_stats() if db is not None else {'enabled': False, 'count': 0}

    return jsonify({
        'session_start':    _session_start_time.isoformat(),
        'duration_seconds': elapsed_sec,
        'duration_display': duration_str,
        'current_clients':  _all_listener_count(),
        'peak_clients':     _peak_clients,
        'total_transcriptions': _all_history_count(),
        'total_words':      _total_words,
        'total_bible_refs': _total_bible_refs,
        'total_translations': _total_translations,
        'total_tts_plays':  _total_tts_plays,
        'db':               db_stats,
        'rooms': [
            {
                'room_id': rid,
                'display_name': st['display_name'],
                'listeners': len(st['listeners']),
                'history': len(st['history']),
            }
            for rid, st in _rooms.items()
        ],
    })

@app.route('/api/analytics/reset', methods=['POST'])
@limiter.limit("5 per minute")
@require_admin_auth
def reset_analytics():
    """Reset session analytics counters (admin only)."""
    global _session_start_time, _peak_clients, _total_words
    global _total_bible_refs, _total_translations, _total_tts_plays
    _session_start_time = datetime.now()
    _peak_clients = _all_listener_count()
    _total_words = 0
    _total_bible_refs = 0
    _total_translations = 0
    _total_tts_plays = 0
    logger.info("Session analytics reset by %s", getattr(request, 'user', {}).get('username', 'unknown'))
    return jsonify({'success': True, 'reset_at': _session_start_time.isoformat()})

@app.route('/api/export/<export_format>', methods=['GET'])
@limiter.limit("10 per minute")
@require_auth
@check_client_access
def export_translations(export_format):
    """Export translations with validation"""
    allowed_formats = ['json', 'txt', 'csv', 'srt']

    if export_format not in allowed_formats:
        return jsonify({'error': f'Unsupported format'}), 400

    # Limit export size (scoped to the requested room, default room if omitted)
    room_id = normalize_room_id(request.args.get('room'))
    max_export = 5000
    export_data = _room(room_id)['history'][-max_export:]

    if export_format == 'json':
        import json as json_module
        output = json_module.dumps({'translations': export_data}, indent=2, ensure_ascii=False)
        return output, 200, {
            'Content-Type': 'application/json; charset=utf-8',
            'Content-Disposition': 'attachment; filename="transcriptions.json"'
        }

    elif export_format == 'txt':
        output = f"EzySpeechTranslate Export\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        output += "=" * 60 + "\n\n"

        for item in export_data:
            output += f"[{item['id']}] {item['timestamp']}\n"
            output += f"Original: {sanitize_text(item['original'], 500)}\n"
            output += f"Corrected: {sanitize_text(item['corrected'], 500)}\n"
            output += "-" * 60 + "\n\n"

        # Add UTF-8 BOM to ensure Windows/Excel correctly identifies encoding
        output = '\ufeff' + output
        return output, 200, {
            'Content-Type': 'text/plain; charset=utf-8',
            'Content-Disposition': 'attachment; filename="transcriptions.txt"'
        }

    elif export_format == 'csv':
        output = "ID,Timestamp,Original,Corrected,Is_Corrected\n"

        for item in export_data:
            row = [
                str(item['id']),
                item['timestamp'],
                f'"{sanitize_text(item["original"], 500).replace(chr(34), chr(34)*2)}"',
                f'"{sanitize_text(item["corrected"], 500).replace(chr(34), chr(34)*2)}"',
                'Yes' if item['is_corrected'] else 'No'
            ]
            output += ','.join(row) + '\n'

        # Add UTF-8 BOM to ensure Windows/Excel correctly identifies encoding
        output = '\ufeff' + output
        return output, 200, {
            'Content-Type': 'text/csv; charset=utf-8',
            'Content-Disposition': 'attachment; filename="transcriptions.csv"'
        }

    elif export_format == 'srt':
        output = ""
        for i, item in enumerate(export_data, 1):
            start_seconds = (i - 1) * 5
            end_seconds = i * 5

            start_time = f"00:{start_seconds // 60:02d}:{start_seconds % 60:02d},000"
            end_time = f"00:{end_seconds // 60:02d}:{end_seconds % 60:02d},000"

            output += f"{i}\n"
            output += f"{start_time} --> {end_time}\n"
            output += f"{sanitize_text(item['corrected'], 500)}\n\n"

        # Add UTF-8 BOM to ensure Windows/Excel correctly identifies encoding
        output = '\ufeff' + output
        return output, 200, {
            'Content-Type': 'text/plain; charset=utf-8',
            'Content-Disposition': 'attachment; filename="transcriptions.srt"'
        }

# ──────────────────────────────────────────
# Translation API with Rate Limiting and Caching
# ──────────────────────────────────────────
from app.services.translation import get_translation_service  # noqa: E402

# Import Edge TTS for cloud-based text-to-speech
from app.services.tts import tts_cache  # noqa: E402

try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
    # Cache for Edge TTS voices (will be populated on demand)
    EDGE_TTS_VOICES_CACHE = None
    EDGE_TTS_VOICES_CACHE_TIME = None

    # All valid Edge TTS language codes extracted from edge-tts library
    # These are the base language codes that can be used for voice selection
    VALID_EDGE_TTS_LANGS = {
        'af-ZA', 'am-ET', 'ar-AE', 'ar-BH', 'ar-DZ', 'ar-EG', 'ar-IQ', 'ar-JO', 'ar-KW', 
        'ar-LB', 'ar-LY', 'ar-MA', 'ar-OM', 'ar-QA', 'ar-SA', 'ar-SY', 'ar-TN', 'ar-YE',
        'az-AZ', 'bg-BG', 'bn-BD', 'bn-IN', 'bs-BA', 'ca-ES', 'cs-CZ', 'cy-GB', 'da-DK',
        'de-AT', 'de-CH', 'de-DE', 'el-GR', 'en-AU', 'en-CA', 'en-GB', 'en-HK', 'en-IE',
        'en-IN', 'en-KE', 'en-NG', 'en-NZ', 'en-PH', 'en-SG', 'en-TZ', 'en-US', 'en-ZA',
        'es-AR', 'es-BO', 'es-CL', 'es-CO', 'es-CR', 'es-CU', 'es-DO', 'es-EC', 'es-ES',
        'es-GQ', 'es-GT', 'es-HN', 'es-MX', 'es-NI', 'es-PA', 'es-PE', 'es-PR', 'es-PY',
        'es-SV', 'es-US', 'es-UY', 'es-VE', 'et-EE', 'fa-IR', 'fi-FI', 'fil-PH', 'fr-BE',
        'fr-CA', 'fr-CH', 'fr-FR', 'ga-IE', 'gl-ES', 'gu-IN', 'he-IL', 'hi-IN', 'hr-HR',
        'hu-HU', 'id-ID', 'is-IS', 'it-IT', 'iu-Cans-CA', 'iu-Latn-CA', 'ja-JP', 'jv-ID',
        'ka-GE', 'kk-KZ', 'km-KH', 'kn-IN', 'ko-KR', 'lo-LA', 'lt-LT', 'lv-LV', 'mk-MK',
        'ml-IN', 'mn-MN', 'mr-IN', 'ms-MY', 'mt-MT', 'my-MM', 'nb-NO', 'ne-NP', 'nl-BE',
        'nl-NL', 'pl-PL', 'ps-AF', 'pt-BR', 'pt-PT', 'ro-RO', 'ru-RU', 'si-LK', 'sk-SK',
        'sl-SI', 'so-SO', 'sq-AL', 'sr-RS', 'su-ID', 'sv-SE', 'sw-KE', 'sw-TZ', 'ta-IN',
        'ta-LK', 'ta-MY', 'ta-SG', 'te-IN', 'th-TH', 'tr-TR', 'uk-UA', 'ur-IN', 'ur-PK',
        'uz-UZ', 'vi-VN', 'zh-CN', 'zh-HK', 'zh-TW', 'zu-ZA',
        # Regional variants
        'zh-CN-liaoning', 'zh-CN-shaanxi'
    }

    # Client rate limiting tracking
    CLIENT_SYNTHESIS_REQUESTS = defaultdict(list)  # client_id -> [(timestamp, request_hash), ...]
    CLIENT_SYNTHESIS_LIMIT = 100  # Max synthesis requests per client per hour

except ImportError:
    logger.warning("edge-tts not installed. Cloud TTS will not be available. Install with: pip install edge-tts")
    EDGE_TTS_AVAILABLE = False
    EDGE_TTS_VOICES_CACHE = None
    EDGE_TTS_VOICES_CACHE_TIME = None
    VALID_EDGE_TTS_LANGS = set()
    CLIENT_SYNTHESIS_REQUESTS = defaultdict(list)

# ✅ Ensure remaining TTS-related globals are defined (fail-safe)
if 'EDGE_TTS_AVAILABLE' not in globals():
    EDGE_TTS_AVAILABLE = False
if 'CLIENT_SYNTHESIS_REQUESTS' not in globals():
    CLIENT_SYNTHESIS_REQUESTS = defaultdict(list)
if 'EDGE_TTS_VOICES_CACHE' not in globals():
    EDGE_TTS_VOICES_CACHE = None
if 'EDGE_TTS_VOICES_CACHE_TIME' not in globals():
    EDGE_TTS_VOICES_CACHE_TIME = None

logger.info(f"🔍 Edge TTS initialized - EDGE_TTS_AVAILABLE={EDGE_TTS_AVAILABLE}, Cache size: {len(tts_cache)} items")

@app.route('/api/translate', methods=['POST'])
@limiter.limit("300 per minute")  # 5 requests per second per client (need headroom for bulk imports)
@check_client_access
def translate_text():
    """
    Translate text from server-side
    
    Request:
        {
            "text": "text to translate",
            "target_lang": "zh",  # target language code
        }
    
    Response:
        {
            "success": true/false,
            "translated": "translated text",
            "original": "original text",
            "target_lang": "zh",
            "source_lang": "auto",
            "cached": true/false,  # true if from cache
            "error": "error message (if failed)"
        }
    """
    try:
        data = request.json or {}
    except Exception:
        security_logger.warning(f"Malformed JSON from {get_client_key()}")
        return jsonify({'success': False, 'error': 'Invalid request'}), 400
    
    text = sanitize_text(data.get('text', ''), max_length=5000)
    target_lang = sanitize_text(data.get('target_lang', 'en'), max_length=20)
    room_id = normalize_room_id(data.get('room') or request.args.get('room'))

    if not text or not target_lang:
        return jsonify({
            'success': False,
            'error': 'Missing required fields: text, target_lang'
        }), 400

    if len(text) > 5000:
        return jsonify({
            'success': False,
            'error': 'Text too long (max 5000 characters)'
        }), 413

    try:
        # Get translation service instance
        translation_service = get_translation_service()

        # Fetch glossary entries matching this room+language (if DB enabled)
        glossary_terms = _get_glossary_for(room_id, target_lang)

        # Perform translation - now returns (success, translated, from_cache)
        success, translated, from_cache = translation_service.translate(
            text, target_lang, glossary=glossary_terms
        )

        return jsonify({
            'success': success,
            'translated': translated,
            'original': text,
            'target_lang': target_lang,
            'source_lang': 'auto',
            'cached': from_cache,
            'room_id': room_id,
            'glossary_applied': len(glossary_terms) if glossary_terms else 0,
            'error': None if success else 'Translation failed'
        })
    
    except Exception as e:
        logger.error(f"Translation error: {e}")
        return jsonify({
            'success': False,
            'error': f'Translation service error: {str(e)}'
        }), 500

@app.route('/api/translate/batch', methods=['POST'])
@limiter.limit("60 per minute")  # 1 request per second per client for batch
@check_client_access
def translate_batch():
    """
    Translate multiple texts in batch
    
    Request:
        {
            "texts": ["text1", "text2", ...],
            "target_lang": "zh"
        }
    
    Response:
        {
            "success": true/false,
            "translations": [
                {
                    "original": "text1",
                    "translated": "translated text1",
                    "success": true,
                    "cached": false
                },
                ...
            ],
            "error": "error message (if failed)"
        }
    """
    try:
        data = request.json or {}
    except Exception:
        security_logger.warning(f"Malformed JSON from {get_client_key()}")
        return jsonify({'success': False, 'error': 'Invalid request'}), 400
    
    texts = data.get('texts', [])
    target_lang = sanitize_text(data.get('target_lang', 'en'), max_length=20)
    room_id = normalize_room_id(data.get('room') or request.args.get('room'))

    if not isinstance(texts, list) or not texts or not target_lang:
        return jsonify({
            'success': False,
            'error': 'Invalid request: expected texts (list) and target_lang'
        }), 400
    
    # Limit batch size
    if len(texts) > 50:
        return jsonify({
            'success': False,
            'error': 'Batch too large (max 50 items)'
        }), 413
    
    try:
        translation_service = get_translation_service()
        glossary_terms = _get_glossary_for(room_id, target_lang)
        results = []
        
        for text in texts:
            sanitized = sanitize_text(text, max_length=5000)
            if not sanitized:
                results.append({
                    'original': text,
                    'translated': text,
                    'success': False,
                    'cached': False,
                    'error': 'Empty or invalid text'
                })
                continue
            
            success, translated, from_cache = translation_service.translate(
                sanitized, target_lang, glossary=glossary_terms
            )
            results.append({
                'original': sanitized,
                'translated': translated,
                'success': success,
                'cached': from_cache,
                'error': None if success else 'Translation failed'
            })
        
        return jsonify({
            'success': True,
            'translations': results,
            'count': len(results),
            'room_id': room_id,
            'glossary_applied': len(glossary_terms) if glossary_terms else 0,
        })
    
    except Exception as e:
        logger.error(f"Batch translation error: {e}")
        return jsonify({
            'success': False,
            'error': f'Batch translation failed: {str(e)}'
        }), 500

@app.route('/api/translate/cache', methods=['POST'])
@limiter.limit("10 per minute")
@require_auth
@check_client_access
def clear_translation_cache():
    """Clear translation cache"""
    try:
        translation_service = get_translation_service()
        translation_service.clear_cache()
        logger.info(f"Translation cache cleared by {request.user.get('username')}")
        return jsonify({'success': True, 'message': 'Cache cleared'})
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ──────────────────────────────────────────
# Text-to-Speech API (Edge TTS - Cloud)
# ──────────────────────────────────────────

def fetch_edge_tts_voices_in_thread():
    """Fetch Edge TTS voices via edge-tts CLI in a background OS thread"""
    global EDGE_TTS_VOICES_CACHE, EDGE_TTS_VOICES_CACHE_TIME

    if not EDGE_TTS_AVAILABLE:
        logger.warning("⚠️ Edge TTS not available, skipping voice fetch")
        return []

    try:
        logger.info("⏳ Fetching Edge TTS voices via CLI...")

        result = subprocess.run(
            [sys.executable, '-m', 'edge_tts', '--list-voices'],
            capture_output=True, text=True, timeout=60,
            close_fds=True,
            start_new_session=True
        )

        if result.returncode != 0:
            logger.error(f"❌ edge-tts --list-voices failed (rc={result.returncode}): {result.stderr}")
            EDGE_TTS_VOICES_CACHE_TIME = None
            return []

        if not result.stdout or not result.stdout.strip():
            logger.error("❌ edge-tts --list-voices returned empty output")
            EDGE_TTS_VOICES_CACHE_TIME = None
            return []

        voices = []
        current = {}
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                if current.get('ShortName'):
                    voices.append(current)
                current = {}
            elif ':' in line:
                key, _, val = line.partition(':')
                key = key.strip()
                val = val.strip()
                if key == 'Name':
                    current['ShortName'] = val
                    current['FriendlyName'] = val
                    # 从 Name 提取 Locale
                    # zh-CN-XiaoxiaoNeural        → zh-CN
                    # zh-CN-liaoning-XiaobeiNeural → zh-CN
                    parts = val.split('-')
                    if len(parts) >= 2:
                        current['Locale'] = f"{parts[0]}-{parts[1]}"
                elif key == 'Gender':
                    current['Gender'] = val
        # 处理最后一条（文件末尾无空行时）
        if current.get('ShortName'):
            voices.append(current)

        if not voices:
            logger.error("❌ No voices parsed from CLI output")
            EDGE_TTS_VOICES_CACHE_TIME = None
            return []

        logger.info(f"✅ Cached {len(voices)} Edge TTS voices via CLI")
        if voices:
            logger.info(f"🔍 First voice sample: {voices[0]}")
        EDGE_TTS_VOICES_CACHE = voices
        EDGE_TTS_VOICES_CACHE_TIME = datetime.now()
        return voices

    except subprocess.TimeoutExpired:
        logger.error("❌ edge-tts --list-voices timeout (60s)")
        EDGE_TTS_VOICES_CACHE_TIME = None
        return []
    except Exception as e:
        logger.error(f"❌ fetch voices error: {e}", exc_info=True)
        EDGE_TTS_VOICES_CACHE_TIME = None
        return []


def get_cached_edge_tts_voices():
    """Get voices from cache, trigger background fetch if needed"""
    global EDGE_TTS_VOICES_CACHE, EDGE_TTS_VOICES_CACHE_TIME

    if not EDGE_TTS_AVAILABLE:
        return []

    # 有缓存且未过期（1小时）
    if EDGE_TTS_VOICES_CACHE is not None:
        if EDGE_TTS_VOICES_CACHE_TIME and (datetime.now() - EDGE_TTS_VOICES_CACHE_TIME).seconds < 3600:
            return EDGE_TTS_VOICES_CACHE

    # 首次：设占位时间防止并发重复触发，然后后台拉取
    if EDGE_TTS_VOICES_CACHE_TIME is None:
        EDGE_TTS_VOICES_CACHE_TIME = datetime.now()
        logger.info("📥 Fetching Edge TTS voices in background OS thread...")
        import threading
        threading.Thread(
            target=fetch_edge_tts_voices_in_thread,
            daemon=True,
            name="tts-voice-fetch"
        ).start()

    return EDGE_TTS_VOICES_CACHE or []


# ──────────────────────────────────────────
# Edge TTS Validation and Rate Limiting
# ──────────────────────────────────────────

def validate_language_code(lang_code):
    """Validate if the language code is supported by Edge TTS."""
    if not lang_code or not isinstance(lang_code, str):
        return False, "Invalid language code format"

    if lang_code not in VALID_EDGE_TTS_LANGS:
        base_lang = lang_code.split('-')[0]
        matching = [l for l in VALID_EDGE_TTS_LANGS if l.startswith(base_lang + '-')]
        if matching:
            return True, f"Language code '{lang_code}' not found. Using '{matching[0]}' instead."
        return False, f"Unsupported language code: '{lang_code}'."

    return True, None


def validate_voice_name(voice_name, available_voices):
    """Validate if the voice name is available and safe."""
    if not voice_name or not isinstance(voice_name, str):
        return True, None, None

    if not re.match(r'^[a-z]{2}-[A-Z]{2}(-[a-zA-Z0-9]+)*Neural$', voice_name):
        return False, f"Invalid voice format: {voice_name}", None

    if available_voices:
        voice_exists = any(v.get('ShortName') == voice_name for v in available_voices)
        if not voice_exists:
            return False, f"Voice '{voice_name}' is not available", None

    return True, None, voice_name


def check_client_synthesis_limit(client_id, request_hash):
    """Check if client has exceeded synthesis rate limit (100 per hour)."""
    global CLIENT_SYNTHESIS_REQUESTS

    current_time = time.time()
    one_hour_ago = current_time - 3600

    if client_id in CLIENT_SYNTHESIS_REQUESTS:
        CLIENT_SYNTHESIS_REQUESTS[client_id] = [
            (ts, rh) for ts, rh in CLIENT_SYNTHESIS_REQUESTS[client_id]
            if ts > one_hour_ago
        ]

    current_count = len(CLIENT_SYNTHESIS_REQUESTS[client_id])

    if current_count >= CLIENT_SYNTHESIS_LIMIT:
        logger.warning(f"⚠️ Client {client_id} exceeded synthesis limit ({current_count}/{CLIENT_SYNTHESIS_LIMIT})")
        return False, f"Rate limit exceeded: {current_count}/{CLIENT_SYNTHESIS_LIMIT} per hour", current_count

    CLIENT_SYNTHESIS_REQUESTS[client_id].append((current_time, request_hash))
    return True, None, current_count + 1


def get_synthesis_cache_key(text, voice):
    """Generate a stable cache key for synthesis requests."""
    cache_input = f"{text}|{voice or 'default'}"
    return hashlib.sha256(cache_input.encode()).hexdigest()


@app.route('/api/tts/synthesize', methods=['POST'])
@limiter.limit("120 per minute")
@require_api_token
@check_client_access
def synthesize_tts():
    """Synthesize speech using Edge TTS CLI"""
    if not EDGE_TTS_AVAILABLE:
        return jsonify({'success': False, 'error': 'Edge TTS not available'}), 503

    try:
        data = request.get_json() or {}
    except Exception:
        return jsonify({'success': False, 'error': 'Invalid JSON'}), 400

    session_info = getattr(request, 'session_info', {})
    sid = session_info.get('sid') or request.client_id or get_remote_address()
    client_id = f"tts_{sid}"

    text = sanitize_text(data.get('text', ''), max_length=5000)
    lang = sanitize_text(data.get('lang', 'en-US'), max_length=20)
    voice = sanitize_text(data.get('voice', ''), max_length=100)

    if not text:
        return jsonify({'success': False, 'error': 'Text is required'}), 400

    if len(text) > 5000:
        return jsonify({'success': False, 'error': 'Text too long (max 5000 chars)'}), 400

    is_valid_lang, lang_error = validate_language_code(lang)
    if not is_valid_lang:
        return jsonify({'success': False, 'error': lang_error}), 400

    available_voices = get_cached_edge_tts_voices()
    is_valid_voice, voice_error, validated_voice = validate_voice_name(voice, available_voices)
    if not is_valid_voice:
        return jsonify({'success': False, 'error': voice_error}), 400

    # 选 voice：优先用请求指定的，否则找该语言第一个，找不到就报错
    if not validated_voice:
        if available_voices:
            lang_voices = [v for v in available_voices if v.get('Locale', '') == lang]
            if not lang_voices:
                # 宽松匹配，例如 zh 匹配 zh-CN
                base = lang.split('-')[0]
                lang_voices = [v for v in available_voices if v.get('Locale', '').startswith(base + '-')]
            if lang_voices:
                validated_voice = lang_voices[0].get('ShortName')
                logger.info(f"Using default voice for {lang}: {validated_voice}")
            else:
                available_locales = list(set(v.get('Locale', '') for v in available_voices[:20]))
                logger.error(f"No voice for lang={lang}, available locales sample: {available_locales}")
                return jsonify({'success': False, 'error': f'No voices available for language: {lang}'}), 400
        else:
            return jsonify({'success': False, 'error': 'Voices not yet loaded, please retry in a moment'}), 503

    # 检查缓存
    cache_key = get_synthesis_cache_key(text, validated_voice)
    cached_audio = tts_cache.get(cache_key)
    if cached_audio is not None:
        logger.info(f"🔄 Cache hit (client: {client_id})")
        return Response(
            cached_audio,
            mimetype='audio/mpeg',
            status=200,
            headers={
                'Content-Type': 'audio/mpeg',
                'Content-Length': str(len(cached_audio)),
                'Content-Disposition': 'inline; filename="speech.mp3"',
                'Cache-Control': 'no-cache, no-store, must-revalidate',
                'Pragma': 'no-cache',
                'Expires': '0',
                'X-Cache': 'HIT',
                'X-Content-Type-Options': 'nosniff'
            }
        )

    is_allowed, rate_limit_error, request_count = check_client_synthesis_limit(client_id, cache_key)
    if not is_allowed:
        return jsonify({'success': False, 'error': rate_limit_error}), 429

    # 合成：用 CLI 写到临时文件，完全绕开 eventlet/asyncio 冲突
    try:
        logger.info(f"🔄 Synthesizing via CLI: len={len(text)}, voice={validated_voice}")

        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            tmp_path = f.name

        try:
            result = subprocess.run(
                [
                    sys.executable, '-m', 'edge_tts',
                    '--voice', validated_voice,
                    '--text', text,
                    '--write-media', tmp_path
                ],
                capture_output=True, text=True, timeout=30,
                close_fds=True,
                start_new_session=True
            )

            if result.returncode != 0:
                logger.error(f"❌ edge-tts synthesis failed (rc={result.returncode}):\n{result.stderr}")
                return jsonify({'success': False, 'error': 'Audio synthesis failed'}), 500

            with open(tmp_path, 'rb') as f:
                audio_data = f.read()

        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    except subprocess.TimeoutExpired:
        logger.error("❌ TTS synthesis timeout (30s)")
        return jsonify({'success': False, 'error': 'Audio synthesis timeout'}), 503
    except Exception as e:
        logger.error(f"❌ Synthesis error: {str(e)[:300]}")
        return jsonify({'success': False, 'error': 'Audio synthesis failed'}), 500

    if not audio_data or len(audio_data) == 0:
        logger.error("❌ TTS synthesis returned empty audio")
        return jsonify({'success': False, 'error': 'Audio synthesis failed - empty output'}), 500

    logger.info(f"✅ Synthesized: {len(audio_data)} bytes, voice={validated_voice}")

    # 写缓存 (TTL + LRU eviction handled by TTSCache)
    tts_cache.set(cache_key, audio_data)
    stats = tts_cache.stats()
    logger.info(f"💾 Cache: {stats['cache_items']} items, {stats['cache_size_mb']:.2f}MB")

    return Response(
        audio_data,
        mimetype='audio/mpeg',
        status=200,
        headers={
            'Content-Type': 'audio/mpeg',
            'Content-Length': str(len(audio_data)),
            'Content-Disposition': 'inline; filename="speech.mp3"',
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0',
            'X-Cache': 'MISS',
            'X-Content-Type-Options': 'nosniff'
        }
    )


@app.route('/api/tts/voices', methods=['GET'])
@limiter.limit("30 per minute")
@check_client_access
def get_tts_voices():
    """Get available TTS voices from Edge TTS"""
    if not EDGE_TTS_AVAILABLE:
        return jsonify({
            'success': True,
            'edge_voices': [],
            'edge_tts_available': False,
            'error': 'Edge TTS not installed'
        })

    try:
        lang_filter = request.args.get('lang', '').strip()
        logger.info(f"TTS voices request - lang_filter: {lang_filter}")

        voices = get_cached_edge_tts_voices()

        if not voices:
            logger.info("Edge TTS voices still loading, returning status and asking client to retry")
            return jsonify({
                'success': True,
                'edge_voices': [],
                'edge_tts_available': True,
                'warning': 'Voices are being loaded, please retry in a moment...',
                'retry_after': 2
            })

        logger.info(f"Retrieved {len(voices)} voices from cache")

        if lang_filter:
            voices = [v for v in voices if v.get('Locale', '').startswith(lang_filter)]
            logger.info(f"After language filter ({lang_filter}): {len(voices)} voices")

        formatted_voices = []
        for v in voices:
            try:
                formatted_voices.append({
                    'name': v.get('ShortName', ''),
                    'locale': v.get('Locale', ''),
                    'gender': v.get('Gender', 'Unknown'),
                    'display_name': v.get('FriendlyName', v.get('ShortName', ''))
                })
            except Exception as e:
                logger.warning(f"Error formatting voice: {e}")
                continue

        logger.info(f"Returning {len(formatted_voices)} formatted voices")
        return jsonify({
            'success': True,
            'edge_voices': formatted_voices,
            'edge_tts_available': True
        })

    except Exception as e:
        logger.error(f"Error in get_tts_voices: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'edge_voices': [],
            'edge_tts_available': False,
            'error': str(e)
        }), 500


@app.route('/api/tts/supported-languages', methods=['GET'])
@limiter.limit("30 per minute")
@check_client_access
def get_supported_languages():
    """Get all supported language codes for Edge TTS."""
    try:
        voices = get_cached_edge_tts_voices()

        languages = set()
        for voice in voices:
            locale = voice.get('Locale', '')
            if locale:
                languages.add(locale)

        return jsonify({
            'success': True,
            'supported_languages': sorted(list(languages)),
            'total_languages': len(languages),
            'total_voices': len(voices) if voices else 0,
            'edge_tts_available': EDGE_TTS_AVAILABLE
        })

    except Exception as e:
        logger.error(f"Error in get_supported_languages: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/tts/cache-stats', methods=['GET'])
@limiter.limit("30 per minute")
def get_tts_cache_stats():
    """Get TTS synthesis cache statistics"""
    try:
        stats = tts_cache.stats()
        stats.update({
            'success': True,
            'message': (
                f"TTS cache using {stats['cache_size_mb']:.2f}MB "
                f"with {stats['cache_items']} items"
            ),
        })
        return jsonify(stats)

    except Exception as e:
        logger.error(f"❌ Error in get_tts_cache_stats: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e),
            'cache_items': 0,
            'cache_size_mb': 0
        }), 500


@app.route('/api/tts/cache-clear', methods=['POST'])
@limiter.limit("10 per minute")
@require_admin_auth
def clear_tts_cache():
    """Clear all TTS synthesis cache (admin only)."""
    try:
        cleared_items, freed_bytes = tts_cache.clear()
        freed_mb = freed_bytes / (1024 * 1024)
        source_ip = get_real_ip()

        logger.info(
            f"🗑️ TTS cache cleared: {cleared_items} items, {freed_mb:.2f}MB freed from {source_ip}"
        )
        security_logger.info(
            f"TTS_ACTION: cache_cleared | Items: {cleared_items} | "
            f"Freed: {freed_mb:.2f}MB | IP: {source_ip}"
        )

        return jsonify({
            'success': True,
            'cleared_items': cleared_items,
            'freed_mb': round(freed_mb, 2)
        })

    except Exception as e:
        logger.error(f"Error clearing TTS cache: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


# ──────────────────────────────────────────
# Rooms API (multi-room support)
# ──────────────────────────────────────────
@app.route('/api/rooms', methods=['GET'])
@limiter.limit("60 per minute")
def list_rooms():
    """Public list of active rooms — used by the user picker overlay."""
    db_rooms = []
    if db is not None:
        try:
            db_rooms = db.list_rooms()
        except Exception as exc:
            logger.warning(f"db.list_rooms failed: {exc}")
    # Merge with in-memory rooms (ensures default 'main' always shows)
    by_id = {r['room_id']: dict(r) for r in db_rooms if r.get('is_active', True)}
    for rid, st in _rooms.items():
        entry = by_id.get(rid, {
            'room_id': rid,
            'display_name': st.get('display_name') or rid,
            'is_active': True,
        })
        entry['listeners'] = len(st['listeners'])
        by_id[rid] = entry
    # Sort: default first, then alphabetical
    rooms_list = sorted(
        by_id.values(),
        key=lambda r: (0 if r['room_id'] == DEFAULT_ROOM_ID else 1, r['room_id']),
    )
    return jsonify({'success': True, 'rooms': rooms_list, 'default': DEFAULT_ROOM_ID})


@app.route('/api/rooms', methods=['POST'])
@limiter.limit("20 per minute")
@require_admin_auth
def create_room():
    """Create or update a room (admin only)."""
    data = request.get_json(silent=True) or {}
    room_id = (data.get('room_id') or '').strip()
    display_name = sanitize_text(data.get('display_name', '') or room_id, max_length=120)
    if not _VALID_ROOM_RE.match(room_id):
        return jsonify({'success': False, 'error': 'Invalid room_id'}), 400
    if db is not None:
        try:
            db.upsert_room(room_id, display_name=display_name,
                           created_by=request.user.get('username'))
        except Exception as exc:
            logger.warning(f"db.upsert_room failed: {exc}")
            return jsonify({'success': False, 'error': 'DB error'}), 500
    # Ensure in-memory state exists
    state = _room(room_id)
    state['display_name'] = display_name
    logger.info(f"[ROOM] Created/updated '{room_id}' by {request.user.get('username')}")
    return jsonify({'success': True, 'room_id': room_id, 'display_name': display_name})


@app.route('/api/rooms/<room_id>', methods=['DELETE'])
@limiter.limit("20 per minute")
@require_admin_auth
def delete_room(room_id):
    """Soft-delete a room (admin only). Default room is protected."""
    room_id = (room_id or '').strip()
    if not _VALID_ROOM_RE.match(room_id):
        return jsonify({'success': False, 'error': 'Invalid room_id'}), 400
    if room_id == DEFAULT_ROOM_ID:
        return jsonify({'success': False, 'error': 'Cannot delete default room'}), 400
    if db is not None:
        try:
            db.delete_room(room_id)
        except Exception as exc:
            logger.warning(f"db.delete_room failed: {exc}")
            return jsonify({'success': False, 'error': 'DB error'}), 500
    # Notify any listeners still in the room
    socketio.emit('room_deleted', {'room_id': room_id}, room=f'room:{room_id}')
    socketio.emit('room_deleted', {'room_id': room_id}, room=f'admin:{room_id}')
    # Drop in-memory state
    _rooms.pop(room_id, None)
    logger.info(f"[ROOM] Deleted '{room_id}' by {request.user.get('username')}")
    return jsonify({'success': True, 'room_id': room_id})


# ──────────────────────────────────────────
# Glossary API (forced translations)
# ──────────────────────────────────────────
@app.route('/api/glossary', methods=['GET'])
@limiter.limit("60 per minute")
@require_auth
def get_glossary():
    """List glossary entries (optionally filtered by room and/or language)."""
    if db is None:
        return jsonify({'success': True, 'entries': []})
    room_param = request.args.get('room')
    room_id = normalize_room_id(room_param) if room_param else None
    include_global = request.args.get('include_global', 'true').lower() != 'false'
    try:
        entries = db.glossary_list(room_id=room_id, include_global=include_global)
    except Exception as exc:
        logger.warning(f"db.glossary_list failed: {exc}")
        return jsonify({'success': False, 'error': 'DB error'}), 500
    lang_filter = (request.args.get('target_lang') or '').lower()
    if lang_filter:
        entries = [e for e in entries if (e.get('target_lang') or '').lower() == lang_filter]
    return jsonify({'success': True, 'entries': entries, 'count': len(entries)})


@app.route('/api/glossary', methods=['POST'])
@limiter.limit("60 per minute")
@require_admin_auth
def add_glossary():
    """Create a new glossary entry."""
    if db is None:
        return jsonify({'success': False, 'error': 'Database disabled'}), 400
    data = request.get_json(silent=True) or {}
    source_term = sanitize_text(data.get('source_term', ''), max_length=200).strip()
    target_lang = sanitize_text(data.get('target_lang', ''), max_length=20).strip()
    translation = sanitize_text(data.get('translation', ''), max_length=500).strip()
    case_sensitive = bool(data.get('case_sensitive', False))
    enabled = bool(data.get('enabled', True))
    room_param = data.get('room')
    room_id = None  # None = global
    if room_param:
        if not _VALID_ROOM_RE.match(str(room_param).strip()):
            return jsonify({'success': False, 'error': 'Invalid room_id'}), 400
        room_id = str(room_param).strip()
        # Verify room actually exists (avoid orphan glossary entries)
        try:
            active_ids = {r['room_id'] for r in db.list_rooms()}
        except Exception:
            active_ids = set()
        if room_id != DEFAULT_ROOM_ID and room_id not in active_ids:
            return jsonify({'success': False, 'error': f"Room '{room_id}' does not exist"}), 400
    if not source_term or not target_lang or not translation:
        return jsonify({'success': False, 'error': 'Missing required fields'}), 400
    try:
        entry_id = db.glossary_add(
            source_term=source_term, target_lang=target_lang, translation=translation,
            room_id=room_id, case_sensitive=case_sensitive, enabled=enabled,
            created_by=request.user.get('username'),
        )
    except Exception as exc:
        logger.warning(f"db.glossary_add failed: {exc}")
        return jsonify({'success': False, 'error': 'DB error'}), 500
    # Bust translation cache so changes take effect immediately
    try:
        get_translation_service().clear_cache()
    except Exception:
        pass
    logger.info(f"[GLOSSARY] Added '{source_term}'→'{translation}' ({target_lang}, room={room_id}) "
                f"by {request.user.get('username')}")
    return jsonify({'success': True, 'id': entry_id})


@app.route('/api/glossary/<int:entry_id>', methods=['PUT'])
@limiter.limit("60 per minute")
@require_admin_auth
def update_glossary(entry_id):
    """Update an existing glossary entry."""
    if db is None:
        return jsonify({'success': False, 'error': 'Database disabled'}), 400
    data = request.get_json(silent=True) or {}
    fields = {}
    if 'source_term' in data:
        fields['source_term'] = sanitize_text(data['source_term'], max_length=200)
    if 'target_lang' in data:
        fields['target_lang'] = sanitize_text(data['target_lang'], max_length=20)
    if 'translation' in data:
        fields['translation'] = sanitize_text(data['translation'], max_length=500)
    if 'case_sensitive' in data:
        fields['case_sensitive'] = bool(data['case_sensitive'])
    if 'enabled' in data:
        fields['enabled'] = bool(data['enabled'])
    if not fields:
        return jsonify({'success': False, 'error': 'Nothing to update'}), 400
    try:
        ok = db.glossary_update(entry_id, **fields)
    except Exception as exc:
        logger.warning(f"db.glossary_update failed: {exc}")
        return jsonify({'success': False, 'error': 'DB error'}), 500
    try:
        get_translation_service().clear_cache()
    except Exception:
        pass
    return jsonify({'success': ok, 'id': entry_id})


@app.route('/api/glossary/<int:entry_id>', methods=['DELETE'])
@limiter.limit("60 per minute")
@require_admin_auth
def remove_glossary(entry_id):
    """Delete a glossary entry."""
    if db is None:
        return jsonify({'success': False, 'error': 'Database disabled'}), 400
    try:
        ok = db.glossary_delete(entry_id)
    except Exception as exc:
        logger.warning(f"db.glossary_delete failed: {exc}")
        return jsonify({'success': False, 'error': 'DB error'}), 500
    try:
        get_translation_service().clear_cache()
    except Exception:
        pass
    return jsonify({'success': ok, 'id': entry_id})


# ──────────────────────────────────────────
# Recording lock (per-room) — prevents two admins from recording the same
# room simultaneously. A force-stop requires re-verifying the admin password.
# ──────────────────────────────────────────

def _recording_owner_dict(state):
    rec = state.get('recording')
    if not rec:
        return None
    # Hide internal sid from public callers
    return {'username': rec.get('username'), 'started_at': rec.get('started_at')}


@app.route('/api/recording/state', methods=['GET'])
@limiter.limit("120 per minute")
@require_auth
def get_recording_state():
    """Report who (if anyone) is currently recording in a given room."""
    rid = normalize_room_id(request.args.get('room'))
    state = _room(rid)
    owner = _recording_owner_dict(state)
    return jsonify({'success': True, 'room_id': rid, 'recording': owner})


@app.route('/api/recording/acquire', methods=['POST'])
@limiter.limit("60 per minute")
@require_admin_auth
def acquire_recording():
    """Acquire the per-room recording lock.

    Returns 200 on success. If another admin holds the lock, returns 423 with
    owner info. To take over, pass {force: true, password_hash: <sha256>}.
    """
    data = request.get_json(silent=True) or {}
    rid = normalize_room_id(data.get('room'))
    state = _room(rid)
    username = (request.user.get('username') if request.user else '') or 'admin'
    sid = data.get('sid')  # optional Socket.IO sid of this admin tab

    current = state.get('recording')
    if current and current.get('username') != username:
        # Lock held by someone else
        if not data.get('force'):
            return jsonify({
                'success': False, 'error': 'locked',
                'owner': _recording_owner_dict(state),
            }), 423
        # Force-takeover requires password re-verification
        password_hash = data.get('password_hash', '')
        account = _accounts.get(username)
        if not account or len(password_hash) != 64 or account['password_hash'] != password_hash:
            security_logger.warning(
                f"Force-recording rejected: bad password from {username} for room '{rid}'"
            )
            return jsonify({'success': False, 'error': 'invalid_password'}), 401
        # Notify the displaced owner so their browser stops recognition
        evicted = current.get('username')
        evicted_sid = current.get('sid')
        socketio.emit(
            'recording_force_stopped',
            {'room_id': rid, 'by': username, 'reason': 'admin_takeover'},
            room=evicted_sid if evicted_sid else f'admin:{rid}',
        )
        logger.warning(
            f"[RECORDING] {username} force-stopped {evicted} in room '{rid}'"
        )

    state['recording'] = {
        'username': username,
        'sid': sid,
        'started_at': datetime.utcnow().isoformat() + 'Z',
    }
    socketio.emit(
        'recording_state',
        {'room_id': rid, 'recording': _recording_owner_dict(state)},
        room=f'admin:{rid}',
    )
    logger.info(f"[RECORDING] {username} acquired room '{rid}'")
    return jsonify({'success': True, 'room_id': rid, 'recording': _recording_owner_dict(state)})


@app.route('/api/recording/release', methods=['POST'])
@limiter.limit("60 per minute")
@require_admin_auth
def release_recording():
    """Release the recording lock for a room.

    Only the current owner (or no-op if no owner) can release.
    """
    data = request.get_json(silent=True) or {}
    rid = normalize_room_id(data.get('room'))
    state = _room(rid)
    username = (request.user.get('username') if request.user else '') or 'admin'
    current = state.get('recording')
    if current and current.get('username') != username:
        return jsonify({'success': False, 'error': 'not_owner',
                        'owner': _recording_owner_dict(state)}), 403
    state['recording'] = None
    socketio.emit(
        'recording_state',
        {'room_id': rid, 'recording': None},
        room=f'admin:{rid}',
    )
    logger.info(f"[RECORDING] {username} released room '{rid}'")
    return jsonify({'success': True, 'room_id': rid})


# ──────────────────────────────────────────
# Editable config.yaml (admin only)
# Sensitive keys are masked on read and ignored on write — they are
# managed via the encrypted secrets.key file, not the YAML config.
# ──────────────────────────────────────────

_CONFIG_FILE_PATH = os.path.join(BASE_DIR, 'config', 'config.yaml') \
    if 'BASE_DIR' in globals() else os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'config.yaml')
_SENSITIVE_CONFIG_KEYS = (
    'admin_password', 'jwt_secret', 'server_secret_key',
    'secret_key', 'encryption_key',
)


def _mask_sensitive(obj):
    """Recursively replace values for known sensitive keys with '***'."""
    if isinstance(obj, dict):
        return {
            k: ('***' if k in _SENSITIVE_CONFIG_KEYS and v else _mask_sensitive(v))
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_mask_sensitive(v) for v in obj]
    return obj


def _strip_masked(new_obj, existing_obj):
    """Where new_obj contains '***' for sensitive keys, restore the value from existing_obj."""
    if isinstance(new_obj, dict) and isinstance(existing_obj, dict):
        out = {}
        for k, v in new_obj.items():
            if k in _SENSITIVE_CONFIG_KEYS and v == '***':
                if k in existing_obj:
                    out[k] = existing_obj[k]
                # else: drop the masked placeholder
            else:
                out[k] = _strip_masked(v, existing_obj.get(k) if isinstance(existing_obj, dict) else None)
        return out
    if isinstance(new_obj, list):
        return [_strip_masked(v, None) for v in new_obj]
    return new_obj


@app.route('/api/config/raw', methods=['GET'])
@limiter.limit("30 per minute")
@require_admin_auth
def get_raw_config():
    """Return the current config.yaml as YAML text (sensitive values masked)."""
    try:
        import yaml  # PyYAML; already a transitive dep via config loader
        if not os.path.exists(_CONFIG_FILE_PATH):
            return jsonify({'success': False, 'error': 'config.yaml not found'}), 404
        with open(_CONFIG_FILE_PATH, 'r', encoding='utf-8') as f:
            raw = f.read()
        parsed = yaml.safe_load(raw) or {}
        masked = _mask_sensitive(parsed)
        return jsonify({
            'success': True,
            'yaml': yaml.safe_dump(masked, allow_unicode=True, sort_keys=False),
            'path': _CONFIG_FILE_PATH,
        })
    except Exception as exc:
        logger.warning(f"get_raw_config error: {exc}")
        return jsonify({'success': False, 'error': str(exc)}), 500


@app.route('/api/config/raw', methods=['POST'])
@limiter.limit("10 per minute")
@require_admin_auth
def save_raw_config():
    """Validate and write config.yaml. Sensitive keys with '***' are preserved
    from the existing file. Caller is warned that some changes require a server
    restart to take effect."""
    try:
        import yaml
        data = request.get_json(silent=True) or {}
        new_text = data.get('yaml', '')
        if not isinstance(new_text, str) or not new_text.strip():
            return jsonify({'success': False, 'error': 'Empty YAML'}), 400
        if len(new_text) > 200_000:
            return jsonify({'success': False, 'error': 'Config too large'}), 400
        try:
            parsed_new = yaml.safe_load(new_text)
        except yaml.YAMLError as exc:
            return jsonify({'success': False, 'error': f'YAML parse error: {exc}'}), 400
        if not isinstance(parsed_new, dict):
            return jsonify({'success': False, 'error': 'Top-level YAML must be a mapping'}), 400

        # Load existing to restore masked sensitive values
        existing = {}
        if os.path.exists(_CONFIG_FILE_PATH):
            with open(_CONFIG_FILE_PATH, 'r', encoding='utf-8') as f:
                existing = yaml.safe_load(f.read()) or {}

        merged = _strip_masked(parsed_new, existing)

        # Atomic write: write to .tmp then rename
        tmp_path = _CONFIG_FILE_PATH + '.tmp'
        with open(tmp_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(merged, f, allow_unicode=True, sort_keys=False)
        os.replace(tmp_path, _CONFIG_FILE_PATH)
        username = (request.user.get('username') if request.user else 'admin') or 'admin'
        logger.warning(f"[CONFIG] config.yaml updated by {username}")
        return jsonify({
            'success': True,
            'message': 'Saved. Restart the server for changes to take effect.',
        })
    except Exception as exc:
        logger.error(f"save_raw_config error: {exc}")
        return jsonify({'success': False, 'error': str(exc)}), 500


# ──────────────────────────────────────────
# WebSocket Events with Security
# ──────────────────────────────────────────
@socketio.on('connect')
def handle_connect():
    """Handle client connection with validation"""
    global _peak_clients
    # Priority: Get client_id from query params (sent by client), then cookies
    client_id = request.args.get('client_id')
    client_type = request.args.get('type', 'user')  # 'user' or 'admin'
    
    if not client_id:
        # Fallback to cookies if query param not provided
        if hasattr(request, 'cookies'):
            client_id = request.cookies.get('_client_id')
    
    # If still no client_id, generate one (fallback)
    if not client_id:
        client_id = f"browser_{secrets.token_hex(16)}"
        logger.warning(f"No client_id provided, generated fallback: {client_id}")

    # Validate client_type to a known whitelist; anything else is treated
    # as 'user'. Prevents callers from injecting arbitrary type strings
    # via the query string and ending up in unexpected branches.
    if client_type not in ('user', 'admin', 'caption'):
        logger.warning(f"Unknown client_type '{client_type}' from {client_id}, defaulting to 'user'")
        client_type = 'user'

    client_key = f"client:{client_id}"
    client_ip = get_real_ip()

    # Room scope for this client (validated; defaults to 'main')
    room_id = normalize_room_id(request.args.get('room'))
    room_state = _room(room_id)

    logger.info(f"Socket.IO connect attempt from {client_ip} (Client: {client_id}, Type: {client_type}, Room: {room_id}, SID: {request.sid})")

    if is_client_blocked(client_key):
        security_logger.warning(f"Blocked client attempted WebSocket: {client_key}")
        logger.error(f"Connection rejected: Client {client_key} is blocked")
        return False

    from flask_socketio import join_room as _join_room

    # Only count user-type clients as listeners (not admin)
    if client_type == 'user':
        # If this client_key already has an old SID anywhere, evict it (handles page refresh)
        for _rs in _rooms.values():
            old_sid = _rs['listeners'].get(client_key)
            if old_sid and old_sid != request.sid:
                logger.info(f"Evicting stale SID {old_sid} for {client_key} (replaced by {request.sid})")
                sid_to_client_key.pop(old_sid, None)
                connected_clients.discard(f"{client_key}:{old_sid}")
                _rs['listeners'].pop(client_key, None)

        client_id_full = f"{client_key}:{request.sid}"
        connected_clients.add(client_id_full)
        room_state['listeners'][client_key] = request.sid
        _join_room(f'room:{room_id}')
        logger.info(
            f"User client connected: {client_ip} (Client: {client_id}, Room: {room_id}, "
            f"SID: {request.sid}, Room listeners: {len(room_state['listeners'])}, "
            f"Total listeners: {_all_listener_count()})"
        )
    elif client_type == 'admin':
        # Admin clients still need to be tracked, but not as listeners
        client_id_full = f"{client_key}:{request.sid}"
        connected_clients.add(client_id_full)
        logger.info(f"Admin client connected: {client_ip} (Client: {client_id}, SID: {request.sid})")

    # Store mapping for reliable cleanup on disconnect (includes room_id)
    sid_to_client_key[request.sid] = (client_key, client_type, room_id)

    # Notify client that history is available via HTTP API (pagination)
    # Don't send all history via WebSocket - use HTTP API for better performance
    # Generate and send short-lived API session token for pagination
    api_token = create_api_token(request.sid)
    emit('ready', {
        'status': 'connected',
        'message': 'Use /api/translations to fetch paginated history',
        'api_token': api_token,
        'room_id': room_id,
    })

    # ── Feature 1: broadcast live viewer count to admins of this room ────
    if client_type == 'user':
        _sid_last_seen[request.sid] = datetime.now()   # start heartbeat tracking
        room_count = len(room_state['listeners'])
        total_count = _all_listener_count()
        if total_count > _peak_clients:
            _peak_clients = total_count
        payload = {'count': room_count, 'room_id': room_id, 'total': total_count}
        socketio.emit('clients_update', payload, room=f'admin:{room_id}')
        socketio.emit('clients_update', payload, room='admins')  # legacy compat

    return True

@socketio.on('disconnect')
def handle_disconnect(sid=None):
    """Handle client disconnection - find and clean up client info"""
    sid_used = sid if sid is not None else request.sid
    
    # Use stored mapping to find client_key and type reliably
    mapping = sid_to_client_key.pop(sid_used, None)
    
    if mapping:
        if len(mapping) >= 3:
            client_key, client_type, room_id = mapping[0], mapping[1], mapping[2]
        else:
            client_key, client_type = mapping[0], mapping[1]
            room_id = DEFAULT_ROOM_ID
        room_id = normalize_room_id(room_id)

        # Clean up only if it was a user (listener)
        if client_type == 'user':
            # Only remove from listener_clients if this SID is still the active one
            # (avoids removing a newer connection when a stale disconnect fires late)
            rs = _rooms.get(room_id)
            if rs is not None and rs['listeners'].get(client_key) == sid_used:
                del rs['listeners'][client_key]
            logger.info(
                f"User client disconnected: SID {sid_used} from {client_key} "
                f"(Room: {room_id}, Total listeners: {_all_listener_count()})"
            )
        else:
            logger.info(f"Admin client disconnected: SID {sid_used} from {client_key}")
    else:
        logger.warning(f"Disconnect: Unknown client mapping for SID {sid_used}")
        client_type = None
        room_id = DEFAULT_ROOM_ID
    
    # Always try to remove from connected_clients
    connected_clients.discard(sid_used)
    for key in list(connected_clients):
        if key.endswith(f":{sid_used}"):
            connected_clients.discard(key)
            break
    
    admin_sessions.pop(sid_used, None)

    # Release recording lock if this disconnecting admin held it
    if client_type == 'admin':
        rs = _rooms.get(room_id)
        if rs and rs.get('recording') and rs['recording'].get('sid') == sid_used:
            rs['recording'] = None
            socketio.emit(
                'recording_state',
                {'room_id': room_id, 'recording': None},
                room=f'admin:{room_id}',
            )
            logger.info(f"[RECORDING] auto-released room '{room_id}' on admin disconnect")

    # Clean up API tokens associated with this SID
    tokens_to_remove = [t for t, info in api_session_tokens.items() if info['sid'] == sid_used]
    for token in tokens_to_remove:
        del api_session_tokens[token]

    # Remove heartbeat record
    _sid_last_seen.pop(sid_used, None)

    # ── Feature 1: broadcast updated viewer count to admins of the room ───
    if client_type == 'user':
        rs = _rooms.get(room_id)
        room_count = len(rs['listeners']) if rs else 0
        payload = {'count': room_count, 'room_id': room_id, 'total': _all_listener_count()}
        socketio.emit('clients_update', payload, room=f'admin:{room_id}')
        socketio.emit('clients_update', payload, room='admins')

@socketio.on('heartbeat')
def handle_heartbeat():
    """Client keepalive — update last-seen timestamp."""
    _sid_last_seen[request.sid] = datetime.now()


def _heartbeat_cleanup_loop():
    """Background greenlet: evict user clients that stopped sending heartbeats.

    A client is considered gone if no heartbeat arrived within
    HEARTBEAT_TIMEOUT seconds.  This catches browsers that close
    without triggering a clean WebSocket close (e.g. mobile sleep,
    Cloudflare Tunnel keepalive masking the real disconnect).
    """
    HEARTBEAT_TIMEOUT = 45   # seconds — 3× client interval (15 s)
    CHECK_INTERVAL   = 15   # how often we scan
    while True:
        eventlet.sleep(CHECK_INTERVAL)
        now = datetime.now()
        stale = [
            sid for sid, last in list(_sid_last_seen.items())
            if (now - last).total_seconds() > HEARTBEAT_TIMEOUT
        ]
        for sid in stale:
            _sid_last_seen.pop(sid, None)
            mapping = sid_to_client_key.get(sid)
            if mapping and mapping[1] == 'user':
                logger.info(f"[HEARTBEAT] Evicting stale user SID {sid} (no heartbeat for >{HEARTBEAT_TIMEOUT}s)")
                # Trigger the same cleanup path as a normal disconnect
                try:
                    handle_disconnect(sid)
                except Exception as _e:
                    logger.warning(f"[HEARTBEAT] Cleanup error for {sid}: {_e}")


@socketio.on('admin_connect')
def handle_admin_connect(data):
    """Handle admin connection with validation"""
    if not data or not isinstance(data, dict):
        emit('admin_connected', {'success': False, 'error': 'Invalid data'})
        return

    token = data.get('token')
    requested_room = normalize_room_id(data.get('room'))

    if not get_config('authentication', 'enabled', default=True):
        admin_sessions[request.sid] = {'username': 'admin', 'room_id': requested_room}
        from flask_socketio import join_room
        join_room('admins')
        join_room(f'admin:{requested_room}')
        # Send room-scoped history
        emit('history', _room(requested_room)['history'])
        emit('admin_connected', {
            'success': True, 'role': 'admin', 'channel': requested_room,
            'display_name': 'Admin', 'room_id': requested_room,
        })
        return

    if not token:
        emit('admin_connected', {'success': False, 'error': 'No token'})
        return

    decoded = validate_jwt_token(token)
    if decoded:
        # Prefer explicit room in payload; fall back to JWT channel; then default
        room_id = normalize_room_id(
            data.get('room') or decoded.get('channel') or DEFAULT_ROOM_ID
        )
        admin_sessions[request.sid] = {
            'username': decoded['username'],
            'room_id': room_id,
        }
        from flask_socketio import join_room
        join_room('admins')
        join_room(f'admin:{room_id}')
        # Send room-scoped history
        emit('history', _room(room_id)['history'])
        emit('admin_connected', {
            'success':      True,
            'role':         decoded.get('role', 'admin'),
            'channel':      room_id,
            'room_id':      room_id,
            'display_name': decoded.get('display_name', decoded['username']),
        })
        logger.info(f"Admin connected: {decoded['username']} ({decoded.get('role', 'admin')}/room={room_id}) from {get_real_ip()}")
    else:
        emit('admin_connected', {'success': False, 'error': 'Invalid token'})


@socketio.on('admin_switch_room')
def handle_admin_switch_room(data):
    """Allow an authenticated admin to switch the room they broadcast into."""
    if not is_admin(request.sid):
        emit('error', {'message': 'Unauthorized'})
        return
    if not data or not isinstance(data, dict):
        emit('error', {'message': 'Invalid data'})
        return
    new_room = normalize_room_id(data.get('room'))
    info = admin_sessions.get(request.sid)
    if not isinstance(info, dict):
        info = {'username': info or 'admin', 'room_id': DEFAULT_ROOM_ID}
    old_room = normalize_room_id(info.get('room_id'))
    if old_room == new_room:
        emit('room_switched', {'success': True, 'room_id': new_room, 'changed': False})
        return
    from flask_socketio import leave_room, join_room
    leave_room(f'admin:{old_room}')
    join_room(f'admin:{new_room}')
    info['room_id'] = new_room
    admin_sessions[request.sid] = info
    # Make sure target room state exists and send its history
    emit('history', _room(new_room)['history'])
    emit('room_switched', {'success': True, 'room_id': new_room, 'changed': True})
    logger.info(f"[ROOM-SWITCH] {_admin_username(request.sid)}: {old_room} -> {new_room}")


@socketio.on('new_transcription')
def handle_new_transcription(data):
    """Handle new transcription with validation
    
    Support two modes:
    - is_final=False: Send interim result for real-time display (no storing)
    - is_final=True: Send final result with translation (store in history)
    """
    if not is_admin(request.sid):
        emit('error', {'message': 'Unauthorized'})
        disconnect()
        return

    if not data or not isinstance(data, dict):
        emit('error', {'message': 'Invalid data'})
        return

    raw_text = sanitize_text(data.get('text', ''), max_length=5000)
    if not raw_text:
        return

    is_final = data.get('is_final', True)  # Default to final for backward compatibility
    temp_id = data.get('temp_id')  # Temporary ID to link interim->final results
    room_id = _admin_room(request.sid)

    if not is_final:
        interim_data = {
            'temp_id': temp_id,
            'text': raw_text,
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'source_language': data.get('language', 'en')[:10],
            'confidence': data.get('confidence'),
            'is_interim': True,
            'room_id': room_id,
        }
        # Broadcast to listeners in this room only
        socketio.emit('realtime_transcription', interim_data,
                      room=f'room:{room_id}', skip_sid=[request.sid])
        logger.info(f"[INTERIM] room={room_id} {len(raw_text)} chars (temp_id: {temp_id})")
    else:
        translation_data = {
            'id': None,  # Will be assigned by add_translation()
            'temp_id': temp_id,
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'original': raw_text,
            'corrected': raw_text,
            'translated': data.get('translated'),
            'is_corrected': False,
            'source_language': data.get('language', 'en')[:10],
            'confidence': data.get('confidence'),
        }

        add_translation(translation_data, room_id=room_id)
        # Emit to listeners in this room only
        socketio.emit('new_translation', translation_data,
                      room=f'room:{room_id}', skip_sid=[request.sid])
        # Echo back to the sending admin for confirmation
        emit('transcription_confirmed', translation_data)
        logger.info(f"[FINAL] room={room_id} ID={translation_data.get('id')}")

@socketio.on('correct_translation')
def handle_correct_translation(data):
    """Handle translation correction with validation"""
    if not is_admin(request.sid):
        emit('error', {'message': 'Unauthorized'})
        disconnect()
        return

    if not data or not isinstance(data, dict):
        emit('error', {'message': 'Invalid data'})
        return

    translation_id = data.get('id')
    corrected_text = sanitize_text(data.get('corrected_text', ''), max_length=5000)

    if not isinstance(translation_id, int) or translation_id < 0:
        emit('error', {'message': 'Invalid ID'})
        return

    if not corrected_text:
        emit('error', {'message': 'Empty correction'})
        return

    # Find translation by ID within the admin's room
    room_id = _admin_room(request.sid)
    history = _room(room_id)['history']
    target_item = None
    for item in history:
        if item['id'] == translation_id:
            target_item = item
            break

    if target_item is None:
        emit('error', {'message': 'Translation not found (may have been removed from history)'})
        return

    target_item['corrected'] = corrected_text
    target_item['is_corrected'] = True

    # Re-detect Bible references in the corrected text so the panel updates
    # if the admin fixed a transcription error into a proper Bible citation.
    if bible_detector is not None:
        try:
            new_refs = bible_detector.detect_and_lookup(corrected_text)
            target_item['bible_refs'] = new_refs if new_refs else []
        except Exception:
            pass  # keep original refs on failure

    # Persist correction to DB
    if db is not None:
        db.update_correction(
            translation_id, corrected_text, True,
            bible_refs=target_item.get('bible_refs'),
            full_item=target_item,
        )

    socketio.emit('translation_corrected', target_item, room=f'room:{room_id}')
    socketio.emit('translation_corrected', target_item, room=f'admin:{room_id}')
    logger.info(f"✏️ [CORRECTED] room={room_id} ID {translation_id}")
    emit('correction_success', {'id': translation_id})

@socketio.on('clear_history')
def handle_clear_history():
    """Handle clear history with authorization (scoped to admin's room)"""
    if not is_admin(request.sid):
        emit('error', {'message': 'Unauthorized'})
        disconnect()
        return

    room_id = _admin_room(request.sid)
    state = _room(room_id)
    state['history'].clear()
    state['next_id'] = 0
    if db is not None:
        db.clear_all(room_id=room_id)
    socketio.emit('history_cleared', {'room_id': room_id}, room=f'room:{room_id}')
    socketio.emit('history_cleared', {'room_id': room_id}, room=f'admin:{room_id}')
    logger.info(f"[CLEARED] room={room_id} by {_admin_username(request.sid)}")

@socketio.on('import_transcription')
def handle_import_transcription(data):
    """Handle import of transcriptions from JSON file"""
    if not is_admin(request.sid):
        emit('error', {'message': 'Unauthorized'})
        disconnect()
        return

    if not data or not isinstance(data, dict):
        emit('error', {'message': 'Invalid data'})
        return

    # Validate required fields
    required_fields = ['original', 'corrected']
    for field in required_fields:
        if field not in data:
            emit('error', {'message': f'Missing required field: {field}'})
            return

    # Sanitize and prepare import data
    translation_data = {
        'id': data.get('id'),  # Use provided ID if available
        'timestamp': data.get('timestamp', datetime.now().strftime('%H:%M:%S')),
        'original': sanitize_text(data.get('original', ''), max_length=5000),
        'corrected': sanitize_text(data.get('corrected', ''), max_length=5000),
        'translated': data.get('translated'),
        'is_corrected': data.get('is_corrected', False),
        'source_language': data.get('language', 'imported')[:10],
        'confidence': data.get('confidence', 0.95)
    }

    # Validate after sanitization
    if not translation_data['original'] or not translation_data['corrected']:
        emit('error', {'message': 'Original and corrected text cannot be empty'})
        return

    # Add to history (scoped to admin's room)
    room_id = _admin_room(request.sid)
    add_translation(translation_data, room_id=room_id)

    # Broadcast to clients in the admin's room
    socketio.emit('new_translation', translation_data, room=f'room:{room_id}')
    socketio.emit('new_translation', translation_data, room=f'admin:{room_id}')
    logger.info(f"[IMPORTED] room={room_id} ID={translation_data['id']} from {_admin_username(request.sid)}")

@socketio.on('delete_items')
def handle_delete_items(data):
    """Handle deletion of multiple items with authorization"""
    if not is_admin(request.sid):
        emit('error', {'message': 'Unauthorized'})
        disconnect()
        return

    if not data or not isinstance(data, dict):
        emit('error', {'message': 'Invalid data'})
        return

    item_ids = data.get('ids', [])
    if not isinstance(item_ids, list):
        emit('error', {'message': 'Invalid IDs format'})
        return

    if not item_ids:
        emit('error', {'message': 'No items to delete'})
        return

    # Scope deletion to the admin's own room
    room_id = _admin_room(request.sid)
    state = _room(room_id)
    original_count = len(state['history'])
    state['history'][:] = [item for item in state['history'] if item.get('id') not in item_ids]
    deleted_count = original_count - len(state['history'])

    # Persist deletion
    if db is not None:
        db.delete_ids(item_ids, room_id=room_id)

    # Broadcast deletion to all connected clients in this room
    socketio.emit('items_deleted', {'ids': item_ids, 'room_id': room_id}, room=f'room:{room_id}')
    socketio.emit('items_deleted', {'ids': item_ids, 'room_id': room_id}, room=f'admin:{room_id}')
    logger.info(f"[DELETED] room={room_id} {deleted_count} item(s) by {_admin_username(request.sid)}")
    emit('deletion_success', {'deleted_count': deleted_count})

# ──────────────────────────────────────────
# Feature 2: Announcement Broadcast
# ──────────────────────────────────────────
@socketio.on('send_announcement')
def handle_send_announcement(data):
    """Broadcast a short announcement to all connected user clients.

    Payload: {text: str, duration: int (ms, 0 = sticky), type: str}
    """
    if not is_admin(request.sid):
        emit('error', {'message': 'Unauthorized'})
        return

    if not data or not isinstance(data, dict):
        emit('error', {'message': 'Invalid data'})
        return

    raw_text = sanitize_text(data.get('text', ''), max_length=300)
    if not raw_text:
        emit('error', {'message': 'Announcement text is empty'})
        return

    duration = int(data.get('duration', 10000))
    # Clamp: 0 = sticky (no auto-dismiss), otherwise 3 s – 5 min
    if duration != 0:
        duration = max(3000, min(300000, duration))

    ann_type = data.get('type', 'info')
    if ann_type not in ('info', 'warning', 'success', 'danger'):
        ann_type = 'info'

    payload = {
        'text':      raw_text,
        'duration':  duration,
        'type':      ann_type,
        'sender':    _admin_username(request.sid),
        'timestamp': datetime.now().strftime('%H:%M:%S'),
    }
    # Broadcast to clients in the admin's room (skip the sender)
    room_id = _admin_room(request.sid)
    payload['room_id'] = room_id
    socketio.emit('announcement', payload, room=f'room:{room_id}', skip_sid=[request.sid])
    emit('announcement_sent', {'success': True, 'text': raw_text})
    logger.info(f"[ANNOUNCEMENT] room={room_id} '{raw_text[:60]}' by {_admin_username(request.sid)}")


@socketio.on_error_default
def default_error_handler(e):
    """Handle WebSocket errors"""
    security_logger.error(f"WebSocket error from {get_real_ip()}: {str(e)[:200]}")
    disconnect()

# ──────────────────────────────────────────
# Error Handlers
# ──────────────────────────────────────────
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(429)
def ratelimit_handler(e):
    client_key = get_client_key()  # Fixed: use client_key instead of client_ip
    security_logger.warning(f"Rate limit exceeded: {client_key}")
    record_rate_violation(client_key)
    return jsonify({'error': 'Too many requests'}), 429

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal error: {error}")
    return jsonify({'error': 'Internal error'}), 500

# ──────────────────────────────────────────
# Server Start (HTTP or HTTPS)
# ──────────────────────────────────────────
if __name__ == '__main__':
    logger.info("Starting EzySpeechTranslate Backend Server...")

    auth_enabled = get_config('authentication', 'enabled', default=True)
    logger.info(f"Authentication: {'Enabled' if auth_enabled else 'Disabled'}")

    # ── Insecure-default credential check ─────────────────────────
    _INSECURE_DEFAULTS = {
        'jwt_secret':     ('authentication', 'jwt_secret'),
        'admin_password': ('authentication', 'admin_password'),
        'secret_key':     ('server', 'secret_key'),
    }
    _BAD_VALUES = {'secret', 'admin123', 'change-this-secret', 'change-this-secret-key', ''}
    for label, cfg_path in _INSECURE_DEFAULTS.items():
        val = get_config(*cfg_path, default='')
        if str(val).strip().lower() in _BAD_VALUES:
            logger.critical(
                "⚠️  SECURITY WARNING: %s is set to an insecure default value. "
                "Update config/config.yaml before deploying to production!", label
            )

    host = get_config('server', 'host', default='0.0.0.0')
    port = get_config('server', 'port', default=1915)
    use_https = get_config('server', 'use_https', default=True)

    logger.info(f"Protocol: {'HTTPS' if use_https else 'HTTP'}")
    logger.info(f"Security logging: logs/security.log")

    # ── Feature 12: Init SQLite and load persisted history ────────
    if db is not None:
        db_enabled = get_config('database', 'enabled', default=False)
        db_path    = get_config('database', 'path', default='data/translations.db')
        db.init_db(os.path.join(BASE_DIR, db_path), enabled=db_enabled)
        if db_enabled:
            persisted = db.load_all()
            if persisted:
                # Group by room_id and populate per-room state
                for item in persisted:
                    rid = normalize_room_id(item.get('room_id'))
                    item['room_id'] = rid
                    state = _room(rid)
                    state['history'].append(item)
                # Restore per-room ID counters
                for rid, state in _rooms.items():
                    max_id = max((it.get('id', -1) for it in state['history']), default=-1)
                    state['next_id'] = max_id + 1
                room_summary = ", ".join(
                    f"{rid}={len(state['history'])}" for rid, state in _rooms.items()
                )
                logger.info(f"✅ Restored {len(persisted)} translations from DB – rooms: {room_summary}")

    # Initialize Edge TTS voice cache in background (non-blocking)
    if EDGE_TTS_AVAILABLE:
        logger.info("🎙️ Pre-loading Edge TTS voices in background...")
        threading.Thread(target=fetch_edge_tts_voices_in_thread, daemon=True, name="tts-voice-preload").start()

    # Start heartbeat cleanup greenlet
    eventlet.spawn(_heartbeat_cleanup_loop)
    logger.info("🫀 Heartbeat cleanup greenlet started (timeout=45s, interval=15s)")

    for directory in ['logs']:
        os.makedirs(directory, exist_ok=True)

    try:
        listener = eventlet.listen((host, port))

        if use_https:
            cert_file = os.path.join(SSL_DIR, 'cert.pem')
            key_file = os.path.join(SSL_DIR, 'key.pem')

            if not (os.path.exists(cert_file) and os.path.exists(key_file)):
                logger.error("SSL certificate or key not found!")
                print(f"\nGenerate SSL certificates with:\n")
                print(f"  cd {SSL_DIR}")
                print("  openssl req -x509 -newkey rsa:2048 -nodes \\")
                print("    -out cert.pem -keyout key.pem -days 365 \\")
                print('    -subj "/CN=localhost"\n')
                exit(1)

            ssl_listener = eventlet.wrap_ssl(
                listener,
                certfile=cert_file,
                keyfile=key_file,
                server_side=True
            )
            logger.info(f"Server running at https://{host}:{port}")
            eventlet.wsgi.server(ssl_listener, app)
        else:
            logger.info(f"Server running at http://{host}:{port}")
            eventlet.wsgi.server(listener, app)

    except PermissionError:
        logger.error(f"Permission denied on port {port}. Use port > 1024 or run with sudo.")
        exit(1)
    except OSError as e:
        logger.error(f"Failed to bind on port {port}: {e}")
        exit(1)
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
        exit(0)
    except Exception as e:
        logger.error(f"Server failed to start: {e}")
        exit(1)