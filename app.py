from flask import Flask, render_template, request, jsonify, Response
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import whisper
import pyaudio
import socket
import threading
import queue
import numpy as np
from googletrans import Translator
import time
import json
from datetime import datetime
import traceback

app = Flask(__name__)
app.config['SECRET_KEY'] = 'ezyspeech_secret_key'
CORS(app)

# socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
socketio = SocketIO(app, cors_allowed_origins="*")

# 全局变量
whisper_model = None
translator = Translator()
audio_queue = queue.Queue()
is_recording = False
translation_history = []
correction_lock = threading.Lock()
system_ready = False


# 初始化 Whisper 模型
def init_whisper():
    global whisper_model, system_ready
    try:
        print("=" * 60)
        print("正在加载 Whisper 模型...")
        print("首次运行需要下载模型文件（约 150MB），请耐心等待...")
        print("=" * 60)
        whisper_model = whisper.load_model("base")
        print("✓ Whisper 模型加载完成")
        system_ready = True
    except Exception as e:
        print(f"✗ Whisper 模型加载失败: {e}")
        print("请确保已正确安装 openai-whisper 和 ffmpeg")
        traceback.print_exc()
        system_ready = False


# 音频录制类
class AudioRecorder:
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
            print(f"PyAudio 初始化失败: {e}")
            self.audio = None

    def start(self):
        if not self.audio:
            raise Exception("PyAudio 未初始化")

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
            print(f"✓ 音频录制已开始 (设备索引: {self.device_index})")
        except Exception as e:
            self.recording = False
            raise Exception(f"无法启动音频流: {e}")

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
                print("✓ 音频录制已停止")
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
            print(f"获取设备列表失败: {e}")

        return devices

    def __del__(self):
        if self.audio:
            try:
                self.audio.terminate()
            except:
                pass


audio_recorder = AudioRecorder()


# ASR 处理线程
def asr_worker():
    global is_recording
    audio_buffer = []
    silence_threshold = 500
    silence_duration = 0

    print("ASR 工作线程已启动")

    while True:
        try:
            if not system_ready:
                time.sleep(1)
                continue

            if not audio_queue.empty():
                chunk = audio_queue.get()
                audio_data = np.frombuffer(chunk, dtype=np.int16)

                # 检测音量
                volume = np.abs(audio_data).mean()

                if volume > silence_threshold:
                    audio_buffer.append(chunk)
                    silence_duration = 0
                else:
                    silence_duration += 1

                # 如果检测到静音且有音频数据，进行转录
                if silence_duration > 20 and len(audio_buffer) > 10:
                    try:
                        audio_bytes = b''.join(audio_buffer)
                        audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0

                        # Whisper 转录
                        result = whisper_model.transcribe(audio_np, language='en', fp16=False)
                        english_text = result['text'].strip()

                        if english_text:
                            print(f"识别: {english_text}")

                            # 翻译
                            try:
                                chinese_text = translator.translate(english_text, src='en', dest='zh-cn').text
                                print(f"翻译: {chinese_text}")
                            except Exception as e:
                                print(f"翻译失败: {e}")
                                chinese_text = "[翻译失败]"

                            # 保存到历史
                            entry = {
                                'id': len(translation_history),
                                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                'english': english_text,
                                'chinese': chinese_text,
                                'corrected': chinese_text,
                                'is_corrected': False
                            }

                            with correction_lock:
                                translation_history.append(entry)

                            # 广播到所有客户端
                            socketio.emit('new_translation', entry)
                    except Exception as e:
                        print(f"转录错误: {e}")

                    audio_buffer = []
                    silence_duration = 0
            else:
                time.sleep(0.01)

        except Exception as e:
            print(f"ASR 线程错误: {e}")
            traceback.print_exc()
            time.sleep(0.1)


# API 路由
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/status')
def get_status():
    """获取系统状态"""
    return jsonify({
        'system_ready': system_ready,
        'is_recording': is_recording,
        'whisper_loaded': whisper_model is not None,
        'history_count': len(translation_history)
    })


