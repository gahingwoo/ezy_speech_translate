# 🎙️ EzySpeechTranslate

A production-ready real-time speech translation system with authentication, admin GUI, and web interface.

## ✨ Features

- **Real-time Speech Recognition** using OpenAI Whisper
- **Multi-language Translation** (100+ languages supported)
- **Admin Desktop GUI** for transcription correction
- **Web Client Interface** with live updates
- **Secure Authentication** with JWT tokens
- **Configuration Management** via YAML
- **Export Functionality** (TXT, JSON, SRT formats)
- **Cross-platform Support** (Windows, macOS, Linux)

## 🏗️ Architecture

```
┌─────────────────┐
│   Admin GUI     │ ◄─── Desktop App (Tkinter)
│  (admin_gui.py) │
└────────┬────────┘
         │
         │ WebSocket + REST API
         │
┌────────▼────────┐
│  Flask Backend  │ ◄─── Server (app.py)
│    (app.py)     │
└────────┬────────┘
         │
         │ WebSocket
         │
┌────────▼────────┐
│  Web Clients    │ ◄─── Browser Interface
│  (index.html)   │
└─────────────────┘
```

## 📋 Prerequisites

- Python 3.8 -3.12
- FFmpeg (for audio processing)
- Microphone or audio input device
- 4GB+ RAM (for Whisper model)

### Installing FFmpeg

**Windows:**
```bash
# Using Chocolatey
choco install ffmpeg
# Or download from: https://ffmpeg.org/download.html
# Or winget install ffmpeg
```

**macOS:**
```bash
brew install ffmpeg
```

**Linux:**
```bash
sudo apt-get install ffmpeg  # Ubuntu/Debian
sudo yum install ffmpeg      # CentOS/RHEL
```

## 🚀 Installation

### 1. Clone or Download the Project

```bash
git clone https://github.com/gahingwoo/ezy_speech_translate.git
cd ezy_speech_translate
```
### Either use one key setup script `setup.py`. Or

### 2. Create Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate it
# Windows:
venv\Scripts\activate

# macOS/Linux:
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure the Application

Edit `config.yaml` to customize settings:

```yaml
# IMPORTANT: Change these in production!
authentication:
  admin_username: "admin"
  admin_password: "your-secure-password"  # CHANGE THIS!
  jwt_secret: "your-jwt-secret-key"      # CHANGE THIS!

server:
  secret_key: "your-flask-secret-key"    # CHANGE THIS!
```

## 🎯 Quick Start

### 1. Start the Backend Server

```bash
python app.py 
# ./start_server.sh (Linux, macOS)
# ./start_server.bat (Windows)
```

The server will start on `http://localhost:5000`

### 2. Launch Admin GUI

In a new terminal:

```bash
python admin_gui.py
# ./start_admin.sh (Linux, macOS)
# ./start_admin.bat (Windows)
```

**Default credentials:**
- Username: `admin`
- Password: `admin123` (change in config.yaml!)

### 3. Open Web Client

Open your browser and navigate to:
```
http://localhost:5000
```

## 📖 Usage Guide

### Admin GUI Workflow

1. **Login**
   - Enter credentials from config.yaml
   - Click "Login"

2. **Select Audio Device**
   - Choose your microphone from dropdown
   - Click "Refresh" if device not shown

3. **Start Recording**
   - Click "🎙️ Start Recording"
   - Speak into microphone
   - Transcriptions appear in real-time

4. **Correct Transcriptions**
   - Select transcription from list
   - Edit text in "Corrected" field
   - Click "Save Correction"
   - Correction broadcasts to all clients

5. **Export Data**
   - Click "Export" button
   - Choose format (TXT, JSON, SRT)
   - Save to file

### Web Client Features

1. **View Translations**
   - Real-time subtitle display
   - Auto-scroll to latest

2. **Change Target Language**
   - Select from dropdown (19 languages)
   - Translations update automatically

3. **Text-to-Speech (TTS)**
   - Click "Enable TTS"
   - Adjust speed and volume
   - Click 🔊 on individual items

4. **Download Subtitles**
   - Click "💾 Download"
   - Saves formatted transcript

## ⚙️ Configuration Reference

### Audio Settings

```yaml
audio:
  sample_rate: 16000        # Audio sampling rate (Hz)
  block_duration: 5         # Seconds between transcriptions
  device_index: null        # null = default device
```

### Whisper Model Settings

```yaml
whisper:
  model_size: "base"        # tiny, base, small, medium, large
  device: "cpu"             # cpu or cuda (Nvidia GPU)
  compute_type: "int8"      # int8, float16, float32
  language: "en"            # Source language or null
  beam_size: 5              # Beam search size
  vad_filter: true          # Voice activity detection
```

**Model Size Guide:**
- `tiny`: Fastest, least accurate (~75MB)
- `base`: Good balance (~150MB) **[Recommended]**
- `small`: Better accuracy (~500MB)
- `medium`: High accuracy (~1.5GB)
- `large`: Best accuracy (~3GB)

