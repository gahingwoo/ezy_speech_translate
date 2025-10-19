# EzySpeechTranslate 实时语音翻译系统

完整的实时语音转文字+翻译系统，支持管理员校对和听众端展示。

## 系统架构

```
麦克风音频（电脑/虚拟声卡）
      │
      ▼
ASR（OpenAI Whisper）实时转录
      │
      ▼
英文文字流（实时）
      │
      ▼
MT（Google Translate）机器翻译
      │
      ▼
中文机器翻译文字流
      │
      ▼
人工校对（Qt6管理员界面）
      │
      ▼
字幕输出 / TTS播放
      │
      ▼
听众端（网页文字展示 + TTS）
```

## 功能特性

### 核心功能
- ✅ **实时语音识别**: 使用 OpenAI Whisper 进行高精度 ASR
- ✅ **自动翻译**: Google Translate API 实时翻译（支持切换 DeepL）
- ✅ **管理员校对**: Qt6 桌面界面，可实时编辑和修正翻译
- ✅ **听众端展示**: 网页端实时显示字幕，支持 TTS 朗读
- ✅ **WebSocket 推送**: 所有客户端实时同步更新
- ✅ **音频源选择**: 支持选择不同的音频输入设备
- ✅ **历史管理**: 完整的翻译历史记录和导出功能

### 管理员功能
- 音频输入设备选择
- 实时翻译流预览
- 逐条编辑和校对翻译
- 清空历史记录
- 连接状态监控

### 听众端功能
- 实时字幕显示
- TTS 自动朗读（可开关）
- 语速和音量调节
- 手动点击朗读单条字幕
- 字幕文件下载
- 校对状态标识

## 安装步骤

### 1. 系统依赖

#### Ubuntu/Debian
```bash
sudo apt-get update
sudo apt-get install portaudio19-dev python3-dev python3-pyqt6 ffmpeg
```

#### macOS
```bash
brew install portaudio ffmpeg
```

#### Windows
- 安装 [Python 3.10+](https://www.python.org/downloads/)
- 安装 [FFmpeg](https://ffmpeg.org/download.html)

### 2. Python 依赖
```bash
# 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # Linux/macOS
# 或
venv\Scripts\activate     # Windows

# 安装依赖
pip install -r requirements.txt
```

### 3. 目录结构
```
EzySpeechTranslate/
├── app.py                 # Flask 后端服务
├── admin_gui.py           # Qt6 管理员界面
├── requirements.txt       # Python 依赖
├── README.md             # 本文件
└── templates/
    └── index.html        # 听众端网页
```

## 使用方法

### 1. 启动系统（推荐方式）

```bash
# 使用跨平台 Python 启动脚本
python start.py
```

这是最简单的方式，支持 Windows/Linux/macOS，完美显示中文。

启动脚本提供以下选项：
- [1] 仅启动后端服务
- [2] 仅启动管理员界面
- [3] 同时启动（推荐）
- [4] 运行系统诊断
- [5] 重新安装依赖

### 2. 手动启动

如果需要手动启动：

```bash
# 终端 1: 启动后端
python app.py

# 终端 2: 启动管理界面
# PyQt6 版本
python admin_gui.py

# 或 PySide6 版本（如果 PyQt6 有 DLL 问题）
python admin_gui_pyside.py
```

### 3. 打开听众端
在浏览器中访问：
```
http://localhost:{config.PORT}
```

或在其他设备上访问（确保在同一网络）：
```
http://[服务器IP]:{config.PORT}
```

## 使用流程

### 管理员端操作

1. **选择音频设备**
   - 点击"刷新设备"加载可用的音频输入
   - 从下拉菜单选择麦克风或虚拟声卡
   - 如需使用系统音频，推荐使用虚拟声卡（如 VB-Cable）

2. **开始录制**
   - 点击"▶ 开始录制"按钮
   - 对着麦克风说英文
   - 系统会自动检测语音并转录

3. **校对翻译**
   - 右侧表格显示所有翻译历史
   - 直接在"中文翻译"列编辑文本
   - 点击"保存"按钮提交校对
   - 校对后的翻译会标记为绿色

4. **管理历史**
   - 点击"🗑 清空历史"清除所有记录
   - 所有客户端会同步更新

### 听众端操作

1. **查看字幕**
   - 自动显示实时翻译结果
   - 校对后的字幕会显示"已校对"标记

2. **TTS 朗读**
   - 点击"🔊 启用 TTS"开启自动朗读
   - 调节语速（0.5x - 2.0x）
   - 调节音量（0% - 100%）
   - 点击单条字幕的 🔊 图标单独朗读

3. **下载字幕**
   - 点击"💾 下载字幕"保存完整记录
   - 文件格式为 TXT，包含时间戳和双语文本

## 高级配置

### 使用 DeepL API
如需使用 DeepL 替代 Google Translate（更高翻译质量）：

1. 注册 [DeepL API](https://www.deepl.com/pro-api)
2. 安装依赖：
   ```bash
   pip install deepl
   ```
3. 修改 `app.py`：
   ```python
   import deepl
   translator = deepl.Translator("YOUR_API_KEY")
   
   # 在翻译部分替换为：
   result = translator.translate_text(english_text, target_lang="ZH")
   chinese_text = result.text
   ```

### 调整 Whisper 模型
在 `app.py` 中修改模型大小：
```python
whisper_model = whisper.load_model("base")  # tiny, base, small, medium, large
```

| 模型 | 大小 | 速度 | 精度 |
|------|------|------|------|
| tiny | 39M | 最快 | 较低 |
| base | 74M | 快 | 中等 |
| small | 244M | 中 | 良好 |
| medium | 769M | 慢 | 很好 |
| large | 1550M | 最慢 | 最佳 |

### 使用虚拟声卡（捕获系统音频）

#### Windows
1. 安装 [VB-CABLE](https://vb-audio.com/Cable/)
2. 将播放设备设为 VB-Cable
3. 在管理员界面选择 "VB-Cable Output"

#### macOS
1. 安装 [BlackHole](https://github.com/ExistentialAudio/BlackHole)
2. 创建多输出设备（音频 MIDI 设置）
3. 在管理员界面选择 BlackHole 设备

#### Linux
使用 PulseAudio 或 PipeWire 创建虚拟音频设备。

## 故障排除

### 问题：找不到音频设备
- 检查麦克风是否正确连接
- 在系统设置中启用麦克风权限
- 尝试点击"刷新设备"

### 问题：Whisper 转录不准确
- 使用更大的模型（如 medium 或 large）
- 确保音频清晰，减少背景噪音
- 调整麦克风增益

### 问题：翻译质量不佳
- 考虑使用 DeepL API
- 通过管理员界面手动校对

### 问题：网页无法连接
- 检查防火墙设置
- 确保 Flask 服务正在运行
- 尝试使用 `0.0.0.0` 而不是 `localhost`

## 技术栈

- **后端**: Flask + Flask-SocketIO + WebSocket
- **ASR**: OpenAI Whisper
- **翻译**: Google Translate API / DeepL API
- **管理端**: PyQt6
- **听众端**: HTML5 + JavaScript + Socket.IO
- **TTS**: Web Speech API

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！

## 更新日志

### v1.0.1 (2025-10-19)
- ✅ 多语言版本发布
- ✅ 实时 ASR + 翻译
- ✅ Qt6 管理员界面
- ✅ 网页听众端
- ✅ TTS 支持
- ✅ 字幕下载功能