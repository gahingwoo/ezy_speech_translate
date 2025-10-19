# EzySpeechTranslate 快速开始指南

## 🚀 5 分钟快速启动

### 方法一：自动安装（推荐）

```bash
# 1. 运行安装向导
python install.py

# 2. 启动系统
# Windows: 双击 "启动系统.bat"
# Linux/macOS: ./启动系统.sh
```

### 方法二：手动安装

#### 步骤 1: 安装系统依赖

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install portaudio19-dev python3-dev ffmpeg
```

**macOS:**
```bash
brew install portaudio ffmpeg
```

**Windows:**
- 下载并安装 [FFmpeg](https://ffmpeg.org/download.html)
- 添加到系统 PATH

#### 步骤 2: 安装 Python 依赖

```bash
# 创建虚拟环境（推荐）
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

#### 步骤 3: 创建必要目录

```bash
mkdir templates
```

#### 步骤 4: 启动系统

```bash
# 终端 1: 启动后端
python app.py

# 终端 2: 启动管理界面
python admin_gui.py
```

## 📱 使用流程

### 管理员端操作

1. **选择音频输入**
   - 启动管理界面后，点击"刷新设备"
   - 从下拉菜单选择麦克风或虚拟声卡
   - 推荐：使用虚拟声卡捕获系统音频

2. **开始录制**
   - 点击"▶ 开始录制"按钮
   - 对着麦克风说英文
   - 左侧实时预览区会显示识别和翻译结果

3. **校对翻译**
   - 右侧表格显示所有翻译记录
   - 直接编辑"中文翻译"列的内容
   - 点击"保存"按钮提交校对
   - 校对后的翻译会变为绿色

4. **管理记录**
   - 点击"🗑 清空历史"清除所有记录
   - 所有客户端会同步更新

### 听众端操作

1. **打开网页**
   - 浏览器访问：`http://localhost:{config.PORT}`
   - 或局域网：`http://[服务器IP]:{config.PORT}`

2. **查看字幕**
   - 页面自动显示实时翻译
   - 校对后的字幕显示"已校对"标记
   - 字幕以动画形式滚动显示

3. **启用 TTS**
   - 点击"🔊 启用 TTS"开启语音播报
   - 调整语速（0.5x - 2.0x）
   - 调整音量（0% - 100%）
   - 点击单条字幕的 🔊 图标单独播放

4. **下载字幕**
   - 点击"💾 下载字幕"
   - 保存为 TXT 文本文件
   - 包含完整时间戳和双语内容

## 🎯 使用场景示例

### 场景 1: 线上会议翻译

```
1. 使用虚拟声卡捕获会议软件音频
2. 管理员启动录制
3. 分享听众端链接给参会者
4. 参会者在网页端查看实时翻译字幕
```

**推荐虚拟声卡:**
- Windows: VB-CABLE
- macOS: BlackHole
- Linux: PulseAudio Loopback

### 场景 2: 讲座实时翻译

```
1. 使用麦克风采集讲者语音
2. 管理员实时校对不准确的翻译
3. 听众通过网页查看字幕
4. 可开启 TTS 用耳机收听
```

### 场景 3: 视频直播字幕

```
1. 使用虚拟声卡捕获视频音频
2. 系统自动生成双语字幕
3. 管理员实时校对专业术语
4. 观众在网页端查看字幕
```

## ⚙️ 常用配置

### 调整 Whisper 模型

编辑 `app.py`：
```python
# 更快的模型（适合低配置）
whisper_model = whisper.load_model("tiny")

# 更准确的模型（需要好的 GPU）
whisper_model = whisper.load_model("large")
```

### 切换翻译服务

#### 使用 DeepL（更高质量）

