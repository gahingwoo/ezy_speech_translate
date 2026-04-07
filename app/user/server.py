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
import secrets
import re
from collections import defaultdict
import time

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
from flask import Flask, render_template, request, jsonify, session
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
        'connect-src': ["'self'", "ws:", "wss:", "https:", "https://translate.googleapis.com"]
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
        # Get token from header or query parameter
        token = request.headers.get('X-API-Session-Token', '')
        if not token:
            token = request.args.get('api_token', '')
        
        if not token:
            return jsonify({'error': 'No API token provided'}), 401
        
        session_info = validate_api_token(token)
        if not session_info:
            return jsonify({'error': 'Invalid or expired API token'}), 401
        
        request.api_session = session_info
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

def is_admin(sid):
    """Check if session is authenticated admin"""
    if not get_config('authentication', 'enabled', default=True):
        return True
    return sid in admin_sessions

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