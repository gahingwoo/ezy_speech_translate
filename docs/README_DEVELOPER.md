# EzySpeechTranslate - Developer Documentation

**Production-Ready Real-Time Speech Translation System**

Complete technical documentation for developers, system administrators, and contributors.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

---

## 📋 Table of Contents

1. [System Architecture](#system-architecture)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [API Documentation](#api-documentation)
5. [Development](#development)
6. [Production Deployment](#production-deployment)
7. [Security](#security)
8. [Troubleshooting](#troubleshooting)
9. [Contributing](#contributing)

---
## System Architecture

### Overview

```
┌─────────────────────────┐
│   Admin Interface       │ ← React/HTML (Port 1916)
│   admin/erver.py       │   JWT Auth + WebSocket
└───────────┬─────────────┘
            │
            │ REST API + WebSocket
            │ JWT Authentication
            │
┌───────────▼─────────────┐
│   Main Backend          │ ← Flask + SocketIO (Port 1915)
│   user/server.py        │   Translation Engine
└───────────┬─────────────┘
            │
            │ WebSocket Broadcast
            │ Real-Time Sync
            │
┌───────────▼─────────────┐
│   User Clients          │ ← Browser (Multiple)
│   user.html             │   No Auth Required
└─────────────────────────┘
```

### Component Details

#### Main Backend (`user/server.py`)

- **Framework**: Flask + Flask-SocketIO
- **Port**: 1915 (configurable)
- **Responsibilities**:
  - Translation processing
  - Real-time broadcast to clients
  - Export functionality
  - Health monitoring

#### Admin Interface (`admin/server.py`)

- **Framework**: Flask + Flask-SocketIO
- **Port**: 1916 (configurable)
- **Responsibilities**:
  - Speech recognition coordination
  - Transcription correction
  - Authentication & authorization
  - Admin-specific APIs

#### User Client (`user.html`)

- **Technology**: Vanilla JavaScript + Socket.IO
- **Features**:
  - Real-time translation display
  - Text-to-speech synthesis
  - Language selection
  - Subtitle export

### Technology Stack

| Component          | Technology     | Version | Purpose                    |
| ------------------ | -------------- | ------- | -------------------------- |
| Backend            | Python         | 3.8+    | Server runtime             |
| Web Framework      | Flask          | 2.x     | HTTP/REST API              |
| Real-Time          | Flask-SocketIO | 5.x     | WebSocket communication    |
| Authentication     | PyJWT          | 2.x     | JWT token generation       |
| Translation        | googletrans    | 4.x     | Multi-language translation |
| Speech Recognition | Web Speech API | -       | Browser-based ASR          |
| Frontend           | JavaScript     | ES6+    | Client-side logic          |
| SSL/TLS            | OpenSSL        | -       | HTTPS support              |

---

## Installation

### Prerequisites

```bash
# System requirements
Python 3.8 or higher
pip (Python package manager)
Git
OpenSSL (for SSL certificates)

# Hardware requirements
CPU: 2+ cores recommended
RAM: 2GB minimum, 4GB recommended
Storage: 500MB for application + logs
Network: Stable internet connection
```

### Quick Setup

```bash
# 1. Clone repository
git clone https://github.com/gahingwoo/ezy_speech_translate.git
cd ezy_speech_translate

# 2. Run automated setup
python setup.py

# The setup script will:
# - Create virtual environment
# - Install dependencies
# - Generate SSL certificates
# - Configure ports and credentials
# - Create necessary directories
```

### Manual Installation

```bash
# 1. Create virtual environment
python -m venv venv

# 2. Activate virtual environment
# Windows
venv\Scripts\activate
# Unix/MacOS
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create directory structure
mkdir -p logs exports data templates static

# 5. Generate SSL certificates (development)
openssl req -x509 -newkey rsa:4096 \
  -keyout key.pem -out cert.pem \
  -days 365 -nodes \
  -subj "/CN=localhost"

# 6. Configure application
cp config.yaml.example config.yaml
# Edit config.yaml with your settings
```

### Dependencies

**Core Dependencies** (`requirements.txt`):

```
PyJWT==2.8.0
cryptography==41.0.7
flask-limiter==3.5.0
flask-talisman==1.1.0
python-dotenv==1.0.0
PyYAML==6.0.1
requests==2.31.0
python-dateutil==2.8.2
psutil==5.9.6
```

**Development Dependencies**:

```bash
pip install pytest pytest-cov black flake8 mypy gunicorn
```

---

## Configuration

### Configuration File (`config.yaml`)

```yaml
# Server Configuration
server:
  host: "0.0.0.0"              # Bind to all interfaces
  port: 1915                    # Main server port
  debug: false                  # Enable debug mode (dev only)
  ssl_cert: "cert.pem"         # SSL certificate path
  ssl_key: "key.pem"           # SSL private key path

admin_server:
  host: "0.0.0.0"
  port: 1916                    # Admin interface port
  debug: false

# Authentication
authentication:
  enabled: true
  admin_username: "admin"
  admin_password: "CHANGE_ME"   # CHANGE THIS
  session_timeout: 7200         # JWT expiration (seconds)
  jwt_secret: "CHANGE_ME"       # CHANGE THIS
  jwt_algorithm: "HS256"

# Translation
translation:
  default_source: "en"          # Default source language
  default_target: "zh-CN"       # Default target language
  cache_size: 1000              # Translation cache size
  timeout: 30                   # Translation request timeout

# Logging
logging:
  level: "INFO"                 # DEBUG, INFO, WARNING, ERROR
  file: "logs/app.log"
  max_bytes: 10485760           # 10MB
  backup_count: 5
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Export
export:
  directory: "exports"
  max_file_size: 52428800       # 50MB
  allowed_formats: ["txt", "json", "srt"]

# WebSocket
websocket:
  ping_interval: 25
  ping_timeout: 60
  cors_allowed_origins: "*"     # Restrict in production

# Security
security:
  max_connections: 100
  rate_limit: "100/hour"
  allowed_origins: ["*"]        # Restrict in production
  require_https: true
```

### Environment Variables

Override config.yaml with environment variables:

```bash
# Server
export SERVER_HOST="0.0.0.0"
export SERVER_PORT="1915"
export ADMIN_PORT="1916"

# Authentication
export ADMIN_USERNAME="admin"
export ADMIN_PASSWORD="secure-password-here"
export JWT_SECRET="random-secret-key-here"

# SSL
export SSL_CERT_PATH="/path/to/cert.pem"
export SSL_KEY_PATH="/path/to/key.pem"

# Logging
export LOG_LEVEL="INFO"
export LOG_FILE="logs/app.log"

# Development
export FLASK_ENV="development"  # or "production"
export FLASK_DEBUG="0"          # 0 or 1
```

### Security Best Practices

**Generate Secure Credentials**:

```python
import secrets

# For JWT secret (64 characters)
jwt_secret = secrets.token_hex(32)
print(f"JWT_SECRET={jwt_secret}")

# For admin password (24 characters, URL-safe)
admin_password = secrets.token_urlsafe(16)
print(f"ADMIN_PASSWORD={admin_password}")
```

**Production Configuration**:

```yaml
authentication:
  admin_password: "USE_GENERATED_PASSWORD"
  jwt_secret: "USE_GENERATED_SECRET"
  session_timeout: 3600  # 1 hour

security:
  allowed_origins: ["https://yourdomain.com"]
  require_https: true
  max_connections: 50
  rate_limit: "50/hour"

websocket:
  cors_allowed_origins: "https://yourdomain.com"
```

---

#### API Documentation

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
  
  ---

## Development

### Project Structure

```
ezy_speech_translate/
├── .gitignore
├── LICENSE
├── README.md
├── requirements.txt
├── setup.py
├── app/
│   ├── admin/
│   │   └── server.py
│   ├── user/
│   │   └── server.py
│   ├── static/
│   │   ├── css/
│   │   └── js/
│   └── templates/
│       ├── admin.html
│       ├── login.html
│       └── user.html
├── config/
│   ├── config.yaml
│   ├── secrets.enc
│   └── ssl/
├── scripts
│   └── tests/
│       └── test_system.py
├── data/
├── exports/
├── logs/
└── venv/                   # Keep only active venv
```

### Running in Development Mode

```bash
# Terminal 1: Main server
export FLASK_ENV=development
export FLASK_DEBUG=1
python user/server.py

# Terminal 2: Admin interface
export FLASK_ENV=development
export FLASK_DEBUG=1
python admin/server.py
```

### Testing

```bash
# Install test dependencies
pip install pytest pytest-cov pytest-mock

# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test file
pytest tests/test_api.py

# Run with verbose output
pytest -v
```

**Example Test**:

```python
# tests/test_api.py
import pytest
from user/server import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_health_endpoint(client):
    response = client.get('/api/health')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'healthy'

def test_login(client):
    response = client.post('/api/login', json={
        'username': 'admin',
        'password': 'test_password'
    })
    assert response.status_code == 200
    data = response.get_json()
    assert 'token' in data
```

### Code Style

**Use Black for formatting**:

```bash
black *.py
```

**Lint with flake8**:

```bash
flake8 *.py --max-line-length=88
```

**Type checking with mypy**:

```bash
mypy *.py --ignore-missing-imports
```

---

## Production Deployment

### SSL Certificates

**Generate Self-Signed (Development)**:

```bash
openssl req -x509 -newkey rsa:4096 \
  -keyout key.pem -out cert.pem \
  -days 365 -nodes \
  -subj "/CN=localhost"
```

**Use Let's Encrypt (Production)**:

```bash
# Install certbot
sudo apt-get install certbot

# Generate certificate
sudo certbot certonly --standalone -d yourdomain.com

# Certificates location
# /etc/letsencrypt/live/yourdomain.com/fullchain.pem
# /etc/letsencrypt/live/yourdomain.com/privkey.pem

# Update config.yaml
ssl_cert: "/etc/letsencrypt/live/yourdomain.com/fullchain.pem"
ssl_key: "/etc/letsencrypt/live/yourdomain.com/privkey.pem"
```

### Firewall Configuration

```bash
# UFW (Ubuntu/Debian)
sudo ufw allow 1915/tcp comment 'EzyTranslate Main'
sudo ufw allow 1916/tcp comment 'EzyTranslate Admin'
sudo ufw enable

# firewalld (CentOS/RHEL)
sudo firewall-cmd --permanent --add-port=1915/tcp
sudo firewall-cmd --permanent --add-port=1916/tcp
sudo firewall-cmd --reload

# iptables
sudo iptables -A INPUT -p tcp --dport 1915 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 1916 -j ACCEPT
sudo iptables-save
```

### Reverse Proxy (Nginx)

```nginx
# /etc/nginx/sites-available/ezytranslate

# Main server
upstream ezytranslate_main {
    server 127.0.0.1:1915;
}

# Admin interface
upstream ezytranslate_admin {
    server 127.0.0.1:1916;
}

# Main server configuration
server {
    listen 80;
    server_name translate.yourdomain.com;

    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name translate.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    # SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Proxy to main server
    location / {
        proxy_pass https://ezytranslate_main;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket support
    location /socket.io/ {
        proxy_pass https://ezytranslate_main;
        proxy_http_version 1.1;
        proxy_buffering off;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
        proxy_set_header Host $host;
    }
}

# Admin interface configuration
server {
    listen 443 ssl http2;
    server_name admin.translate.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    # SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # IP whitelist (optional)
    # allow 192.168.1.0/24;
    # deny all;

    # Proxy to admin server
    location / {
        proxy_pass https://ezytranslate_admin;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location /socket.io/ {
        proxy_pass https://ezytranslate_admin;
        proxy_http_version 1.1;
        proxy_buffering off;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
    }
}
```

**Enable configuration**:

```bash
sudo ln -s /etc/nginx/sites-available/ezytranslate /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### Systemd Services

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
ExecStart=/path/to/venv/bin/python /path/to/user/server.py
Restart=always

[Install]
WantedBy=multi-user.target
```

**Admin Server Service** (`/etc/systemd/system/ezyspeech-admin.service`):

```ini
[Unit]
Description=EzySpeechTranslate Admin Interface
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/ezy_speech_translate
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/python /path/to/admin/server.py
Restart=always

[Install]
WantedBy=multi-user.target
```

**Service Management**:

```bash
# Create dedicated user if need max security
sudo useradd -r -s /bin/false ezyspeech

# Set permissions
sudo chown -R ezyspeech:ezyspeech /opt/ezy_speech_translate
sudo chmod 750 /opt/ezy_speech_translate

# Enable services
sudo systemctl daemon-reload
sudo systemctl enable ezyspeech-main ezyspeech-admin
sudo systemctl start ezyspeech-main ezyspeech-admin

# Check status
sudo systemctl status ezyspeech-main
sudo systemctl status ezyspeech-admin

# View logs
sudo journalctl -u ezyspeech-main -f
sudo journalctl -u ezyspeech-admin -f
```

### Using Gunicorn (Alternative)

```bash
# Install gunicorn
pip install gunicorn[eventlet]

# Run with gunicorn
gunicorn --worker-class eventlet \
  --workers 1 \
  --bind 0.0.0.0:1915 \
  --certfile=cert.pem \
  --keyfile=key.pem \
  --access-logfile logs/access.log \
  --error-logfile logs/error.log \
  --log-level info \
  user/server:app
```

**Gunicorn systemd service**:

```ini
[Service]
ExecStart=/opt/ezy_speech_translate/venv/bin/gunicorn \
  --worker-class eventlet \
  --workers 1 \
  --bind 0.0.0.0:1915 \
  --certfile=/opt/ezy_speech_translate/cert.pem \
  --keyfile=/opt/ezy_speech_translate/key.pem \
  user/server:app
```

### Docker Deployment

**Dockerfile**:

```dockerfile
FROM python:3.10-slim

# Install dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create necessary directories
RUN mkdir -p logs exports data

# Expose ports
EXPOSE 1915 1916

# Run application
CMD ["python", "user/server.py"]
```

**docker-compose.yml**:

```yaml
version: '3.8'

services:
  main-server:
    build: .
    container_name: ezyspeech-main
    ports:
      - "1915:1915"
    volumes:
      - ./logs:/app/logs
      - ./exports:/app/exports
      - ./config.yaml:/app/config.yaml
      - ./cert.pem:/app/cert.pem
      - ./key.pem:/app/key.pem
    environment:
      - FLASK_ENV=production
      - PYTHONUNBUFFERED=1
    restart: unless-stopped
    networks:
      - ezyspeech

  admin-server:
    build: .
    container_name: ezyspeech-admin
    command: python admin_server.py
    ports:
      - "1916:1916"
    volumes:
      - ./logs:/app/logs
      - ./config.yaml:/app/config.yaml
      - ./cert.pem:/app/cert.pem
      - ./key.pem:/app/key.pem
    environment:
      - FLASK_ENV=production
      - PYTHONUNBUFFERED=1
    restart: unless-stopped
    networks:
      - ezyspeech

networks:
  ezytranslate:
    driver: bridge
```

**Deploy with Docker**:

```bash
# Build and start
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Rebuild after changes
docker-compose up -d --build
```

---

## Security

### Best Practices

1. **Change Default Credentials**
   
   ```yaml
   authentication:
     admin_username: "custom_admin"
     admin_password: "STRONG_RANDOM_PASSWORD"
     jwt_secret: "LONG_RANDOM_SECRET_KEY"
   ```

2. **Use HTTPS Only**
   
   - Obtain valid SSL certificates
   - Disable HTTP access
   - Set `require_https: true`

3. **Restrict CORS Origins**
   
   ```yaml
   security:
     allowed_origins: ["https://yourdomain.com"]
   websocket:
     cors_allowed_origins: "https://yourdomain.com"
   ```

4. **Rate Limiting**
   
   ```yaml
   security:
     rate_limit: "100/hour"  # Adjust as needed
     max_connections: 50
   ```

5. **Firewall Rules**
   
   - Only expose necessary ports
   - Restrict admin port to trusted IPs
   - Use IP whitelisting for admin interface

6. **Regular Updates**
   
   ```bash
   # Update dependencies regularly
   pip list --outdated
   pip install -U package_name
   ```

7. **Log Monitoring**
   
   ```bash
   # Monitor logs for suspicious activity
   tail -f logs/app.log | grep -i "error\|fail\|unauthorized"
   ```

### Security Checklist

- [ ] Change default admin password
- [ ] Generate secure JWT secret
- [ ] Use valid SSL certificates (Let's Encrypt)
- [ ] Restrict CORS origins
- [ ] Enable rate limiting
- [ ] Enable SELinux
- [ ] Configure firewall rules
- [ ] Restrict admin port access
- [ ] Regular security updates
- [ ] Monitor logs
- [ ] Backup configuration
- [ ] Document security procedures

---

## Troubleshooting

### Port Already in Use

```bash
# Find process using port
# Linux/Mac
lsof -i :1915
kill -9 <PID>

# Windows
netstat -ano | findstr :1915
taskkill /PID <PID> /F

# Or change port in config.yaml
```

### SSL Certificate Errors

```bash
# Regenerate self-signed certificate
openssl req -x509 -newkey rsa:4096 \
  -keyout key.pem -out cert.pem \
  -days 365 -nodes

# Check certificate validity
openssl x509 -in cert.pem -text -noout

# Verify certificate and key match
openssl x509 -noout -modulus -in cert.pem | openssl md5
openssl rsa -noout -modulus -in key.pem | openssl md5
# Hashes should match
```

### WebSocket Connection Issues

```bash
# Check server logs
tail -f logs/app.log

# Test WebSocket endpoint
curl -i -N -H "Connection: Upgrade" \
  -H "Upgrade: websocket" \
  https://localhost:1915/socket.io/

# Check firewall
sudo ufw status
sudo ufw allow 1915/tcp
```

### Translation Service Failures

```bash
# Test internet connection
ping google.com

# Check translation API
python -c "from googletrans import Translator; t = Translator(); print(t.translate('hello', dest='zh-CN').text)"

# Common issues:
# - Rate limiting (use API key)
# - Network connectivity
# - Proxy configuration
```

### Permission Errors

```bash
# Fix directory permissions
chmod 755 logs exports data
chown -R $USER:$USER logs exports data

# SELinux issues (CentOS/RHEL)
sudo chcon -R -t bin_t venv/bin/
sudo setsebool -P httpd_can_network_connect 1
```

### Memory Issues

```bash
# Check memory usage
free -h
ps aux | grep python

# Limit in systemd service
[Service]
MemoryLimit=512M

# Or use gunicorn with memory limits
gunicorn --max-requests 1000 \
  --max-requests-jitter 50 \
  --worker-class eventlet \
  user/server:app
```

### Log Analysis

```bash
# Error patterns
grep -i "error" logs/app.log | tail -20

# Failed authentication attempts
grep "authentication failed" logs/app.log

# WebSocket disconnections
grep "disconnect" logs/app.log

# Performance issues
grep "timeout\|slow" logs/app.log
```

---

## Contributing

### Development Workflow

1. **Fork the repository**

2. **Create feature branch**
   
   ```bash
   git checkout -b feature/amazing-feature
   ```

3. **Make changes**
   
   - Follow code style guidelines
   - Add tests for new features
   - Update documentation

4. **Test thoroughly**

5. **Commit changes**
   
   ```bash
   git commit -m "Add amazing feature"
   ```

6. **Push to branch**
   
   ```bash
   git push origin feature/amazing-feature
   ```

7. **Create Pull Request**
   
   - Describe changes
   - Reference issues
   - Add screenshots if UI changes

### Code Style Guide

**Python Style**:

- Follow PEP 8
- Use Black for formatting
- Maximum line length: 88 characters
- Use type hints where appropriate

```python
from typing import Dict, List, Optional

def process_translation(
    text: str,
    source_lang: str,
    target_lang: str
) -> Optional[Dict[str, str]]:
    """Process and return translation.

    Args:
        text: Text to translate
        source_lang: Source language code
        target_lang: Target language code

    Returns:
        Translation dict or None if failed
    """
    # Implementation
    pass
```

**JavaScript Style**:

- Use ES6+ features
- Consistent indentation (2 spaces)
- Use const/let, not var
- Add JSDoc comments for functions

```javascript
/**
 * Connect to WebSocket server
 * @param {string} url - Server URL
 * @returns {Socket} Socket instance
 */
function connectWebSocket(url) {
  const socket = io(url, {
    transports: ['websocket'],
    upgrade: false
  });
  return socket;
}
```

### Testing Guidelines

**Unit Tests**:

```python
def test_translation_cache():
    """Test translation caching functionality."""
    cache = TranslationCache(max_size=100)
    cache.set('hello', 'en', 'zh-CN', '你好')
    result = cache.get('hello', 'en', 'zh-CN')
    assert result == '你好'
```

**Integration Tests**:

```python
def test_websocket_broadcast(client, socketio_client):
    """Test WebSocket message broadcasting."""
    # Emit message
    socketio_client.emit('new_transcription', {
        'text': 'Test',
        'language': 'en'
    })
    # Verify broadcast
    received = socketio_client.get_received()
    assert len(received) > 0
```

### Documentation

- Update README for user-facing changes
- Add docstrings to all functions
- Include usage examples
- Update API documentation
- Add inline comments for complex logic

### Issue Reporting

**Bug Report Template**:

```markdown
**Describe the bug**
A clear description of the bug.

**To Reproduce**
Steps to reproduce:
1. Go to '...'
2. Click on '...'
3. See error

**Expected behavior**
What you expected to happen.

**Screenshots**
If applicable, add screenshots.

**Environment:**
- OS: [e.g., Ubuntu 22.04]
- Python version: [e.g., 3.10]
- Browser: [e.g., Chrome 120]

**Additional context**
Any other relevant information.
```

**Feature Request Template**:

```markdown
**Is your feature request related to a problem?**
Describe the problem.

**Describe the solution you'd like**
What you want to happen.

**Describe alternatives you've considered**
Other solutions you've thought about.

**Additional context**
Any other context or screenshots.
```

---

## License

This project is licensed under the MIT License - see [LICENSE](../LICENSE) file for details.

```
MIT License

Copyright (c) 2025 Ga Hing Woo

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## Credits

- **Web Speech API** - Browser-based speech recognition
- **Google Translate** - Translation services
- **Flask** & **SocketIO** - Web framework and real-time communication
- **Contributors** - See [GitHub Contributors](https://github.com/gahingwoo/ezy_speech_translate/graphs/contributors)

---

## Support

- **GitHub Issues**: [Report Issues](https://github.com/gahingwoo/ezy_speech_translate/issues)
- **Documentation**: This README and inline code comments
- **Discussions**: [GitHub Discussions](https://github.com/gahingwoo/ezy_speech_translate/discussions)

---

**Made with ❤️ by [Ga Hing Woo](https://github.com/gahingwoo)**

*Last Updated: December 2025 | Version 3.3.0*
