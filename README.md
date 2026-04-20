# Project Documentation

## 1. Overview

EzySpeechTranslate is a two-server web system for live speech transcription and multilingual translation during events.

It solves a practical gap: one operator can speak and correct text in real time, while many viewers follow in their own language with optional text-to-speech playback.

Core features implemented in code:
- Live admin speech capture in browser (Web Speech API)
- Real-time interim and final transcript broadcast over Socket.IO
- Admin correction, deletion, import, clear, and export workflows
- Viewer-side translation mode and transcription-only mode
- Server-side translation API with caching and retry logic
- Dual TTS support: browser system voices and Edge TTS via backend
- Session-based and token-based protections, rate limiting, input sanitization, and security logging
- Optional OEM branding from config

Tech stack (from runtime code and dependencies):
- Python 3.8+
- Flask 3, Flask-SocketIO 5, eventlet
- Flask-CORS, Flask-Limiter, Flask-Talisman
- PyJWT
- PyYAML
- requests
- edge-tts
- Frontend: server-rendered HTML + vanilla JavaScript + CSS
- Real-time transport: Socket.IO (WebSocket + polling fallback)
- Translation provider: Google Translate web endpoint (`translate.googleapis.com`)
- Speech recognition: browser Web Speech API (admin client)
- Optional service management: systemd via `ezy_manager.py`

---

## 2. System Architecture

### High-Level Structure

- `app/user/server.py`
  - Primary backend and viewer UI host (default port `1915`)
  - Maintains translation history in memory
  - Exposes translation/TTS/export/history APIs
  - Handles Socket.IO events for viewers and admin-originated transcript actions

- `app/admin/server.py`
  - Admin/login frontend host (default port `1916`)
  - Handles admin session login and admin-facing API endpoints
  - Proxies TTS cache admin actions to user server

- `app/static/js/admin.js`
  - Admin workflow client: microphone capture, interim/final transcript emit, correction, reorder, import/export, health polling

- `app/static/js/user.js`
  - Viewer workflow client: live stream rendering, translation requests, TTS queueing, display/search/export settings

- `app/translation_service.py`
  - Server-side translation service wrapper with cache and retry/backoff

- `secure_loader.py` + `setup.py`
  - Loads and injects secrets from `config/secrets.key` (Fernet-encrypted)
  - Generates initial secrets and optional self-signed SSL certs

- `config/config.yaml`
  - Runtime configuration for ports, HTTPS flags, security limits, CORS, features, OEM branding

### Data/control flow

1. Admin logs in on admin server (`/api/login`) and gets JWT + session cookie.
2. Admin UI connects to user server Socket.IO and emits `admin_connect` with JWT.
3. Admin browser speech recognition produces interim/final transcript payloads.
4. User server validates and broadcasts:
   - interim: `realtime_transcription` (not persisted)
   - final: `new_translation` (persisted in in-memory history)
5. Viewer UI receives events, loads paginated history via `/api/translations` using per-socket API token from `ready` event.
6. Viewer UI requests translation via `/api/translate` and TTS via `/api/tts/synthesize`.
7. Admin corrections and deletions are broadcast to all connected clients.

### Component communication

- Admin server ↔ User server: HTTP calls for TTS cache stats/clear (localhost)
- Admin browser ↔ Admin server: login/session APIs
- Admin browser ↔ User server: Socket.IO for transcript operations and sync
- Viewer browser ↔ User server: Socket.IO + HTTP APIs

### Text diagram

```text
[Admin Browser]
  ├─ HTTP/HTTPS -> [Admin Server :1916]  (login/session, config)
  └─ WS/HTTP -> [User Server :1915] (admin_connect, new_transcription, corrections)

[Viewer Browser]
  └─ WS/HTTP/HTTPS -> [User Server :1915] (ready/api_token, history, translate, TTS, exports)

[User Server]
  ├─ In-memory history + session token maps
  ├─ Google Translate endpoint
  └─ Edge TTS CLI
```

---

## 3. User Perspective (User)

### 3.1 Non-native speakers

- Viewer flow is short: open URL, choose target language, read live cards.
- Language auto-detection is implemented and can be overridden manually.
- Display language and translation language are separate settings, which helps mixed-language audiences.
- UI has direct labels and live status badges (online/offline/waiting).

Potential barriers:
- Translation quality depends on source transcript quality and external translation availability.
- Some status/error strings are still English-only in UI logic.
- Recommended follow-up: add a localization backlog item to move hardcoded status/error text into the shared i18n map.

### 3.2 Users with disabilities

Current support in templates/UI:
- `aria-label`, `role`, and `aria-live` are used in multiple controls and status areas.
- Keyboard shortcuts exist (for example: `Esc`, admin `Ctrl/Cmd+R`, `Ctrl/Cmd+S`).
- Font size, theme toggle, and TTS controls help readability and auditory access.

