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
from datetime import datetime, timedelta, timezone
from logging.handlers import RotatingFileHandler
import jwt
from functools import wraps
import hashlib
from app.core import concurrency
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
import queue
import threading
import types
from urllib.parse import unquote_plus
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
    async_mode=concurrency.ASYNC_MODE,
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
# The five tables above change together (an attempt counted, then a block), so
# under this lock: on real threads two failed sign-ins at once could each
# count from the same list and one be lost.
_security_lock = threading.RLock()

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

    with _security_lock:
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
    with _security_lock:
        attempts = failed_login_attempts[client_key]

        # Clean old attempts
        attempts[:] = [t for t in attempts if now - t < LOGIN_ATTEMPT_WINDOW]
        attempts.append(now)

        if len(attempts) < MAX_LOGIN_ATTEMPTS:
            return False
        blocked_clients.add(client_key)
        blocked_since[client_key] = now
    security_logger.critical(f"CLIENT BLOCKED due to failed login attempts: {client_key}")
    return True

def record_rate_violation(client_key=None):
    """Record rate limit violation for a client/session"""
    if client_key is None:
        client_key = get_client_key()

    with _security_lock:
        rate_limit_violations[client_key] += 1
        if rate_limit_violations[client_key] < MAX_RATE_VIOLATIONS:
            return False
        blocked_clients.add(client_key)
        blocked_since[client_key] = datetime.now()
    security_logger.critical(f"CLIENT BLOCKED due to rate limit violations: {client_key}")
    return True

def record_suspicious_activity(reason, client_key=None):
    """Record suspicious activity for a client/session"""
    if client_key is None:
        client_key = get_client_key()

    security_logger.warning(f"Suspicious activity from {client_key}: {reason}")
    with _security_lock:
        suspicious_patterns[client_key] += 1
        if suspicious_patterns[client_key] < MAX_SUSPICIOUS_PATTERNS:
            return False
        blocked_clients.add(client_key)
        blocked_since[client_key] = datetime.now()
    security_logger.critical(f"CLIENT BLOCKED due to suspicious patterns: {client_key}")
    return True

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
# The live state: the rooms (their lines, numbers, listeners, reading
# languages and microphone), who is connected, the API tokens and the
# analytics counters. Anything that changes it, or reads more than one piece
# of it as a whole, holds this lock, and for as short a time as it can: never
# while sending, translating or writing the database. Under eventlet it is a
# green lock and costs nothing; on real threads (docs/EVENTLET_MIGRATION.md)
# it is what keeps a line's number and its place in the room together.
# Reentrant, so a helper that takes it can be called by another that has it.
state_lock = threading.RLock()
_rooms_lock = state_lock

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
    with state_lock:
        return sum(len(s['listeners']) for s in _rooms.values())

def _all_history_count() -> int:
    with state_lock:
        return sum(len(s['history']) for s in _rooms.values())


def rooms_snapshot() -> list:
    """[(room_id, state)] as they are now, to go through without holding the
    lock (a room made meanwhile is simply not in it)."""
    with state_lock:
        return list(_rooms.items())


def history_snapshot(room_id: str) -> list:
    """A room's lines on screen, each a copy: to send, page or search while
    lines go on being added, changed or deleted (sending a line while another
    thread adds its translation would otherwise fail half-way). A line's
    nested parts (its translations, its Bible references) are replaced when
    they change, never changed in place, so a copy's are as they were."""
    state = _room(room_id)
    with state_lock:
        return [dict(it) for it in state['history']]


def update_line(room_id: str, line_id, change=None):
    """The line with this id on a room's screens, changed by change(line)
    under the lock when given; returns a copy of it as it is then, or None
    when it is no longer on the screens."""
    state = _room(room_id)
    with state_lock:
        for it in state['history']:
            if it.get('id') == line_id:
                if change is not None:
                    change(it)
                return dict(it)
    return None


def remove_lines(room_id: str, ids) -> list:
    """Take the lines with these ids off a room's screens; returns the ids
    that were there."""
    wanted = set(ids)
    state = _room(room_id)
    with state_lock:
        gone = [it.get('id') for it in state['history'] if it.get('id') in wanted]
        if gone:
            state['history'][:] = [it for it in state['history'] if it.get('id') not in wanted]
    return gone


def clear_room(room_id: str) -> None:
    """Every line off a room's screens (they stay in the database)."""
    state = _room(room_id)
    with state_lock:
        state['history'].clear()


