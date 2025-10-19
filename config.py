"""
EzySpeechTranslate Configuration File
配置文件 - 所有设置都在这里修改
"""

import os

# ==================== Server Configuration / 服务器配置 ====================
HOST = '0.0.0.0'  # Server address / 服务器地址
PORT = 1915       # Server port / 服务器端口
DEBUG = False     # Debug mode / 调试模式
SECRET_KEY = 'ezyspeech_secret_key_change_this'  # Flask secret key

# ==================== Whisper Configuration / Whisper 配置 ====================
WHISPER_MODEL = 'tiny'  # Model: tiny, base, small, medium, large
"""
Model Selection Guide / 模型选择指南:
- tiny (39M): Fastest, good for VM / 最快，适合虚拟机
- base (74M): Balanced / 平衡
- small (244M): High quality / 高质量
- medium (769M): Very high quality / 很高质量
- large (1550M): Best quality / 最佳质量

For VM: Use 'tiny' / 虚拟机推荐使用 'tiny'
For Native: Use 'base' or 'small' / 原生系统使用 'base' 或 'small'
"""

WHISPER_LANGUAGE = 'en'  # Source language / 源语言
WHISPER_FP16 = False     # Use FP16 (requires GPU) / 使用 FP16（需要 GPU）
WHISPER_DEVICE = 'cpu'   # 'cpu' or 'cuda' / 设备选择

# Whisper optimization / Whisper 优化
WHISPER_BEST_OF = 1      # Beam search candidates (1=fastest) / 候选数量
WHISPER_BEAM_SIZE = 1    # Beam size (1=fastest) / Beam 大小
WHISPER_TEMPERATURE = 0.0 # Temperature for sampling / 采样温度

# ==================== Audio Configuration / 音频配置 ====================
AUDIO_FORMAT = 'int16'
AUDIO_CHANNELS = 1           # Mono / 单声道
AUDIO_RATE = 16000          # Sample rate (Hz) / 采样率
AUDIO_CHUNK = 4000          # Chunk size (smaller = faster response) / 块大小

# Voice Activity Detection / 语音活动检测
SILENCE_THRESHOLD = 300      # Volume threshold / 音量阈值 (lower = more sensitive)
SILENCE_DURATION = 10        # Silence chunks before processing / 静音块数
MIN_AUDIO_LENGTH = 5         # Minimum audio chunks / 最小音频块数

# ==================== Translation Configuration / 翻译配置 ====================
TRANSLATOR_SERVICE = 'google'  # 'google' or 'deepl'

# Google Translate
GOOGLE_TRANSLATE_ENABLED = True

# DeepL (if using)
DEEPL_API_KEY = ''           # Your DeepL API key / DeepL API 密钥
DEEPL_TARGET_LANG = 'ZH'     # Target language / 目标语言

# Translation retry / 翻译重试
TRANSLATION_RETRY_TIMES = 3
TRANSLATION_RETRY_DELAY = 1  # seconds / 秒

# ==================== Storage Configuration / 存储配置 ====================
# Data directories / 数据目录
DATA_DIR = 'data'
LOGS_DIR = 'logs'
EXPORTS_DIR = 'exports'
RECORDINGS_DIR = 'recordings'

# Auto-create directories / 自动创建目录
AUTO_CREATE_DIRS = True

# Save ASR records / 保存 ASR 记录
SAVE_ASR_RECORDS = True                    # Enable saving / 启用保存
ASR_RECORDS_FILE = 'asr_records.jsonl'     # File name / 文件名
ASR_RECORDS_PATH = os.path.join(DATA_DIR, ASR_RECORDS_FILE)

# Save translation history / 保存翻译历史
SAVE_TRANSLATION_HISTORY = False
TRANSLATION_HISTORY_FILE = 'translation_history.jsonl'
TRANSLATION_HISTORY_PATH = os.path.join(DATA_DIR, TRANSLATION_HISTORY_FILE)

# Maximum records to keep in memory / 内存中保留的最大记录数
MAX_HISTORY_LENGTH = 1000
AUTO_SAVE_INTERVAL = 30  # seconds (0 = disabled) / 秒（0 = 禁用）

# ==================== WebSocket Configuration / WebSocket 配置 ====================
SOCKETIO_ASYNC_MODE = None   # Let it auto-detect / 自动检测
SOCKETIO_PING_TIMEOUT = 60
SOCKETIO_PING_INTERVAL = 25
SOCKETIO_CORS_ORIGINS = '*'  # CORS origins / 跨域设置

# ==================== Logging Configuration / 日志配置 ====================
LOG_LEVEL = 'DEBUG'  # DEBUG, INFO, WARNING, ERROR
LOG_FILE = os.path.join(LOGS_DIR, 'ezyspeech.log')
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_TO_FILE = True          # Enable file logging / 启用文件日志
LOG_TO_CONSOLE = True       # Enable console logging / 启用控制台日志

# ==================== Performance Configuration / 性能配置 ====================
USE_GPU = False  # Enable GPU acceleration / 启用 GPU 加速
NUM_THREADS = 4  # Number of threads / 线程数

