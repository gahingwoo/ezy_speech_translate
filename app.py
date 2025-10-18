from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import whisper
import pyaudio
import threading
import queue
import numpy as np
from googletrans import Translator, LANGUAGES
import time
from datetime import datetime
import traceback

app = Flask(__name__)
app.config['SECRET_KEY'] = 'ezyspeech_secret_key'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Global variables
whisper_model = None
translator = Translator()
audio_queue = queue.Queue()
is_recording = False
translation_history = []
correction_lock = threading.Lock()
system_ready = False

# Supported languages (all Google Translate languages)
SUPPORTED_LANGUAGES = LANGUAGES


def init_whisper():
    """Initialize Whisper model"""
    global whisper_model, system_ready
    try:
        print("=" * 60)
        print("Loading Whisper model...")
        print("First run requires downloading model (~150MB)")
        print("=" * 60)
        whisper_model = whisper.load_model("base")
        print("✓ Whisper model loaded")
        system_ready = True
    except Exception as e:
        print(f"✗ Failed to load Whisper model: {e}")
        traceback.print_exc()
        system_ready = False


class AudioRecorder:
    """Audio recording class"""

    def __init__(self, device_index=None):
        self.device_index = device_index
        self.audio = None
        self.stream = None
        self.recording = False
        self.init_audio()

    def init_audio(self):
        try:
            self.audio = pyaudio.PyAudio()
        except Exception as e:
            print(f"PyAudio initialization failed: {e}")
            self.audio = None

    def start(self):
        if not self.audio:
            raise Exception("PyAudio not initialized")

        self.recording = True
        try:
            self.stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                input_device_index=self.device_index,
                frames_per_buffer=8000,
                stream_callback=self.callback
            )
            self.stream.start_stream()
            print(f"✓ Recording started (device index: {self.device_index})")
        except Exception as e:
            self.recording = False
            raise Exception(f"Failed to start audio stream: {e}")

    def callback(self, in_data, frame_count, time_info, status):
        if self.recording:
            audio_queue.put(in_data)
        return (in_data, pyaudio.paContinue)

    def stop(self):
        self.recording = False
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
                print("✓ Recording stopped")
            except:
                pass

    def get_devices(self):
        if not self.audio:
            return []

        devices = []
        try:
            for i in range(self.audio.get_device_count()):
                try:
                    info = self.audio.get_device_info_by_index(i)
                    if info['maxInputChannels'] > 0:
                        devices.append({
                            'index': i,
                            'name': info['name'],
                            'channels': info['maxInputChannels']
                        })
                except:
                    continue
        except Exception as e:
            print(f"Failed to get device list: {e}")

        return devices

    def __del__(self):
        if self.audio:
            try:
                self.audio.terminate()
            except:
                pass


audio_recorder = AudioRecorder()


def asr_worker():
    """ASR processing thread"""
    global is_recording
    audio_buffer = []
    silence_threshold = 500
    silence_duration = 0

    print("ASR worker thread started")

    while True:
        try:
            if not system_ready:
                time.sleep(1)
                continue

            if not audio_queue.empty():
                chunk = audio_queue.get()
                audio_data = np.frombuffer(chunk, dtype=np.int16)

                # Detect volume
                volume = np.abs(audio_data).mean()

                if volume > silence_threshold:
                    audio_buffer.append(chunk)
                    silence_duration = 0
                else:
                    silence_duration += 1

                # Process when silence detected
                if silence_duration > 20 and len(audio_buffer) > 10:
                    try:
                        audio_bytes = b''.join(audio_buffer)
                        audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0

                        # Whisper transcription
                        result = whisper_model.transcribe(audio_np, language='en', fp16=False)
                        source_text = result['text'].strip()

                        if source_text:
                            print(f"Recognized: {source_text}")

                            # Create entry (translation will be done on client side)
                            entry = {
                                'id': len(translation_history),
                                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                'source': source_text,
                                'source_lang': 'en',
                                'corrected': source_text,
                                'is_corrected': False
                            }

                            with correction_lock:
                                translation_history.append(entry)

                            # Broadcast to all clients
                            socketio.emit('new_translation', entry)
                    except Exception as e:
                        print(f"Transcription error: {e}")

                    audio_buffer = []
                    silence_duration = 0
            else:
                time.sleep(0.01)

        except Exception as e:
            print(f"ASR thread error: {e}")
            traceback.print_exc()
            time.sleep(0.1)


