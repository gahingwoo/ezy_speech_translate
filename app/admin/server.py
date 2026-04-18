"""
EzySpeechTranslate Admin Server (HTTPS Version)
Serves the admin HTML interface securely with eventlet SSL
"""

import os
import sys
import yaml
import logging
import hashlib
import jwt
import time
import requests
from datetime import datetime, timedelta
from functools import wraps
from collections import defaultdict

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
from flask import Flask, render_template, jsonify, redirect, url_for, request, session
from flask_cors import CORS
from flask_socketio import SocketIO
import eventlet
import eventlet.wsgi
CONFIG_DIR = os.path.join(BASE_DIR, "config")
SSL_DIR = os.path.join(CONFIG_DIR, "ssl")
LOGS_DIR = os.path.join(BASE_DIR, "logs")

TEMPLATE_DIR = os.path.join(APP_DIR, "templates")
STATIC_DIR = os.path.join(APP_DIR, "static")

# Ensure working directory is project root
os.chdir(BASE_DIR)

# Ensure logs directory exists
os.makedirs(LOGS_DIR, exist_ok=True)

# ──────────────────────────────────────────
# Logging Setup
# ──────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# Security logger
security_logger = logging.getLogger("security")
security_handler = logging.FileHandler(os.path.join(LOGS_DIR, "security.log"))
security_handler.setFormatter(
    logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
)
security_logger.addHandler(security_handler)
security_logger.setLevel(logging.INFO)

# ──────────────────────────────────────────
# Secure Configuration Loader
# ──────────────────────────────────────────
# Secure Configuration Loader
# ──────────────────────────────────────────
sys.path.insert(0, BASE_DIR)  # Add project root to path for secure_loader import

config_file_path = os.path.join(CONFIG_DIR, "config.yaml")

try:
    from secure_loader import SecureConfig
    config_loader = SecureConfig(config_file_path)

    def get_config(*keys, default=None):
        return config_loader.get(*keys, default=default)

    logger.info("✓ Loaded encrypted configuration via secure_loader")

except ImportError as e:
    logger.warning(f"Secure loader not found ({e}), falling back to YAML config")

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

    config_loader = ConfigFallback(config_file_path)

    def get_config(*keys, default=None):
        return config_loader.get(*keys, default=default)

# ──────────────────────────────────────────
# Security Configuration
# ──────────────────────────────────────────
AUTH_ENABLED = get_config("authentication", "enabled", default=True)
ADMIN_USERNAME = get_config("authentication", "admin_username", default="admin")
ADMIN_PASSWORD = get_config("authentication", "admin_password", default="admin123")
JWT_SECRET = get_config("authentication", "jwt_secret", default="change-this-secret")
SESSION_TIMEOUT = get_config("authentication", "session_timeout", default=7200)

# Debug: Log password loading status
logger.info(f"='='='= INITIALIZATION START ='='='=")
logger.info(f"✓ AUTH_ENABLED: {AUTH_ENABLED}")
logger.info(f"✓ ADMIN_USERNAME: {ADMIN_USERNAME}")
logger.info(f"✓ ADMIN_PASSWORD type: {type(ADMIN_PASSWORD)}, loaded: {bool(ADMIN_PASSWORD)}, length: {len(ADMIN_PASSWORD) if ADMIN_PASSWORD else 0}")
logger.info(f"✓ JWT_SECRET type: {type(JWT_SECRET)}, loaded: {bool(JWT_SECRET)}, length: {len(JWT_SECRET) if JWT_SECRET else 0}")

# Verify password is not None or empty string
if not ADMIN_PASSWORD:
    logger.critical(f"✗✗✗ CRITICAL: ADMIN_PASSWORD is empty or None! Login will fail! ✗✗✗")
    ADMIN_PASSWORD = "admin123"  # Fallback to default

# Protocol configuration (HTTP/HTTPS)
USE_HTTPS = get_config("admin_server", "use_https", default=True)

# ──────────────────────────────────────────
# Security Storage (In-Memory)
# ──────────────────────────────────────────
login_attempts = defaultdict(lambda: {"count": 0, "timestamp": 0})
blocked_ips = {}
request_history = defaultdict(list)
websocket_connections = defaultdict(int)