def count_translation(n: int = 1) -> None:
    """A line put into a language by a provider (not from the cache), for the
    session's analytics."""
    with state_lock:
        S._total_translations += n

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
S._total_translations = 0             # count_translation(): lines a provider translated

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
    admin_name = get_config('authentication', 'admin_username', default='admin')
    raw_accounts = get_config('authentication', 'accounts', default=None)
    if raw_accounts and isinstance(raw_accounts, list):
        for acct in raw_accounts:
            uname = acct.get('username', '')
            # The shipped config lists the one admin as an account, by the
            # default name and with no password of its own. That entry is
            # admin_username, whatever it has been changed to: read as
            # "admin", the console's sign-in and this server disagreed about
            # who was signed in once the name was changed, and the old name
            # went on working here.
            if (uname == 'admin' and admin_name != 'admin'
                    and not acct.get('password') and not acct.get('password_hash')):
                uname = admin_name
            if uname:
                _accounts[uname] = {
                    'verifier':     _account_verifier(acct),
                    'role':         acct.get('role', 'operator'),
                    'channel':      acct.get('channel', 'main'),
                    'display_name': acct.get('display_name', uname),
                }
    # The admin the console signs in as is always an admin here
    if admin_name not in _accounts:
        uname = admin_name
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


# ── Who is connected ────────────────────────────────────────────────────────
# What a socket arriving or leaving changes, each under state_lock as a whole;
# the Socket.IO handlers (sockets.py) do the sending, after.

def listener_joined(room_id: str, client_key: str, sid: str, client_type: str) -> None:
    """A socket is here. A listener's earlier socket (the same phone,
    reloaded) is forgotten, wherever it was, so the phone counts once."""
    room_id = normalize_room_id(room_id)
    state = _room(room_id)
    with state_lock:
        if client_type == 'user':
            for rs in _rooms.values():
                old_sid = rs['listeners'].get(client_key)
                if old_sid and old_sid != sid:
                    logger.info(f"Evicting stale SID {old_sid} for {client_key} (replaced by {sid})")
                    sid_to_client_key.pop(old_sid, None)
                    connected_clients.discard(f"{client_key}:{old_sid}")
                    rs['listeners'].pop(client_key, None)
                    rs['reading'].pop(old_sid, None)
                    _sid_last_seen.pop(old_sid, None)
            state['listeners'][client_key] = sid
            _sid_last_seen[sid] = datetime.now()   # start heartbeat tracking
        if client_type in ('user', 'admin'):
            connected_clients.add(f"{client_key}:{sid}")
        sid_to_client_key[sid] = (client_key, client_type, room_id)
        if client_type == 'user':
            total = sum(len(rs['listeners']) for rs in _rooms.values())
            if total > S._peak_clients:
                S._peak_clients = total


def client_left(sid: str) -> dict:
    """A socket has gone. Returns what it was: {'client_key', 'client_type',
    'room_id', 'released'} (released: the microphone it held, now free), or
    {} for a socket this server did not know."""
    with state_lock:
        mapping = sid_to_client_key.pop(sid, None)
        connected_clients.discard(sid)
        for key in [k for k in connected_clients if k.endswith(f":{sid}")]:
            connected_clients.discard(key)
        admin_sessions.pop(sid, None)
        _sid_last_seen.pop(sid, None)
        for token in [t for t, info in api_session_tokens.items() if info['sid'] == sid]:
            del api_session_tokens[token]
        if not mapping:
            return {}
        client_key, client_type = mapping[0], mapping[1]
        room_id = normalize_room_id(mapping[2] if len(mapping) >= 3 else DEFAULT_ROOM_ID)
        rs = _rooms.get(room_id)
        released = False
        if rs is not None:
            if client_type == 'user':
                # Only if this socket is still the phone's own: a reload's
                # late disconnect must not take the new socket off the count.
                if rs['listeners'].get(client_key) == sid:
                    del rs['listeners'][client_key]
                rs['reading'].pop(sid, None)
            elif client_type == 'admin' and rs.get('recording') and rs['recording'].get('sid') == sid:
                rs['recording'] = None
                released = True
        return {'client_key': client_key, 'client_type': client_type,
                'room_id': room_id, 'released': released}


def heartbeat(sid: str) -> None:
    with state_lock:
        _sid_last_seen[sid] = datetime.now()


def stale_sids(timeout: float) -> list:
    """The listeners' sockets with no heartbeat for `timeout` seconds,
    forgotten by the sweep (the caller then treats each as gone)."""
    now = datetime.now()
    with state_lock:
        stale = [sid for sid, last in _sid_last_seen.items()
                 if (now - last).total_seconds() > timeout]
        for sid in stale:
            _sid_last_seen.pop(sid, None)
        return [sid for sid in stale
                if (sid_to_client_key.get(sid) or (None, None))[1] == 'user']


