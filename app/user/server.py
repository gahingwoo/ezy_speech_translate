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
import asyncio
import io
import subprocess

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
# Secure Configuration Loader
# ──────────────────────────────────────────
sys.path.insert(0, BASE_DIR)  # Add project root to path for secure_loader import

try:
    from secure_loader import SecureConfig
    config_loader = SecureConfig(os.path.join(CONFIG_DIR, 'config.yaml'))

    def get_config(*keys, default=None):
        return config_loader.get(*keys, default=default)

    logging.getLogger("config_loader").info("✓ Loaded encrypted configuration via secure_loader")

except ImportError as e:
    logging.getLogger("config_loader").warning(f"Secure loader not found ({e}), falling back to YAML config")

    class ConfigFallback:
        def __init__(self, config_path='config/config.yaml'):
            try:
                with open(config_path, 'r') as f:
                    self.data = yaml.safe_load(f) or {}
            except FileNotFoundError:
                print(f"Error: Configuration file not found at {config_path}")
                self.data = {}

        def get(self, *keys, default=None):
            val = self.data
            for key in keys:
                if isinstance(val, dict):
                    val = val.get(key)
                    if val is None:
                        return default
                else:
                    return default
            return val if val is not None else default

    config_loader = ConfigFallback('config/config.yaml')

    def get_config(*keys, default=None):
        return config_loader.get(*keys, default=default)

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
    ping_timeout=get_config('advanced', 'websocket', 'ping_timeout', default=60),
    ping_interval=get_config('advanced', 'websocket', 'ping_interval', default=25),
    max_http_buffer_size=get_config('advanced', 'websocket', 'max_message_size', default=1048576)
)

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
# Security: Input Validation
# ──────────────────────────────────────────
def sanitize_text(text, max_length=5000):
    """Sanitize text input"""
    if not text or not isinstance(text, str):
        return ""

    # Remove control characters
    text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)

    # Limit length
    text = text[:max_length]

    # Remove dangerous HTML/JS patterns
    dangerous = [
        r'<script[^>]*>.*?</script>',
        r'javascript:',
        r'on\w+\s*=',
        r'<iframe',
        r'<embed',
        r'<object>',
        r'data:text/html'
    ]

    for pattern in dangerous:
        if re.search(pattern, text, re.IGNORECASE):
            security_logger.warning(f"Dangerous pattern detected from {get_real_ip()}")
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)

    return text.strip()

def validate_jwt_token(token):
    """Validate JWT token securely"""
    if not token:
        return None

    try:
        decoded = jwt.decode(
            token,
            get_config('authentication', 'jwt_secret', default='secret'),
            algorithms=['HS256'],
            options={"verify_exp": True}
        )
        return decoded
    except jwt.ExpiredSignatureError:
        security_logger.info("Expired token used")
        return None
    except jwt.InvalidTokenError:
        security_logger.warning(f"Invalid token from {get_real_ip()}")
        return None

# ──────────────────────────────────────────
# In-memory Storage with Limits from Config
# ──────────────────────────────────────────
MAX_HISTORY_SIZE = get_config('advanced', 'performance', 'cache_size', default=1000)
translations_history = []
next_translation_id = 0  # Global ID counter (never resets, always increments)
connected_clients = set()          # all socket SIDs
listener_clients = {}              # client_key -> latest SID  (user clients only, 1 per user)
admin_sessions = {}                 # sid -> username (admin sessions)
api_session_tokens = {}             # Maps token -> {sid, created_at, expires_at}
sid_to_client_key = {}              # Mapping: sid -> (client_key, client_type) for cleanup on disconnect

def add_translation(data):
    """Add translation with size limit"""
    global translations_history, next_translation_id

    # Assign stable ID (independent of history size)
    if 'id' not in data or data['id'] is None:
        data['id'] = next_translation_id
        next_translation_id += 1

    translations_history.append(data)

    # Limit history size - keep only the most recent entries
    if len(translations_history) > MAX_HISTORY_SIZE:
        translations_history = translations_history[-MAX_HISTORY_SIZE:]
        logger.info(f"History trimmed to {MAX_HISTORY_SIZE} items. Total IDs generated: {next_translation_id}")

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

        # Verify it's the admin user
        admin_username = get_config('authentication', 'admin_username', default='admin')
        if decoded.get('username') != admin_username:
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
    return render_template('user.html')

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
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'success': False, 'error': 'Missing credentials'}), 400

    # Rate limiting check
    if len(username) > 100 or len(password) > 100:
        record_suspicious_activity("Oversized credentials", client_key)
        return jsonify({'success': False, 'error': 'Invalid credentials'}), 400

    # Verify credentials
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    stored_password_hash = hashlib.sha256(
        get_config('authentication', 'admin_password', default='admin123').encode()
    ).hexdigest()

    if (username == get_config('authentication', 'admin_username', default='admin') and
            password_hash == stored_password_hash):

        # Generate secure token
        token = jwt.encode(
            {
                'username': username,
                'exp': datetime.utcnow() + timedelta(
                    seconds=get_config('authentication', 'session_timeout', default=7200)
                ),
                'iat': datetime.utcnow(),
                'jti': secrets.token_hex(16)
            },
            get_config('authentication', 'jwt_secret', default='secret'),
            algorithm='HS256'
        )

        logger.info(f"✓ Admin login successful: {username} from {client_key}")
        return jsonify({
            'success': True,
            'token': token,
            'username': username
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
    
    # Validate parameters
    offset = max(0, min(offset, len(translations_history)))
    limit = max(1, min(limit, 1000))  # Max 1000 items per request
    
    # Get total count
    total = len(translations_history)
    
    # Get slice of translations (newest first)
    start = max(0, total - offset - limit)
    end = max(0, total - offset)
    translations_slice = translations_history[start:end]
    translations_slice.reverse()  # Most recent first
    
    has_more = (offset + limit) < total
    
    return jsonify({
        'translations': translations_slice,
        'offset': offset,
        'limit': limit,
        'total': total,
        'has_more': has_more
    })

@app.route('/api/translations/clear', methods=['POST'])
@limiter.limit("10 per minute")
@require_auth
@check_client_access
def clear_translations():
    """Clear translation history"""
    global translations_history, next_translation_id
    translations_history = []
    next_translation_id = 0  # Reset ID counter when clearing history
    socketio.emit('history_cleared')
    logger.info(f"Translation history cleared by {request.user.get('username')}")
    return jsonify({'success': True})

@app.route('/favicon.ico', methods=['GET'])
def favicon():
    """Favicon endpoint - return empty response to prevent 404"""
    return '', 204

@app.route('/api/health', methods=['GET'])
@limiter.limit("120 per minute")
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'clients': len(listener_clients),
        'translations': len(translations_history)
    })