Gaps:
- No dedicated focus-management workflow for modal dialogs.
- Drag-and-drop reorder is feature-rich but not fully keyboard-equivalent.
- Screen-reader behavior is not validated by automated accessibility tests.

### 3.3 Native speakers

- Fast operator workflow: continuous recognition with auto-restart and interim streaming.
- Power features: bulk import/delete, reorder, correction broadcast, multi-format export.
- Viewer customization: display mode, source-text visibility, search, font size, theme, TTS engine/voice/rate/volume.

### 3.4 Common workflows

1. **Admin live session**
   - Log in at `/login` (admin server)
   - Select source language and start recording
   - Speech results stream to viewers
   - Correct items as needed
   - Export transcript data

2. **Viewer follow-along**
   - Open user URL `/`
   - Wait for connection (`ready` event + history load)
   - Select display/target language
   - Optionally enable TTS
   - Download local export from viewer UI

Common errors and resolution:
- Microphone denied: browser permission and HTTPS/browser compatibility checks
- No live updates: verify user server availability and WebSocket connection state
- TTS edge failures: retry after voices load, check rate limits or backend availability
- Missing translations: fallback behavior may show source text if translation fails

---

## 4. Administrator Perspective (Admin)

### Deployment steps

Two deployment paths exist in repo:
- `python3 setup.py` (local setup helper, secrets + venv + optional SSL)
- `sudo python3 ezy_manager.py install` (Linux systemd deployment to `/opt/ezy_speech_translate`)

`ezy_manager.py install` performs:
- OS/package checks
- service user creation (`ezyspeech`)
- app deployment to `/opt/ezy_speech_translate`
- virtualenv + dependency install
- systemd unit install (`ezyspeech-user.service`, `ezyspeech-admin.service`)

### Configuration

Primary file: `config/config.yaml`
Key sections used by runtime:
- `server.*`, `admin_server.*`
- `authentication.*`
- `advanced.websocket.*`, `advanced.security.*`, `advanced.performance.*`
- `logging.*`
- `oem.*`
- `features.*`

Secrets flow:
- Encrypted secrets in `config/secrets.key`
- Loaded by `secure_loader.py` into runtime config

### Start/stop services

Using manager CLI:
- `sudo python3 ezy_manager.py manage start`
- `sudo python3 ezy_manager.py manage stop`
- `sudo python3 ezy_manager.py manage restart`
- `python3 ezy_manager.py manage status`
- `python3 ezy_manager.py manage logs:user -f`
- `python3 ezy_manager.py manage logs:admin -f`

Manual (development):
- `python app/user/server.py`
- `python app/admin/server.py`

### Logging and monitoring

- Main logs: `logs/app.log` (rotating handler)
- Security logs: `logs/security.log`
- Default app log rotation (from `config/config.yaml`): `max_bytes=10485760` (10MB), `backup_count=5`.
- Health endpoints:
  - user server: `GET /api/health`
  - admin server: `GET /health`
- Admin UI polls user health (`/api/health`) and shows client/translation counts.

### Debugging and troubleshooting

- Verify login/session path on admin server (`/api/login`).
- Verify admin-to-user connectivity (`/api/config` on admin gives user URL).
- Check TTS cache endpoints from admin (`/api/tts/cache-stats`, `/api/tts/cache-clear`).
- Check browser console for Socket.IO reconnect/auth failures.

### Security considerations and permissions

Implemented controls:
- JWT validation for protected endpoints
- Session auth on admin panel
- Request size limits and sanitization
- Client/session-based blocking and rate-limit escalation
- CSP and security headers
- Optional HTTPS with cert files under `config/ssl`

Operational cautions:
- `config/secrets.key` is sensitive and machine-local.
- Debug endpoints exist in admin server (`/api/debug/*`) and must be removed or fully disabled in production deployments.

---

## 5. Developer Perspective (Developer)

### 5.1 Code Structure

- `app/user/server.py`: core backend + viewer APIs + websocket event hub
- `app/admin/server.py`: admin auth/frontend host + selected admin APIs
- `app/static/js/user.js`: viewer state machine, pagination, translation/TTS pipelines
- `app/static/js/admin.js`: operator workflow and microphone recognition handling
- `app/templates/*.html`: login/admin/user pages
- `app/translation_service.py`: translation API wrapper
- `app/oem_manager.py`: brand config composition
- `secure_loader.py`: encrypted secret loading/migration
- `setup.py`, `update.py`, `ezy_manager.py`: ops lifecycle scripts

### 5.2 Core Logic

- Real-time channel is Socket.IO; persistence is in-memory list (`translations_history`).
- Translation items are ID-based and broadcast to all listeners.
- Viewer history loading uses tokenized paginated HTTP API (`/api/translations`).
- Viewer translation path:
  1) server `/api/translate`
  2) client-side fallback logic if needed