1. 注册 [DeepL API](https://www.deepl.com/pro-api)
2. 安装依赖：
   ```bash
   pip install deepl
   ```
3. 修改 `app.py`：
   ```python
   import deepl
   translator = deepl.Translator("YOUR_API_KEY")
   
   # 在翻译函数中：
   result = translator.translate_text(english_text, target_lang="ZH")
   chinese_text = result.text
   ```

### 调整音频参数

编辑 `app.py`：
```python
# 静音检测阈值（越高越不敏感）
silence_threshold = 500  # 默认值

# 静音持续时间（块数，每块约 0.5 秒）
silence_duration = 20  # 默认约 1 秒

# 最小音频长度
MIN_AUDIO_LENGTH = 10  # 默认约 0.5 秒
```

## 🔧 故障排除

### 问题 1: "Invalid async_mode specified"

**原因:** SocketIO 配置问题或依赖冲突

**解决方案 1（自动修复）:**
```bash
python fix_common_issues.py
# 选择选项 1 或 7
```

**解决方案 2（手动修复）:**
```bash
# 卸载冲突的包
pip uninstall -y eventlet

# 安装正确的依赖
pip install simple-websocket
pip install --upgrade flask-socketio

# 重新启动
python app.py
```

### 问题 2: "无法加载设备"

**原因:** PyAudio 未正确安装或无权限

**解决:**
```bash
# 重新安装 PyAudio
pip uninstall pyaudio
pip install pyaudio

# macOS 需要先安装 portaudio
brew install portaudio
pip install pyaudio
```

### 问题 2: "Whisper 模型加载失败"

**原因:** FFmpeg 未安装

**解决:**
```bash
# Ubuntu/Debian
sudo apt-get install ffmpeg

# macOS
brew install ffmpeg

# Windows
# 下载 FFmpeg 并添加到 PATH
```

### 问题 3: "翻译服务失败"

**原因:** 网络问题或 API 限制

**解决:**
```bash
# 更新 googletrans
pip install --upgrade googletrans==4.0.0rc1

# 或切换到 DeepL API
```

### 问题 4: "端口被占用"

**解决:**
```bash
# 查找占用进程
# Windows:
netstat -ano | findstr :PORT

# Linux/macOS:
lsof -i :PORT

# 修改端口（编辑 config.py）
PORT=5001
```

### 问题 5: "管理界面无法连接服务器"

**检查清单:**
- [ ] 后端服务是否正在运行
- [ ] 防火墙是否阻止了端口 
- [ ] 服务器地址是否正确

**解决:**
```bash
# 1. 确认后端正在运行
curl http://localhost:PORT/api/status

# 2. 检查防火墙
# Windows: 允许 Python 通过防火墙
# Linux: sudo ufw allow PORT

# 3. 修改管理界面服务器地址（admin_gui.py）
self.server_url = 'http://localhost:PORT'
```

## 📊 性能优化

### CPU 优化

```python
# 使用更小的 Whisper 模型
whisper_model = whisper.load_model("tiny")  # 最快

# 减小音频块大小
frames_per_buffer=4000  # 默认 8000
```

### GPU 加速

```python
# 在支持 CUDA 的系统上
whisper_model = whisper.load_model("base", device="cuda")
```

### 网络优化

```python
# 调整 WebSocket 参数（app.py）
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    ping_timeout=60,
    ping_interval=25
)
```

## 📞 获取帮助

### 运行诊断工具

```bash
python diagnose.py
```

### 运行系统测试

```bash
python test_system.py
```

### 查看日志

```bash
# 后端日志在终端输出
# 或查看日志文件（如果配置了）
tail -f logs/ezyspeech.log
```

## 🎓 下一步学习

1. **阅读完整文档**
   - `README.md` - 详细使用说明
   - `PROJECT_OVERVIEW.md` - 项目架构说明

2. **自定义配置**
   - `config.py` - 配置文件说明

3. **API 开发**
   - 查看 REST API 和 WebSocket 事件文档
   - 开发自定义客户端

4. **部署到生产环境**
   - 使用 Nginx 反向代理
   - 配置 HTTPS
   - 使用 Gunicorn 部署

## ✅ 检查清单

使用前确保：
- [ ] Python 3.8+ 已安装
- [ ] FFmpeg 已安装
- [ ] 所有依赖包已安装
- [ ] 麦克风已连接（或虚拟声卡已配置）
- [ ] 系统授予了麦克风权限
- [ ] 端口未被占用
- [ ] 网络连接正常（用于翻译 API）

## 🎉 开始使用

一切就绪！现在可以：

1. 启动后端：`python app.py`
2. 启动管理界面：`python admin_gui.py`
3. 开始翻译！

祝使用愉快！ 🚀