@app.route('/api/history', methods=['GET'])
@limiter.limit("60 per minute")
@require_auth
def get_history():
    """Get all transcription history"""
    return jsonify({
        'success': True,
        'translations': translations_history,
        'count': len(translations_history)
    })

@app.route('/api/export/<export_format>', methods=['GET'])
@limiter.limit("10 per minute")
@require_auth
@check_client_access
def export_translations(export_format):
    """Export translations with validation"""
    allowed_formats = ['json', 'txt', 'csv', 'srt']

    if export_format not in allowed_formats:
        return jsonify({'error': f'Unsupported format'}), 400

    # Limit export size
    max_export = 5000
    export_data = translations_history[-max_export:]

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
try:
    from .translation_service import get_translation_service
except ImportError:
    from app.translation_service import get_translation_service

# Import Edge TTS for cloud-based text-to-speech
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
    
    # Synthesis request cache (hash -> audio_data) to avoid duplicate requests
    SYNTHESIS_REQUEST_CACHE = {}
    SYNTHESIS_CACHE_TIME = {}
    SYNTHESIS_CACHE_TTL = 3600  # 1 hour cache for identical requests
    
    # Client rate limiting tracking
    CLIENT_SYNTHESIS_REQUESTS = defaultdict(list)  # client_id -> [(timestamp, request_hash), ...]
    CLIENT_SYNTHESIS_LIMIT = 100  # Max synthesis requests per client per hour
    
except ImportError:
    logger.warning("edge-tts not installed. Cloud TTS will not be available. Install with: pip install edge-tts")
    EDGE_TTS_AVAILABLE = False
    EDGE_TTS_VOICES_CACHE = None
    EDGE_TTS_VOICES_CACHE_TIME = None
    VALID_EDGE_TTS_LANGS = set()
    SYNTHESIS_REQUEST_CACHE = {}
    SYNTHESIS_CACHE_TIME = {}
    CLIENT_SYNTHESIS_REQUESTS = defaultdict(list)

# ✅ Ensure all TTS-related globals are defined (fail-safe)
# This prevents AttributeError if Edge TTS import fails partially
if 'EDGE_TTS_AVAILABLE' not in globals():
    EDGE_TTS_AVAILABLE = False
if 'SYNTHESIS_REQUEST_CACHE' not in globals():
    SYNTHESIS_REQUEST_CACHE = {}
if 'SYNTHESIS_CACHE_TIME' not in globals():
    SYNTHESIS_CACHE_TIME = {}
if 'SYNTHESIS_CACHE_TTL' not in globals():
    SYNTHESIS_CACHE_TTL = 3600
if 'CLIENT_SYNTHESIS_REQUESTS' not in globals():
    CLIENT_SYNTHESIS_REQUESTS = defaultdict(list)
if 'EDGE_TTS_VOICES_CACHE' not in globals():
    EDGE_TTS_VOICES_CACHE = None
if 'EDGE_TTS_VOICES_CACHE_TIME' not in globals():
    EDGE_TTS_VOICES_CACHE_TIME = None