# ──────────────────────────────────────────
# Flask App
# ──────────────────────────────────────────
app = Flask(__name__, static_folder=STATIC_DIR, template_folder=TEMPLATE_DIR)
app.config['SECRET_KEY'] = get_config("server", "secret_key", default="change-this-secret-key")

CORS(app, origins=get_config("advanced", "security", "cors_origins", default="*"))

# Initialize OEM Configuration
try:
    init_oem_config(app, get_config)
    logger.info("✓ OEM configuration initialized successfully")
except Exception as e:
    logger.warning(f"⚠ OEM configuration initialization failed: {e}")

socketio = SocketIO(app, cors_allowed_origins="*")

# ──────────────────────────────────────────
# Server Settings
# ──────────────────────────────────────────
ADMIN_PORT = get_config("admin_server", "port", default=5001)
ADMIN_HOST = get_config("admin_server", "host", default="0.0.0.0")
MAIN_SERVER_PORT = get_config("server", "port", default=1915)
MAIN_SERVER_HOST = get_config("server", "host", default="0.0.0.0")

# ──────────────────────────────────────────
# Security Settings
# ──────────────────────────────────────────
MAX_LOGIN_ATTEMPTS = get_config("advanced", "security", "max_login_attempts", default=10)
LOCKOUT_DURATION = get_config("advanced", "security", "block_duration_minutes", default=60) * 60  # Convert to seconds
MAX_REQUESTS_PER_MINUTE = get_config("advanced", "security", "max_requests_per_minute", default=60)
RATE_LIMIT_ENABLED = get_config("advanced", "security", "rate_limit_enabled", default=True)
MAX_WS_CONNECTIONS = get_config("advanced", "security", "max_ws_connections", default=5)

# ──────────────────────────────────────────
# Security Helper Functions
# ──────────────────────────────────────────
def get_client_ip():
    """Get real client IP (handles proxies)"""
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    return request.remote_addr

def hash_password(password):
    """Hash password with SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def is_ip_blocked(ip):
    """Check if IP is currently blocked"""
    if ip in blocked_ips:
        if time.time() < blocked_ips[ip]:
            return True
        else:
            del blocked_ips[ip]
    return False

def block_ip(ip, duration=LOCKOUT_DURATION):
    """Block an IP for specified duration"""
    blocked_ips[ip] = time.time() + duration
    security_logger.warning(f"IP blocked: {ip} for {duration}s")

def check_login_attempts(ip):
    """Check and update login attempts for IP"""
    current_time = time.time()

    # Reset counter if more than 1 minute has passed
    if current_time - login_attempts[ip]["timestamp"] > 60:
        login_attempts[ip] = {"count": 0, "timestamp": current_time}

    login_attempts[ip]["count"] += 1
    login_attempts[ip]["timestamp"] = current_time

    # Block if exceeded max attempts
    if login_attempts[ip]["count"] >= MAX_LOGIN_ATTEMPTS:
        block_ip(ip)
        return False

    return True

def check_rate_limit(ip):
    """Check API rate limiting"""
    if not RATE_LIMIT_ENABLED:
        return True

    current_time = time.time()

    # Clean old requests (older than 1 minute)
    request_history[ip] = [
        timestamp for timestamp in request_history[ip]
        if current_time - timestamp < 60
    ]

    # Check if exceeded limit
    if len(request_history[ip]) >= MAX_REQUESTS_PER_MINUTE:
        return False

    request_history[ip].append(current_time)
    return True

def sanitize_input(text):
    """Basic XSS protection"""
    if not isinstance(text, str):
        return text

    dangerous_chars = {
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#x27;',
        '/': '&#x2F;'
    }

    for char, escaped in dangerous_chars.items():
        text = text.replace(char, escaped)

    return text

def validate_path(path):
    """Prevent path traversal attacks"""
    if '..' in path or path.startswith('/'):
        return False
    return True

def generate_token(username):
    """Generate JWT token"""
    payload = {
        'username': username,
        'exp': datetime.utcnow() + timedelta(seconds=SESSION_TIMEOUT),
        'iat': datetime.utcnow()
    }
    return jwt.encode(payload, JWT_SECRET, algorithm='HS256')

def verify_token(token):
    """Verify JWT token"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

