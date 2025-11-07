"""
EzySpeechTranslate Admin Frontend Server
Serves the admin HTML interface on a separate port
"""

from flask import Flask, render_template, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO
import yaml
import logging
import os

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
MAIN_SERVER_PORT = config.get('server', {}).get('port', 5000)

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
    logger.info(f"Starting EzySpeechTranslate Admin Frontend Server...")
    logger.info(f"Admin Interface: http://{ADMIN_HOST}:{ADMIN_PORT}")
    logger.info(f"User Client should be running on: http://{ADMIN_HOST}:{MAIN_SERVER_PORT}")

    # Create templates directory if not exists
    os.makedirs('templates', exist_ok=True)

    # Replace app.run() with socketio.run()
    socketio.run(
        app,
        host=ADMIN_HOST,
        port=ADMIN_PORT,
        debug=config.get('admin_server', {}).get('debug', False)
    )