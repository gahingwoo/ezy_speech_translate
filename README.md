# 🎙️ EzySpeechTranslate

A production-ready real-time speech translation system with secure authentication, modern admin interface, and web client.

## ✨ Features

- **Real-time Speech Recognition** using Web Speech API
- **Multi-language Translation** (20+ languages supported)
- **Modern Admin Interface** with web-based GUI
- **Responsive Web Client** with live updates
- **Secure Authentication** with JWT tokens
- **YAML Configuration** for easy customization
- **Export Functionality** (TXT, JSON, SRT formats)
- **Cross-platform Support** (Windows, macOS, Linux)
- **Text-to-Speech** with adjustable speed and volume
- **Dark/Light Theme** support

## 🏗️ Architecture

```
┌─────────────────────┐
│   Admin Interface   │ ◄─── Web Interface (Port 1916)
│  (admin_server.py)  │      Modern, responsive GUI
└─────────┬───────────┘
          │
          │ WebSocket + REST API
          │
┌─────────▼───────────┐
│   Main Backend      │ ◄─── Server (Port 1915)
│  (user_server.py)   │      Flask + SocketIO
└─────────┬───────────┘
          │
          │ WebSocket
          │
┌─────────▼───────────┐
│   User Clients      │ ◄─── Browser Interface
│   (user.html)      │      Real-time translations
└─────────────────────┘
```

## 📋 Prerequisites

- Python 3.8-3.14
- Microphone or audio input device
- Modern web browser (Chrome/Edge recommended for speech recognition)
- 2GB+ RAM

## 🚀 Quick Installation

### Option 1: Automated Setup (Recommended)

```bash
# 1. Clone or download the project
git clone https://github.com/gahingwoo/ezy_speech_translate.git
cd ezy_speech_translate

# 2. Run setup script
python setup.py

# Follow the interactive prompts to:
# - Install dependencies
# - Configure ports (default: 1915 for main, 1916 for admin)
# - Set admin credentials
```

### Option 2: Manual Setup

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

# 4. Edit config.yaml
# - Set admin credentials
# - Configure ports
# - Adjust other settings

# 5. Create required directories
mkdir logs exports data templates
```

## 🎯 Quick Start

### 1. Start the Main Server

```bash
# Windows
start_server.bat

# macOS/Linux
./start_server.sh

# Or manually:
venv/bin/python user_server.py
```

The server starts on `https://localhost:1915` (or your configured port)

### 2. Launch Admin Interface

In a **new terminal**:

```bash
# Windows
start_admin.bat

# macOS/Linux
./start_admin.sh

# Or manually:
venv/bin/python admin_server.py
```

Admin interface: `https://localhost:1916` (or your configured port)

### 3. Access User Interface

Open your browser:

```
https://localhost:1915
```

## 📖 Usage Guide

### Admin Interface Workflow

1. **Login**
   
   - Open `https://localhost:1916`
   - Enter username and  password from config.yaml
   - Click "Sign In"

2. **Start Recording**
   
   - Select source language (English, Chinese, etc.)
   - Choose audio device (usually "System Default")
   - Click "🎙️ Start Recording"
   - Speak into microphone
   - Speech is automatically recognized and sent

3. **View & Edit Transcriptions**
   
   - Transcriptions appear in real-time
   - **Click on a card** to select it (checkbox auto-checks)
   - Edit text in "Corrected" field
   - Click "💾 Save" to broadcast correction
   - All connected users see the update instantly

4. **Export Data**
   
   - Click "📤 Export" button
   - Choose format:
     - **txt** - Plain text with formatting
     - **json** - Structured JSON data
     - **srt** - Subtitle format for videos

### User Interface Features

1. **View Translations**
   
   - Real-time subtitle display
   - Newest translations appear at top
   - Automatic translation to target language

2. **Change Target Language**
   
   - Select from 20+ languages
   - Translations update automatically
   - Supports: Chinese (Cantonese/Mandarin), Japanese, Korean, Spanish, French, German, and more

3. **Text-to-Speech (TTS)**
   
   - Click "Enable TTS" to auto-play translations
   - Adjust speed (0.5x to 2.0x)
   - Adjust volume (0% to 100%)
   - Click 🔊 on individual items to hear them

4. **Download Subtitles**
   
   - Click "💾 Download Subtitles"
   - Saves formatted transcript with timestamps
   - Includes both original and translated text

## ⚙️ Configuration

### Port Configuration

Ports can be customized during setup or in `config.yaml`:

```yaml
# Main Server
server:
  host: "0.0.0.0"
  port: 1915  # Change this

# Admin Interface
admin_server:
  host: "0.0.0.0"
  port: 1916  # Change this
```

**Important:** Main server and admin interface must use **different ports**.

### Authentication Settings

```yaml
authentication:
  enabled: true
  admin_username: "admin"
  admin_password: "your-secure-password"  # CHANGE THIS!
  session_timeout: 7200  # seconds
  jwt_secret: "your-jwt-secret"  # CHANGE THIS!
```

## 🔒 Security Best Practices

### 1. Change Default Credentials

**During setup:**

- Use strong, unique passwords

**In production:**

```yaml
authentication:
  admin_password: "Use-A-Very-Strong-Password-Here"
  jwt_secret: "Generate-A-Random-Secret-Key"
```

Generate secure secrets:

```python
import secrets
print(secrets.token_hex(32))  # For secret keys
print(secrets.token_urlsafe(16))  # For passwords
```

### 2. Use HTTPS in Production

Generate SSL Certificate

```shell
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes
```

