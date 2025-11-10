"""
EzySpeechTranslate Admin Frontend Server (HTTPS Version)
Serves the admin HTML interface securely with eventlet SSL
"""

from flask import Flask, render_template, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO
import yaml
import logging
import os
import eventlet
import eventlet.wsgi

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Load config
try:
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)
except Exception as e:
    logger.error(f"Failed to load config: {e}")
    config = {}

# Initialize Flask app
app = Flask(__name__, static_folder='static')
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Admin server configuration
ADMIN_PORT = config.get('admin_server', {}).get('port', 5001)
ADMIN_HOST = config.get('admin_server', {}).get('host', '0.0.0.0')
MAIN_SERVER_PORT = config.get('server', {}).get('port', 1915)

@app.route('/')
def index():
    """Serve admin interface"""
    return render_template('admin.html')

@app.route('/api/config')
def get_config():
    """Get client configuration"""
    return jsonify({
        'mainServerPort': MAIN_SERVER_PORT,
        'adminPort': ADMIN_PORT
    })

@app.route('/health')
def health():
    """Health check endpoint"""
    return {'status': 'healthy', 'service': 'admin-frontend'}, 200

@app.errorhandler(404)
def not_found(error):
    return {'error': 'Not found'}, 404

if __name__ == '__main__':
    logger.info("Starting EzySpeechTranslate Admin Frontend Server (HTTPS)...")
    logger.info(f"Admin Interface: https://{ADMIN_HOST}:{ADMIN_PORT}")
    logger.info(f"User Client should be running on: http://{ADMIN_HOST}:{MAIN_SERVER_PORT}")

    # Ensure templates directory exists
    os.makedirs('templates', exist_ok=True)

    cert_file = 'cert.pem'
    key_file = 'key.pem'

    if not (os.path.exists(cert_file) and os.path.exists(key_file)):
        logger.error("SSL certificate or key not found!")
        print("\nGenerate with:\n")
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
        logger.error(f"Permission denied on port {ADMIN_PORT}. Try port > 1024 or run with sudo.")
    except OSError as e:
        logger.error(f"Failed to bind on {ADMIN_PORT}: {e}")
    except Exception as e:
        logger.error(f"Server failed to start: {e}")