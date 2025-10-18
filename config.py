"""
EzySpeechTranslate 配置文件
"""

# ==================== 服务器配置 ====================
HOST = '0.0.0.0'  # 服务器地址，0.0.0.0 表示监听所有网络接口
PORT = 5000       # 服务器端口
DEBUG = False     # 调试模式（生产环境请设为 False）

# ==================== Whisper 配置 ====================
WHISPER_MODEL = 'base'  # 可选: tiny, base, small, medium, large
"""
模型选择建议:
- tiny (39M): 速度最快，适合测试
- base (74M): 平衡速度和精度，推荐
- small (244M): 更高精度
- medium (769M): 很高精度，需要较好硬件
- large (1550M): 最高精度，需要强大硬件
"""

WHISPER_LANGUAGE = 'en'  # 源语言（英文）

# ==================== 音频配置 ====================
AUDIO_FORMAT = 'int16'
AUDIO_CHANNELS = 1        # 单声道
AUDIO_RATE = 16000       # 采样率 16kHz
AUDIO_CHUNK = 8000       # 每次读取的音频块大小

# 语音检测参数
SILENCE_THRESHOLD = 500   # 静音阈值（音量）
SILENCE_DURATION = 20     # 静音持续时间（块数），约 1 秒
MIN_AUDIO_LENGTH = 10     # 最小音频长度（块数），约 0.5 秒

# ==================== 翻译配置 ====================
TRANSLATOR_SERVICE = 'google'  # 可选: google, deepl

# Google Translate 配置
GOOGLE_TRANSLATE_ENABLED = True

# DeepL 配置（如果使用）
DEEPL_API_KEY = ''  # 在此填入您的 DeepL API 密钥
DEEPL_TARGET_LANG = 'ZH'  # 目标语言（中文）

# 翻译重试配置
TRANSLATION_RETRY_TIMES = 3
TRANSLATION_RETRY_DELAY = 1  # 秒

# ==================== WebSocket 配置 ====================
SOCKETIO_ASYNC_MODE = 'eventlet'  # 可选: eventlet, threading
SOCKETIO_PING_TIMEOUT = 60
SOCKETIO_PING_INTERVAL = 25

# ==================== 数据存储配置 ====================
MAX_HISTORY_LENGTH = 1000  # 最大历史记录数量
AUTO_SAVE_INTERVAL = 300   # 自动保存间隔（秒），0 表示不自动保存

# ==================== 日志配置 ====================
LOG_LEVEL = 'INFO'  # 可选: DEBUG, INFO, WARNING, ERROR
LOG_FILE = 'ezyspeech.log'
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# ==================== 性能优化配置 ====================
USE_GPU = True  # 是否使用 GPU 加速（需要 CUDA）
NUM_THREADS = 4  # 处理线程数

# ==================== 安全配置 ====================
SECRET_KEY = 'change-this-to-random-secret-key'  # Flask 密钥，请修改
CORS_ORIGINS = '*'  # CORS 允许的源，生产环境请设置具体域名

# ==================== UI 配置 ====================
# 管理员界面
ADMIN_WINDOW_WIDTH = 1400
ADMIN_WINDOW_HEIGHT = 800

# 听众端
MAX_SUBTITLE_DISPLAY = 50  # 网页端最多显示的字幕条数

# ==================== 导出配置 ====================
EXPORT_FORMAT = 'txt'  # 可选: txt, srt, json
EXPORT_ENCODING = 'utf-8'