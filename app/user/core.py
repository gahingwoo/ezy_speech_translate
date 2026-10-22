"""The listener server's shared part: configuration, the Flask app and its
Socket.IO, security, the rooms and what they hold, sign-in, and the helpers
every route uses. server.py patches eventlet, imports this, then the modules
that add routes to it:

    routes_pages.py      the pages, history, languages and Scripture
    routes_translate.py  the translation API
    routes_admin.py      session figures, rooms, glossary, the recording lock, config.yaml
    sockets.py           the live events, and announcements

They share one namespace (each does `from app.user.core import *`), so a name
reassigned at run time lives on S instead, where every module sees the change.

Copyright (C) 2025-2026 Ga Hing Woo (Jiaxing Hu)

This file is part of EzySpeech.

EzySpeech is free software: you can redistribute it and/or modify it under
the terms of the GNU Affero General Public License as published by the Free
Software Foundation, either version 3 of the License, or (at your option)
any later version. Two additional terms apply under section 7: the author
attribution in the about dialog must be preserved, and no trademark rights
are granted. See LICENSE and TRADEMARK.md.

EzySpeech is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE. See the GNU Affero General Public License for more
details.
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
# Everything, sockets included. This server is one thread: a call that waits
# on a socket eventlet has not patched waits with the whole server, so every
# translation, Bible lookup and admin push queued behind the slowest of them,
# and live captions stopped for every listener while one was answered. Eight
# listeners asking at once took seven seconds where they now take under two.
#
# Sockets were left unpatched for an in-process asyncio Edge TTS client. That
# client, and cloud speech with it, is gone; nothing here needs the native
# modules any more.
import secrets
import hmac
import re
from collections import defaultdict
import time
import threading
import types
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def local_now() -> datetime:
    """Now, in the church's own time. A container's clock is UTC unless TZ is
    set and the zone data is there to read it; the installer sets TZ to the
    host's zone, and `tzdata` (in requirements.txt) is the zone data where the
    image has none. Without it Sunday morning in Auckland was Saturday."""
    tz = os.environ.get('TZ', '').lstrip(':')
    if tz:
        try:
            return datetime.now(ZoneInfo(tz)).replace(tzinfo=None)
        except (ZoneInfoNotFoundError, ValueError):
            pass
    return datetime.now()

from app.services.translation import get_translation_service  # noqa: E402

# Counters and caches that are reassigned, not mutated: on this one object,
# so the modules split from this file all see the same values.
S = types.SimpleNamespace()

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
    from .oem_manager import init_oem_config, favicon_from_oem
except ImportError:
    # Fallback for direct script execution
    from app.oem_manager import init_oem_config, favicon_from_oem

# Now import Flask and other app modules
from flask import Flask, render_template, request, jsonify, session, Response, redirect
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
from app.core.config import get_config, config_loader, ensure_runtime_secret  # noqa: E402

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
from app.core.static_version import make_static_url
from app.core.compress import install as install_compression

app = Flask(__name__,
            template_folder=TEMPLATE_DIR,
            static_folder=STATIC_DIR,
            static_url_path='/static')
# Templates address static files through static_url(), which appends a hash of
# the file's contents so a changed stylesheet is never served from cache.
app.jinja_env.globals["static_url"] = make_static_url(STATIC_DIR)
from app.core.version import VERSION as APP_VERSION  # noqa: E402
app.jinja_env.globals["app_version"] = APP_VERSION
# First, so its hook runs last: what goes out is compressed after every
# other hook has had its say about the headers.
install_compression(app)

# Secure configuration — resolve (and persist) a strong Flask secret key.
# Existing configured keys are used unchanged; missing/insecure ones are
# generated and stored in secrets.key so they survive restarts.
secret_key = ensure_runtime_secret('server_secret_key', ('server', 'secret_key'))

# Resolve (and persist) the JWT signing secret. Shared with the admin server
# via secrets.key; never falls back to a guessable default.
JWT_SECRET = ensure_runtime_secret('jwt_secret', ('authentication', 'jwt_secret'))

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
    logger.info("OEM configuration initialized successfully")
except Exception as e:
    logger.warning(f"OEM configuration initialization failed: {e}")

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
S.BIBLE_SOURCE_TRANSLATION = get_config('features', 'bible_detection', 'source_translation', default='WEB')
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
            source_translation=S.BIBLE_SOURCE_TRANSLATION,
            target_translation=BIBLE_TARGET_TRANSLATION,
            max_verses=BIBLE_MAX_VERSES,
            api_timeout=BIBLE_API_TIMEOUT,
        )
        bible_detector = _bible_mod
        # The wording index loads on first use, and first use was the first
        # line of the sermon: 70ms with every listener's feed held behind it.
        _bible_mod.detect_and_lookup("the Lord is my shepherd")
        logging.getLogger("bible").info(
            f"Bible detection enabled (source={S.BIBLE_SOURCE_TRANSLATION}"
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
    return _decode_jwt(token, JWT_SECRET)

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
                    # After every line the room has kept, so a new line never
                    # takes the number of one already in a transcript.
                    'next_id': db.next_id(rid) if db is not None else 0,
                    'display_name': rid.replace('_', ' ').title() if rid != DEFAULT_ROOM_ID else 'Main',
                    'recording': None,   # None or {'username': str, 'sid': str, 'started_at': iso}
                    'reading': {},       # sid -> the language that screen reads in
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
S._session_start_time = datetime.now()
S._peak_clients       = 0             # peak concurrent user-type listeners
S._total_words        = 0             # running word count across all final transcriptions
S._session_lines      = 0             # lines this service, as against every line ever
S._total_bible_refs   = 0             # running count of bible references detected
S._total_translations = 0             # incremented by /api/translate

ANALYTICS_ENABLED = get_config('features', 'session_analytics', 'enabled', default=True)

# ──────────────────────────────────────────
# Multi-account auth (Feature 6)
# Build a dict  username -> {verifier, role, channel, display_name}
# Falls back to the single admin_username if there is no accounts list.
#
# An account is checked against a PBKDF2 verifier, never a password: the admin
# one from secrets.key, or an account's own password_hash. An account given a
# plain `password` in config.yaml is hashed here and warned about. There is no
# default any more: with nothing configured, nobody signs in, rather than
# anyone who knows "admin123".
# ──────────────────────────────────────────
_accounts: dict = {}

from app.auth.passwords import (  # noqa: E402
    verify as _verify_password, make_verifier as _make_verifier,
    client_hash as _client_hash, is_verifier as _is_verifier,
)


def _account_verifier(acct: dict):
    if _is_verifier(acct.get('password_hash')):
        return acct['password_hash']
    if acct.get('password'):
        security_logger.warning(
            "Account '%s' has a plain-text password in config.yaml; it works, "
            "but give it a password_hash instead", acct.get('username'))
        return _make_verifier(_client_hash(acct['password']))
    return get_config('authentication', 'admin_password_hash', default=None)


def _build_accounts():
    raw_accounts = get_config('authentication', 'accounts', default=None)
    if raw_accounts and isinstance(raw_accounts, list):
        for acct in raw_accounts:
            uname = acct.get('username', '')
            if uname:
                _accounts[uname] = {
                    'verifier':     _account_verifier(acct),
                    'role':         acct.get('role', 'operator'),
                    'channel':      acct.get('channel', 'main'),
                    'display_name': acct.get('display_name', uname),
                }
    # Always ensure the legacy admin account is present
    if not _accounts:
        uname = get_config('authentication', 'admin_username', default='admin')
        _accounts[uname] = {
            'verifier':     get_config('authentication', 'admin_password_hash', default=None),
            'role':         'admin',
            'channel':      'main',
            'display_name': uname,
        }
    for uname, acct in _accounts.items():
        if not acct['verifier']:
            logger.critical(
                "No password is set for '%s', so it cannot sign in. Set one with "
                "python -m app.auth.set_password  (in Docker: ezyspeech password).", uname)

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
    # When it was said, with the date: what a service's transcript is
    # gathered by. An imported line is dated by when it was imported.
    data.setdefault('at', local_now().isoformat(timespec='seconds'))

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
        S._total_words    += len(text_for_stats.split())
        S._session_lines  += 1
        S._total_bible_refs += len(data.get('bible_refs') or [])

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


# ── Translating once, for everyone ──────────────────────────────────────────
# Every listener used to ask for its own translation of every line: fifty
# phones, fifty requests the moment a sentence ended, each a round trip before
# its reader saw anything. The server already knew the line first. Now each
# screen says which language it reads, and the server translates a line once
# per language present and sends the result to the screens reading it; a
# screen that hears nothing in time still asks, as before.

_READING_LANG = re.compile(r'^[a-z]{2,3}(-[a-z0-9]{2,8})?$')


def _language_base(code: str) -> str:
    """Same rule as sameLanguage() in user.js: Chinese splits by script and
    Cantonese is its own language; everything else by its first subtag."""
    c = (code or '').lower()
    if c.startswith('yue'):
        return 'yue'
    if c.startswith('zh-tw') or '-hant' in c:
        return 'zh-tw'
    if c.startswith('zh'):
        return 'zh'
    return c.split('-')[0]


def _reading_room(room_id: str, lang: str) -> str:
    return f'room:{room_id}:lang:{lang}'


def _push_translations(room_id: str, item: dict) -> None:
    """Translate one line into every language its room is reading, at once,
    and send each to the screens reading it. Runs in its own greenlet."""
    text = item.get('corrected') or item.get('original') or ''
    if not text:
        return
    spoken = _language_base(item.get('source_language') or 'en')
    wanted = {lang for lang in _room(room_id).get('reading', {}).values()
              if _language_base(lang) != spoken}
    if not wanted:
        return
    service = get_translation_service()

    def one(lang):
        try:
            ok, translated, _ = service.translate(text, lang, glossary=_get_glossary_for(room_id, lang))
        except Exception as exc:                 # never fatal: the screen asks itself
            logger.warning(f"Push translation to {lang} failed: {exc}")
            ok, translated = False, None
        if not ok or not translated:
            # Said at once, so the screens stop waiting and ask for themselves
            # (the browser can still reach the service when this server cannot).
            socketio.emit('line_translated', {
                'id': item.get('id'), 'room_id': room_id, 'lang': lang,
                'source': text, 'translated': None,
            }, room=_reading_room(room_id, lang))
            return
        # Kept on the line, so a screen that loads it later has it already,
        # and in the database, so the service's transcript has it too.
        item.setdefault('translations', {})[lang] = {'source': text, 'text': translated}
        if db is not None and item.get('id') is not None:
            db.save_line_translation(room_id, item['id'], lang, text, translated)
        socketio.emit('line_translated', {
            'id': item.get('id'), 'room_id': room_id, 'lang': lang,
            'source': text, 'translated': translated,
        }, room=_reading_room(room_id, lang))

    pool = eventlet.GreenPool(8)
    for lang in sorted(wanted):
        pool.spawn_n(one, lang)
    pool.waitall()


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
    """Add security headers and set client ID cookie.

    CSP is only injected when Talisman has not already set it (HTTPS mode).
    This prevents the dynamically-built CSP from silently overwriting the
    stricter policy that Talisman configures for HTTPS deployments.
    """
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'

    # Only set a dynamic CSP if one hasn't been set yet (e.g. by Talisman for HTTPS).
    if 'Content-Security-Policy' not in response.headers:
        external_url = get_config('server', 'external_url', default='')

        connect_src_list = ["'self'", "http://localhost:*", "http://127.0.0.1:*",
                            "ws://localhost:*", "ws://127.0.0.1:*",
                            "https://cdnjs.cloudflare.com", "https://translate.googleapis.com",
                            "https://fonts.googleapis.com", "https://fonts.gstatic.com"]

        if external_url:
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
            # Auth disabled: provide an empty user dict so routes that call
            # request.user.get(...) do not raise AttributeError.
            if not hasattr(request, 'user'):
                request.user = {}
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
            # Auth disabled: provide an empty user dict so routes that call
            # request.user.get(...) do not raise AttributeError.
            if not hasattr(request, 'user'):
                request.user = {}
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
        
        # Files carry their own ETag. This used to call set_etag() with no tag,
        # which raises, so a missing file was answered with a 500, not a 404.
        if response.status_code == 200 and not response.headers.get('ETag'):
            response.add_etag()
    
    return response

# Static file versioning lives in app/core/static_version.py; the URL is
# built by static_url() in the templates.


# Everything above, for the route modules' `from app.user.core import *`,
# underscored helpers included: they were one file, and share one namespace.
__all__ = [_n for _n in dir() if not _n.startswith('__')]
