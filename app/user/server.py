"""
EzySpeechTranslate Backend Server - Simplified HTTPS Version
Real-time speech recognition and translation system
"""

import os
import yaml
import logging
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import jwt
from functools import wraps
import hashlib
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

# Change to project root for relative paths
os.chdir(BASE_DIR)


# ──────────────────────────────────────────
# Configuration Loader
# ──────────────────────────────────────────

class Config:
    def __init__(self, config_path='config/config.yaml'):
        try:
            with open(config_path, 'r') as f:
                self.data = yaml.safe_load(f) or {}
        except FileNotFoundError:
            print(f"Error: Configuration file not found at {config_path}")
            self.data = {}

    def get(self, *keys, default=None):
        """Safely get nested config value"""
        val = self.data
        for key in keys:
            if isinstance(val, dict):
                val = val.get(key, default)
            else:
                return default
        return val if val is not None else default


config = Config()


# ──────────────────────────────────────────
# Logging Setup
# ──────────────────────────────────────────

log_file = config.get('logging', 'file', default='logs/app.log')
log_dir = os.path.dirname(log_file) or 'logs'
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=config.get('logging', 'level', default='INFO'),
    format=config.get('logging', 'format', 
                     default='%(asctime)s - %(name)s - %(levelname)s - %(message)s'),
    handlers=[
        RotatingFileHandler(
            log_file,
            maxBytes=config.get('logging', 'max_bytes', default=10 * 1024 * 1024),
            backupCount=config.get('logging', 'backup_count', default=5)
        ),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────
# Flask Initialization
# ──────────────────────────────────────────

app = Flask(__name__, 
            template_folder=TEMPLATE_DIR,
            static_folder=STATIC_DIR,
            static_url_path='/static')
app.config['SECRET_KEY'] = config.get('server', 'secret_key', default='changeme')
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')


# ──────────────────────────────────────────
# In-memory Storage
# ──────────────────────────────────────────

translations_history = []
connected_clients = set()
admin_sessions = {}


# ──────────────────────────────────────────
# Authentication
# ──────────────────────────────────────────

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not config.get('authentication', 'enabled', default=True):
            return f(*args, **kwargs)

        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if not token:
            token = request.args.get('token', '')

        if not token:
            return jsonify({'error': 'No token provided'}), 401

        try:
            jwt.decode(
                token,
                config.get('authentication', 'jwt_secret', default='secret'),
                algorithms=['HS256']
            )
            return f(*args, **kwargs)
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401

    return decorated


def is_admin(sid):
    """Check if session is authenticated admin"""
    if not config.get('authentication', 'enabled', default=True):
        return True
    return sid in admin_sessions


# ──────────────────────────────────────────
# Routes
# ──────────────────────────────────────────

@app.route('/')
def index():
    """Main client interface"""
    return render_template('user.html')


@app.route('/admin')
def admin_route():
    """Admin interface route"""
    return jsonify({'message': 'Use admin_server.py for admin interface'}), 404


@app.route('/api/login', methods=['POST'])
def login():
    """Admin login endpoint"""
    data = request.json or {}
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    if not username or not password:
        return jsonify({'success': False, 'error': 'Missing credentials'}), 400

    # Hash password for comparison
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    stored_password_hash = hashlib.sha256(
        config.get('authentication', 'admin_password', default='admin123').encode()
    ).hexdigest()

    if (username == config.get('authentication', 'admin_username', default='admin') and
            password_hash == stored_password_hash):
        # Generate JWT token
        token = jwt.encode(
            {
                'username': username,
                'exp': datetime.utcnow() + timedelta(
                    seconds=config.get('authentication', 'session_timeout', default=7200)
                )
            },
            config.get('authentication', 'jwt_secret', default='secret'),
            algorithm='HS256'
        )

        logger.info(f"✓ Admin login successful: {username}")
        return jsonify({
            'success': True,
            'token': token,
            'username': username
        })

    logger.warning(f"✗ Failed login attempt: {username}")
    return jsonify({'success': False, 'error': 'Invalid credentials'}), 401


@app.route('/api/config', methods=['GET'])
@require_auth
def get_config():
    """Get current configuration"""
    return jsonify({
        'audio': config.get('audio'),
        'whisper': config.get('whisper'),
        'translation': config.get('translation'),
        'mainServerPort': config.get('server', 'port', default=1915)
    })


@app.route('/api/translations', methods=['GET'])
@require_auth
def get_translations():
    """Get translation history"""
    return jsonify({'translations': translations_history})


@app.route('/api/translations/clear', methods=['POST'])
@require_auth
def clear_translations():
    """Clear translation history"""
    global translations_history
    translations_history = []
    socketio.emit('history_cleared')
    logger.info("Translation history cleared")
    return jsonify({'success': True})


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'clients': len(connected_clients),
        'translations': len(translations_history)
    })


