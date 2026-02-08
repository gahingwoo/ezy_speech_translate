"""
EzySpeechTranslate User Server - Secured HTTPS Version
Real-time speech recognition and translation system with security hardening
"""

import os
import yaml
import logging
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from flask import Flask, render_template, request, jsonify, session
from flask_socketio import SocketIO, emit, disconnect
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman
import jwt
from functools import wraps
import hashlib
import eventlet
import eventlet.wsgi
import secrets
import re
import sys
from collections import defaultdict
import time

# ──────────────────────────────────────────
# Path Setup
# ──────────────────────────────────────────
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CONFIG_DIR = os.path.join(BASE_DIR, "config")
SSL_DIR = os.path.join(CONFIG_DIR, "ssl")

TEMPLATE_DIR = os.path.join(APP_DIR, "templates")
STATIC_DIR = os.path.join(APP_DIR, "static")

os.chdir(BASE_DIR)

# ──────────────────────────────────────────
# Secure Configuration Loader
# ──────────────────────────────────────────
sys.path.insert(0, os.path.join(BASE_DIR, 'config'))

try:
    from secure_loader import SecureConfig
    config_loader = SecureConfig(os.path.join(CONFIG_DIR, 'config.yaml'))

    def get_config(*keys, default=None):
        return config_loader.get(*keys, default=default)

    logging.getLogger("config_loader").info("✓ Loaded encrypted configuration")