# ──────────────────────────────────────────
# Security Decorators
# ──────────────────────────────────────────
def require_auth(f):
    """Decorator to require authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not AUTH_ENABLED:
            return f(*args, **kwargs)

        # Check for token in header or session
        token = request.headers.get('Authorization')
        if token and token.startswith('Bearer '):
            token = token[7:]
            payload = verify_token(token)
            if payload:
                return f(*args, **kwargs)

        # Check session
        if 'authenticated' in session and session['authenticated']:
            return f(*args, **kwargs)

        return jsonify({"error": "Authentication required"}), 401

    return decorated_function

def require_admin_auth(f):
    """Decorator to require admin authentication via session"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not AUTH_ENABLED:
            return f(*args, **kwargs)

        # Check session authentication
        # If user has logged in successfully, session['authenticated'] will be True
        if 'authenticated' in session and session['authenticated']:
            return f(*args, **kwargs)

        # Not authenticated
        logger.warning(f"Unauthorized access attempt to admin endpoint from {get_client_ip()}")
        return jsonify({"error": "Admin authentication required", "success": False}), 401

    return decorated_function

def rate_limit_check(f):
    """Decorator for rate limiting"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        ip = get_client_ip()

        # Check if IP is blocked
        if is_ip_blocked(ip):
            security_logger.warning(f"Blocked IP attempted access: {ip}")
            return jsonify({"error": "IP temporarily blocked"}), 403

        # Check rate limit
        if not check_rate_limit(ip):
            security_logger.warning(f"Rate limit exceeded: {ip}")
            return jsonify({"error": "Rate limit exceeded"}), 429

        return f(*args, **kwargs)

    return decorated_function

# ──────────────────────────────────────────
# Cache Control Middleware (prevent browser caching of JS/CSS)
# ──────────────────────────────────────────
@app.after_request
def set_cache_headers(response):
    """Set proper cache headers for static and dynamic content"""
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
    
    # For static files (JS, CSS, images), allow short-term caching but always validate
    elif request.path.startswith('/static/'):
        # Browser can cache these for 1 hour, but MUST revalidate with server
        response.headers['Cache-Control'] = 'public, max-age=3600, must-revalidate'
        # Add ETag for better cache validation
        if not response.headers.get('ETag'):
            response.set_etag()
    
    return response

# ──────────────────────────────────────────
# Routes
# ──────────────────────────────────────────
@app.route("/")
def index():
    """Redirect root to login page"""
    return redirect(url_for('login_page'))

@app.route("/login")
def login_page():
    """Serve login page"""
    return render_template("login.html")

@app.route("/admin")
def admin_page():
    """Serve admin dashboard page"""
    return render_template("admin.html")

@app.route("/api/login", methods=["POST"])
@rate_limit_check
def login():
    """Login endpoint with security checks"""
    ip = get_client_ip()

    # Check if IP is blocked
    if is_ip_blocked(ip):
        security_logger.warning(f"Login attempt from blocked IP: {ip}")
        return jsonify({"error": "Too many failed attempts. Try again later."}), 403

    # Check login rate limit
    if not check_login_attempts(ip):
        security_logger.warning(f"Too many login attempts from IP: {ip}")
        return jsonify({"error": "Too many login attempts. IP blocked for 30 minutes."}), 403

    # Get request data
    try:
        data = request.get_json()
    except Exception as e:
        security_logger.error(f"Failed to parse JSON from login request: {e}")
        return jsonify({"error": "Invalid request format"}), 400
    
    if not data:
        security_logger.error(f"No JSON data in login request from {ip}")
        return jsonify({"error": "Missing request body"}), 400
        
    username = sanitize_input(data.get("username", ""))
    password = data.get("password", "")
    
    security_logger.debug(f"Raw request data: username_key_exists={('username' in data)}, password_key_exists={('password' in data)}")
    security_logger.debug(f"After sanitize: username='{username}' (len={len(username)}), password='{('*' * len(password) if password else 'EMPTY')}'")

    # Debug logging
    security_logger.debug(f"Login attempt - username: {username}, ADMIN_USERNAME: {ADMIN_USERNAME}")
    security_logger.debug(f"ADMIN_PASSWORD loaded: {bool(ADMIN_PASSWORD)}, length: {len(ADMIN_PASSWORD) if ADMIN_PASSWORD else 0}")
    
    if ADMIN_PASSWORD is None or ADMIN_PASSWORD == "":
        security_logger.error(f"✗ CRITICAL: ADMIN_PASSWORD is empty or None! Cannot authenticate")
    
    # Verify credentials
    provided_hash = hash_password(password)
    expected_hash = hash_password(ADMIN_PASSWORD) if ADMIN_PASSWORD else "NO_PASSWORD"
    
    if username == ADMIN_USERNAME and hash_password(password) == hash_password(ADMIN_PASSWORD):
        # Reset login attempts on successful login
        if ip in login_attempts:
            del login_attempts[ip]
        
        # Generate JWT token
        token = jwt.encode(
            {
                "username": username,
                "exp": datetime.utcnow() + timedelta(seconds=SESSION_TIMEOUT),
                "iat": datetime.utcnow()
            },
            JWT_SECRET,
            algorithm="HS256"
        )
        
        # ⭐ Set session to mark as authenticated
        session['authenticated'] = True
        session['username'] = username
        session['token'] = token
        session.permanent = True
        
        security_logger.info(f"✓ Successful login: {username} from {ip}")
        return jsonify({
            "success": True,
            "token": token,
            "username": username
        })
    
    # Failed login
    security_logger.warning(f"✗ Failed login attempt: {username} from {ip} (username_match={username == ADMIN_USERNAME}, password_match={provided_hash == expected_hash})")
    return jsonify({"error": "Invalid credentials"}), 401

@app.route("/api/logout", methods=["POST"])
def logout():
    """Logout endpoint"""
    session.clear()
    return jsonify({"success": True})

@app.route("/api/debug/config", methods=["GET"])
def debug_config():
    """Debug endpoint to check configuration loading (REMOVE IN PRODUCTION)"""
    return jsonify({
        "admin_username": ADMIN_USERNAME,
        "admin_password_loaded": bool(ADMIN_PASSWORD),
        "admin_password_length": len(ADMIN_PASSWORD) if ADMIN_PASSWORD else 0,
        "jwt_secret_loaded": bool(JWT_SECRET),
        "jwt_secret_length": len(JWT_SECRET) if JWT_SECRET else 0,
        "auth_enabled": AUTH_ENABLED,
        "config_source": "secure_loader"
    })

@app.route("/api/debug/login-info")
def debug_login_info():
    """Debug endpoint to check login configuration"""
    return jsonify({
        "status": "ok",
        "admin_username": ADMIN_USERNAME,
        "admin_password_configured": bool(ADMIN_PASSWORD),
        "admin_password_length": len(ADMIN_PASSWORD) if ADMIN_PASSWORD else 0,
        "auth_enabled": AUTH_ENABLED,
        "message": f"Admin login is configured. Use username: '{ADMIN_USERNAME}' with password from config"
    })

@app.route("/api/config")
def get_admin_config():
    """API endpoint to get server configuration"""
    # Check if external URL is configured (e.g., CF Tunnel)
    external_url = get_config("server", "external_url", default=None)
    
    # Determine protocol for user server
    user_server_https = get_config("server", "use_https", default=True)
    user_server_protocol = "https" if user_server_https else "http"
    
    if external_url:
        # Use external URL as-is (already includes protocol and domain)
        return jsonify({
            "mainServerUrl": external_url,
            "mainServerPort": MAIN_SERVER_PORT,
            "mainServerProtocol": user_server_protocol,
            "adminPort": ADMIN_PORT
        })
    else:
        # Fall back to localhost/127.0.0.1
        return jsonify({
            "mainServerPort": MAIN_SERVER_PORT,
            "mainServerProtocol": user_server_protocol,
            "adminPort": ADMIN_PORT
        })

@app.route("/api/oem-config")
def get_oem_config_admin():
    """Get OEM configuration for frontend"""
    return jsonify(app.config.get('OEM', {}))

@app.route("/api/tts/cache-stats", methods=["GET"])
@require_admin_auth
@rate_limit_check
def get_tts_cache_stats():
    """
    Get TTS synthesis cache statistics (admin only)
    
    Makes a request to the user server to fetch cache stats.
    Requires admin authentication.
    
    Note: Always uses localhost for internal communication.
    external_url is only for external client access, not server-to-server.
    """
    try:
        # Always use localhost for internal server-to-server communication
        # external_url (CF tunnel, etc.) is for external clients only
        user_server_port = get_config('server', 'port', default=1915)
        user_server_url = f'http://localhost:{user_server_port}'
        
        logger.debug(f"Fetching TTS cache stats from user server: {user_server_url}")
        
        # Request cache stats from user server
        # No need for auth header - user server trusts admin panel requests
        response = requests.get(
            f'{user_server_url}/api/tts/cache-stats',
            timeout=5,
            verify=False  # For self-signed certs
        )
        
        if response.status_code == 200:
            data = response.json()
            logger.debug(f"✅ TTS cache stats retrieved: {data}")
            return jsonify({
                'success': True,
                'cache_items': data.get('cache_items', 0),
                'cache_size_mb': data.get('cache_size_mb', 0),
                'cache_ttl_seconds': data.get('cache_ttl_seconds', 3600),
                'max_cache_size_mb': data.get('max_cache_size_mb', 1000),
                'max_cache_items': data.get('max_cache_items', 1000),
                'timestamp': datetime.utcnow().isoformat()
            })
        else:
            error_msg = f'User server error: {response.status_code}'
            try:
                error_data = response.json()
                error_msg = error_data.get('error', error_msg)
            except:
                pass
            logger.warning(f"⚠️ {error_msg}")
            return jsonify({
                'success': False,
                'error': error_msg
            }), response.status_code
    
    except Exception as e:
        logger.error(f"❌ Error fetching TTS cache stats: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route("/api/tts/cache-clear", methods=["POST"])
@require_admin_auth
@rate_limit_check
def clear_tts_cache():
    """
    Clear all TTS synthesis cache (admin only)
    
    Makes a request to the user server to clear cache.
    Requires admin authentication. This action is logged for audit purposes.
    
    Note: Always uses localhost for internal communication.
    external_url is only for external client access, not server-to-server.
    """
    try:
        # Always use localhost for internal server-to-server communication
        # external_url (CF tunnel, etc.) is for external clients only
        user_server_port = get_config('server', 'port', default=1915)
        user_server_url = f'http://localhost:{user_server_port}'
        
        logger.debug(f"Clearing TTS cache on user server: {user_server_url}")
        
        # Request cache clear from user server
        # No need for auth header - user server trusts admin panel requests
        response = requests.post(
            f'{user_server_url}/api/tts/cache-clear',
            timeout=5,
            verify=False  # For self-signed certs
        )
        
        if response.status_code == 200:
            data = response.json()
            cleared_items = data.get('cleared_items', 0)
            freed_mb = data.get('freed_mb', 0)
            
            admin_session_user = session.get('username', 'unknown')
            client_ip = get_client_ip()
            
            # Detailed security audit log
            security_logger.info(f"🗑️ ADMIN_ACTION: TTS cache cleared | Admin: {admin_session_user} | IP: {client_ip} | Items: {cleared_items} | Freed: {freed_mb}MB")
            logger.info(f"✅ TTS cache cleared: {cleared_items} items, {freed_mb:.2f}MB freed by admin {admin_session_user}")
            
            return jsonify({
                'success': True,
                'cleared_items': cleared_items,
                'freed_mb': freed_mb,
                'message': f"Cleared {cleared_items} items, freed {freed_mb}MB"
            })
        else:
            error_msg = f'User server error: {response.status_code}'
            try:
                error_data = response.json()
                error_msg = error_data.get('error', error_msg)
            except:
                pass
            logger.warning(f"⚠️ {error_msg}")
            return jsonify({
                'success': False,
                'error': error_msg
            }), response.status_code
    
    except Exception as e:
        logger.error(f"❌ Error clearing TTS cache: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route("/api/protected-endpoint")
@require_auth
@rate_limit_check
def protected_endpoint():
    """Example protected endpoint"""
    return jsonify({"message": "Access granted"})

@app.route("/health")
def health():
    """Health check endpoint"""
    return {"status": "healthy", "service": "admin-frontend"}, 200

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    ip = get_client_ip()
    security_logger.info(f"404 error from {ip}: {request.path}")
    return {"error": "Not found"}, 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    ip = get_client_ip()
    security_logger.error(f"500 error from {ip}: {error}")
    return {"error": "Internal server error"}, 500

# ──────────────────────────────────────────
# WebSocket Security
# ──────────────────────────────────────────
@socketio.on('connect')
def handle_connect(auth):
    """Handle WebSocket connection with rate limiting"""
    ip = get_client_ip()

    # Check if IP is blocked
    if is_ip_blocked(ip):
        security_logger.warning(f"Blocked IP attempted WebSocket connection: {ip}")
        return False

    # Check WebSocket connection limit
    if websocket_connections[ip] >= MAX_WS_CONNECTIONS:
        security_logger.warning(f"Too many WebSocket connections from {ip}")
        return False

    websocket_connections[ip] += 1
    security_logger.info(f"WebSocket connected: {ip} (total: {websocket_connections[ip]})")

@socketio.on('disconnect')
def handle_disconnect():
    """Handle WebSocket disconnection"""
    ip = get_client_ip()
    if websocket_connections[ip] > 0:
        websocket_connections[ip] -= 1
    security_logger.info(f"WebSocket disconnected: {ip}")

# ──────────────────────────────────────────
# Request Logging Middleware
# ──────────────────────────────────────────
@app.before_request
def log_request():
    """Log all requests for security monitoring"""
    ip = get_client_ip()

    # Log suspicious patterns
    suspicious_patterns = ['..', '<script>', 'DROP TABLE', 'SELECT *', 'UNION SELECT']
    request_str = str(request.path) + str(request.args) + str(request.get_data())

    for pattern in suspicious_patterns:
        if pattern.lower() in request_str.lower():
            security_logger.warning(
                f"Suspicious request from {ip}: {request.method} {request.path}"
            )
            break

# ──────────────────────────────────────────
# Main Entry
# ──────────────────────────────────────────
if __name__ == "__main__":
    logger.info("Starting EzySpeechTranslate Admin Server...")
    logger.info(f"Protocol: {'HTTPS' if USE_HTTPS else 'HTTP'}")
    logger.info(f"Security logging: logs/security.log")
    
    protocol = "https" if USE_HTTPS else "http"
    logger.info(f"Login Page: {protocol}://{ADMIN_HOST}:{ADMIN_PORT}/login")
    logger.info(f"Admin Interface: {protocol}://{ADMIN_HOST}:{ADMIN_PORT}/admin")
    
    # Check for external URL configuration
    external_url = get_config("server", "external_url", default=None)
    if external_url:
        logger.info(f"User Server (external): {external_url}")
        logger.info("ℹ️  Using CF Tunnel or reverse proxy configuration")
    else:
        logger.info(f"User Client expected at: {protocol}://{ADMIN_HOST}:{MAIN_SERVER_PORT}")

    try:
        listener = eventlet.listen((ADMIN_HOST, ADMIN_PORT))

        if USE_HTTPS:
            cert_file = os.path.join(SSL_DIR, "cert.pem")
            key_file = os.path.join(SSL_DIR, "key.pem")

            if not (os.path.exists(cert_file) and os.path.exists(key_file)):
                logger.error(f"SSL certificate or key missing in {SSL_DIR}")
                print("\nGenerate with:\n")
                print(f"cd {SSL_DIR}")
                print("openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes")
                exit(1)

            ssl_listener = eventlet.wrap_ssl(
                listener,
                certfile=cert_file,
                keyfile=key_file,
                server_side=True
            )
            eventlet.wsgi.server(ssl_listener, app)
        else:
            eventlet.wsgi.server(listener, app)

    except PermissionError:
        logger.error(f"Permission denied on port {ADMIN_PORT}. Use port >1024 or run with sudo.")
    except OSError as e:
        logger.error(f"Failed to bind to port {ADMIN_PORT}: {e}")
    except Exception as e:
        logger.error(f"Server failed to start: {e}")