# Cache settings / 缓存设置
ENABLE_CACHE = True
CACHE_SIZE = 1000  # Number of items / 条目数

# ==================== Security Configuration / 安全配置 ====================
# IMPORTANT: Change these in production! / 重要：生产环境请修改！
SECRET_KEY = 'change-this-to-random-secret-key-in-production'
CORS_ORIGINS = '*'  # Set specific domains in production / 生产环境设置具体域名

# Rate limiting / 速率限制
ENABLE_RATE_LIMIT = False
RATE_LIMIT_PER_MINUTE = 60

# ==================== UI Configuration / 界面配置 ====================
# Admin interface / 管理界面
ADMIN_WINDOW_WIDTH = 1400
ADMIN_WINDOW_HEIGHT = 800
ADMIN_DEFAULT_LANG = 'en'  # 'en' or 'cn'

# Client interface / 客户端界面
MAX_SUBTITLE_DISPLAY = 50  # Maximum subtitles to display / 最多显示字幕数
DEFAULT_TARGET_LANG = 'zh-cn'  # Default target language / 默认目标语言

# ==================== Export Configuration / 导出配置 ====================
EXPORT_FORMAT = 'txt'  # txt, srt, json, csv
EXPORT_ENCODING = 'utf-8'
EXPORT_WITH_TIMESTAMP = True
EXPORT_WITH_CORRECTIONS = True

# ==================== Feature Flags / 功能开关 ====================
ENABLE_TTS = True               # Enable TTS support / 启用 TTS
ENABLE_CORRECTION = True        # Enable admin correction / 启用管理员校对
ENABLE_HISTORY = True           # Enable history / 启用历史记录
ENABLE_EXPORT = True            # Enable export / 启用导出
ENABLE_MULTILANG = True         # Enable multi-language / 启用多语言

# ==================== Development Configuration / 开发配置 ====================
# Fast mode for testing / 测试快速模式
FAST_MODE = False  # Skip some validations / 跳过某些验证
MOCK_ASR = False   # Use mock ASR for testing / 使用模拟 ASR

# ==================== Helper Functions / 辅助函数 ====================
def ensure_directories():
    """Create required directories / 创建必需的目录"""
    if AUTO_CREATE_DIRS:
        dirs = [DATA_DIR, LOGS_DIR, EXPORTS_DIR, RECORDINGS_DIR]
        for d in dirs:
            os.makedirs(d, exist_ok=True)

def get_whisper_params():
    """Get Whisper transcription parameters / 获取 Whisper 转录参数"""
    return {
        'language': WHISPER_LANGUAGE,
        'fp16': WHISPER_FP16,
        'best_of': WHISPER_BEST_OF,
        'beam_size': WHISPER_BEAM_SIZE,
        'temperature': WHISPER_TEMPERATURE
    }

def get_audio_params():
    """Get audio recording parameters / 获取音频录制参数"""
    return {
        'format': AUDIO_FORMAT,
        'channels': AUDIO_CHANNELS,
        'rate': AUDIO_RATE,
        'chunk': AUDIO_CHUNK
    }

# ==================== Validation / 验证 ====================
def validate_config():
    """Validate configuration / 验证配置"""
    errors = []

    # Check Whisper model
    valid_models = ['tiny', 'base', 'small', 'medium', 'large']
    if WHISPER_MODEL not in valid_models:
        errors.append(f"Invalid WHISPER_MODEL: {WHISPER_MODEL}")

    # Check port
    if not (1024 <= PORT <= 65535):
        errors.append(f"Invalid PORT: {PORT} (must be 1024-65535)")

    # Check audio rate
    if AUDIO_RATE not in [8000, 16000, 22050, 44100, 48000]:
        errors.append(f"Unusual AUDIO_RATE: {AUDIO_RATE}")

    if errors:
        print("⚠️  Configuration Warnings:")
        for error in errors:
            print(f"  - {error}")
        return False

    return True

# Run validation on import
if __name__ != '__main__':
    validate_config()
    if AUTO_CREATE_DIRS:
        ensure_directories()

# ==================== Print Configuration / 打印配置 ====================
def print_config():
    """Print current configuration / 打印当前配置"""
    print("\n" + "="*60)
    print("  EzySpeechTranslate Configuration")
    print("="*60)
    print(f"Server: {HOST}:{PORT}")
    print(f"Whisper Model: {WHISPER_MODEL}")
    print(f"Audio: {AUDIO_RATE}Hz, {AUDIO_CHANNELS}ch, chunk={AUDIO_CHUNK}")
    print(f"Silence Detection: threshold={SILENCE_THRESHOLD}, duration={SILENCE_DURATION}")
    print(f"Save ASR Records: {SAVE_ASR_RECORDS}")
    print(f"Save History: {SAVE_TRANSLATION_HISTORY}")
    print(f"Data Directory: {DATA_DIR}")
    print("="*60 + "\n")

if __name__ == '__main__':
    # Test configuration
    ensure_directories()
    validate_config()
    print_config()
    print("✓ Configuration is valid")