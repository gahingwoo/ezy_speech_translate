# 🌍 EzySpeechTranslate

**Production-Ready Real-Time Speech Translation System**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![GitHub](https://img.shields.io/github/stars/gahingwoo/ezy_speech_translate?style=social)](https://github.com/gahingwoo/ezy_speech_translate)

Real-time speech recognition and translation system with secure authentication, modern admin interface, and audience display capabilities.

---

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

---

## 🎯 Choose Your Guide

Select the guide that matches your role:

### 👨‍💼 [Administrator Guide](docs/README_ADMIN.md)

**For event hosts, speakers, and moderators**

Learn how to:

- Set up and start recording sessions
- Monitor and correct transcriptions in real-time
- Manage translations for your audience
- Export session transcripts

**→ [Read Administrator Guide](docs/README_ADMIN.md)**

---

### 👥 [Viewer Guide](docs/README_CLIENT.md)

**For audience members and participants**

Learn how to:

- View real-time translations in your language
- Use text-to-speech features
- Download transcripts after events
- Customize your viewing experience

**→ [Read Viewer Guide](docs/README_CLIENT.md)**

---

### 👨‍💻 [Developer Guide](docs/README_DEVELOPER.md)

**For developers, system administrators, and contributors**

Learn about:

- System architecture and technical stack
- Installation and configuration
- API documentation and WebSocket events
- Production deployment and security
- Development workflow and contributing

**→ [Read Developer Guide](docs/README_DEVELOPER.md)**

---

## ⚡ Quick Start

### For Administrators

1. **Access your admin interface** (provided by IT)
2. **Log in** with your credentials
3. **Select language** and **start recording**
4. **Speak clearly** - system handles the rest!

[Full Admin Guide →](docs/README_ADMIN.md)

### For Viewers

1. **Open the URL** (shared by organizers)
2. **Select your language** from dropdown
3. **View translations** in real-time
4. **Download transcript** when done

[Full Viewer Guide →](docs/README_CLIENT.md)

### For Developers

```bash
# Quick installation
git clone https://github.com/gahingwoo/ezy_speech_translate.git
cd ezy_speech_translate
python setup.py

# Start services
python user_server.py      # Main server (port 1915)
python admin_server.py     # Admin interface (port 1916)
```

[Full Developer Guide →](docs/README_DEVELOPER.md)

---

## 🌟 Key Features

### Real-Time Processing

- **Instant speech recognition** using Web Speech API
- **Live translation** to 20+ languages
- **Auto-updates** for all connected viewers
- **Low latency** broadcast system

### Professional Admin Tools

- **Correction system** for accurate transcriptions
- **Bulk editing** for multiple items
- **Export options** (TXT, JSON, SRT formats)
- **Session management** with history

### Audience Experience

- **Clean interface** with modern design
- **Text-to-speech** with adjustable speed
- **Language selection** from 20+ options
- **Transcript download** for later reference

### Enterprise Ready

- **JWT authentication** for secure access
- **HTTPS/SSL support** for encryption
- **WebSocket** for real-time communication
- **Production deployment** guides included

---

## 🏆 Perfect For

| Use Case                  | Description                                    |
| ------------------------- | ---------------------------------------------- |
| ⛪️ **Religious Services** | Live sermon and worship translation            |
| 🎓 **Education**          | Lecture translation for international students |
| 💼 **Business**           | Multilingual meeting support                   |
| 🎥 **Live Events**        | Conference and presentation subtitles          |
| 🏥 **Healthcare**         | Doctor-patient communication assistance        |
| 🎤 **Conferences**        | Real-time interpretation services              |

---

## 📚 Documentation Structure

```
docs/
├── README_ADMIN.md          # For administrators
├── README_CLIENT.md         # For viewers
└── README_DEVELOPER.md      # For developers

images/
├── system_overview.png
├── admin_*.png             # Admin screenshots
└── client_*.png            # Client screenshots
```

---

## 🛠️ Technical Stack

| Component          | Technology                 |
| ------------------ | -------------------------- |
| Backend            | Python 3.8+ with Flask     |
| Real-Time          | Flask-SocketIO + WebSocket |
| Frontend           | Vanilla JavaScript         |
| Authentication     | JWT (PyJWT)                |
| Translation        | Google Translate API       |
| Speech Recognition | Web Speech API             |
| Protocol           | HTTPS/WSS with SSL         |

---

## 🌐 Supported Languages

**20+ languages including:**

Chinese (Simplified, Traditional, Cantonese) • English • Spanish • French • German • Italian • Japanese • Korean • Russian • Arabic • Hindi • Portuguese • Dutch • Polish • Thai • Vietnamese • Indonesian • Turkish • Hebrew • Danish

*See [Viewer Guide](docs/README_CLIENT.md) for complete list*

---

## 🚀 System Requirements

### Minimum

- Python 3.8+
- 2GB RAM
- Stable internet connection
- Modern web browser (Chrome/Edge recommended)

### Recommended

- Python 3.10+
- 4GB RAM
- Dedicated microphone
- Multiple cores for concurrent users

*See [Developer Guide](docs/README_DEVELOPER.md) for detailed requirements*

---

## 📝 Quick Links

- [Administrator Guide](docs/README_ADMIN.md) - For event hosts
- [Viewer Guide](docs/README_CLIENT.md) - For audience members  
- [Developer Guide](docs/README_DEVELOPER.md) - For technical users
- [GitHub Repository](https://github.com/gahingwoo/ezy_speech_translate)
- [Report Issues](https://github.com/gahingwoo/ezy_speech_translate/issues)
- [Discussions](https://github.com/gahingwoo/ezy_speech_translate/discussions)

---

## 🤝 Contributing

We welcome contributions! Please see the [Developer Guide](docs/README_DEVELOPER.md) for:

- Development setup
- Code style guidelines
- Testing procedures
- Pull request process

---

## 📄 License

This project is licensed under the MIT License - see [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgments

- **Web Speech API** - Browser speech recognition
- **Google Translate** - Translation services
- **Flask & SocketIO** - Real-time communication framework
- **Community Contributors** - Thank you for your support!

---

## 📞 Support

**Need help?**

- 📖 Check the appropriate guide (Admin/Client/Developer)
- 🐛 [Report bugs](https://github.com/gahingwoo/ezy_speech_translate/issues)
- 💬 [Ask questions](https://github.com/gahingwoo/ezy_speech_translate/discussions)
- 📧 Contact your system administrator

---

## 🎯 Version Information

**Current Version:** 3.3.0

**Recent Updates:**

- Enhanced security features
- Updated documentation structure
- Performance optimizations

**Changelog:** See [Commit History](https://github.com/gahingwoo/ezy_speech_translate/commits/main/)

---

<div align="center">

**Made with ❤️ by [Ga Hing Woo](https://github.com/gahingwoo)**

*Breaking down language barriers, one word at a time*

[⬆ Back to Top](#-ezyspeech translate)

</div>