except ImportError:
    logging.getLogger("config_loader").warning("Secure loader not found, falling back to YAML config")

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
        'style-src': ["'self'", "'unsafe-inline'"],
        'img-src': ["'self'", "data:", "https:"],
        'connect-src': ["'self'", "wss:", "https:"]
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
    # For HTTP mode, use minimal security headers
    csp = {
        'default-src': ["'self'"],
        'script-src': ["'self'", "'unsafe-inline'"],
        'style-src': ["'self'", "'unsafe-inline'"],
        'img-src': ["'self'", "data:"],
        'connect-src': ["'self'", "ws:"]
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
max_ws_connections = get_config('advanced', 'security', 'max_ws_connections', default=5)

if rate_limit_enabled:
    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
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
blocked_ips = set()
failed_login_attempts = defaultdict(list)  # IP: [timestamps]
rate_limit_violations = defaultdict(int)  # IP: count
suspicious_patterns = defaultdict(int)  # IP: count

MAX_LOGIN_ATTEMPTS = get_config('advanced', 'security', 'max_login_attempts', default=10)
login_window_min = get_config('advanced', 'security', 'login_attempt_window_minutes', default=15)
LOGIN_ATTEMPT_WINDOW = timedelta(minutes=login_window_min)
MAX_RATE_VIOLATIONS = get_config('advanced', 'security', 'max_rate_violations', default=10)
block_minutes = get_config('advanced', 'security', 'block_duration_minutes', default=60)
BLOCK_DURATION = timedelta(minutes=block_minutes)

def is_ip_blocked(ip):
    """Check if IP is blocked"""
    return ip in blocked_ips

def record_failed_login(ip):
    """Record failed login attempt"""
    now = datetime.now()
    attempts = failed_login_attempts[ip]

    # Clean old attempts
    attempts[:] = [t for t in attempts if now - t < LOGIN_ATTEMPT_WINDOW]
    attempts.append(now)

    if len(attempts) >= MAX_LOGIN_ATTEMPTS:
        blocked_ips.add(ip)
        security_logger.critical(f"IP BLOCKED due to failed login attempts: {ip}")
        return True

    return False

def record_rate_violation(ip):
    """Record rate limit violation"""
    rate_limit_violations[ip] += 1

    if rate_limit_violations[ip] >= MAX_RATE_VIOLATIONS:
        blocked_ips.add(ip)
        security_logger.critical(f"IP BLOCKED due to rate limit violations: {ip}")
        return True

    return False

def record_suspicious_activity(ip, reason):
    """Record suspicious activity"""
    suspicious_patterns[ip] += 1
    security_logger.warning(f"Suspicious activity from {ip}: {reason}")

    if suspicious_patterns[ip] >= 5:
        blocked_ips.add(ip)
        security_logger.critical(f"IP BLOCKED due to suspicious patterns: {ip}")
        return True

    return False

def check_ip_access(f):
    """Decorator to check IP access"""
    @wraps(f)
    def decorated(*args, **kwargs):
        client_ip = request.remote_addr
        if is_ip_blocked(client_ip):
            security_logger.warning(f"Blocked IP attempted access: {client_ip}")
            return jsonify({'error': 'Access denied'}), 403
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
            security_logger.warning(f"Dangerous pattern detected from {request.remote_addr}")
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
        security_logger.warning(f"Invalid token from {request.remote_addr}")
        return None

# ──────────────────────────────────────────
# In-memory Storage with Limits from Config
# ──────────────────────────────────────────
MAX_HISTORY_SIZE = get_config('advanced', 'performance', 'cache_size', default=1000)
translations_history = []
connected_clients = set()
admin_sessions = {}

def add_translation(data):
    """Add translation with size limit"""
    global translations_history
    translations_history.append(data)

    # Limit history size
    if len(translations_history) > MAX_HISTORY_SIZE:
        translations_history = translations_history[-MAX_HISTORY_SIZE:]
        logger.info(f"History trimmed to {MAX_HISTORY_SIZE} items")

# ──────────────────────────────────────────
# Middleware
# ──────────────────────────────────────────
@app.before_request
def before_request():
    """Security checks before each request"""
    client_ip = request.remote_addr

    # Check IP blocking
    if is_ip_blocked(client_ip):
        return jsonify({'error': 'Access denied'}), 403

    # Check request size
    if request.content_length and request.content_length > app.config['MAX_CONTENT_LENGTH']:
        security_logger.warning(f"Large request from {client_ip}: {request.content_length}")
        return jsonify({'error': 'Request too large'}), 413

    # Check for path traversal
    if '../' in request.path or '..\\' in request.path:
        record_suspicious_activity(client_ip, "Path traversal attempt")
        return jsonify({'error': 'Invalid request'}), 400

    # Check for SQL injection patterns
    sql_patterns = ['union select', 'drop table', 'insert into', '--', ';--']
    query_string = request.query_string.decode('utf-8', 'ignore').lower()
    if any(pattern in query_string for pattern in sql_patterns):
        record_suspicious_activity(client_ip, "SQL injection attempt")
        return jsonify({'error': 'Invalid request'}), 400

@app.after_request
def after_request(response):
    """Add security headers"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
    return response

# ──────────────────────────────────────────
# Authentication with Security
# ──────────────────────────────────────────
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
@check_ip_access
def index():
    """Main client interface"""
    return render_template('user.html')

@app.route('/admin')
def admin_route():
    """Admin interface route"""
    return jsonify({'message': 'Use admin_server.py for admin interface'}), 404

@app.route('/api/login', methods=['POST'])
@limiter.limit("5 per minute")
@check_ip_access
def login():
    """Admin login with brute force protection"""
    client_ip = request.remote_addr

    try:
        data = request.json or {}
    except Exception:
        security_logger.warning(f"Malformed JSON from {client_ip}")
        return jsonify({'success': False, 'error': 'Invalid request'}), 400

    username = sanitize_text(data.get('username', ''), max_length=100)
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'success': False, 'error': 'Missing credentials'}), 400

    # Rate limiting check
    if len(username) > 100 or len(password) > 100:
        record_suspicious_activity(client_ip, "Oversized credentials")
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

        logger.info(f"✓ Admin login successful: {username} from {client_ip}")
        return jsonify({
            'success': True,
            'token': token,
            'username': username
        })

    # Failed login
    logger.warning(f"✗ Failed login attempt: {username} from {client_ip}")
    if record_failed_login(client_ip):
        return jsonify({'success': False, 'error': 'Too many failed attempts. IP blocked.'}), 403

    return jsonify({'success': False, 'error': 'Invalid credentials'}), 401

@app.route('/api/config', methods=['GET'])
@limiter.limit("30 per minute")
@require_auth
@check_ip_access
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

@app.route('/api/translations', methods=['GET'])
@limiter.limit("60 per minute")
@require_auth
@check_ip_access
def get_translations():
    """Get translation history"""
    return jsonify({'translations': translations_history})

@app.route('/api/translations/clear', methods=['POST'])
@limiter.limit("10 per minute")
@require_auth
@check_ip_access
def clear_translations():
    """Clear translation history"""
    global translations_history
    translations_history = []
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
        'clients': len(connected_clients),
        'translations': len(translations_history)
    })

@app.route('/api/export/<export_format>', methods=['GET'])
@limiter.limit("10 per minute")
@require_auth
@check_ip_access
def export_translations(export_format):
    """Export translations with validation"""
    allowed_formats = ['json', 'txt', 'csv', 'srt']

    if export_format not in allowed_formats:
        return jsonify({'error': f'Unsupported format'}), 400

    # Limit export size
    max_export = 5000
    export_data = translations_history[-max_export:]

    if export_format == 'json':
        return jsonify({'translations': export_data})

    elif export_format == 'txt':
        output = f"EzySpeechTranslate Export\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        output += "=" * 60 + "\n\n"

        for item in export_data:
            output += f"[{item['id']}] {item['timestamp']}\n"
            output += f"Original: {sanitize_text(item['original'], 500)}\n"
            output += f"Corrected: {sanitize_text(item['corrected'], 500)}\n"
            output += "-" * 60 + "\n\n"

        return output, 200, {'Content-Type': 'text/plain; charset=utf-8'}

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

        return output, 200, {'Content-Type': 'text/csv; charset=utf-8'}

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

        return output, 200, {'Content-Type': 'text/plain; charset=utf-8'}

# ──────────────────────────────────────────
# WebSocket Events with Security
# ──────────────────────────────────────────
@socketio.on('connect')
def handle_connect():
    """Handle client connection with validation"""
    client_ip = request.remote_addr

    if is_ip_blocked(client_ip):
        security_logger.warning(f"Blocked IP attempted WebSocket: {client_ip}")
        return False

    # Limit connections per IP
    client_connections = sum(1 for c in connected_clients if c.startswith(client_ip))
    if client_connections >= max_ws_connections:
        security_logger.warning(f"Too many connections from {client_ip}")
        return False

    client_id = f"{client_ip}:{request.sid}"
    connected_clients.add(client_id)
    logger.info(f"Client connected: {client_ip} (Total: {len(connected_clients)})")

    # Send sanitized history
    safe_history = [
        {**item, 'original': sanitize_text(item['original'], 1000),
         'corrected': sanitize_text(item['corrected'], 1000)}
        for item in translations_history[-100:]
    ]
    emit('history', safe_history)

    return True

@socketio.on('disconnect')
def handle_disconnect(sid=None):
    """Handle client disconnection; accept optional sid to avoid TypeError from some SocketIO versions"""
    client_ip = request.remote_addr
    sid_used = sid if sid is not None else request.sid
    client_id = f"{client_ip}:{sid_used}"
    connected_clients.discard(client_id)
    admin_sessions.pop(sid_used, None)
    logger.info(f"Client disconnected: {client_ip} (Total: {len(connected_clients)})")

@socketio.on('admin_connect')
def handle_admin_connect(data):
    """Handle admin connection with validation"""
    if not data or not isinstance(data, dict):
        emit('admin_connected', {'success': False, 'error': 'Invalid data'})
        return

    token = data.get('token')

    if not get_config('authentication', 'enabled', default=True):
        admin_sessions[request.sid] = 'admin'
        emit('admin_connected', {'success': True})
        return

    if not token:
        emit('admin_connected', {'success': False, 'error': 'No token'})
        return

    decoded = validate_jwt_token(token)
    if decoded:
        admin_sessions[request.sid] = decoded['username']
        emit('admin_connected', {'success': True})
        logger.info(f"Admin connected: {decoded['username']} from {request.remote_addr}")
    else:
        emit('admin_connected', {'success': False, 'error': 'Invalid token'})

@socketio.on('new_transcription')
def handle_new_transcription(data):
    """Handle new transcription with validation"""
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

    translation_data = {
        'id': len(translations_history),
        'timestamp': datetime.now().strftime('%H:%M:%S'),
        'original': raw_text,
        'corrected': raw_text,
        'translated': None,
        'is_corrected': False,
        'source_language': data.get('language', 'en')[:10],  # Limit language code
        'confidence': data.get('confidence')
    }

    add_translation(translation_data)
    socketio.emit('new_translation', translation_data)
    logger.info(f"[NEW] {len(raw_text)} chars from {request.remote_addr}")

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

    if translation_id >= len(translations_history):
        emit('error', {'message': 'ID out of range'})
        return

    if not corrected_text:
        emit('error', {'message': 'Empty correction'})
        return

    translations_history[translation_id]['corrected'] = corrected_text
    translations_history[translation_id]['is_corrected'] = True

    socketio.emit('translation_corrected', translations_history[translation_id])
    logger.info(f"✏️ [CORRECTED] ID {translation_id}")
    emit('correction_success', {'id': translation_id})

@socketio.on('clear_history')
def handle_clear_history():
    """Handle clear history with authorization"""
    if not is_admin(request.sid):
        emit('error', {'message': 'Unauthorized'})
        disconnect()
        return

    global translations_history
    translations_history = []
    socketio.emit('history_cleared')
    logger.info(f"[CLEARED] History by {admin_sessions.get(request.sid)}")

@socketio.on_error_default
def default_error_handler(e):
    """Handle WebSocket errors"""
    security_logger.error(f"WebSocket error from {request.remote_addr}: {str(e)[:200]}")
    disconnect()

# ──────────────────────────────────────────
# Error Handlers
# ──────────────────────────────────────────
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(429)
def ratelimit_handler(e):
    client_ip = request.remote_addr
    security_logger.warning(f"Rate limit exceeded: {client_ip}")
    record_rate_violation(client_ip)
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