@app.route('/api/devices')
def get_devices():
    """获取音频设备列表"""
    try:
        devices = audio_recorder.get_devices()
        return jsonify(devices)
    except Exception as e:
        print(f"获取设备错误: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/start', methods=['POST'])
def start_recording():
    """开始录制"""
    global is_recording

    if not system_ready:
        return jsonify({'error': 'Whisper 模型未加载完成，请稍候'}), 503

    data = request.json or {}
    device_index = data.get('device_index', None)

    if is_recording:
        return jsonify({'error': '已在录制中'}), 400

    try:
        audio_recorder.device_index = device_index
        audio_recorder.start()
        is_recording = True
        return jsonify({'status': 'started', 'device_index': device_index})
    except Exception as e:
        print(f"启动录制失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/stop', methods=['POST'])
def stop_recording():
    """停止录制"""
    global is_recording
    try:
        audio_recorder.stop()
        is_recording = False
        return jsonify({'status': 'stopped'})
    except Exception as e:
        print(f"停止录制失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/history')
def get_history():
    """获取翻译历史"""
    with correction_lock:
        return jsonify(translation_history)


@app.route('/api/correct', methods=['POST'])
def correct_translation():
    """校对翻译"""
    data = request.json or {}
    entry_id = data.get('id')
    corrected_text = data.get('corrected')

    if entry_id is None or corrected_text is None:
        return jsonify({'error': '缺少必要参数'}), 400

    with correction_lock:
        if 0 <= entry_id < len(translation_history):
            translation_history[entry_id]['corrected'] = corrected_text
            translation_history[entry_id]['is_corrected'] = True

            # 广播更新
            socketio.emit('translation_corrected', translation_history[entry_id])
            return jsonify({'status': 'success'})

    return jsonify({'error': '无效的ID'}), 400


@app.route('/api/clear', methods=['POST'])
def clear_history():
    """清空历史"""
    global translation_history
    with correction_lock:
        translation_history = []
    socketio.emit('history_cleared', {})
    return jsonify({'status': 'cleared'})


# SocketIO 事件
@socketio.on('connect')
def handle_connect():
    print('客户端已连接')
    with correction_lock:
        emit('history', translation_history)


@socketio.on('disconnect')
def handle_disconnect():
    print('客户端已断开')


# 错误处理
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("  EzySpeechTranslate 服务器启动中...")
    print("=" * 60 + "\n")

    # 获取本机 IP 地址
    hostname = socket.gethostname()
    try:
        local_ip = socket.gethostbyname(hostname)
    except Exception:
        # 万一上面获取失败（例如没有网络），使用 127.0.0.1 兜底
        local_ip = "127.0.0.1"

    # 初始化 Whisper 模型
    print("步骤 1/3: 初始化 Whisper 模型...")
    init_thread = threading.Thread(target=init_whisper)
    init_thread.start()
    init_thread.join()

    if not system_ready:
        print("\n" + "=" * 60)
        print("警告: Whisper 模型加载失败")
        print("系统将启动但无法进行语音识别")
        print("请检查依赖安装: pip install openai-whisper")
        print("=" * 60 + "\n")

    # 启动 ASR 工作线程
    print("步骤 2/3: 启动 ASR 处理线程...")
    asr_thread = threading.Thread(target=asr_worker, daemon=True)
    asr_thread.start()

    # 启动 Flask 服务器
    print("步骤 3/3: 启动 Flask 服务器...\n")
    print("=" * 60)
    print("服务器已就绪！")
    print("=" * 60)
    print(f"管理员界面: python admin_gui.py")
    print(f"听众端网页 (本机): http://localhost:5000")
    print(f"听众端网页 (局域网): http://{local_ip}:5000")
    print("=" * 60 + "\n")

    socketio.run(app, host='0.0.0.0', port=5000, debug=False, allow_unsafe_werkzeug=True)