@app.route('/api/export/<format>', methods=['GET'])
@require_auth
def export_translations(export_format):
    """Export translations in various formats"""
    if export_format == 'json':
        return jsonify({'translations': translations_history})

    elif export_format == 'txt':
        output = "EzySpeechTranslate Export\n"
        output += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        output += "=" * 60 + "\n\n"

        for item in translations_history:
            output += f"[{item['id']}] {item['timestamp']}\n"
            output += f"Original: {item['original']}\n"
            output += f"Corrected: {item['corrected']}\n"
            if item['is_corrected']:
                output += "(✓ Manually corrected)\n"
            output += "-" * 60 + "\n\n"

        return output, 200, {'Content-Type': 'text/plain; charset=utf-8'}

    elif export_format == 'csv':
        output = "ID,Timestamp,Original,Corrected,Is_Corrected\n"
        
        for item in translations_history:
            row = [
                str(item['id']),
                item['timestamp'],
                f'"{item["original"].replace(chr(34), chr(34)*2)}"',
                f'"{item["corrected"].replace(chr(34), chr(34)*2)}"',
                'Yes' if item['is_corrected'] else 'No'
            ]
            output += ','.join(row) + '\n'

        return output, 200, {'Content-Type': 'text/csv; charset=utf-8'}

    elif export_format == 'srt':
        output = ""
        for i, item in enumerate(translations_history, 1):
            start_seconds = (i - 1) * 5
            end_seconds = i * 5

            start_time = f"00:{start_seconds // 60:02d}:{start_seconds % 60:02d},000"
            end_time = f"00:{end_seconds // 60:02d}:{end_seconds % 60:02d},000"

            output += f"{i}\n"
            output += f"{start_time} --> {end_time}\n"
            output += f"{item['corrected']}\n\n"

        return output, 200, {'Content-Type': 'text/plain; charset=utf-8'}

    else:
        return jsonify({'error': f'Unsupported format: {export_format}'}), 400


# ──────────────────────────────────────────
# WebSocket Events
# ──────────────────────────────────────────

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    client_id = request.sid
    connected_clients.add(client_id)
    logger.info(f"Client connected: {client_id} (Total: {len(connected_clients)})")

    # Send existing history to new client
    emit('history', translations_history)


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    client_id = request.sid
    connected_clients.discard(client_id)
    logger.info(f"👥 Client disconnected: {client_id} (Total: {len(connected_clients)})")
    
    # Remove from admin sessions if applicable
    admin_sessions.pop(client_id, None)


@socketio.on('admin_connect')
def handle_admin_connect(data):
    """Handle admin GUI connection"""
    token = data.get('token') if data else None

    if not config.get('authentication', 'enabled', default=True):
        emit('admin_connected', {'success': True})
        logger.info("Admin connected (auth disabled)")
        return

    if not token:
        emit('admin_connected', {'success': False, 'error': 'No token provided'})
        return

    try:
        decoded = jwt.decode(
            token,
            config.get('authentication', 'jwt_secret', default='secret'),
            algorithms=['HS256']
        )
        admin_sessions[request.sid] = decoded['username']
        emit('admin_connected', {'success': True})
        logger.info(f"Admin connected: {decoded['username']}")
    except jwt.ExpiredSignatureError:
        emit('admin_connected', {'success': False, 'error': 'Token expired'})
        logger.warning("Admin connection failed: Token expired")
    except jwt.InvalidTokenError:
        emit('admin_connected', {'success': False, 'error': 'Invalid token'})
        logger.warning("Admin connection failed: Invalid token")


@socketio.on('new_transcription')
def handle_new_transcription(data):
    """Handle new transcription from admin"""
    if not is_admin(request.sid):
        emit('error', {'message': 'Unauthorized'})
        return

    raw_text = data.get('text', '').strip() if data else ''
    if not raw_text:
        return

    # Create translation data
    translation_data = {
        'id': len(translations_history),
        'timestamp': datetime.now().strftime('%H:%M:%S'),
        'original': raw_text,
        'corrected': raw_text,
        'translated': None,
        'is_corrected': False,
        'source_language': data.get('language', 'en') if data else 'en',
        'confidence': data.get('confidence')
    }

    translations_history.append(translation_data)
    socketio.emit('new_translation', translation_data)
    logger.info(f"[NEW] {len(raw_text)} chars: '{raw_text[:70]}{'...' if len(raw_text) > 70 else ''}'")


