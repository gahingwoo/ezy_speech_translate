"""
EzySpeechTranslate User Server
Real-time speech recognition and translation system with security hardening

Copyright (C) 2025-2026 Ga Hing Woo (Jiaxing Hu)

This file is part of EzySpeech.

EzySpeech is free software: you can redistribute it and/or modify it under
the terms of the GNU Affero General Public License as published by the Free
Software Foundation, either version 3 of the License, or (at your option)
any later version. Two additional terms apply under section 7: the author
attribution in the about dialog must be preserved, and no trademark rights
are granted. See LICENSE and TRADEMARK.md.

EzySpeech is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE. See the GNU Affero General Public License for more
details.
"""

# Patched before anything else is imported: select first, as the admin server
# explains, then eventlet over the standard library.
import select  # noqa: F401,E402
import eventlet  # noqa: E402
import eventlet.wsgi  # noqa: E402,F401
eventlet.monkey_patch()

import os  # noqa: E402
import sys  # noqa: E402

# The repository root, so `app` imports when this is run as a script
_BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _BASE not in sys.path:
    sys.path.insert(0, _BASE)

# The shared part, then each module adding its routes and events to it.
from app.user.core import *  # noqa: E402,F401,F403
from app.user import routes_pages, routes_translate, routes_admin, sockets, transcripts  # noqa: E402,F401
from app.user.sockets import _heartbeat_cleanup_loop, _translation_health_loop  # noqa: E402

# Connections served at once: listeners, consoles and page loads together
MAX_LISTENER_CONNECTIONS = 10000

# ──────────────────────────────────────────
# Error Handlers
# ──────────────────────────────────────────
# (Its decorator and def were lost in 051c433, which left this return as the
# last line of the WebSocket error handler and unknown paths without a JSON 404.)
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(429)
def ratelimit_handler(e):
    client_key = get_client_key()  # Fixed: use client_key instead of client_ip
    security_logger.warning(f"Rate limit exceeded: {client_key}")
    record_rate_violation(client_key)
    return jsonify({'error': 'Too many requests'}), 429

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal error: {error}")
    return jsonify({'error': 'Internal error'}), 500

# ──────────────────────────────────────────
# Server Start (HTTP or HTTPS)
# ──────────────────────────────────────────
if __name__ == '__main__':
    logger.info("Starting EzySpeechTranslate Backend Server...")

    auth_enabled = get_config('authentication', 'enabled', default=True)
    logger.info(f"Authentication: {'Enabled' if auth_enabled else 'Disabled'}")

    # ── Insecure-default credential check ─────────────────────────
    _INSECURE_DEFAULTS = {
        'jwt_secret':     ('authentication', 'jwt_secret'),
        'secret_key':     ('server', 'secret_key'),
    }
    _BAD_VALUES = {'secret', 'admin123', 'change-this-secret', 'change-this-secret-key', ''}
    for label, cfg_path in _INSECURE_DEFAULTS.items():
        val = get_config(*cfg_path, default='')
        if str(val).strip().lower() in _BAD_VALUES:
            logger.critical(
                "SECURITY WARNING: %s is set to an insecure default value. "
                "Update config/config.yaml before deploying to production!", label
            )

    # A server for the network, by design (bandit B104)
    host = get_config('server', 'host', default='0.0.0.0')  # nosec B104
    port = get_config('server', 'port', default=1915)
    use_https = get_config('server', 'use_https', default=True)

    logger.info(f"Protocol: {'HTTPS' if use_https else 'HTTP'}")
    logger.info(f"Security logging: logs/security.log")

    # ── Feature 12: Init SQLite and load persisted history ────────
    if db is not None:
        db_enabled = get_config('database', 'enabled', default=False)
        db_path    = get_config('database', 'path', default='data/translations.db')
        db.init_db(os.path.join(BASE_DIR, db_path), enabled=db_enabled)
        _seeded = db.seed_default_glossary(os.path.join(BASE_DIR, 'app', 'data', 'default_glossary.json'))
        if _seeded:
            logger.info(f"Default glossary: {_seeded} church terms added (edit them in the console)")
        if db_enabled:
            persisted = db.load_all()
            if persisted:
                # Group by room_id and populate per-room state
                for item in persisted:
                    rid = normalize_room_id(item.get('room_id'))
                    item['room_id'] = rid
                    state = _room(rid)
                    state['history'].append(item)
                # Restore per-room ID counters
                for rid, state in _rooms.items():
                    max_id = max((it.get('id', -1) for it in state['history']), default=-1)
                    state['next_id'] = max(max_id + 1, db.next_id(rid))
                room_summary = ", ".join(
                    f"{rid}={len(state['history'])}" for rid, state in _rooms.items()
                )
                logger.info(f"Restored {len(persisted)} translations from DB – rooms: {room_summary}")

    # Start heartbeat cleanup greenlet
    eventlet.spawn(_heartbeat_cleanup_loop)
    eventlet.spawn(_translation_health_loop)
    logger.info("Heartbeat cleanup greenlet started (timeout=45s, interval=15s)")

    for directory in ['logs']:
        os.makedirs(directory, exist_ok=True)

    # Every listener holds a socket and a green thread for as long as the page
    # is open. systemd gives a service 1024 open files and eventlet serves 1024
    # connections at once unless told otherwise: a ceiling of about a thousand
    # phones, met in the load test. Raised here, for every way of installing.
    try:
        import resource
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        want = MAX_LISTENER_CONNECTIONS + 1024 if hard == resource.RLIM_INFINITY else min(hard, MAX_LISTENER_CONNECTIONS + 1024)
        if soft < want:
            resource.setrlimit(resource.RLIMIT_NOFILE, (want, hard))
    except (ImportError, ValueError, OSError) as exc:
        logger.warning(f"Open-file limit left as it is ({exc})")

    try:
        # A backlog for the moment a restart sends every phone back at once
        listener = eventlet.listen((host, port), backlog=1024)

        if use_https:
            cert_file = os.path.join(SSL_DIR, 'cert.pem')
            key_file = os.path.join(SSL_DIR, 'key.pem')

            if not (os.path.exists(cert_file) and os.path.exists(key_file)):
                logger.error("SSL certificate or key not found!")
                print(f"\nGenerate SSL certificates with:\n")
                print(f"  cd {SSL_DIR}")
                print("  openssl req -x509 -newkey rsa:2048 -nodes \\")
                print("    -out cert.pem -keyout key.pem -days 365 \\")
                print('    -subj "/CN=localhost"\n')
                exit(1)

            ssl_listener = eventlet.wrap_ssl(
                listener,
                certfile=cert_file,
                keyfile=key_file,
                server_side=True
            )
            logger.info(f"Server running at https://{host}:{port}")
            eventlet.wsgi.server(ssl_listener, app, max_size=MAX_LISTENER_CONNECTIONS)
        else:
            logger.info(f"Server running at http://{host}:{port}")
            eventlet.wsgi.server(listener, app, max_size=MAX_LISTENER_CONNECTIONS)

    except PermissionError:
        logger.error(f"Permission denied on port {port}. Use port > 1024 or run with sudo.")
        exit(1)
    except OSError as e:
        logger.error(f"Failed to bind on port {port}: {e}")
        exit(1)
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
        exit(0)
    except Exception as e:
        logger.error(f"Server failed to start: {e}")
        exit(1)
