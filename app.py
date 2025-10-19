#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EzySpeechTranslate - Config-Integrated Fast Backend
真正使用 config.py 的优化版本
Saves ASR records to file / 保存 ASR 记录到文件
"""

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import whisper
import pyaudio
import threading
import queue
import numpy as np
from datetime import datetime
import traceback
import json
import os

# Import configuration / 导入配置
try:
    import config

    print("✓ Configuration loaded from config.py")
    config.ensure_directories()  # Create required directories
except ImportError:
    print("⚠️  config.py not found, using default settings")


    # Fallback configuration
    class config:
        HOST = '0.0.0.0'
        PORT = 5000
        SECRET_KEY = 'fallback_key'
        WHISPER_MODEL = 'tiny'
        AUDIO_RATE = 16000
        AUDIO_CHANNELS = 1
        AUDIO_CHUNK = 4000
        SILENCE_THRESHOLD = 300
        SILENCE_DURATION = 10
        MIN_AUDIO_LENGTH = 5
        SAVE_ASR_RECORDS = True
        ASR_RECORDS_PATH = 'data/asr_records.jsonl'
        SAVE_TRANSLATION_HISTORY = True
        TRANSLATION_HISTORY_PATH = 'data/translation_history.jsonl'
        DATA_DIR = 'data'

        @staticmethod
        def ensure_directories():
            os.makedirs('data', exist_ok=True)

        @staticmethod
        def get_whisper_params():
            return {
                'language': 'en',
                'fp16': False,
                'best_of': 1,
                'beam_size': 1,
                'temperature': 0.0
            }

        @staticmethod
        def get_audio_params():
            return {
                'rate': 16000,
                'channels': 1,
                'chunk': 4000
            }

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = config.SECRET_KEY
CORS(app)
socketio = SocketIO(app, cors_allowed_origins=getattr(config, 'SOCKETIO_CORS_ORIGINS', '*'))

# Global variables
whisper_model = None
audio_queue = queue.Queue()
is_recording = False
translation_history = []
asr_records = []  # Store ASR records
correction_lock = threading.Lock()
system_ready = False

# Statistics
stats = {
    'total_recognitions': 0,
    'total_words': 0,
    'avg_confidence': 0.0,
    'start_time': None
}


def save_asr_record(record):
    """Save ASR record to file / 保存 ASR 记录到文件"""
    if not config.SAVE_ASR_RECORDS:
        return
    else:
        try:
            with open(config.ASR_RECORDS_PATH, 'a', encoding='utf-8') as f:
                json.dump(record, f, ensure_ascii=False)
                f.write('\n')
        except Exception as e:
            print(f"Failed to save ASR record: {e}")


def save_translation_history():
    """Save translation history to file / 保存翻译历史"""
    if not config.SAVE_TRANSLATION_HISTORY:
        return
    else:
        try:
            with open(config.TRANSLATION_HISTORY_PATH, 'w', encoding='utf-8') as f:
                for entry in translation_history:
                    json.dump(entry, f, ensure_ascii=False)
                    f.write('\n')
        except Exception as e:
            print(f"Failed to save translation history: {e}")


def load_asr_records():
    """Load ASR records from file / 从文件加载 ASR 记录"""
    if not os.path.exists(config.ASR_RECORDS_PATH):
        return []

    records = []
    try:
        with open(config.ASR_RECORDS_PATH, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))
    except Exception as e:
        print(f"Failed to load ASR records: {e}")

    return records


def init_whisper():
    """Initialize Whisper model using config / 使用配置初始化 Whisper"""
    global whisper_model, system_ready
    try:
        print("=" * 60)
        print(f"Loading Whisper '{config.WHISPER_MODEL}' model...")
        print("=" * 60)
        whisper_model = whisper.load_model(config.WHISPER_MODEL)
        print(f"✓ Whisper model loaded: {config.WHISPER_MODEL}")
        system_ready = True
        stats['start_time'] = datetime.now()
    except Exception as e:
        print(f"✗ Failed to load Whisper model: {e}")
        traceback.print_exc()
        system_ready = False


class AudioRecorder:
    """Audio recorder using config parameters / 使用配置参数的音频录制器"""

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

        audio_params = config.get_audio_params()
        self.recording = True
        try:
            self.stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=audio_params['channels'],
                rate=audio_params['rate'],
                input=True,
                input_device_index=self.device_index,
                frames_per_buffer=audio_params['chunk'],
                stream_callback=self.callback
            )
            self.stream.start_stream()
            print(f"✓ Recording started (model: {config.WHISPER_MODEL}, device: {self.device_index})")
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
    """ASR processing thread using config / 使用配置的 ASR 处理线程"""
    global is_recording, stats
    audio_buffer = []
    silence_duration = 0

    print(f"ASR worker started (threshold={config.SILENCE_THRESHOLD}, duration={config.SILENCE_DURATION})")

    while True:
        try:
            if not system_ready:
                time.sleep(1)
                continue

            if not audio_queue.empty():
                chunk = audio_queue.get()
                audio_data = np.frombuffer(chunk, dtype=np.int16)

                volume = np.abs(audio_data).mean()

                if volume > config.SILENCE_THRESHOLD:
                    audio_buffer.append(chunk)
                    silence_duration = 0
                else:
                    silence_duration += 1

                # Process when silence detected (using config)
                if silence_duration > config.SILENCE_DURATION and len(audio_buffer) > config.MIN_AUDIO_LENGTH:
                    try:
                        audio_bytes = b''.join(audio_buffer)
                        audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0

                        # Get Whisper params from config
                        whisper_params = config.get_whisper_params()

                        # Transcribe
                        transcribe_start = time.time()
                        result = whisper_model.transcribe(audio_np, **whisper_params)
                        transcribe_time = time.time() - transcribe_start

                        source_text = result['text'].strip()

                        if source_text:
                            # Update statistics
                            stats['total_recognitions'] += 1
                            stats['total_words'] += len(source_text.split())

                            print(f"✓ Recognized ({transcribe_time:.2f}s): {source_text}")

                            # Create ASR record
                            asr_record = {
                                'id': len(asr_records),
                                'timestamp': datetime.now().isoformat(),
                                'text': source_text,
                                'language': 'en',
                                'model': config.WHISPER_MODEL,
                                'transcribe_time': round(transcribe_time, 3),
                                'audio_duration': len(audio_bytes) / (config.AUDIO_RATE * 2),  # bytes to seconds
                                'word_count': len(source_text.split()),
                                'volume': float(volume)
                            }

                            # Save ASR record
                            asr_records.append(asr_record)
                            save_asr_record(asr_record)

                            # Create translation entry
                            entry = {
                                'id': len(translation_history),
                                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                'source': source_text,
                                'source_lang': 'en',
                                'corrected': source_text,
                                'is_corrected': False,
                                'asr_record_id': asr_record['id']
                            }

                            with correction_lock:
                                translation_history.append(entry)
                                # Auto-save history periodically
                                if len(translation_history) % 10 == 0:
                                    save_translation_history()

                            # Broadcast to clients
                            socketio.emit('new_translation', entry)
                    except Exception as e:
                        print(f"Transcription error: {e}")
                        traceback.print_exc()

                    audio_buffer = []
                    silence_duration = 0
            else:
                time.sleep(0.005)

        except Exception as e:
            print(f"ASR thread error: {e}")
            traceback.print_exc()
            time.sleep(0.1)


# API routes
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/status')
def get_status():
    """Get system status with config info / 获取系统状态和配置信息"""
    uptime = None
    if stats['start_time']:
        uptime = (datetime.now() - stats['start_time']).total_seconds()

    return jsonify({
        'system_ready': system_ready,
        'is_recording': is_recording,
        'whisper_loaded': whisper_model is not None,
        'whisper_model': config.WHISPER_MODEL,
        'history_count': len(translation_history),
        'asr_records_count': len(asr_records),
        'config': {
            'model': config.WHISPER_MODEL,
            'audio_rate': config.AUDIO_RATE,
            'audio_chunk': config.AUDIO_CHUNK,
            'silence_threshold': config.SILENCE_THRESHOLD,
            'save_asr': config.SAVE_ASR_RECORDS,
            'save_history': config.SAVE_TRANSLATION_HISTORY
        },
        'stats': {
            'total_recognitions': stats['total_recognitions'],
            'total_words': stats['total_words'],
            'uptime_seconds': round(uptime) if uptime else None
        }
    })


@app.route('/api/config')
def get_config():
    """Get current configuration / 获取当前配置"""
    return jsonify({
        'whisper_model': config.WHISPER_MODEL,
        'audio_rate': config.AUDIO_RATE,
        'audio_channels': config.AUDIO_CHANNELS,
        'audio_chunk': config.AUDIO_CHUNK,
        'silence_threshold': config.SILENCE_THRESHOLD,
        'silence_duration': config.SILENCE_DURATION,
        'save_asr_records': config.SAVE_ASR_RECORDS,
        'save_translation_history': config.SAVE_TRANSLATION_HISTORY,
        'asr_records_path': config.ASR_RECORDS_PATH,
        'translation_history_path': config.TRANSLATION_HISTORY_PATH
    })


@app.route('/api/asr_records')
def get_asr_records():
    """Get all ASR records / 获取所有 ASR 记录"""
    return jsonify(asr_records)


@app.route('/api/stats')
def get_stats():
    """Get detailed statistics / 获取详细统计"""
    uptime = None
    if stats['start_time']:
        uptime = (datetime.now() - stats['start_time']).total_seconds()

    return jsonify({
        'total_recognitions': stats['total_recognitions'],
        'total_words': stats['total_words'],
        'avg_words_per_recognition': stats['total_words'] / max(stats['total_recognitions'], 1),
        'uptime_seconds': round(uptime) if uptime else None,
        'asr_records_saved': len(asr_records),
        'translations_saved': len(translation_history)
    })


@app.route('/api/devices')
def get_devices():
    try:
        devices = audio_recorder.get_devices()
        return jsonify(devices)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/start', methods=['POST'])
def start_recording():
    global is_recording

    if not system_ready:
        return jsonify({'error': 'Whisper model not loaded'}), 503

    data = request.json or {}
    device_index = data.get('device_index', None)

    if is_recording:
        return jsonify({'error': 'Already recording'}), 400

    try:
        audio_recorder.device_index = device_index
        audio_recorder.start()
        is_recording = True
        return jsonify({
            'status': 'started',
            'device_index': device_index,
            'config': {
                'model': config.WHISPER_MODEL,
                'audio_rate': config.AUDIO_RATE,
                'chunk_size': config.AUDIO_CHUNK
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/stop', methods=['POST'])
def stop_recording():
    global is_recording
    try:
        audio_recorder.stop()
        is_recording = False
        # Save history when stopping
        save_translation_history()
        return jsonify({
            'status': 'stopped',
            'asr_records_saved': len(asr_records),
            'translations_saved': len(translation_history)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/history')
def get_history():
    with correction_lock:
        return jsonify(translation_history)


@app.route('/api/correct', methods=['POST'])
def correct_translation():
    data = request.json or {}
    entry_id = data.get('id')
    corrected_text = data.get('corrected')

    if entry_id is None or corrected_text is None:
        return jsonify({'error': 'Missing required parameters'}), 400

    with correction_lock:
        if 0 <= entry_id < len(translation_history):
            translation_history[entry_id]['corrected'] = corrected_text
            translation_history[entry_id]['is_corrected'] = True
            translation_history[entry_id]['corrected_at'] = datetime.now().isoformat()

            # Save after correction
            save_translation_history()

            socketio.emit('translation_corrected', translation_history[entry_id])
            return jsonify({'status': 'success'})

    return jsonify({'error': 'Invalid ID'}), 400


@app.route('/api/clear', methods=['POST'])
def clear_history():
    global translation_history
    with correction_lock:
        translation_history = []
        # Clear saved history file
        if config.SAVE_TRANSLATION_HISTORY:
            try:
                with open(config.TRANSLATION_HISTORY_PATH, 'w') as f:
                    pass  # Clear file
            except:
                pass
    socketio.emit('history_cleared', {})
    return jsonify({'status': 'cleared'})


@app.route('/api/export/asr', methods=['GET'])
def export_asr_records():
    """Export ASR records / 导出 ASR 记录"""
    format_type = request.args.get('format', 'json')

    if format_type == 'json':
        return jsonify(asr_records)
    elif format_type == 'txt':
        content = "EzySpeechTranslate - ASR Records\n"
        content += f"Generated: {datetime.now().isoformat()}\n"
        content += f"Total Records: {len(asr_records)}\n"
        content += "=" * 60 + "\n\n"

        for record in asr_records:
            content += f"[{record['id']}] {record['timestamp']}\n"
            content += f"Text: {record['text']}\n"
            content += f"Model: {record['model']}, Time: {record['transcribe_time']}s\n"
            content += f"Words: {record['word_count']}\n"
            content += "-" * 60 + "\n\n"

        return content, 200, {'Content-Type': 'text/plain; charset=utf-8'}
    else:
        return jsonify({'error': 'Invalid format'}), 400


@app.route('/api/export/history', methods=['GET'])
def export_history():
    """Export translation history / 导出翻译历史"""
    format_type = request.args.get('format', 'json')

    if format_type == 'json':
        return jsonify(translation_history)
    elif format_type == 'txt':
        content = "EzySpeechTranslate - Translation History\n"
        content += f"Generated: {datetime.now().isoformat()}\n"
        content += f"Total Entries: {len(translation_history)}\n"
        content += "=" * 60 + "\n\n"

        for entry in translation_history:
            content += f"[{entry['id']}] {entry['timestamp']}\n"
            content += f"Source: {entry['source']}\n"
            content += f"Corrected: {entry['corrected']}\n"
            if entry['is_corrected']:
                content += "(Manually corrected)\n"
            content += "-" * 60 + "\n\n"

        return content, 200, {'Content-Type': 'text/plain; charset=utf-8'}
    else:
        return jsonify({'error': 'Invalid format'}), 400


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


# Cleanup on exit
import atexit
import signal
import time


def cleanup():
    """Save all data before exit / 退出前保存所有数据"""
    print("\nSaving data before exit...")
    save_translation_history()
    print(f"✓ Saved {len(asr_records)} ASR records")
    print(f"✓ Saved {len(translation_history)} translation entries")


atexit.register(cleanup)


def signal_handler(sig, frame):
    print("\nReceived shutdown signal...")
    cleanup()
    import sys
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("  EzySpeechTranslate Server")
    print("  Config-Integrated Version with ASR Recording")
    print("=" * 60 + "\n")

    # Print configuration
    if hasattr(config, 'print_config'):
        config.print_config()
    else:
        print(f"Model: {config.WHISPER_MODEL}")
        print(f"Audio: {config.AUDIO_RATE}Hz, chunk={config.AUDIO_CHUNK}")
        print(f"Save ASR: {config.SAVE_ASR_RECORDS}")
        print(f"ASR File: {config.ASR_RECORDS_PATH}")
        print()

    # Load existing records
    print("Loading existing data...")
    asr_records = load_asr_records()
    print(f"✓ Loaded {len(asr_records)} ASR records")

    # Initialize Whisper
    print("\nStep 1/3: Initializing Whisper model...")
    init_thread = threading.Thread(target=init_whisper)
    init_thread.start()
    init_thread.join()

    if not system_ready:
        print("\n" + "=" * 60)
        print("WARNING: Whisper model failed to load")
        print("System will start but cannot perform speech recognition")
        print("=" * 60 + "\n")

    # Start ASR worker
    print("Step 2/3: Starting ASR processing thread...")
    asr_thread = threading.Thread(target=asr_worker, daemon=True)
    asr_thread.start()

    # Start Flask server
    print("Step 3/3: Starting Flask server...\n")
    print("=" * 60)
    print("Server Ready!")
    print("=" * 60)
    print(f"Admin: python admin_gui_multilang.py")
    print(f"Client: http://{config.HOST if config.HOST != '0.0.0.0' else 'localhost'}:{config.PORT}")
    print(f"ASR Records: {config.ASR_RECORDS_PATH}")
    print(f"Translation History: {config.TRANSLATION_HISTORY_PATH}")
    print("=" * 60 + "\n")

    socketio.run(
        app,
        host=config.HOST,
        port=config.PORT,
        debug=config.DEBUG if hasattr(config, 'DEBUG') else False,
        allow_unsafe_werkzeug=True
    )