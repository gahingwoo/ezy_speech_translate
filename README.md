<div align="center">

# 🌍 [EzySpeechTranslate](https://github.com/gahingwoo/ezy_speech_translate)

**Production-Ready Real-Time Speech Translation System**

With Secure Authentication, Modern Admin Interface, and Web Client

[Quick Start](#-quick-start) • [Features](#-features) • [Documentation](#-usage-guide) • [Deployment](#-production-deployment) • [API](#-api-documentation)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

</div>

---

## 📖 Overview

EzySpeechTranslate is a complete real-time speech recognition and translation system with administrator proofreading capabilities and audience display interface. Perfect for:

- ⛪️ **Church / Religious Services** - Real-time transcription and translation for sermons and worship
- 🎓 **Education** - Real-time lecture translation for international students
- 💼 **Business** - Multilingual meeting transcription and translation  
- 🎥 **Content Creation** - Live streaming with real-time subtitles
- 🏥 **Healthcare** - Doctor-patient communication assistance
- 🎤 **Conferences** - Live interpretation for international events

## ✨ Features

### Core Features

- **Real-Time Speech Recognition** - Browser-based speech recognition using Web Speech API
- **Multi-Language Translation** - Support for 20+ languages
- **Modern Admin Interface** - Responsive web-based GUI
- **Live Client Display** - Real-time subtitle display with auto-updates
- **Secure Authentication** - JWT token-based security
- **Multiple Export Formats** - TXT, JSON, and SRT formats
- **Theme Switching** - Dark/Light theme support
- **Text-to-Speech** - Adjustable speed and volume TTS

### Technical Features

- **YAML Configuration** - Easy-to-use configuration files
- **Cross-Platform** - Windows, macOS, Linux support
- **Real-Time Sync** - WebSocket real-time communication
- **Structured API** - RESTful + WebSocket dual protocol

## System Architecture

```
┌─────────────────────────┐
│   Admin Interface       │ ← Web Interface (Port 1916)
│   admin_server.py       │   
└───────────┬─────────────┘
            │
            │ WebSocket + REST API
            │
┌───────────▼─────────────┐
│   Main Backend          │ ← Server (Port 1915)
│   user_server.py        │   Flask + SocketIO
└───────────┬─────────────┘
            │
            │ WebSocket Real-Time Communication
            │
┌───────────▼─────────────┐
│   User Client           │ ← Browser Interface
│   user.html             │   Real-Time Translation Display
└─────────────────────────┘
```

## Quick Start

### System Requirements

- **Python**: 3.8+
- **Hardware**: Microphone or audio input device
- **Browser**: Chrome/Edge (recommended for speech recognition)
- **Memory**: 2GB+ RAM

### One-Click Installation (Recommended)

```bash
# 1. Clone the repository
git clone https://github.com/gahingwoo/ezy_speech_translate.git
cd ezy_speech_translate

# 2. Run setup script
python setup.py
```

The setup script will automatically:
- ✅ Install dependencies
- ✅ Configure ports (default: main server 1915, admin interface 1916)
- ✅ Set administrator credentials

### Manual Installation

<details>
<summary>Click to expand manual installation steps</summary>

```bash
# 1. Create virtual environment
python -m venv venv

# 2. Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create necessary directories
mkdir logs exports data templates

# 5. Configure config.yaml
# Edit the file to set admin credentials and ports
```

</details>

### Starting Services

**Method 1: Using Startup Scripts**

```bash
# Windows
start_server.bat    # Start main server
start_admin.bat     # Start admin interface

# macOS/Linux
./start_server.sh   # Start main server
./start_admin.sh    # Start admin interface
```

**Method 2: Manual Start**

```bash
# Start main server
venv/bin/python user_server.py

# Start admin interface (new terminal)
venv/bin/python admin_server.py
```

### Access Interfaces

- **Main Server**: https://localhost:1915
- **Admin Interface**: https://localhost:1916

## Usage Guide

### Administrator Operations

#### 1. Login to System

1. Open browser and navigate to `https://localhost:1916`
2. Enter username and password configured in `config.yaml`
3. Click "Sign In" to log in

#### 2. Start Recording

1. Select source language (Chinese, English, etc.)
2. Choose audio device (usually "System Default")
3. Click "🎙️ Start Recording"
4. Speak into microphone - system will automatically recognize and send

#### 3. View and Edit Transcriptions

1. Transcriptions appear in real-time
2. Click a card to select (checkbox auto-checks)
3. Edit text in "Corrected" field
4. Click "💾 Save" to broadcast correction
5. All connected users see the update instantly

#### 4. Export Data

1. Click "📤 Export" button
2. Choose export format:
   - **txt** - Formatted plain text
   - **json** - Structured JSON data
   - **srt** - Video subtitle format

### User Client Operations

#### 1. View Translations

- Real-time subtitle display
- Latest translations appear at top
- Automatic translation to target language

#### 2. Switch Target Language

- Choose from 20+ languages
- Translations update automatically
- Supports: Chinese (Cantonese/Mandarin), Japanese, Korean, Spanish, French, German, etc.

#### 3. Text-to-Speech (TTS)

- Click "Enable TTS" to auto-play translations
- Adjust speed (0.5x - 2.0x)
- Adjust volume (0% - 100%)
- Click 🔊 on individual items to play them

#### 4. Download Subtitles

- Click "Download Subtitles"
- Saves formatted transcript with timestamps
- Includes both original and translated text

## Configuration

### Port Configuration

Customize ports in `config.yaml`:

```yaml
# Main Server
server:
  host: "0.0.0.0"
  port: 1915        # Change this

# Admin Interface
admin_server:
  host: "0.0.0.0"
  port: 1916        # Change this
```

> **Important**: Main server and admin interface must use different ports

### Security Configuration

```yaml
authentication:
  enabled: true
  admin_username: "admin"
  admin_password: "your-secure-password"  # CHANGE THIS!
  session_timeout: 7200                   # seconds
  jwt_secret: "your-jwt-secret"           # CHANGE THIS!
```

**Production Security Recommendations:**

```yaml
authentication:
  admin_password: "Use-A-Very-Strong-Password-Here"
  jwt_secret: "Generate-A-Random-Secret-Key"
```

**Generate Secure Keys:**

```python
import secrets
print(secrets.token_hex(32))      # For secret keys
print(secrets.token_urlsafe(16))  # For passwords
```

## 🔧 Troubleshooting

<details>
<summary><strong>Address Already in Use Error</strong></summary>

**Linux/macOS:**
```bash
lsof -i :1915
kill -9 <PID>
```

**Windows:**
```cmd
netstat -ano | findstr :1915
taskkill /PID <PID> /F
```

Or change the port in `config.yaml`
</details>

<details>
<summary><strong>Admin/Client Cannot Connect</strong></summary>

```bash
# 1. Check if server is running
curl https://localhost:1915/api/health

# 2. Check firewall
sudo ufw status

# 3. Verify port configuration in config.yaml

# 4. Check server logs
tail -f logs/app.log
```
</details>

<details>
<summary><strong>Browser Says "Not Supported"</strong></summary>

- ✅ Use Chrome or Edge (Web Speech API required)
- ✅ Allow microphone permissions
- ✅ Ensure running on HTTPS
- ✅ Verify microphone works in system settings
</details>

<details>
<summary><strong>No Microphone Found</strong></summary>

**Linux:**
```bash
arecord -l
sudo usermod -a -G audio $USER
```

**macOS:**
```bash
system_profiler SPAudioDataType
```

**Windows:** Check Sound Settings
</details>

<details>
<summary><strong>Translation Failed</strong></summary>

- ✅ Check internet connection (uses Google Translate API)
- ✅ Clear browser cache
- ✅ Try different target language
- ✅ Check browser console for errors
</details>

## Production Deployment

### SSL Certificate Generation

```bash
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes
```

### Firewall Configuration

```bash
# Allow only necessary ports
sudo ufw allow 1915/tcp  # Main server
sudo ufw allow 1916/tcp  # Admin interface
sudo ufw enable
```

### Environment Variables

Instead of `config.yaml`, use environment variables:

```bash
export ADMIN_PASSWORD="secure-password"
export JWT_SECRET="random-secret-key"
export SERVER_PORT="1915"
export ADMIN_PORT="1916"
```

### Using Gunicorn

```bash
# Install gunicorn
pip install gunicorn eventlet

# Run main server
gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:1915 user_server:app

# Run admin server
gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:1916 admin_server:app
```

### Systemd Service Configuration

<details>
<summary>Click to view complete systemd configuration</summary>

**Main Server Service** (`/etc/systemd/system/ezyspeech-main.service`):

```ini
[Unit]
Description=EzySpeechTranslate Main Server
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/ezy_speech_translate
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/python /path/to/user_server.py
Restart=always

[Install]
WantedBy=multi-user.target
```

**Admin Interface Service** (`/etc/systemd/system/ezyspeech-admin.service`):

```ini
[Unit]
Description=EzySpeechTranslate Admin Interface
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/ezy_speech_translate
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/python /path/to/admin_server.py
Restart=always

[Install]
WantedBy=multi-user.target
```

**Start Services:**

```bash
# If using SELinux
sudo chcon -R -t bin_t /path/to/venv/bin/

# Enable and start services
sudo systemctl enable ezyspeech-main ezyspeech-admin
sudo systemctl start ezyspeech-main ezyspeech-admin

# Check status
sudo systemctl status ezyspeech-main ezyspeech-admin
```

</details>

## API Documentation

### REST API

#### Login Authentication

```http
POST /api/login
Content-Type: application/json

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

#### Get Configuration

```http
GET /api/config
Authorization: Bearer <token>
```

#### Get Translation History

```http
GET /api/history
Authorization: Bearer <token>
```

#### Clear All Translations

```http
POST /api/clear
Authorization: Bearer <token>
```

#### Export Translations

```http
GET /api/export?format={txt|json|srt}
```

#### Health Check

```http
GET /api/health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-01-01T12:00:00",
  "clients": 3,
  "translations": 42
}
```

### WebSocket API

#### Admin Events

**Emit:**
- `admin_connect` - Authenticate admin session
  ```javascript
  socket.emit('admin_connect', { token: 'JWT_TOKEN' });
  ```
- `new_transcription` - Send new transcription
  ```javascript
  socket.emit('new_transcription', {
    text: 'Hello world',
    language: 'en',
    timestamp: '2025-01-01T12:00:00'
  });
  ```
- `correct_translation` - Update translation
  ```javascript
  socket.emit('correct_translation', {
    id: 0,
    corrected_text: 'Corrected text'
  });
  ```
- `clear_history` - Clear all translations

**Receive:**
- `history` - Initial translation history
- `new_translation` - New translation added
- `translation_corrected` - Translation updated
- `history_cleared` - History cleared

## 🎨 Customization

### Adding New Languages

Add option in `user.html`:
```html
<option value="your-code">Your Language Name</option>
```

### Custom Theme Colors

Modify CSS variables in `user.html` or `admin.html`:

```css
:root {
  --primary: #0066cc;    /* Primary color */
  --success: #3ec930;    /* Success color */
  --danger: #ee0000;     /* Danger color */
}
```

### Extend Export Formats

Add custom export logic in `user_server.py`:

```python
@app.route('/api/export/custom')
@require_auth
def export_custom():
    # Your custom export logic
    return custom_formatted_data
```

## Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see [LICENSE](LICENSE) file for details

## Acknowledgments

- [Web Speech API](https://developer.mozilla.org/en-US/docs/Web/API/Web_Speech_API) - Browser-based speech recognition
- [Google Translate](https://translate.google.com/) - Translation services
- [Flask](https://flask.palletsprojects.com/) & [SocketIO](https://socket.io/) - Real-time communication

## Support

Have questions or issues?

- **GitHub Issues**: [Create an Issue](https://github.com/gahingwoo/ezy_speech_translate/issues/new/choose)
- **Documentation**: Check this README and code comments
- **Logs**: Review `logs/app.log` for troubleshooting
- **Discussions**: Join [GitHub Discussions](https://github.com/gahingwoo/ezy_speech_translate/discussions)

## Version History
- v3.2.2 (Current)
- Add transcription only function
- Add reset settings button


---

<div align="center">

**Made with ❤️ by [Ga Hing Woo](https://github.com/gahingwoo)**

🌍 *Ezy-Speech - Let language no longer stand in the way of connection.*

[⬆ Back to Top](#-ezyspeech translate)

</div>