@socketio.on('correct_translation')
def handle_correct_translation(data):
    """Handle translation correction from admin"""
    if not is_admin(request.sid):
        emit('error', {'message': 'Unauthorized'})
        return

    if not data:
        return

    translation_id = data.get('id')
    corrected_text = data.get('corrected_text', '').strip()

    if not isinstance(translation_id, int) or translation_id < 0:
        emit('error', {'message': 'Invalid translation ID'})
        return

    if translation_id >= len(translations_history):
        emit('error', {'message': 'Translation ID out of range'})
        return

    if not corrected_text:
        emit('error', {'message': 'Corrected text cannot be empty'})
        return

    # Update translation
    translations_history[translation_id]['corrected'] = corrected_text
    translations_history[translation_id]['is_corrected'] = True
    translations_history[translation_id]['translated'] = None

    # Broadcast correction to all clients
    socketio.emit('translation_corrected', translations_history[translation_id])
    logger.info(f"✏️ [CORRECTED] ID {translation_id}: '{corrected_text[:70]}...'")
    emit('correction_success', {'id': translation_id})


@socketio.on('update_order')
def handle_update_order(data):
    """Handle order update from admin GUI"""
    if not is_admin(request.sid):
        emit('error', {'message': 'Unauthorized'})
        return

    if not data:
        return

    global translations_history
    new_order = data.get('translations', [])

    if not isinstance(new_order, list):
        emit('error', {'message': 'Invalid order data'})
        return

    translations_history = new_order
    socketio.emit('order_updated', {
        'translations': translations_history
    }, include_self=False)

    logger.info(f"[ORDER] Updated: {len(translations_history)} items")
    emit('order_update_success', {'count': len(translations_history)})


@socketio.on('clear_history')
def handle_clear_history():
    """Handle clear history request from admin"""
    if not is_admin(request.sid):
        emit('error', {'message': 'Unauthorized'})
        return

    global translations_history
    translations_history = []

    socketio.emit('history_cleared')
    logger.info("[CLEARED] History cleared and broadcast")


# ──────────────────────────────────────────
# Error Handlers
# ──────────────────────────────────────────

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal error: {error}")
    return jsonify({'error': 'Internal server error'}), 500


# ──────────────────────────────────────────
# HTTPS Server Start
# ──────────────────────────────────────────

if __name__ == '__main__':
    logger.info("Starting EzySpeechTranslate User Backend Server...")

    # Configuration logging
    auth_enabled = config.get('authentication', 'enabled', default=True)
    logger.info(f"Authentication: {'Enabled' if auth_enabled else 'Disabled'}")

    host = config.get('server', 'host', default='0.0.0.0')
    port = config.get('server', 'port', default=1915)
    debug = config.get('server', 'debug', default=False)

    logger.info(f"Server: {host}:{port}")

    # Ensure required directories exist
    for directory in ['logs']:
        os.makedirs(directory, exist_ok=True)

    # Check SSL certificates
    cert_file = os.path.join(SSL_DIR, 'cert.pem')
    key_file = os.path.join(SSL_DIR, 'key.pem')

    if not (os.path.exists(cert_file) and os.path.exists(key_file)):
        logger.error("SSL certificate or key not found!")
        print("\nGenerate SSL certificates with:\n")
        print(f"  cd {SSL_DIR}")
        print("  openssl req -x509 -newkey rsa:2048 -nodes \\")
        print("    -out cert.pem -keyout key.pem -days 365 \\")
        print('    -subj "/CN=localhost"\n')
        exit(1)

    # Start server
    try:
        logger.info(f"SSL: {cert_file}")
        logger.info("All checks passed, starting server...")
        
        listener = eventlet.listen((host, port))
        ssl_listener = eventlet.wrap_ssl(
            listener, 
            certfile=cert_file, 
            keyfile=key_file, 
            server_side=True
        )
        logger.info(f"Server is running at https://{host}:{port}")
        eventlet.wsgi.server(ssl_listener, app)
        
    except PermissionError:
        logger.error(f"Permission denied on port {port}. Try port > 1024 or run with sudo.")
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