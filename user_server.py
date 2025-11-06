"""
EzySpeechTranslate Backend Server - Simplified Version
Real-time speech recognition and translation system
Removed: Sentence merging functionality
"""

import os
import yaml
import logging
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from flask import Flask, render_template, request, jsonify, session
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import jwt
from functools import wraps
import hashlib


# Configuration loader
class Config:
    def __init__(self, config_path='config.yaml'):
        with open(config_path, 'r') as f:
            self.data = yaml.safe_load(f)

    def get(self, *keys, default=None):
        """Get nested config value"""
        val = self.data
        for key in keys:
            if isinstance(val, dict):
                val = val.get(key)
            else:
                return default
            if val is None:
                return default
        return val


# Initialize config
config = Config()

# Setup logging
log_dir = os.path.dirname(config.get('logging', 'file', default='logs/app.log'))
if log_dir and not os.path.exists(log_dir):
    os.makedirs(log_dir)

logging.basicConfig(
    level=config.get('logging', 'level', default='INFO'),
    format=config.get('logging', 'format'),
    handlers=[
        RotatingFileHandler(
            config.get('logging', 'file', default='logs/app.log'),
            maxBytes=config.get('logging', 'max_bytes', default=10485760),
            backupCount=config.get('logging', 'backup_count', default=5)
        ),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = config.get('server', 'secret_key')
CORS(app)

# Initialize SocketIO
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# In-memory storage
translations_history = []
connected_clients = set()
admin_sessions = {}


# Authentication decorator
def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not config.get('authentication', 'enabled', default=True):
            return f(*args, **kwargs)

        # Try to get token from header first
        token = request.headers.get('Authorization', '').replace('Bearer ', '')

        # If not in header, try URL parameter (for export/download links)
        if not token:
            token = request.args.get('token', '')

        if not token:
            return jsonify({'error': 'No token provided'}), 401

        try:
            jwt.decode(
                token,
                config.get('authentication', 'jwt_secret'),
                algorithms=['HS256']
            )
            return f(*args, **kwargs)
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401

    return decorated


# Routes
@app.route('/')
def index():
    """Main client interface"""
    return render_template('index.html')


@app.route('/admin')
def admin():
    """Admin interface route"""
    return jsonify({'message': 'Use admin_server.py for admin interface'})


@app.route('/api/login', methods=['POST'])
def login():
    """Admin login endpoint"""
    data = request.json
    username = data.get('username')
    password = data.get('password')

    # Hash password for comparison
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    stored_password_hash = hashlib.sha256(
        config.get('authentication', 'admin_password').encode()
    ).hexdigest()

    if (username == config.get('authentication', 'admin_username') and
            password_hash == stored_password_hash):
        # Generate JWT token
        token = jwt.encode(
            {
                'username': username,
                'exp': datetime.utcnow() + timedelta(
                    seconds=config.get('authentication', 'session_timeout', default=3600)
                )
            },
            config.get('authentication', 'jwt_secret'),
            algorithm='HS256'
        )

        logger.info(f"Admin login successful: {username}")
        return jsonify({
            'success': True,
            'token': token,
            'username': username
        })

    logger.warning(f"Failed login attempt: {username}")
    return jsonify({'success': False, 'error': 'Invalid credentials'}), 401


@app.route('/api/config', methods=['GET'])
@require_auth
def get_config():
    """Get current configuration"""
    return jsonify({
        'audio': config.get('audio'),
        'whisper': config.get('whisper'),
        'translation': config.get('translation')
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


# WebSocket events
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
    logger.info(f"Client disconnected: {client_id} (Total: {len(connected_clients)})")


@socketio.on('admin_connect')
def handle_admin_connect(data):
    """Handle admin GUI connection"""
    token = data.get('token')

    if not config.get('authentication', 'enabled', default=True):
        emit('admin_connected', {'success': True})
        logger.info("Admin connected (auth disabled)")
        return

    try:
        decoded = jwt.decode(
            token,
            config.get('authentication', 'jwt_secret'),
            algorithms=['HS256']
        )
        admin_sessions[request.sid] = decoded['username']
        emit('admin_connected', {'success': True})
        logger.info(f"Admin connected: {decoded['username']}")
    except jwt.InvalidTokenError:
        emit('admin_connected', {'success': False, 'error': 'Invalid token'})
        logger.warning("Admin connection failed: Invalid token")


@socketio.on('new_transcription')
def handle_new_transcription(data):
    """Handle new transcription - Direct pass-through"""
    if not is_admin(request.sid):
        emit('error', {'message': 'Unauthorized'})
        return

    raw_text = data.get('text', '').strip()
    if not raw_text:
        return

    # Direct pass-through - no sentence merging
    translation_data = {
        'id': len(translations_history),
        'timestamp': datetime.now().strftime('%H:%M:%S'),
        'original': raw_text,
        'corrected': raw_text,
        'translated': None,
        'is_corrected': False,
        'source_language': data.get('language', 'en')
    }

    translations_history.append(translation_data)
    socketio.emit('new_translation', translation_data)
    logger.info(f"[SENT] {len(raw_text)} chars: '{raw_text[:70]}...'")


@socketio.on('correct_translation')
def handle_correct_translation(data):
    """Handle translation correction from admin"""
    if not is_admin(request.sid):
        emit('error', {'message': 'Unauthorized'})
        return

    translation_id = data.get('id')
    corrected_text = data.get('corrected_text')

    if 0 <= translation_id < len(translations_history):
        translations_history[translation_id]['corrected'] = corrected_text
        translations_history[translation_id]['is_corrected'] = True
        translations_history[translation_id]['translated'] = None

        # Broadcast correction to all clients
        socketio.emit('translation_corrected', translations_history[translation_id])
        logger.info(f"Translation corrected: ID {translation_id}")
        emit('correction_success', {'id': translation_id})
    else:
        emit('error', {'message': 'Invalid translation ID'})


@socketio.on('update_order')
def handle_update_order(data):
    """Handle order update from admin GUI"""
    if not is_admin(request.sid):
        emit('error', {'message': 'Unauthorized'})
        return

    global translations_history
    new_order = data.get('translations', [])

    if new_order:
        translations_history = new_order
        socketio.emit('order_updated', {
            'translations': translations_history
        }, include_self=False)

        logger.info(f"[ORDER] Updated: {len(translations_history)} items")
        emit('order_update_success', {'count': len(translations_history)})
    else:
        emit('error', {'message': 'Invalid order data'})


@socketio.on('clear_history')
def handle_clear_history():
    """Handle clear history request from admin"""
    if not is_admin(request.sid):
        emit('error', {'message': 'Unauthorized'})
        return

    global translations_history
    translations_history = []

    socketio.emit('history_cleared')
    logger.info("History cleared and broadcast")


def is_admin(sid):
    """Check if session is authenticated admin"""
    if not config.get('authentication', 'enabled', default=True):
        return True
    return sid in admin_sessions


# Export functionality
@app.route('/api/export/<format>', methods=['GET'])
@require_auth
def export_translations(format):
    """Export translations in various formats"""
    if format == 'json':
        return jsonify({'translations': translations_history})

    elif format == 'txt':
        output = "EzySpeechTranslate Export\n"
        output += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        output += "=" * 60 + "\n\n"

        for item in translations_history:
            output += f"[{item['id']}] {item['timestamp']}\n"
            output += f"Original: {item['original']}\n"
            output += f"Corrected: {item['corrected']}\n"
            if item['is_corrected']:
                output += "(Manually corrected)\n"
            output += "-" * 60 + "\n\n"

        return output, 200, {'Content-Type': 'text/plain; charset=utf-8'}

    elif format == 'srt':
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
        return jsonify({'error': 'Unsupported format'}), 400


# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal error: {error}")
    return jsonify({'error': 'Internal server error'}), 500


# Main entry point
if __name__ == '__main__':
    logger.info("Starting EzySpeechTranslate Server (Simplified Version)...")
    logger.info(f"Authentication: {'Enabled' if config.get('authentication', 'enabled') else 'Disabled'}")
    logger.info(f"Server: {config.get('server', 'host')}:{config.get('server', 'port')}")

    # Create necessary directories
    for directory in ['logs', 'exports', 'data', 'templates']:
        if not os.path.exists(directory):
            os.makedirs(directory)

    socketio.run(
        app,
        host=config.get('server', 'host', default='0.0.0.0'),
        port=config.get('server', 'port', default=5000),
        debug=config.get('server', 'debug', default=False)
    )