### 3. Firewall Configuration

```bash
# Allow only necessary ports
sudo ufw allow 1915/tcp  # Main server
sudo ufw allow 1916/tcp  # Admin interface
sudo ufw enable
```

### 4. Environment Variables (Optional)

Instead of config.yaml:

```bash
export ADMIN_PASSWORD="secure-password"
export JWT_SECRET="random-secret-key"
export SERVER_PORT="1915"
export ADMIN_PORT="1916"
```

## 🌐 Production Deployment

### With Gunicorn

```bash
# Install gunicorn
pip install gunicorn eventlet

# Run main server
gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:1915 user_server:app

# Run admin server (in another terminal)
gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:1916 admin_server:app
```

### Systemd Service (Linux)

Create `/etc/systemd/system/ezyspeech-main.service`:

```ini
[Unit]
Description=EzySpeechTranslate Main Server
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/ezy_speech_translate
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/python user_server.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Create `/etc/systemd/system/ezyspeech-admin.service`:

```ini
[Unit]
Description=EzySpeechTranslate Admin Interface
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/ezy_speech_translate
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/python admin_server.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo chcon -R -t bin_t /path/to/venv/bin/ # do this if using SELinux
sudo systemctl enable ezyspeech-main ezyspeech-admin
sudo systemctl start ezyspeech-main ezyspeech-admin
sudo systemctl status ezyspeech-main ezyspeech-admin
```

## 🔧 Troubleshooting

### Port Already in Use

**Problem:** `Address already in use` error

**Solution:**

```bash
# Find process using port
# Linux/macOS:
lsof -i :1915
kill -9 <PID>

# Windows:
netstat -ano | findstr :1915
taskkill /PID <PID> /F

# Or change port in config.yaml
```

### Cannot Connect to Server

**Problem:** Admin/client can't connect

**Solution:**

```bash
# 1. Check if server is running
curl https://localhost:1915/api/health

# 2. Check firewall
sudo ufw status

# 3. Verify ports in config.yaml match your setup

# 4. Check server logs
tail -f logs/app.log
```

### Speech Recognition Not Working

**Problem:** Browser says "not supported"

**Solution:**

- Use Chrome or Edge (required for Web Speech API)
- Allow microphone permissions
- Check if running on HTTPS
- Verify microphone is working in system settings

### No Audio Devices

**Problem:** No microphone found

**Solution:**

```bash
# Check system audio
# Linux:
arecord -l

# macOS:
system_profiler SPAudioDataType

# Windows: Check Sound Settings

# Verify permissions
# Linux:
sudo usermod -a -G audio $USER
```

### Translation Not Working

**Problem:** Translations show "translation failed"

**Solution:**

- Check internet connection (Google Translate API)
- Clear browser cache
- Try different target language
- Check browser console for errors

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

Get configuration (requires auth)

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

#### GET `/api/health`

Health check endpoint

**Response:**

```json
{
  "status": "healthy",
  "timestamp": "2025-01-01T12:00:00",
  "clients": 3,
  "translations": 42
}
```

### WebSocket Events

#### Client → Server

- `admin_connect`: Authenticate admin session
  
  ```javascript
  socket.emit('admin_connect', { token: 'JWT_TOKEN' });
  ```

- `new_transcription`: Send new transcription
  
  ```javascript
  socket.emit('new_transcription', {
    text: 'Hello world',
    language: 'en',
    timestamp: '2025-01-01T12:00:00'
  });
  ```

- `correct_translation`: Update translation
  
  ```javascript
  socket.emit('correct_translation', {
    id: 0,
    corrected_text: 'Corrected text'
  });
  ```

- `clear_history`: Clear all translations
  
  ```javascript
  socket.emit('clear_history');
  ```

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

Add to `user.html`:

```html
<option value="your-code">Your Language Name</option>
```

### Custom Styling

Modify CSS variables in `user.html` or `admin.html`:

```css
:root {
    --primary: #0066cc;      /* Change primary color */
    --success: #3ec930;      /* Change success color */
    --danger: #ee0000;       /* Change danger color */
}
```

### Custom Export Formats

Extend `user_server.py`:

```python
@app.route('/api/export/custom')
@require_auth
def export_custom():
    # Your custom export logic
    return custom_formatted_data
```

## 📝 Use Cases

- 🎓 **Education**: Real-time lecture translation for international students
- 💼 **Business**: Multilingual meeting transcription and translation
- 🎥 **Content Creation**: Live streaming with real-time subtitles
- 🏥 **Healthcare**: Doctor-patient communication assistance
- 📞 **Customer Support**: Real-time call translation
- 🎤 **Conferences**: Live interpretation for international events
- 🎮 **Gaming**: Team communication across languages

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

MIT License - See LICENSE file for details

## 🙏 Acknowledgments

- **Web Speech API** for browser-based speech recognition
- **Google Translate** for translation services
- **Flask & SocketIO** for real-time communication

## 📧 Support

For issues and questions:

- 📝 **GitHub Issues**: [Create an issue](https://github.com/gahingwoo/ezy_speech_translate/issues/new/choose)
- 📖 **Documentation**: Check this README and inline code comments
- 🔍 **Logs**: Review `logs/app.log` for troubleshooting
- 💬 **Discussions**: Join GitHub Discussions for community support

## 🔄 Version History

### v3.2.0 (Current)
- Multiple export formats (TXT, JSON, CSV, SRT) for user
- Real-time search
- Customizable font size

---

**Made with ❤️ by Ga Hing Woo for breaking language barriers**

🌍 *Because everyone deserves to be understood*