# API routes
@app.route('/')
def index():
    """Client page"""
    return render_template('index.html')


@app.route('/api/status')
def get_status():
    """Get system status"""
    return jsonify({
        'system_ready': system_ready,
        'is_recording': is_recording,
        'whisper_loaded': whisper_model is not None,
        'history_count': len(translation_history)
    })


@app.route('/api/languages')
def get_languages():
    """Get supported languages list"""
    return jsonify(SUPPORTED_LANGUAGES)


@app.route('/api/devices')
def get_devices():
    """Get audio device list"""
    try:
        devices = audio_recorder.get_devices()
        return jsonify(devices)
    except Exception as e:
        print(f"Get devices error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/start', methods=['POST'])
def start_recording():
    """Start recording"""
    global is_recording

    if not system_ready:
        return jsonify({'error': 'Whisper model not loaded, please wait'}), 503

    data = request.json or {}
    device_index = data.get('device_index', None)

    if is_recording:
        return jsonify({'error': 'Already recording'}), 400

    try:
        audio_recorder.device_index = device_index
        audio_recorder.start()
        is_recording = True
        return jsonify({'status': 'started', 'device_index': device_index})
    except Exception as e:
        print(f"Failed to start recording: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/stop', methods=['POST'])
def stop_recording():
    """Stop recording"""
    global is_recording
    try:
        audio_recorder.stop()
        is_recording = False
        return jsonify({'status': 'stopped'})
    except Exception as e:
        print(f"Failed to stop recording: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/history')
def get_history():
    """Get translation history"""
    with correction_lock:
        return jsonify(translation_history)


@app.route('/api/correct', methods=['POST'])
def correct_translation():
    """Correct translation"""
    data = request.json or {}
    entry_id = data.get('id')
    corrected_text = data.get('corrected')

    if entry_id is None or corrected_text is None:
        return jsonify({'error': 'Missing required parameters'}), 400

    with correction_lock:
        if 0 <= entry_id < len(translation_history):
            translation_history[entry_id]['corrected'] = corrected_text
            translation_history[entry_id]['is_corrected'] = True

            # Broadcast update
            socketio.emit('translation_corrected', translation_history[entry_id])
            return jsonify({'status': 'success'})

    return jsonify({'error': 'Invalid ID'}), 400


@app.route('/api/clear', methods=['POST'])
def clear_history():
    """Clear history"""
    global translation_history
    with correction_lock:
        translation_history = []
    socketio.emit('history_cleared', {})
    return jsonify({'status': 'cleared'})


# SocketIO events
@socketio.on('connect')
def handle_connect():
    print('Client connected')
    with correction_lock:
        emit('history', translation_history)


@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')


# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("  EzySpeechTranslate Server Starting...")
    print("=" * 60 + "\n")

    # Initialize Whisper in separate thread
    print("Step 1/3: Initializing Whisper model...")
    init_thread = threading.Thread(target=init_whisper)
    init_thread.start()
    init_thread.join()

    if not system_ready:
        print("\n" + "=" * 60)
        print("WARNING: Whisper model failed to load")
        print("System will start but cannot perform speech recognition")
        print("Please check dependencies: pip install openai-whisper")
        print("=" * 60 + "\n")

    # Start ASR worker thread
    print("Step 2/3: Starting ASR processing thread...")
    asr_thread = threading.Thread(target=asr_worker, daemon=True)
    asr_thread.start()

    # Start Flask server
    print("Step 3/3: Starting Flask server...\n")
    print("=" * 60)
    print("Server Ready!")
    print("=" * 60)
    print("Admin Interface: python admin_gui.py")
    print("Client Web Page: http://localhost:5000")
    print("=" * 60 + "\n")

    socketio.run(app, host='0.0.0.0', port=5000, debug=False, allow_unsafe_werkzeug=True)