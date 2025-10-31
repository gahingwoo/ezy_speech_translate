"""
EzySpeechTranslate Backend Server - With Sentence Merging
Real-time speech recognition and translation system
Added: Smart sentence merging functionality
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
from typing import List


# Smart Sentence Merger
class SmartSentenceMerger:
    """
    Smart sentence merger v5 - Micro-particle buffering and intelligent reassembly
    Like clay that can be broken down and reshaped!

    Strategy:
    1. Break text into micro-units (words/tokens)
    2. Buffer them intelligently
    3. Assemble into complete sentences when appropriate
    """

    def __init__(self, max_buffer_words=200, min_sentence_words=10):
        self.end_punctuations = {'.', '?', '!'}
        self.max_buffer_words = max_buffer_words
        self.min_sentence_words = min_sentence_words

        # Abbreviations that shouldn't trigger sentence split
        self.abbreviations = {
            'mr.', 'mrs.', 'ms.', 'dr.', 'prof.', 'sr.', 'jr.',
            'etc.', 'vs.', 'e.g.', 'i.e.', 'p.m.', 'a.m.',
            'st.', 'ave.', 'blvd.', 'dept.', 'inc.', 'corp.'
        }

        # Pause indicators (suggests sentence might end soon)
        self.pause_indicators = {',', ';', ':', '—', '–', '-'}

    def tokenize(self, text: str) -> list:
        """
        Break text into micro-particles (words + punctuation)
        Keeps punctuation attached to words when appropriate
        """
        import re

        # Pattern to split while keeping punctuation
        # Matches: word characters, apostrophes in words, or standalone punctuation
        pattern = r"\b[\w']+\b|[.,;:!?—–\-]"
        tokens = re.findall(pattern, text)

        return [t.strip() for t in tokens if t.strip()]

    def is_sentence_boundary(self, tokens: list, position: int) -> bool:
        """
        Check if position in token list is a sentence boundary
        More intelligent than just checking for period
        """
        if position >= len(tokens):
            return False

        token = tokens[position].lower()

        # Not a punctuation mark at all
        if token not in self.end_punctuations:
            return False

        # Question marks and exclamation marks are strong indicators
        if token in {'?', '!'}:
            return True

        # For periods, need more checks
        if token == '.':
            # Check if it's part of abbreviation
            if position > 0:
                prev_token = tokens[position - 1].lower()
                if prev_token + '.' in self.abbreviations:
                    return False

            # Check if followed by lowercase (continuation)
            if position + 1 < len(tokens):
                next_token = tokens[position + 1]
                if next_token and next_token[0].islower():
                    return False

            # Check for ellipsis (...)
            if position > 0 and tokens[position - 1] == '.':
                return False
            if position + 1 < len(tokens) and tokens[position + 1] == '.':
                return False

        return True

    def calculate_sentence_confidence(self, tokens: list) -> float:
        """
        Calculate how confident we are that tokens form a complete sentence
        Returns: 0.0 to 1.0
        """
        if not tokens:
            return 0.0

        confidence = 0.0

        # Check word count (longer = more likely complete)
        word_count = sum(1 for t in tokens if t not in self.end_punctuations | self.pause_indicators)

        # CRITICAL: Must have ending punctuation to be confident
        last_token = tokens[-1] if tokens else ''
        if last_token not in self.end_punctuations:
            # No ending punctuation = very low confidence
            return 0.1

        # Check for ellipsis at end (incomplete thought)
        if len(tokens) >= 3 and tokens[-1] == '.' and tokens[-2] == '.' and tokens[-3] == '.':
            return 0.2  # Very low - ellipsis means incomplete

        # CRITICAL: Check if ends with period but buffer seems incomplete
        if last_token == '.':
            # Check last 2-3 words before the period
            words_before_period = []
            for i in range(len(tokens) - 2, max(-1, len(tokens) - 5), -1):
                if i >= 0 and tokens[i] not in self.end_punctuations | self.pause_indicators:
                    words_before_period.insert(0, tokens[i].lower())

            # Words that strongly suggest incompleteness
            incomplete_endings = {
                'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to',
                'for', 'of', 'with', 'by', 'as', 'from', 'up', 'down', 'out',
                'be', 'is', 'are', 'was', 'were', 'been', 'being',
                'your', 'my', 'his', 'her', 'their', 'our', 'its'
            }

            # Check last word
            if words_before_period and words_before_period[-1] in incomplete_endings:
                return 0.25  # Very low - clearly incomplete

            # Check last two words for common incomplete patterns
            if len(words_before_period) >= 2:
                last_two = ' '.join(words_before_period[-2:])
                incomplete_patterns = {
                    'to be', 'to have', 'to get', 'to go', 'to do',
                    'will be', 'will have', 'can be', 'should be',
                    'and the', 'or the', 'but the', 'with the',
                    'in the', 'on the', 'at the', 'of the'
                }
                if last_two in incomplete_patterns:
                    return 0.25  # Very low

        # Now build up confidence for complete sentences
        base_confidence = 0.0

        if word_count >= self.min_sentence_words:
            base_confidence += 0.3
        if word_count >= self.min_sentence_words * 2:
            base_confidence += 0.2

        # Check ending punctuation quality
        if last_token in {'?', '!'}:
            base_confidence += 0.4  # Very confident
        elif last_token == '.':
            base_confidence += 0.3  # Moderately confident

        # Check if starts with capital (more likely a sentence start)
        if tokens and tokens[0] and len(tokens[0]) > 0 and tokens[0][0].isupper():
            base_confidence += 0.1

        # Bonus: Check for verb-like patterns
        verb_indicators = sum(1 for t in tokens if any(t.lower().endswith(suffix)
                             for suffix in ['ed', 'ing', 's', 'es']))
        if verb_indicators >= 2:
            base_confidence += 0.1

        return min(base_confidence, 1.0)

    def assemble_sentences(self, token_buffer: list) -> tuple:
        """
        Intelligently assemble tokens into sentences
        REWRITTEN: Simpler, more reliable logic
        Returns: (complete_sentences, remaining_tokens)
        """
        if not token_buffer:
            return [], []

        complete_sentences = []
        current_tokens = []

        for i in range(len(token_buffer)):
            current_tokens.append(token_buffer[i])
            current_token = token_buffer[i]

            # Only consider splitting at punctuation
            if current_token not in self.end_punctuations:
                continue

            # === CHECK 1: Ellipsis - never split ===
            if self._is_ellipsis(current_tokens):
                continue

            # === CHECK 2: Look ahead - is there a continuation? ===
            if self._has_continuation_ahead(token_buffer, i):
                continue

            # === CHECK 3: Is this a valid sentence boundary? ===
            if not self.is_sentence_boundary(current_tokens, len(current_tokens) - 1):
                continue

            # === CHECK 4: Calculate confidence ===
            confidence = self.calculate_sentence_confidence(current_tokens)

            # === CHECK 5: Must have high confidence ===
            if confidence < 0.75:
                continue

            # === CHECK 6: Reconstruct and final validation ===
            sentence = self.reconstruct_text(current_tokens)

            # No ellipsis in reconstructed text
            if sentence.rstrip().endswith('...'):
                continue

            # === ALL CHECKS PASSED - This is a complete sentence ===
            complete_sentences.append(sentence)
            current_tokens = []

        # Return complete sentences and remaining buffer
        return complete_sentences, current_tokens

    def _is_ellipsis(self, tokens: list) -> bool:
        """Check if token sequence ends with ellipsis"""
        if len(tokens) < 3:
            return False
        return (tokens[-1] == '.' and
                tokens[-2] == '.' and
                tokens[-3] == '.')

    def _has_continuation_ahead(self, all_tokens: list, current_position: int) -> bool:
        """
        Check if there's a continuation after current position
        This means we should NOT split here
        """
        next_position = current_position + 1

        # No next token = no continuation
        if next_position >= len(all_tokens):
            return False

        next_token = all_tokens[next_position]

        # Empty token
        if not next_token:
            return False

        # Check 1: Lowercase start = continuation
        if next_token[0].islower():
            return True

        # Check 2: Common connectors = continuation
        connectors = {
            'and', 'but', 'or', 'so', 'because', 'although', 'though',
            'while', 'if', 'when', 'where', 'which', 'that', 'who',
            'whom', 'whose', 'as', 'since', 'until', 'unless', 'than',
            'for', 'nor', 'yet'
        }

        if next_token.lower() in connectors:
            return True

        return False

    def reconstruct_text(self, tokens: list) -> str:
        """
        Reconstruct natural text from tokens
        Handles spacing around punctuation correctly
        """
        if not tokens:
            return ""

        result = []
        for i, token in enumerate(tokens):
            if token in self.end_punctuations | self.pause_indicators:
                # Punctuation: attach to previous word (no space before)
                if result:
                    result[-1] += token
                else:
                    result.append(token)
            else:
                result.append(token)

        return ' '.join(result)

    def should_force_send(self, tokens: list) -> bool:
        """
        Check if we should force send the buffer even if not confident
        ONLY if buffer is extremely long (prevent memory issues)
        """
        word_count = sum(1 for t in tokens if t not in self.end_punctuations | self.pause_indicators)
        # Very high threshold - only force if absurdly long
        return word_count >= self.max_buffer_words * 2

    def merge_by_completion(self, sentences: list) -> list:
        """
        Main entry point - merge text fragments intelligently
        NOTE: This method is for testing/compatibility only
        The real work is done in assemble_sentences()
        """
        # Tokenize all input
        all_tokens = []
        for sentence in sentences:
            all_tokens.extend(self.tokenize(sentence))

        if not all_tokens:
            return []

        # Assemble into sentences using the intelligent algorithm
        complete, remaining = self.assemble_sentences(all_tokens)

        # NEVER force send remaining tokens - they should stay in buffer
        # Only return complete sentences
        return complete if complete else []

    def get_buffer_info(self, tokens: list) -> dict:
        """
        Get information about current buffer state
        """
        word_count = sum(1 for t in tokens if t not in self.end_punctuations | self.pause_indicators)
        confidence = self.calculate_sentence_confidence(tokens)
        text = self.reconstruct_text(tokens)

        return {
            'token_count': len(tokens),
            'word_count': word_count,
            'confidence': confidence,
            'preview': text[:100] + ('...' if len(text) > 100 else ''),
            'should_send': confidence >= 0.6 or self.should_force_send(tokens)
        }


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

# Initialize sentence merger with micro-particle buffering
sentence_merger = SmartSentenceMerger(
    max_buffer_words=config.get('sentence_merging', 'max_buffer_words', default=150),
    min_sentence_words=config.get('sentence_merging', 'min_sentence_words', default=8)
)

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = config.get('server', 'secret_key')
CORS(app)

# Initialize SocketIO
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# In-memory storage (replace with database in production)
translations_history = []
connected_clients = set()
admin_sessions = {}
pending_token_buffers = {}  # Store micro-tokens per admin session


# Authentication decorator
def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not config.get('authentication', 'enabled', default=True):
            return f(*args, **kwargs)

        token = request.headers.get('Authorization', '').replace('Bearer ', '')
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
    return jsonify({'message': 'Use admin_gui.py for admin interface'})


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
        'translation': config.get('translation'),
        'sentence_merging': {
            'enabled': config.get('sentence_merging', 'enabled', default=True)
        }
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
    global translations_history, pending_token_buffers
    translations_history = []
    pending_token_buffers = {}
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
        'translations': len(translations_history),
        'pending_buffers': len(pending_token_buffers)
    })


@app.route('/api/merge-test', methods=['POST'])
def merge_test():
    """Test sentence merging functionality"""
    data = request.json
    sentences = data.get('sentences', [])

    if not sentences:
        return jsonify({'error': 'No sentences provided'}), 400

    merged = sentence_merger.merge_by_completion(sentences)

    return jsonify({
        'original': sentences,
        'merged': merged,
        'count_before': len(sentences),
        'count_after': len(merged)
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

    # Clear token buffer for this session
    if client_id in pending_token_buffers:
        del pending_token_buffers[client_id]

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
    """Handle new transcription - MICRO-PARTICLE BUFFERING & INTELLIGENT ASSEMBLY"""
    if not is_admin(request.sid):
        emit('error', {'message': 'Unauthorized'})
        return

    raw_text = data.get('text', '').strip()
    if not raw_text:
        return

    session_id = request.sid
    use_merger = config.get('sentence_merging', 'enabled', default=True)

    if use_merger:
        # Initialize token buffer for this session
        if session_id not in pending_token_buffers:
            pending_token_buffers[session_id] = []

        # Tokenize new input into micro-particles
        new_tokens = sentence_merger.tokenize(raw_text)

        # Add to buffer
        pending_token_buffers[session_id].extend(new_tokens)

        # Get buffer info
        buffer_info = sentence_merger.get_buffer_info(pending_token_buffers[session_id])

        # Try to assemble complete sentences
        complete_sentences, remaining_tokens = sentence_merger.assemble_sentences(
            pending_token_buffers[session_id]
        )

        # Update buffer with remaining tokens
        pending_token_buffers[session_id] = remaining_tokens

        if not complete_sentences:
            # Nothing complete yet, inform client
            buffer_preview = buffer_info['preview']
            logger.info(f"[WAIT] {buffer_info['word_count']} words, "
                       f"conf={buffer_info['confidence']:.2f}, "
                       f"tokens={len(pending_token_buffers[session_id])}: '{buffer_preview[:60]}...'")
            emit('fragment_pending', {
                'fragment': raw_text,
                'buffer_info': buffer_info
            })
            return

        # Send each complete sentence
        for sentence_text in complete_sentences:
            # Recalculate confidence for logging
            tokens = sentence_merger.tokenize(sentence_text)
            final_confidence = sentence_merger.calculate_sentence_confidence(tokens)

            translation_data = {
                'id': len(translations_history),
                'timestamp': datetime.now().strftime('%H:%M:%S'),
                'original': sentence_text,
                'corrected': sentence_text,
                'translated': None,
                'is_corrected': False,
                'source_language': data.get('language', 'en'),
                'is_merged': True
            }

            translations_history.append(translation_data)
            socketio.emit('new_translation', translation_data)

            logger.info(f"[SENT] conf={final_confidence:.2f}, "
                       f"{len(sentence_text)} chars, "
                       f"{len(tokens)} tokens: '{sentence_text[:70]}...'")

        # Log remaining buffer status
        if remaining_tokens:
            remaining_info = sentence_merger.get_buffer_info(remaining_tokens)
            logger.info(f"[REMAIN] {remaining_info['word_count']} words, "
                       f"conf={remaining_info['confidence']:.2f}, "
                       f"{len(remaining_tokens)} tokens")

    else:
        # No merging - send as-is
        translation_data = {
            'id': len(translations_history),
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'original': raw_text,
            'corrected': raw_text,
            'translated': None,
            'is_corrected': False,
            'source_language': data.get('language', 'en'),
            'is_merged': False
        }

        translations_history.append(translation_data)
        socketio.emit('new_translation', translation_data)
        logger.info(f"[DIRECT] {raw_text[:50]}...")


@socketio.on('flush_pending')
def handle_flush_pending():
    """Flush pending tokens (force send incomplete sentences)"""
    if not is_admin(request.sid):
        emit('error', {'message': 'Unauthorized'})
        return

    session_id = request.sid

    if session_id not in pending_token_buffers or not pending_token_buffers[session_id]:
        emit('flush_result', {
            'success': False,
            'message': 'No pending tokens to flush'
        })
        return

    # Reconstruct text from tokens
    flushed_text = sentence_merger.reconstruct_text(pending_token_buffers[session_id])

    # Create translation entry
    translation_data = {
        'id': len(translations_history),
        'timestamp': datetime.now().strftime('%H:%M:%S'),
        'original': flushed_text,
        'corrected': flushed_text,
        'translated': None,
        'is_corrected': False,
        'source_language': 'en',
        'is_merged': True,
        'is_flushed': True
    }

    translations_history.append(translation_data)
    socketio.emit('new_translation', translation_data)

    # Clear buffer
    token_count = len(pending_token_buffers[session_id])
    pending_token_buffers[session_id] = []

    logger.info(f"[FLUSH] Forced send: {token_count} tokens → '{flushed_text[:80]}...'")
    emit('flush_result', {
        'success': True,
        'text': flushed_text,
        'token_count': token_count,
        'message': 'Pending tokens flushed successfully'
    })


@socketio.on('get_pending_buffer')
def handle_get_pending_buffer():
    """Get current pending buffer contents"""
    if not is_admin(request.sid):
        emit('error', {'message': 'Unauthorized'})
        return

    session_id = request.sid
    tokens = pending_token_buffers.get(session_id, [])

    if tokens:
        buffer_info = sentence_merger.get_buffer_info(tokens)
        emit('pending_buffer', {
            'tokens': tokens[:50],  # First 50 tokens
            'total_tokens': len(tokens),
            'buffer_info': buffer_info
        })
    else:
        emit('pending_buffer', {
            'tokens': [],
            'total_tokens': 0,
            'buffer_info': {'preview': '', 'word_count': 0, 'confidence': 0.0}
        })


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
        translations_history[translation_id]['translated'] = None  # Reset translation

        # Broadcast correction to all clients
        socketio.emit('translation_corrected', translations_history[translation_id])
        logger.info(f"Translation corrected: ID {translation_id}")
        emit('correction_success', {'id': translation_id})
    else:
        emit('error', {'message': 'Invalid translation ID'})


@socketio.on('update_order')
def handle_update_order(data):
    """Handle order update from admin GUI (drag & drop, sort, etc.)"""
    if not is_admin(request.sid):
        emit('error', {'message': 'Unauthorized'})
        return

    global translations_history
    new_order = data.get('translations', [])

    if new_order:
        # Update the global history with new order
        translations_history = new_order

        # Broadcast the complete new order to all frontend clients (exclude admin)
        socketio.emit('order_updated', {
            'translations': translations_history
        }, include_self=False)

        logger.info(f"[ORDER] Manually updated: {len(translations_history)} items")
        emit('order_update_success', {'count': len(translations_history)})
    else:
        emit('error', {'message': 'Invalid order data'})


@socketio.on('clear_history')
def handle_clear_history():
    """Handle clear history request from admin"""
    if not is_admin(request.sid):
        emit('error', {'message': 'Unauthorized'})
        return

    global translations_history, pending_token_buffers
    translations_history = []
    pending_token_buffers = {}

    # Broadcast to all clients
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
            if item.get('is_merged'):
                output += "(Sentence-merged)\n"
            if item.get('is_flushed'):
                output += "(Flushed from buffer)\n"
            if item['is_corrected']:
                output += "(Manually corrected)\n"
            output += "-" * 60 + "\n\n"

        return output, 200, {'Content-Type': 'text/plain; charset=utf-8'}

    elif format == 'srt':
        # SRT subtitle format
        output = ""
        for i, item in enumerate(translations_history, 1):
            # Create time codes (estimate 5 seconds per subtitle)
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
    logger.info("Starting EzySpeechTranslate Server with Sentence Merging...")
    logger.info(f"Authentication: {'Enabled' if config.get('authentication', 'enabled') else 'Disabled'}")
    logger.info(f"Sentence Merging: {'Enabled' if config.get('sentence_merging', 'enabled', default=True) else 'Disabled'}")
    logger.info(f"Server: {config.get('server', 'host')}:{config.get('server', 'port')}")

    # Create necessary directories
    for directory in ['logs', 'exports', 'data']:
        if not os.path.exists(directory):
            os.makedirs(directory)

    socketio.run(
        app,
        host=config.get('server', 'host', default='0.0.0.0'),
        port=config.get('server', 'port', default=5000),
        debug=config.get('server', 'debug', default=False)
    )