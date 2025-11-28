"""
EzySpeechTranslate Admin Server (HTTPS Version)
Serves the admin HTML interface securely with eventlet SSL
"""

from flask import Flask, render_template, jsonify, redirect, url_for, request, session
from flask_cors import CORS
from flask_socketio import SocketIO
import yaml
import logging
import os
import sys
import eventlet
import eventlet.wsgi
import hashlib
import jwt
import time
from datetime import datetime, timedelta
from functools import wraps
from collections import defaultdict

# ──────────────────────────────────────────
# Path Setup
# ──────────────────────────────────────────
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CONFIG_DIR = os.path.join(BASE_DIR, "config")
SSL_DIR = os.path.join(CONFIG_DIR, "ssl")
LOGS_DIR = os.path.join(BASE_DIR, "logs")

TEMPLATE_DIR = os.path.join(APP_DIR, "templates")
STATIC_DIR = os.path.join(APP_DIR, "static")

# Ensure logs directory exists
os.makedirs(LOGS_DIR, exist_ok=True)

# ──────────────────────────────────────────
# Logging Setup
# ──────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
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
sys.path.insert(0, os.path.join(BASE_DIR, 'config'))

config_file_path = os.path.join(CONFIG_DIR, "config.yaml")

try:
    from secure_loader import SecureConfig
    config_loader = SecureConfig(os.path.join(CONFIG_DIR, 'config.yaml'))

    def get_config(*keys, default=None):
        return config_loader.get(*keys, default=default)

    logger.info("✓ Loaded encrypted configuration")

except ImportError:
    logger.warning("Secure loader not found, using default YAML loading")

    try:
        with open(config_file_path, "r") as f:
            config_data = yaml.safe_load(f) or {}

        def get_config(*keys, default=None):
            val = config_data
            for key in keys:
                if isinstance(val, dict):
                    val = val.get(key)
                    if val is None:
                        return default
                else:
                    return default
            return val if val is not None else default

    except Exception as e:
        logger.error(f"Failed to load config: {e}")

        def get_config(*keys, default=None):
            return default

# ──────────────────────────────────────────
# Security Configuration
# ──────────────────────────────────────────
AUTH_ENABLED = get_config("authentication", "enabled", default=True)
ADMIN_USERNAME = get_config("authentication", "admin_username", default="admin")
ADMIN_PASSWORD = get_config("authentication", "admin_password", default="admin123")
JWT_SECRET = get_config("authentication", "jwt_secret", default="change-this-secret")
SESSION_TIMEOUT = get_config("authentication", "session_timeout", default=7200)

# Rate limiting settings
RATE_LIMIT_ENABLED = get_config("advanced", "security", "rate_limit_enabled", default=True)
MAX_REQUESTS_PER_MINUTE = get_config("advanced", "security", "max_requests_per_minute", default=60)

# Brute force protection
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION = 1800  # 30 minutes in seconds
LOGIN_RATE_LIMIT = 5  # Max 5 login attempts per minute

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
socketio = SocketIO(app, cors_allowed_origins="*")

# ──────────────────────────────────────────
# Server Settings
# ──────────────────────────────────────────
ADMIN_PORT = get_config("admin_server", "port", default=5001)
ADMIN_HOST = get_config("admin_server", "host", default="0.0.0.0")
MAIN_SERVER_PORT = get_config("server", "port", default=1915)

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

    data = request.get_json()
    username = sanitize_input(data.get("username", ""))
    password = data.get("password", "")

    # Verify credentials
    if username == ADMIN_USERNAME and hash_password(password) == hash_password(ADMIN_PASSWORD):
        # Reset login attempts on successful login
        if ip in login_attempts:
            del login_attempts[ip]

        # Generate token
        token = generate_token(username)

        # Set session
        session['authenticated'] = True
        session['username'] = username

        security_logger.info(f"Successful login: {username} from {ip}")

        return jsonify({
            "success": True,
            "token": token,
            "username": username
        })

    # Failed login
    security_logger.warning(f"Failed login attempt: {username} from {ip}")
    return jsonify({"error": "Invalid credentials"}), 401

@app.route("/api/logout", methods=["POST"])
def logout():
    """Logout endpoint"""
    session.clear()
    return jsonify({"success": True})

@app.route("/api/config")
@rate_limit_check
def get_admin_config():
    """API endpoint to get server configuration"""
    return jsonify({
        "mainServerPort": MAIN_SERVER_PORT,
        "adminPort": ADMIN_PORT
    })

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
def handle_connect():
    """Handle WebSocket connection with rate limiting"""
    ip = get_client_ip()

    # Check if IP is blocked
    if is_ip_blocked(ip):
        security_logger.warning(f"Blocked IP attempted WebSocket connection: {ip}")
        return False

    # Check WebSocket connection limit (max 5 per IP)
    if websocket_connections[ip] >= 5:
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
    logger.info(f"Security logging: logs/security.log")
    logger.info(f"Login Page: https://{ADMIN_HOST}:{ADMIN_PORT}/login")
    logger.info(f"Admin Interface: https://{ADMIN_HOST}:{ADMIN_PORT}/admin")
    logger.info(f"User Client expected at: http://{ADMIN_HOST}:{MAIN_SERVER_PORT}")

    cert_file = os.path.join(SSL_DIR, "cert.pem")
    key_file = os.path.join(SSL_DIR, "key.pem")

    if not (os.path.exists(cert_file) and os.path.exists(key_file)):
        logger.error(f"SSL certificate or key missing in {SSL_DIR}")
        print("\nGenerate with:\n")
        print(f"cd {SSL_DIR}")
        print("openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes")
        exit(1)

    try:
        listener = eventlet.listen((ADMIN_HOST, ADMIN_PORT))
        ssl_listener = eventlet.wrap_ssl(
            listener,
            certfile=cert_file,
            keyfile=key_file,
            server_side=True
        )
        eventlet.wsgi.server(ssl_listener, app)

    except PermissionError:
        logger.error(f"Permission denied on port {ADMIN_PORT}. Use port >1024 or run with sudo.")
    except OSError as e:
        logger.error(f"Failed to bind to port {ADMIN_PORT}: {e}")
    except Exception as e:
        logger.error(f"Server failed to start: {e}")