def set_reading(sid: str, room_id: str, lang) -> tuple:
    """A screen reads in lang now (None: in no other language). Returns
    (before, now), the same when nothing changed."""
    state = _room(room_id)
    with state_lock:
        reading = state['reading']
        previous = reading.get(sid)
        if previous != lang:
            if lang:
                reading[sid] = lang
            else:
                reading.pop(sid, None)
        return previous, lang


def reading_languages(room_id: str) -> set:
    """The languages a room's screens read in now."""
    state = _room(room_id)
    with state_lock:
        return set(state['reading'].values())


def set_admin_session(sid: str, username: str, room_id: str) -> None:
    with state_lock:
        admin_sessions[sid] = {'username': username, 'room_id': normalize_room_id(room_id)}


def claim_recording(room_id: str, username: str, sid, expected=None, force: bool = False):
    """The microphone of a room, for this console, if it is free, already
    this account's, or (force) still held by `expected`, the owner the caller
    saw before checking the password. Returns the owner it took it from ({}
    when it was free or its own), or None when someone else has it: two
    consoles claiming at once never both get it."""
    state = _room(room_id)
    with state_lock:
        current = state.get('recording')
        if current and current.get('username') != username:
            if not force or current is not expected:
                return None
        state['recording'] = {
            'username': username,
            'sid': sid,
            'started_at': datetime.now(timezone.utc).replace(tzinfo=None).isoformat() + 'Z',
        }
        return current if current and current.get('username') != username else {}


def free_recording(room_id: str, username: str):
    """Free a room's microphone if this account has it, or nobody does.
    Returns False when another account holds it."""
    state = _room(room_id)
    with state_lock:
        current = state.get('recording')
        if current and current.get('username') != username:
            return False
        state['recording'] = None
        return True


# ── The database, after the sending ─────────────────────────────────────────
# A line used to wait for its row to be committed before it was sent, and its
# translation for another commit: on a slow disk (a hard disk, an SD card), a
# sync on every commit, and under eventlet, where SQLite does not yield, every
# screen waited with it. Now what changes the lines' rows is put on one queue
# and written by one writer, in the order it was put there, after the sending.
# The transcript and the console's Services read the database; they can be a
# moment behind the screens, never out of order. Before the writer runs (at
# startup, in the tests) a write is made at once, as before.

_db_writes = queue.Queue()
_db_writer_running = False


def db_write(fn, *args) -> None:
    """fn(*args) on the database, after what is being sent, in order."""
    if db is None:
        return
    if not _db_writer_running:
        fn(*args)
        return
    _db_writes.put((fn, args))


def db_flush(timeout: float = 10.0) -> bool:
    """Wait until every write put on the queue so far is made (before
    something that must see them, as deleting a service counts its rows)."""
    if not _db_writer_running:
        return True
    done = threading.Event()
    _db_writes.put((done.set, ()))
    return done.wait(timeout)


def db_writer_loop() -> None:
    """The one writer; the listener server starts it before serving."""
    global _db_writer_running
    _db_writer_running = True
    try:
        while True:
            job = _db_writes.get()
            if job is None:                  # stop (the tests)
                return
            fn, args = job
            try:
                fn(*args)
            except Exception as exc:         # a write lost is logged, not fatal
                logger.warning(f"Database write {getattr(fn, '__name__', fn)} failed: {exc}")
    finally:
        _db_writer_running = False


def _persist_line(room_id: str, line_id, fallback: dict) -> None:
    """A line's row as the line is when it is written: with the translations
    and references it has by then. One taken off the screens meanwhile (a
    clear) is written as it was when it was said."""
    db.persist(update_line(room_id, line_id) or fallback)