### Authentication Settings

```yaml
authentication:
  enabled: true             # Enable/disable auth
  admin_username: "admin"
  admin_password: "admin123"
  session_timeout: 3600     # Seconds
  jwt_secret: "secret-key"
```

**⚠️ Security Warning:** Always change default credentials in production!

## 🔒 Security Best Practices

1. **Change Default Credentials**
   ```yaml
   authentication:
     admin_password: "use-a-strong-password"
     jwt_secret: "generate-random-secret"
   ```

2. **Use HTTPS in Production**
   - Configure reverse proxy (nginx, Apache)
   - Obtain SSL certificate (Let's Encrypt)

3. **Firewall Configuration**
   ```bash
   # Only allow necessary ports
   sudo ufw allow 5000/tcp
   ```

4. **Environment Variables** (Alternative to config.yaml)
   ```bash
   export ADMIN_PASSWORD="secure-password"
   export JWT_SECRET="random-secret"
   ```

## 🌐 Deployment

### Production Server with Gunicorn

```bash
# Install gunicorn
pip install gunicorn eventlet

# Run with gunicorn
gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:5000 app:app
```

### Systemd Service (Linux)

Create `/etc/systemd/system/ezyspeech.service`:

```ini
[Unit]
Description=EzySpeechTranslate Service
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/EzySpeechTranslate
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/python app.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable ezyspeech
sudo systemctl start ezyspeech
sudo systemctl status ezyspeech
```

## 🔧 Troubleshooting

### Audio Device Issues

**Problem:** No audio devices found

**Solution:**
```bash
# List all audio devices
python -c "import sounddevice as sd; print(sd.query_devices())"

# Check device permissions (Linux)
sudo usermod -a -G audio $USER
```

### Whisper Model Download

**Problem:** Model download fails

**Solution:**
```bash
# Pre-download model
python -c "from faster_whisper import WhisperModel; WhisperModel('base', device='cpu', compute_type='int8')"
```

### WebSocket Connection Failed

**Problem:** Client can't connect to server

**Solution:**
```bash
# Check if server is running
curl http://localhost:5000/api/health

# Check firewall
sudo ufw status
```

### High CPU Usage

**Problem:** CPU usage too high

**Solution:**
- Use smaller Whisper model (tiny or base)
- Increase `block_duration` in config.yaml
- Enable GPU acceleration (CUDA)

### Permission Errors (Linux/Mac)

```bash
# Fix permissions
chmod +x admin_gui.py app.py
```

## 📊 API Reference

### REST Endpoints

#### POST `/api/login`
Authenticate admin user

**Request:**
```json
{
  "username": "admin",
  "password": "password"
}
```

**Response:**
```json
{
  "success": true,
  "token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "username": "admin"
}
```

#### GET `/api/config`
Get current configuration (requires auth)

**Headers:**
```
Authorization: Bearer <token>
```

#### GET `/api/translations`
Get translation history (requires auth)

#### POST `/api/translations/clear`
Clear all translations (requires auth)

#### GET `/api/export/<format>`
Export translations (txt, json, srt)

### WebSocket Events

#### Client → Server

- `admin_connect`: Authenticate admin session
- `new_transcription`: Send new transcription
- `correct_translation`: Update translation

#### Server → Client

- `history`: Initial translation history
- `new_translation`: New translation added
- `translation_corrected`: Translation updated
- `history_cleared`: History cleared

## 🎨 Customization

### Adding New Languages

Edit `config.yaml`:

```yaml
translation:
  supported_languages:
    - "your-language-code"
```

### Custom Styling

Edit `templates/index.html`:

```css
/* Modify colors, fonts, layout */
body {
    background: your-gradient;
}
```

### Custom Export Formats

Extend `app.py`:

```python
@app.route('/api/export/custom')
def export_custom():
    # Your custom export logic
    pass
```

## 📝 Use Cases

- 🎓 **Lectures & Presentations**: Real-time translation for international audiences
- 💼 **Business Meetings**: Multilingual meeting transcription
- 🎥 **Live Streaming**: Add live subtitles to streams
- 🏥 **Healthcare**: Doctor-patient communication assistance
- 📞 **Customer Support**: Real-time call translation

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create feature branch
3. Commit changes
4. Push to branch
5. Open pull request

## 📄 License

MIT License - See LICENSE file for details

## 🙏 Acknowledgments

- OpenAI Whisper for speech recognition
- Google Translate for translation API
- Flask & SocketIO for real-time communication

## 📧 Support

For issues and questions:
- Create an issue on GitHub
- Check troubleshooting section
- Review logs in `logs/app.log`

## 🔄 Version History

### v2.0.2 (Current)
- Add Cantonese support
- A better front-end UI


---

**Made with ❤️ for breaking language barriers**