- Viewer TTS path:
  - system speech synthesis, or
  - backend Edge TTS synthesis endpoint returning `audio/mpeg`

### 5.3 Key Design Decisions

- **Two-server split**: admin UI and user backend are separated by port/process.
  - Trade-off: cleaner role boundary, but more cross-service config complexity.
- **In-memory history**: simple and fast.
  - Trade-off: no persistence across restarts.
- **Browser speech recognition**: avoids server ASR dependencies.
  - Trade-off: browser compatibility and permission constraints.
- **Socket + paginated HTTP hybrid**: avoids sending full history over websocket.
  - Trade-off: token/session lifecycle coordination is required.

### 5.4 Issues and Improvements

Observed weak points from current code:
- `app/static/js/user.js` is very large and contains duplicate/redefined functions, increasing maintenance risk.
  - Recommended follow-up: split this file by concern (socket lifecycle, translation pipeline, TTS, rendering) and deduplicate shared helpers.
- `app/admin/server.py` uses broad CORS and includes debug endpoints that should be gated or removed in hardened deployments.
  - Recommended follow-up: disable `/api/debug/*` by default and expose only behind an explicit development-only config flag.
- Admin and user auth models are mixed (session + JWT + API token), which increases complexity.
- Translation history is memory-only; restart loses state.
- Some UI behavior and language strings are inconsistent between templates and JS.

---

## 6. API / Interfaces

### HTTP APIs (selected)

User server (`app/user/server.py`):
- `POST /api/login` -> admin JWT (for user-server protected endpoints)
- `GET /api/config` -> runtime config (auth required)
- `GET /api/oem-config` -> OEM payload
- `GET /api/health` -> service health
- `GET /api/history` -> full history (auth required)
- `GET /api/translations?offset=&limit=&api_token=` -> paginated history
- `POST /api/translations/clear` -> clear history (auth required)
- `GET /api/export/<json|txt|csv|srt>` -> transcript export (auth required)
- `POST /api/translate` -> single translation
- `POST /api/translate/batch` -> batch translation
- `POST /api/translate/cache` -> clear translation cache (auth required)
- `POST /api/tts/synthesize` -> MP3 audio bytes (API token required)
- `GET /api/tts/voices?lang=` -> Edge TTS voices
- `GET /api/tts/supported-languages`
- `GET /api/tts/cache-stats`
- `POST /api/tts/cache-clear`

Admin server (`app/admin/server.py`):
- `POST /api/login` -> admin session + JWT
- `POST /api/logout`
- `GET /api/config` -> user server URL info
- `GET /api/oem-config`
- `GET /api/tts/cache-stats` -> proxied admin cache stats
- `POST /api/tts/cache-clear` -> proxied admin cache clear
- `GET /health`

### Socket.IO events (user server)

Inbound:
- `admin_connect`
- `new_transcription`
- `correct_translation`
- `clear_history`
- `import_transcription`
- `delete_items`

Outbound:
- `ready` (contains `api_token`)
- `realtime_transcription`
- `new_translation`
- `transcription_confirmed`
- `translation_corrected`
- `history_cleared`
- `items_deleted`

---

## 7. Usage Examples

### Minimal local run (development)

```bash
cd ezy_speech_translate
python3 setup.py
python3 app/user/server.py
python3 app/admin/server.py
```

Run the two server commands in separate terminals (or run one in background) so both services stay available.

Open:
- Viewer: `http(s)://localhost:1915/`
- Admin login: `http(s)://localhost:1916/login`

### Translation API request

```bash
curl -X POST http://localhost:1915/api/translate \
  -H 'Content-Type: application/json' \
  -d '{"text":"Hello world","target_lang":"zh"}'
```

### Service operations (Linux/systemd path)

```bash
sudo python3 ezy_manager.py manage start
python3 ezy_manager.py manage status
python3 ezy_manager.py manage logs:user -f
```

---

## 8. Appendix

### Dependencies

Runtime dependencies are declared in `requirements.txt`.
Primary production dependencies include Flask, Flask-SocketIO, eventlet, Flask-Limiter, Flask-Talisman, PyJWT, PyYAML, requests, edge-tts, and gunicorn.

### Build / setup process

No compile/build step is defined.
Project lifecycle is script-driven:
- `setup.py` for local bootstrap and secret generation
- `ezy_manager.py` for install/manage/setup/uninstall on Linux
- `update.py` for pull-and-restore update flow in deployed environments

### Version notes

UI and legacy docs reference version `3.3.0`.
There is no single canonical version constant in runtime code; the value is repeated in documentation/template text.
No formal changelog file is present; commit history is the source of change detail.