def add_translation(data, room_id: str = DEFAULT_ROOM_ID, on_numbered=None):
    """Add a line to a room: its number, its place, the session's counts,
    then its Bible references, then its row in the database (after the
    sending, see db_write). Returns a copy of the line to send: data itself
    is the room's from here on, changed under state_lock.

    on_numbered(line), when given, is called as soon as the line has its
    number, before the references are looked for: what starts translating
    it, so a translation does not wait for anything it does not need."""
    room_id = normalize_room_id(room_id)
    state = _room(room_id)

    # Tag the record with its room so DB / clients can filter
    data['room_id'] = room_id
    # When it was said, with the date: what a service's transcript is
    # gathered by. An imported line is dated by when it was imported.
    data.setdefault('at', local_now().isoformat(timespec='seconds'))

    # Its number and its place in the room, together: two lines said at once
    # in one room never share a number, and the room's lines stay in the
    # order they were numbered.
    trimmed = False
    with state_lock:
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
        state['history'].append(data)

        # ── Session analytics ──────────────────────────────────────
        if ANALYTICS_ENABLED:
            text_for_stats = data.get('corrected') or data.get('original') or ''
            S._total_words    += len(text_for_stats.split())
            S._session_lines  += 1
            S._total_bible_refs += len(data.get('bible_refs') or [])

        # Limit history size (per room)
        if len(state['history']) > MAX_HISTORY_SIZE:
            state['history'][:] = state['history'][-MAX_HISTORY_SIZE:]
            trimmed = True
        next_id = state['next_id']
        line = dict(data)

    if on_numbered is not None:
        on_numbered(line)

    # Bible reference detection — opt-in via config.
    if bible_detector is not None and 'bible_refs' not in line:
        try:
            scan_text = line.get('corrected') or line.get('original') or ''
            results = bible_detector.detect_and_lookup(scan_text)
        except Exception as e:
            results = None
            logger.warning(f"Bible detection failed: {e}")
        if results:
            def refer(item):
                item['bible_refs'] = results
            line = update_line(room_id, line['id'], refer) or dict(line, bible_refs=results)
            if ANALYTICS_ENABLED:
                with state_lock:
                    S._total_bible_refs += len(results)

    # ── SQLite persistence, after the sending ──────────────────────
    db_write(_persist_line, room_id, line['id'], line)

    if trimmed:
        logger.debug(
            f"History trimmed to {MAX_HISTORY_SIZE} items for room '{room_id}'. "
            f"Total IDs generated: {next_id}"
        )
    return line


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
    wanted = {lang for lang in reading_languages(room_id)
              if _language_base(lang) != spoken}
    if not wanted:
        return
    service = get_translation_service()

    def one(lang):
        try:
            ok, translated, cached = service.translate(text, lang, glossary=_get_glossary_for(room_id, lang))
        except Exception as exc:                 # never fatal: the screen asks itself
            logger.warning(f"Push translation to {lang} failed: {exc}")
            ok, translated, cached = False, None, False
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
        def keep(line):
            if (line.get('corrected') or line.get('original') or '') == text:
                line['translations'] = dict(line.get('translations') or {},
                                            **{lang: {'source': text, 'text': translated}})
        if item.get('id') is not None:
            update_line(room_id, item['id'], keep)
        socketio.emit('line_translated', {
            'id': item.get('id'), 'room_id': room_id, 'lang': lang,
            'source': text, 'translated': translated,
        }, room=_reading_room(room_id, lang))
        if not cached:
            count_translation()
        if db is not None and item.get('id') is not None:
            db_write(db.save_line_translation, room_id, item['id'], lang, text, translated)

    concurrency.run_all(one, sorted(wanted), 8)


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

    # Check for SQL injection patterns. (Every query here binds its values,
    # so this is a tripwire, not the protection; a bare '--' is in too much
    # that is innocent to be one.)
    sql_patterns = ['union select', 'drop table', 'insert into', ';--']
    # Decoded: a space comes as %20 or +, and undecoded none of these matched.
    query_string = unquote_plus(request.query_string.decode('utf-8', 'ignore')).lower()
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
    # Hex, not URL-safe base64: that has '-', and a token with '--' in it
    # was refused below as an SQL comment, so about one page in a hundred
    # opened with no lines.
    return secrets.token_hex(32)

def create_api_token(sid):
    """Create a new API token for this WebSocket session"""
    token = generate_api_session_token()
    with state_lock:
        api_session_tokens[token] = {
            'sid': sid,
            'created_at': datetime.now(),
            'expires_at': datetime.now() + timedelta(hours=24)  # Valid for 24 hours
        }
    return token

def validate_api_token(token):
    """Validate and return session info if token is valid"""
    with state_lock:
        session_info = api_session_tokens.get(token)
        if session_info is None:
            return None
        # Check if expired
        if datetime.now() > session_info['expires_at']:
            api_session_tokens.pop(token, None)
            return None
        return session_info


def drop_api_tokens(sid) -> None:
    """The tokens a socket was given, when it goes."""
    with state_lock:
        for token in [t for t, info in api_session_tokens.items() if info['sid'] == sid]:
            del api_session_tokens[token]

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
