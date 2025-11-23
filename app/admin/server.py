"""
EzySpeechTranslate Admin Frontend Server (HTTPS Version)
Serves the admin HTML interface securely with eventlet SSL
"""

from flask import Flask, render_template, jsonify, redirect, url_for
from flask_cors import CORS
from flask_socketio import SocketIO
import yaml
import logging
import os
import eventlet
import eventlet.wsgi

# ──────────────────────────────────────────
# Path Setup
# ──────────────────────────────────────────
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CONFIG_DIR = os.path.join(BASE_DIR, "config")
SSL_DIR = os.path.join(CONFIG_DIR, "ssl")

TEMPLATE_DIR = os.path.join(APP_DIR, "templates")
STATIC_DIR = os.path.join(APP_DIR, "static")

# ──────────────────────────────────────────
# Logging
# ──────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────
# Load config.yaml
# ──────────────────────────────────────────
config_file_path = os.path.join(CONFIG_DIR, "config.yaml")

try:
    with open(config_file_path, "r") as f:
        config = yaml.safe_load(f)
except Exception as e:
    logger.error(f"Failed to load config ({config_file_path}): {e}")
    config = {}

# ──────────────────────────────────────────
# Flask App
# ──────────────────────────────────────────
app = Flask(__name__, static_folder=STATIC_DIR, template_folder=TEMPLATE_DIR)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# ──────────────────────────────────────────
# Server Settings
# ──────────────────────────────────────────
ADMIN_PORT = config.get("admin_server", {}).get("port", 5001)
ADMIN_HOST = config.get("admin_server", {}).get("host", "0.0.0.0")
MAIN_SERVER_PORT = config.get("server", {}).get("port", 1915)

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

@app.route("/api/config")
def get_config():
    """API endpoint to get server configuration"""
    return jsonify({
        "mainServerPort": MAIN_SERVER_PORT,
        "adminPort": ADMIN_PORT
    })

@app.route("/health")
def health():
    """Health check endpoint"""
    return {"status": "healthy", "service": "admin-frontend"}, 200

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return {"error": "Not found"}, 404


# ──────────────────────────────────────────
# Main Entry
# ──────────────────────────────────────────
if __name__ == "__main__":
    logger.info("Starting EzySpeechTranslate Admin Server...")
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