logger.info(f"🔍 Edge TTS initialized - EDGE_TTS_AVAILABLE={EDGE_TTS_AVAILABLE}, Cache size: {len(SYNTHESIS_REQUEST_CACHE)} items")

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
        
        # Perform translation - now returns (success, translated, from_cache)
        success, translated, from_cache = translation_service.translate(text, target_lang)
        
        return jsonify({
            'success': success,
            'translated': translated,
            'original': text,
            'target_lang': target_lang,
            'source_lang': 'auto',
            'cached': from_cache,
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
            
            success, translated, from_cache = translation_service.translate(sanitized, target_lang)
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
            'count': len(results)
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
    """Fetch Edge TTS voices using subprocess (avoids eventlet/asyncio conflicts)"""
    global EDGE_TTS_VOICES_CACHE, EDGE_TTS_VOICES_CACHE_TIME
    
    if not EDGE_TTS_AVAILABLE:
        logger.warning("⚠️ Edge TTS not available, skipping voice fetch")
        return []
    
    try:
        logger.info("⏳ Fetching Edge TTS voices via subprocess...")
        
        # Use subprocess to avoid eventlet's monkeypatch conflicts
        import subprocess
        import json
        
        code = """
import asyncio
import edge_tts
import sys
import json

async def fetch():
    try:
        voices = await edge_tts.list_voices()
        return voices
    except Exception as e:
        print(f"ERROR in subprocess: {str(e)}", file=sys.stderr)
        raise

voices = asyncio.run(fetch())
print(json.dumps(voices))
"""
        
        # ✅ Use sys.executable to ensure we use the correct Python environment (venv)
        # instead of hardcoded 'python3' which would use system Python
        result = subprocess.run(
            [sys.executable, '-c', code],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode != 0:
            logger.error(f"❌ Edge TTS subprocess failed with return code {result.returncode}")
            if result.stderr:
                logger.error(f"   stderr: {result.stderr[:500]}")  # Log first 500 chars
            return []
        
        if not result.stdout or not result.stdout.strip():
            logger.error("❌ Edge TTS subprocess returned empty output")
            return []
        
        # Parse JSON from subprocess output
        import json
        try:
            voices_list = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            logger.error(f"❌ Failed to parse Edge TTS JSON response: {e}")
            logger.error(f"   stdout (first 500 chars): {result.stdout[:500]}")
            return []
        
        if not voices_list or len(voices_list) == 0:
            logger.warning("⚠️ No voices returned from Edge TTS subprocess")
            return []
        
        logger.info(f"✅ Successfully cached {len(voices_list)} Edge TTS voices via subprocess")
        EDGE_TTS_VOICES_CACHE = voices_list
        EDGE_TTS_VOICES_CACHE_TIME = datetime.now()
        return voices_list
            
    except subprocess.TimeoutExpired:
        logger.error("❌ Edge TTS subprocess timeout (60 seconds exceeded)")
        return []
    except Exception as e:
        logger.error(f"❌ Error fetching Edge TTS voices: {e}", exc_info=True)
        return []

def get_cached_edge_tts_voices():
    """Get Edge TTS voices from cache, or fetch if not cached yet"""
    global EDGE_TTS_VOICES_CACHE, EDGE_TTS_VOICES_CACHE_TIME
    
    if not EDGE_TTS_AVAILABLE:
        return []
    
    # Return cached voices if available and fresh (cache for 1 hour)
    if EDGE_TTS_VOICES_CACHE is not None:
        if EDGE_TTS_VOICES_CACHE_TIME and (datetime.now() - EDGE_TTS_VOICES_CACHE_TIME).seconds < 3600:
            return EDGE_TTS_VOICES_CACHE
    
    # If not cached, fetch in a background thread
    if EDGE_TTS_VOICES_CACHE is None and EDGE_TTS_VOICES_CACHE_TIME is None:
        logger.info("📥 Fetching Edge TTS voices for the first time in background thread...")
        import threading
        thread = threading.Thread(target=fetch_edge_tts_voices_in_thread, daemon=True)
        thread.start()
        # Return empty list on first request while loading
        return []
    
    return EDGE_TTS_VOICES_CACHE or []

# ──────────────────────────────────────────
# Edge TTS Validation and Rate Limiting
# ──────────────────────────────────────────

def validate_language_code(lang_code):
    """
    Validate if the language code is supported by Edge TTS.
    
    Args:
        lang_code: Language code (e.g., 'zh-CN', 'en-US')
    
    Returns:
        (is_valid, error_message)
    """
    if not lang_code or not isinstance(lang_code, str):
        return False, "Invalid language code format"
    
    # Check against known valid language codes
    if lang_code not in VALID_EDGE_TTS_LANGS:
        # Try to find closest match (e.g., 'zh' -> 'zh-CN')
        base_lang = lang_code.split('-')[0]
        matching = [l for l in VALID_EDGE_TTS_LANGS if l.startswith(base_lang + '-')]
        if matching:
            return True, f"Language code '{lang_code}' not found. Using '{matching[0]}' instead."
        return False, f"Unsupported language code: '{lang_code}'. Run 'edge-tts --list-voices' to see supported languages."
    
    return True, None

def validate_voice_name(voice_name, available_voices):
    """
    Validate if the voice name is available and safe.
    
    Args:
        voice_name: Voice name (e.g., 'zh-CN-XiaoxiuNeural', 'zh-CN-liaoning-XiaobeiNeural')
        available_voices: List of available voices from cache
    
    Returns:
        (is_valid, error_message, validated_voice_name)
    """
    if not voice_name or not isinstance(voice_name, str):
        return True, None, None  # None voice allowed (uses default)
    
    # Check for malicious patterns
    # Support regional variants like zh-CN-liaoning-XiaobeiNeural and zh-CN-shaanxi-XiaoniNeural
    if not re.match(r'^[a-z]{2}-[A-Z]{2}(-[a-zA-Z0-9]+)*Neural$', voice_name):
        return False, f"Invalid voice format: {voice_name}", None
    
    # Verify voice exists in available list if we have it
    if available_voices:
        voice_exists = any(v.get('ShortName') == voice_name for v in available_voices)
        if not voice_exists:
            return False, f"Voice '{voice_name}' is not available", None
    
    return True, None, voice_name

def check_client_synthesis_limit(client_id, request_hash):
    """
    Check if client has exceeded synthesis rate limit (100 per hour).
    Track requests for abuse detection.
    
    Args:
        client_id: Unique client identifier
        request_hash: Hash of the synthesis request
    
    Returns:
        (is_allowed, error_message, current_count)
    """
    global CLIENT_SYNTHESIS_REQUESTS
    
    current_time = time.time()
    one_hour_ago = current_time - 3600
    
    # Clean up old entries
    if client_id in CLIENT_SYNTHESIS_REQUESTS:
        CLIENT_SYNTHESIS_REQUESTS[client_id] = [
            (ts, rh) for ts, rh in CLIENT_SYNTHESIS_REQUESTS[client_id]
            if ts > one_hour_ago
        ]
    
    # Count current requests
    current_count = len(CLIENT_SYNTHESIS_REQUESTS[client_id])
    
    if current_count >= CLIENT_SYNTHESIS_LIMIT:
        logger.warning(f"⚠️ Client {client_id} exceeded synthesis limit ({current_count}/{CLIENT_SYNTHESIS_LIMIT} requests in last hour)")
        return False, f"Rate limit exceeded: {current_count}/{CLIENT_SYNTHESIS_LIMIT} synthesis requests per hour", current_count
    
    # Record this request
    CLIENT_SYNTHESIS_REQUESTS[client_id].append((current_time, request_hash))
    
    return True, None, current_count + 1

def get_synthesis_cache_key(text, voice):
    """
    Generate a stable cache key for synthesis requests.
    This helps avoid duplicate synthesis of identical content.
    """
    cache_input = f"{text}|{voice or 'default'}"
    return hashlib.sha256(cache_input.encode()).hexdigest()

def compress_audio_to_low_quality(audio_data):
    """
    Compress audio to low quality (16kHz mono MP3) to save memory.
    Uses ffmpeg if available, otherwise returns original audio.
    
    Args:
        audio_data: Raw MP3 audio bytes
    
    Returns:
        Compressed audio data (bytes)
    """
    # Validate input
    if not audio_data or len(audio_data) == 0:
        logger.warning("⚠️ Empty audio data passed to compression")
        return audio_data
    
    try:
        original_size_kb = len(audio_data) / 1024
        logger.info(f"🔄 Starting audio compression: {original_size_kb:.1f}KB → 16kHz mono MP3")
        
        # Check if ffmpeg is available
        result = subprocess.run(['which', 'ffmpeg'], capture_output=True)
        if result.returncode != 0:
            # ffmpeg not available, return original
            logger.info("⚠️ ffmpeg not available, using original audio quality")
            return audio_data
        
        # Write input audio to temporary file
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as input_file:
            input_file.write(audio_data)
            input_path = input_file.name
        
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as output_file:
            output_path = output_file.name
        
        try:
            # Compress to 64kbps mono MP3 (reduces size by ~70%)
            compress_cmd = [
                'ffmpeg',
                '-i', input_path,
                '-q:a', '9',  # Lowest quality (-q range: 0-9, 9 is lowest)
                '-ac', '1',   # Convert to mono
                '-ar', '16000', # 16kHz sample rate (sufficient for speech)
                '-y',  # Overwrite output
                output_path
            ]
            
            result = subprocess.run(
                compress_cmd,
                capture_output=True,
                timeout=10,
                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE
            )
            
            if result.returncode != 0:
                stderr_msg = result.stderr.decode('utf-8', errors='ignore') if result.stderr else "Unknown error"
                logger.warning(f"⚠️ Audio compression failed with return code {result.returncode}: {stderr_msg[:200]}")
                return audio_data
            
            # Read compressed audio
            if not os.path.exists(output_path):
                logger.warning(f"⚠️ ffmpeg output file not created: {output_path}")
                return audio_data
            
            with open(output_path, 'rb') as f:
                compressed_data = f.read()
            
            # Validate compressed audio - check for valid MP3 frame headers
            if not compressed_data or len(compressed_data) == 0:
                logger.warning(f"⚠️ ffmpeg produced empty output file")
                return audio_data
            
            # Check for valid MP3 (frame sync or ID3 tag)
            is_valid_compressed = False
            if len(compressed_data) >= 2:
                first_byte = compressed_data[0]
                second_byte = compressed_data[1]
                
                # Check for MPEG frame sync (FF followed by byte with bits 7,6,5 set)
                if first_byte == 0xff and (second_byte & 0xe0) == 0xe0:
                    is_valid_compressed = True
                
                # Also check for ID3 tag
                if len(compressed_data) >= 3 and compressed_data[:3] == b'ID3':
                    is_valid_compressed = True
            
            if not is_valid_compressed:
                logger.warning(f"⚠️ Compressed audio doesn't look like valid MP3 (header bytes: {compressed_data[:4].hex() if len(compressed_data) >= 4 else compressed_data.hex()})")
                return audio_data
            
            original_size = len(audio_data) / 1024  # KB
            compressed_size = len(compressed_data) / 1024  # KB
            compression_ratio = (1 - len(compressed_data) / len(audio_data)) * 100
            
            logger.info(f"✅ Audio compressed: {original_size:.1f}KB → {compressed_size:.1f}KB ({compression_ratio:.1f}% reduction)")
            
            return compressed_data
            
        finally:
            # Clean up temp files
            try:
                if os.path.exists(input_path):
                    os.unlink(input_path)
                if os.path.exists(output_path):
                    os.unlink(output_path)
            except Exception as cleanup_error:
                logger.warning(f"⚠️ Failed to clean up temp files: {cleanup_error}")
                
    except Exception as e:
        logger.warning(f"⚠️ Audio compression error (returning original): {e}")
        return audio_data

@app.route('/api/tts/synthesize', methods=['POST'])
@limiter.limit("120 per minute")
@require_api_token
@check_client_access
def synthesize_tts():
    """
    Synthesize speech using Edge TTS (Cloud-based)
    
    Request:
        {
            "text": "text to speak",
            "lang": "zh-CN",  # Language code (e.g., zh-CN, en-US, ja-JP)
            "voice": "zh-CN-XiaoxiuNeural"  # Optional: specific voice name
        }
    
    Response:
        Audio stream (.mp3 format) or JSON error
    
    Authentication:
        Requires API token in Authorization header (from WebSocket connection)
        Header: Authorization: Bearer <api_token>
    """
    if not EDGE_TTS_AVAILABLE:
        return jsonify({'success': False, 'error': 'Edge TTS not available'}), 503
    
    try:
        data = request.get_json() or {}
    except Exception:
        return jsonify({'success': False, 'error': 'Invalid JSON'}), 400
    
    # Get client ID from WebSocket session ID (stable per user)
    session_info = getattr(request, 'session_info', {})
    sid = session_info.get('sid') or request.client_id or get_remote_address()
    client_id = f"tts_{sid}"
    
    # Sanitize input
    text = sanitize_text(data.get('text', ''), max_length=5000)
    lang = sanitize_text(data.get('lang', 'en-US'), max_length=20)
    voice = sanitize_text(data.get('voice', ''), max_length=100)
    
    # Validate inputs
    if not text:
        return jsonify({'success': False, 'error': 'Text is required'}), 400
    
    if len(text) > 5000:
        return jsonify({'success': False, 'error': 'Text too long (max 5000 chars)'}), 400
    
    # Validate language code
    is_valid_lang, lang_error = validate_language_code(lang)
    if not is_valid_lang:
        return jsonify({'success': False, 'error': lang_error}), 400
    
    # Validate voice name
    available_voices = get_cached_edge_tts_voices()
    is_valid_voice, voice_error, validated_voice = validate_voice_name(voice, available_voices)
    if not is_valid_voice:
        return jsonify({'success': False, 'error': voice_error}), 400
    
    # If no voice specified, use the first available voice for this language
    if not validated_voice and available_voices:
        lang_voices = [v for v in available_voices if v.get('Locale') == lang]
        if lang_voices:
            validated_voice = lang_voices[0].get('ShortName')
            logger.debug(f"Using default voice for {lang}: {validated_voice}")
        else:
            # Fallback to any available voice
            validated_voice = available_voices[0].get('ShortName')
            logger.debug(f"Using first available voice: {validated_voice}")
    
    if not validated_voice:
        return jsonify({'success': False, 'error': 'No voices available for this language'}), 400
    
    # Generate cache key for this synthesis request
    cache_key = get_synthesis_cache_key(text, validated_voice)
    
    # Check if this request is cached
    if cache_key in SYNTHESIS_REQUEST_CACHE:
        cache_time = SYNTHESIS_CACHE_TIME.get(cache_key, 0)
        if time.time() - cache_time < SYNTHESIS_CACHE_TTL:
            logger.info(f"🔄 Cache hit for synthesis request (client: {client_id})")
            audio_data = SYNTHESIS_REQUEST_CACHE[cache_key]
            return Response(
                audio_data,
                mimetype='audio/mpeg',
                headers={
                    'Content-Disposition': 'attachment; filename="speech.mp3"',
                    'Cache-Control': 'no-cache, no-store, must-revalidate',
                    'X-Cache': 'HIT'
                }
            )
    
    # Check client rate limit
    is_allowed, rate_limit_error, request_count = check_client_synthesis_limit(client_id, cache_key)
    if not is_allowed:
        logger.warning(f"❌ Rate limit exceeded for client {client_id}: {rate_limit_error}")
        return jsonify({'success': False, 'error': rate_limit_error}), 429
    
    try:
        # Use subprocess to avoid eventlet/asyncio conflicts
        import base64
        import json
        
        # Pass arguments via JSON to avoid string escaping issues
        args = {"text": text, "voice": validated_voice if validated_voice else None}
        
        # Create Python code to synthesize audio in subprocess
        synthesis_code = """
import asyncio
import edge_tts
import io
import base64
import json
import sys

async def synthesize():
    args = json.loads(sys.stdin.read())
    text = args['text']
    voice = args['voice']
    
    audio_buffer = io.BytesIO()
    try:
        communicate = edge_tts.Communicate(
            text=text,
            voice=voice,
            rate="+0%"  # rate must be a string
        )
        
        async for chunk in communicate.stream():
            if chunk['type'] == 'audio':
                audio_buffer.write(chunk['data'])
        
        audio_buffer.seek(0)
        audio_data = audio_buffer.getvalue()
        # Base64 encode for transmission through subprocess
        encoded = base64.b64encode(audio_data).decode('utf-8')
        print(encoded)
    except Exception as e:
        print(f"ERROR: {str(e)}", file=sys.stderr)
        sys.exit(1)

asyncio.run(synthesize())
"""
        
        result = subprocess.run(
            [sys.executable, '-c', synthesis_code],
            input=json.dumps(args),
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            stderr_text = result.stderr if result.stderr else "(no stderr output)"
            logger.error(f"❌ Synthesis subprocess error (return code: {result.returncode})")
            logger.error(f"   stderr: {stderr_text[:500]}")  # Log first 500 chars
            
            # Check if it's a network/connectivity error
            if '403' in stderr_text or 'Invalid response status' in stderr_text:
                return jsonify({'success': False, 'error': 'Edge TTS service unavailable (403). Server may need network access to speech.platform.bing.com'}), 503
            elif 'wss://' in stderr_text or 'WebSocket' in stderr_text:
                return jsonify({'success': False, 'error': 'Network connection error: Cannot reach Bing Edge TTS service'}), 503
            else:
                return jsonify({'success': False, 'error': 'Audio synthesis failed'}), 500
        
        if not result.stdout or not result.stdout.strip():
            logger.error(f"❌ Synthesis subprocess returned empty output")
            logger.error(f"   stderr was: {result.stderr[:200] if result.stderr else '(none)'}")
            return jsonify({'success': False, 'error': 'Audio synthesis failed - empty output'}), 500
        
        # Decode Base64 audio data
        import base64
        try:
            audio_data = base64.b64decode(result.stdout.strip())
        except Exception as decode_error:
            logger.error(f"Base64 decode error: {decode_error}")
            return jsonify({'success': False, 'error': 'Audio synthesis failed - decode error'}), 500
        
        if not audio_data or len(audio_data) == 0:
            logger.error(f"Synthesis produced empty audio data")
            return jsonify({'success': False, 'error': 'Audio synthesis failed - empty audio'}), 500
        
        # Validate audio data looks like MP3 (has MP3 frame header)
        logger.info(f"📊 Raw audio size: {len(audio_data)} bytes, header bytes: {audio_data[:4].hex()}")
        
        # MP3 files can have multiple valid frame headers:
        # - FF FB/FA/FE/FC: MPEG frame sync with different configs
        # - FF F3: Alternative MPEG frame sync
        # - ID3: ID3 tag header (sometimes added by ffmpeg)
        # Check for MPEG frame sync (FF followed by byte with bits 7-6 set, and bit 5 should be 1 for Layer 3)
        # Or check for ID3 tag
        
        is_valid_mp3 = False
        if len(audio_data) >= 2:
            first_byte = audio_data[0]
            second_byte = audio_data[1]
            
            # Check for MPEG frame sync: first byte is FF
            if first_byte == 0xff:
                # Second byte should have pattern 111xxxxx for valid MPEG frame
                # (bits 7, 6, 5 all set = 0b111xxxxx)
                if (second_byte & 0xe0) == 0xe0:  # Check if bits 7,6,5 are all 1
                    is_valid_mp3 = True
            
            # Also check for ID3 tag
            if len(audio_data) >= 3 and audio_data[:3] == b'ID3':
                is_valid_mp3 = True
        
        if not is_valid_mp3:
            logger.warning(f"⚠️ Audio may not be valid MP3 format (header: {audio_data[:4].hex() if len(audio_data) >= 4 else audio_data.hex()}). Will use as-is without compression.")
            # Don't compress potentially invalid audio - might be corrupted
            compressed_audio = audio_data
        else:
            # Check if we should compress (can be disabled for debugging)
            # Default: disabled if ffmpeg is not available
            # Enable with: export ENABLE_AUDIO_COMPRESSION=true
            should_compress = os.environ.get('ENABLE_AUDIO_COMPRESSION', 'false').lower() == 'true'
            
            if should_compress:
                # Compress audio before caching (to save memory)
                logger.info("🔄 Compressing audio...")
                compressed_audio = compress_audio_to_low_quality(audio_data)
            else:
                logger.info("⏭️ Audio compression disabled (set ENABLE_AUDIO_COMPRESSION=true to enable)")
                compressed_audio = audio_data
        
        if not compressed_audio or len(compressed_audio) == 0:
            logger.error(f"No valid audio data after processing")
            return jsonify({'success': False, 'error': 'Audio synthesis failed - no valid output'}), 500
        
        # Cache the synthesized audio (compressed)
        SYNTHESIS_REQUEST_CACHE[cache_key] = compressed_audio
        SYNTHESIS_CACHE_TIME[cache_key] = time.time()
        cache_size_mb = sum(len(v) for v in SYNTHESIS_REQUEST_CACHE.values()) / (1024 * 1024)
        logger.info(f"💾 Cached synthesis result: {len(SYNTHESIS_REQUEST_CACHE)} items, {cache_size_mb:.2f}MB total (client: {client_id})")
        
        # Clean up old cache entries if cache gets too large (limit to 1000MB)
        max_cache_size_mb = 1000
        current_size_mb = cache_size_mb
        if current_size_mb > max_cache_size_mb:
            oldest_key = min(SYNTHESIS_CACHE_TIME.keys(), key=lambda k: SYNTHESIS_CACHE_TIME[k])
            removed_size = len(SYNTHESIS_REQUEST_CACHE[oldest_key]) / (1024 * 1024)
            del SYNTHESIS_REQUEST_CACHE[oldest_key]
            del SYNTHESIS_CACHE_TIME[oldest_key]
            logger.info(f"🗑️ Cleaned up synthesis cache (removed {removed_size:.2f}MB, now {(current_size_mb - removed_size):.2f}MB)")
        
        # Limit maximum number of cached items (1000 items max)
        if len(SYNTHESIS_REQUEST_CACHE) > 1000:
            oldest_key = min(SYNTHESIS_CACHE_TIME.keys(), key=lambda k: SYNTHESIS_CACHE_TIME[k])
            del SYNTHESIS_REQUEST_CACHE[oldest_key]
            del SYNTHESIS_CACHE_TIME[oldest_key]
            logger.info(f"🗑️ Trimmed synthesis cache (now {len(SYNTHESIS_REQUEST_CACHE)} items)")
        
        
        # Build response with CSP header explicitly
        # Return compressed audio (both cached and new requests return compressed version)
        response = Response(
            compressed_audio,
            mimetype='audio/mpeg',
            headers={
                'Content-Disposition': 'attachment; filename="speech.mp3"',
                'Cache-Control': 'no-cache, no-store, must-revalidate',
                'X-Cache': 'MISS',
                'Content-Security-Policy': (
                    "default-src 'self'; "
                    "script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
                    "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://fonts.googleapis.com; "
                    "media-src 'self' blob:; "
                    "connect-src 'self' http://localhost:* http://127.0.0.1:* ws://localhost:* ws://127.0.0.1:* https://cdnjs.cloudflare.com https://translate.googleapis.com https://fonts.googleapis.com https://fonts.gstatic.com; "
                    "img-src 'self' data:; "
                    "font-src 'self' data: https://cdnjs.cloudflare.com https://fonts.gstatic.com"
                )
            }
        )
        return response
    
    except subprocess.TimeoutExpired:
        logger.error("Synthesis subprocess timeout")
        return jsonify({'success': False, 'error': 'Synthesis timeout'}), 500
    except Exception as e:
        logger.error(f"Edge TTS synthesis error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/tts/voices', methods=['GET'])
@limiter.limit("30 per minute")
@check_client_access
def get_tts_voices():
    """
    Get available TTS voices from Edge TTS
    
    Query parameters:
        lang (str): Optional language code to filter voices (e.g., 'zh-CN', 'en-US')
    
    Response:
        {
            "success": true,
            "edge_voices": [
                {
                    "name": "zh-CN-XiaoxiuNeural",
                    "locale": "zh-CN",
                    "gender": "Female",
                    "display_name": "Microsoft Xiaoxiu"
                }
            ],
            "edge_tts_available": true
        }
    """
    if not EDGE_TTS_AVAILABLE:
        logger.warning("Edge TTS not available: module not imported")
        return jsonify({
            'success': True,
            'edge_voices': [],
            'edge_tts_available': False,
            'error': 'Edge TTS not installed'
        })
    
    try:
        lang_filter = request.args.get('lang', '').strip()
        logger.info(f"TTS voices request - lang_filter: {lang_filter}")
        
        # Get cached voices or request caching if not yet loaded
        voices = get_cached_edge_tts_voices()
        
        if not voices:
            logger.info("Edge TTS voices still loading, returning status and asking client to retry")
            return jsonify({
                'success': True,
                'edge_voices': [],
                'edge_tts_available': True,
                'warning': 'Voices are being loaded, please retry in a moment...',
                'retry_after': 2  # Suggest retry after 2 seconds
            })
        
        logger.info(f"Retrieved {len(voices)} voices from cache")
        
        # Filter by language if specified
        if lang_filter:
            voices = [v for v in voices if v.get('Locale', '').startswith(lang_filter)]
            logger.info(f"After language filter ({lang_filter}): {len(voices)} voices")
        
        # Format voices for frontend
        formatted_voices = []
        for v in voices:
            try:
                formatted_voices.append({
                    'name': v.get('ShortName', ''),
                    'locale': v.get('Locale', ''),
                    'gender': v.get('Gender', 'Unknown'),
                    'display_name': v.get('FriendlyName', v.get('Name', ''))  # Use FriendlyName first
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
    """
    Get all supported language codes for Edge TTS.
    This endpoint provides information about which languages are available.
    
    Response:
        {
            "success": true,
            "supported_languages": [
                "af-ZA", "am-ET", "ar-AE", ..., "zh-TW", "zu-ZA"
            ],
            "total_languages": 100+,
            "total_voices": 322
        }
    """
    try:
        voices = get_cached_edge_tts_voices()
        
        # Extract unique language codes from voices
        languages = set()
        for voice in voices:
            locale = voice.get('Locale', '')
            if locale:
                languages.add(locale)
        
        sorted_languages = sorted(list(languages))
        
        return jsonify({
            'success': True,
            'supported_languages': sorted_languages,
            'total_languages': len(languages),
            'total_voices': len(voices) if voices else 0,
            'edge_tts_available': EDGE_TTS_AVAILABLE
        })
    
    except Exception as e:
        logger.error(f"Error in get_supported_languages: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/tts/cache-stats', methods=['GET'])
@limiter.limit("30 per minute")
def get_tts_cache_stats():
    """
    Get TTS synthesis cache statistics
    
    Note: This endpoint is primarily called by the admin panel (which handles auth).
    Direct external access may require authentication based on configuration.
    
    Response:
        {
            "success": true,
            "cache_items": 150,
            "cache_size_mb": 45.5,
            "cache_ttl_seconds": 3600,
            "max_cache_size_mb": 500,
            "max_cache_items": 500
        }
    """
    try:
        # ✅ Safely check if SYNTHESIS_REQUEST_CACHE is defined and is a dict
        if not isinstance(SYNTHESIS_REQUEST_CACHE, dict):
            logger.warning("⚠️ SYNTHESIS_REQUEST_CACHE is not initialized as dict")
            return jsonify({
                'success': True,
                'cache_items': 0,
                'cache_size_mb': 0,
                'cache_ttl_seconds': SYNTHESIS_CACHE_TTL if 'SYNTHESIS_CACHE_TTL' in globals() else 3600,
                'max_cache_size_mb': 1000,
                'max_cache_items': 1000,
                'message': 'TTS cache not initialized'
            })
        
        cache_size_bytes = sum(len(v) for v in SYNTHESIS_REQUEST_CACHE.values())
        cache_size_mb = cache_size_bytes / (1024 * 1024)
        
        logger.debug(f"📊 TTS cache stats: {len(SYNTHESIS_REQUEST_CACHE)} items, {cache_size_mb:.2f}MB")
        
        return jsonify({
            'success': True,
            'cache_items': len(SYNTHESIS_REQUEST_CACHE),
            'cache_size_mb': round(cache_size_mb, 2),
            'cache_ttl_seconds': SYNTHESIS_CACHE_TTL,
            'max_cache_size_mb': 1000,
            'max_cache_items': 1000,
            'message': f'TTS cache using {cache_size_mb:.2f}MB with {len(SYNTHESIS_REQUEST_CACHE)} items'
        })
    
    except Exception as e:
        logger.error(f"❌ Error in get_tts_cache_stats: {e}", exc_info=True)
        # Return proper JSON error even if something goes wrong
        return jsonify({
            'success': False,
            'error': str(e),
            'cache_items': 0,
            'cache_size_mb': 0
        }), 500

@app.route('/api/tts/cache-clear', methods=['POST'])
@limiter.limit("10 per minute")
def clear_tts_cache():
    """
    Clear all TTS synthesis cache
    
    Note: This endpoint is primarily called by the admin panel (which handles auth).
    Direct external access may require authentication based on configuration.
    
    Response:
        {
            "success": true,
            "cleared_items": 150,
            "freed_mb": 45.5
        }
    """
    try:
        global SYNTHESIS_REQUEST_CACHE, SYNTHESIS_CACHE_TIME
        
        cleared_items = len(SYNTHESIS_REQUEST_CACHE)
        freed_bytes = sum(len(v) for v in SYNTHESIS_REQUEST_CACHE.values())
        freed_mb = freed_bytes / (1024 * 1024)
        
        # Get request source info for logging
        source_ip = get_real_ip()
        
        SYNTHESIS_REQUEST_CACHE.clear()
        SYNTHESIS_CACHE_TIME.clear()
        
        # Audit log - record the cache clearing action
        logger.info(f"🗑️ TTS cache cleared: {cleared_items} items, {freed_mb:.2f}MB freed from {source_ip}")
        security_logger.info(f"TTS_ACTION: cache_cleared | Items: {cleared_items} | Freed: {freed_mb:.2f}MB | IP: {source_ip}")
        
        return jsonify({
            'success': True,
            'cleared_items': cleared_items,
            'freed_mb': round(freed_mb, 2)
        })
    
    except Exception as e:
        logger.error(f"Error clearing TTS cache: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ──────────────────────────────────────────
# WebSocket Events with Security
# ──────────────────────────────────────────
@socketio.on('connect')
def handle_connect():
    """Handle client connection with validation"""
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

    client_key = f"client:{client_id}"
    client_ip = get_real_ip()

    logger.info(f"Socket.IO connect attempt from {client_ip} (Client: {client_id}, Type: {client_type}, SID: {request.sid})")

    if is_client_blocked(client_key):
        security_logger.warning(f"Blocked client attempted WebSocket: {client_key}")
        logger.error(f"Connection rejected: Client {client_key} is blocked")
        return False

    # Only count user-type clients as listeners (not admin)
    if client_type == 'user':
        # If this client_key already has an old SID, evict it (handles page refresh)
        old_sid = listener_clients.get(client_key)
        if old_sid and old_sid != request.sid:
            logger.info(f"Evicting stale SID {old_sid} for {client_key} (replaced by {request.sid})")
            sid_to_client_key.pop(old_sid, None)
            stale_key = f"{client_key}:{old_sid}"
            connected_clients.discard(stale_key)

        client_id_full = f"{client_key}:{request.sid}"
        connected_clients.add(client_id_full)
        listener_clients[client_key] = request.sid  # Only keep latest SID per user
        logger.info(f"User client connected: {client_ip} (Client: {client_id}, SID: {request.sid}, Total listeners: {len(listener_clients)})")
    elif client_type == 'admin':
        # Admin clients still need to be tracked, but not as listeners
        client_id_full = f"{client_key}:{request.sid}"
        connected_clients.add(client_id_full)
        logger.info(f"Admin client connected: {client_ip} (Client: {client_id}, SID: {request.sid})")
    
    # Store mapping for reliable cleanup on disconnect
    sid_to_client_key[request.sid] = (client_key, client_type)

    # Notify client that history is available via HTTP API (pagination)
    # Don't send all history via WebSocket - use HTTP API for better performance
    # Generate and send short-lived API session token for pagination
    api_token = create_api_token(request.sid)
    emit('ready', {
        'status': 'connected',
        'message': 'Use /api/translations to fetch paginated history',
        'api_token': api_token
    })

    return True

@socketio.on('disconnect')
def handle_disconnect(sid=None):
    """Handle client disconnection - find and clean up client info"""
    sid_used = sid if sid is not None else request.sid
    
    # Use stored mapping to find client_key and type reliably
    mapping = sid_to_client_key.pop(sid_used, None)
    
    if mapping:
        client_key, client_type = mapping
        
        # Clean up only if it was a user (listener)
        if client_type == 'user':
            # Only remove from listener_clients if this SID is still the active one
            # (avoids removing a newer connection when a stale disconnect fires late)
            if listener_clients.get(client_key) == sid_used:
                del listener_clients[client_key]
            logger.info(f"User client disconnected: SID {sid_used} from {client_key} (Total listeners: {len(listener_clients)})")
        else:
            logger.info(f"Admin client disconnected: SID {sid_used} from {client_key}")
    else:
        logger.warning(f"Disconnect: Unknown client mapping for SID {sid_used}")
    
    # Always try to remove from connected_clients
    connected_clients.discard(sid_used)
    for key in list(connected_clients):
        if key.endswith(f":{sid_used}"):
            connected_clients.discard(key)
            break
    
    admin_sessions.pop(sid_used, None)
    
    # Clean up API tokens associated with this SID
    tokens_to_remove = [t for t, info in api_session_tokens.items() if info['sid'] == sid_used]
    for token in tokens_to_remove:
        del api_session_tokens[token]

@socketio.on('admin_connect')
def handle_admin_connect(data):
    """Handle admin connection with validation"""
    if not data or not isinstance(data, dict):
        emit('admin_connected', {'success': False, 'error': 'Invalid data'})
        return

    token = data.get('token')

    if not get_config('authentication', 'enabled', default=True):
        admin_sessions[request.sid] = 'admin'
        # Send translation history to admin
        emit('history', translations_history)
        emit('admin_connected', {'success': True})
        return

    if not token:
        emit('admin_connected', {'success': False, 'error': 'No token'})
        return

    decoded = validate_jwt_token(token)
    if decoded:
        admin_sessions[request.sid] = decoded['username']
        # Send translation history to admin
        emit('history', translations_history)
        emit('admin_connected', {'success': True})
        logger.info(f"Admin connected: {decoded['username']} from {get_real_ip()}")
    else:
        emit('admin_connected', {'success': False, 'error': 'Invalid token'})

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
    
    if not is_final:
        # Send interim result ONLY to listeners (non-admin users)
        # Emit to all listener SIDs (exclude admins naturally)
        interim_data = {
            'temp_id': temp_id,
            'text': raw_text,
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'source_language': data.get('language', 'en')[:10],
            'confidence': data.get('confidence'),
            'is_interim': True
        }
        # Broadcast to all non-admin clients
        socketio.emit('realtime_transcription', interim_data, skip_sid=[request.sid])
        logger.info(f"[INTERIM] {len(raw_text)} chars (temp_id: {temp_id})")
    else:
        # Send final result with translation
        translation_data = {
            'id': None,  # Will be assigned by add_translation()
            'temp_id': temp_id,  # Link to interim result if present
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'original': raw_text,
            'corrected': raw_text,
            'translated': data.get('translated'),  # Can be pre-translated by admin
            'is_corrected': False,
            'source_language': data.get('language', 'en')[:10],
            'confidence': data.get('confidence')
        }

        add_translation(translation_data)
        # Emit to listeners (non-admin users)
        socketio.emit('new_translation', translation_data, skip_sid=[request.sid])
        # Emit to admin only (the one who sent the transcription)
        emit('transcription_confirmed', translation_data)
        logger.info(f"[FINAL] ID={translation_data.get('id')}")

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

    # Find translation by ID (not by index)
    target_item = None
    for item in translations_history:
        if item['id'] == translation_id:
            target_item = item
            break

    if target_item is None:
        emit('error', {'message': 'Translation not found (may have been removed from history)'})
        return

    target_item['corrected'] = corrected_text
    target_item['is_corrected'] = True

    socketio.emit('translation_corrected', target_item)
    logger.info(f"✏️ [CORRECTED] ID {translation_id}")
    emit('correction_success', {'id': translation_id})

@socketio.on('clear_history')
def handle_clear_history():
    """Handle clear history with authorization"""
    if not is_admin(request.sid):
        emit('error', {'message': 'Unauthorized'})
        disconnect()
        return

    global translations_history, next_translation_id
    translations_history = []
    next_translation_id = 0  # Reset ID counter when clearing history
    socketio.emit('history_cleared')
    logger.info(f"[CLEARED] History by {admin_sessions.get(request.sid)}")

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

    # Add to history
    add_translation(translation_data)

    # Broadcast to all connected clients
    socketio.emit('new_translation', translation_data)
    logger.info(f"[IMPORTED] ID={translation_data['id']} from {admin_sessions.get(request.sid)}")

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

    global translations_history

    # Filter out items with IDs in the deletion list (ID-based deletion, not index-based)
    original_count = len(translations_history)
    translations_history = [item for item in translations_history if item.get('id') not in item_ids]
    deleted_count = original_count - len(translations_history)

    # Broadcast deletion to all connected clients
    socketio.emit('items_deleted', {'ids': item_ids})
    logger.info(f"[DELETED] {deleted_count} item(s) by {admin_sessions.get(request.sid)}")
    emit('deletion_success', {'deleted_count': deleted_count})

@socketio.on_error_default
def default_error_handler(e):
    """Handle WebSocket errors"""
    security_logger.error(f"WebSocket error from {get_real_ip()}: {str(e)[:200]}")
    disconnect()

# ──────────────────────────────────────────
# Error Handlers
# ──────────────────────────────────────────
@app.errorhandler(404)
def not_found(error):
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

    host = get_config('server', 'host', default='0.0.0.0')
    port = get_config('server', 'port', default=1915)
    use_https = get_config('server', 'use_https', default=True)

    logger.info(f"Protocol: {'HTTPS' if use_https else 'HTTP'}")
    logger.info(f"Security logging: logs/security.log")

    # Initialize Edge TTS voice cache in background (non-blocking)
    if EDGE_TTS_AVAILABLE:
        logger.info("🎙️ Pre-loading Edge TTS voices in background...")
        import threading
        cache_thread = threading.Thread(target=fetch_edge_tts_voices_in_thread, daemon=True)
        cache_thread.start()

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