"""The listener server: its pages, the history, languages and Scripture.

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

from app.user.core import *  # noqa: F401,F403  (one namespace, split by subject)

# ──────────────────────────────────────────
# Routes with Protection
# ──────────────────────────────────────────
@app.route('/')
@limiter.limit("60 per minute")
@check_client_access
def index():
    """Main client interface"""
    return render_template(
        'user.html',
        bible_detection_enabled=bool(BIBLE_DETECTION_ENABLED and bible_detector is not None),
    )

@app.route('/captions')
@limiter.limit("60 per minute")
@check_client_access
def captions():
    """OBS / streaming overlay — transparent caption renderer.

    Configurable via URL query params (see captions.html header for full list).
    Examples:
        /captions?mode=translated&size=64&pos=bottom
        /captions?mode=both&color=ffff00&strokew=6
    """
    return render_template('captions.html')

@app.route('/projection')
@limiter.limit("60 per minute")
@check_client_access
def projection():
    """The screen at the front of the room.

    Read-only, and outside the app shell: no masthead, no sidebar, nothing to
    press. It follows one room's feed and shows the line being said now with
    the two before it.

    Query params (read by projection.js, not here):
        /projection?room=main&lang=yue&join=ezyspeech.mabc.qzz.io
    """
    return render_template('projection.html')

@app.route('/admin')
def admin_route():
    """Admin interface route"""
    return jsonify({'message': 'Use admin_server.py for admin interface'}), 404

@app.route('/api/login', methods=['POST'])
@limiter.limit("5 per minute")
@check_client_access
def login():
    """Admin login with brute force protection"""
    client_key = get_client_key()

    try:
        data = request.json or {}
    except Exception:
        security_logger.warning(f"Malformed JSON from {client_key}")
        return jsonify({'success': False, 'error': 'Invalid request'}), 400

    username = sanitize_text(data.get('username', ''), max_length=100)
    # Accept client-side pre-hashed password (SHA-256 hex) only
    password_hash = data.get('password_hash', '')

    if not username or not password_hash or len(password_hash) != 64:
        return jsonify({'success': False, 'error': 'Missing credentials'}), 400

    # Rate limiting check
    if len(username) > 100:
        record_suspicious_activity("Oversized credentials", client_key)
        return jsonify({'success': False, 'error': 'Invalid credentials'}), 400

    # Verify credentials against multi-account table: the browser sends
    # sha256(password), checked against the account's PBKDF2 verifier.
    account = _accounts.get(username)

    if account and _verify_password(password_hash, account['verifier']):
        acct_role    = account.get('role', 'operator')
        acct_channel = account.get('channel', 'main')
        acct_display = account.get('display_name', username)

        # Generate secure token
        token = jwt.encode(
            {
                'username': username,
                'role':     acct_role,
                'channel':  acct_channel,
                'display_name': acct_display,
                'exp': datetime.utcnow() + timedelta(
                    seconds=get_config('authentication', 'session_timeout', default=7200)
                ),
                'iat': datetime.utcnow(),
                'jti': secrets.token_hex(16)
            },
            JWT_SECRET,
            algorithm='HS256'
        )

        logger.info(f"Login successful: {username} ({acct_role}/{acct_channel}) from {client_key}")
        return jsonify({
            'success':      True,
            'token':        token,
            'username':     username,
            'role':         acct_role,
            'channel':      acct_channel,
            'display_name': acct_display,
        })

    # Failed login
    logger.warning(f"Failed login attempt: {username} from {client_key}")
    if record_failed_login(client_key):
        return jsonify({'success': False, 'error': 'Too many failed attempts. Session blocked.'}), 403

    return jsonify({'success': False, 'error': 'Invalid credentials'}), 401

@app.route('/api/config', methods=['GET'])
@limiter.limit("30 per minute")
@require_auth
@check_client_access
def get_runtime_config():
    """Get current configuration (filtered)"""
    # Only return non-sensitive config
    return jsonify({
        'audio': {
            'sample_rate': get_config('audio', 'sample_rate'),
            'channels': get_config('audio', 'channels')
        },
        'mainServerPort': get_config('server', 'port', default=1915)
    })

@app.route('/api/oem-config', methods=['GET'])
@limiter.limit("60 per minute")
@check_client_access
def get_oem_config():
    """Get OEM configuration for frontend"""
    return jsonify(app.config.get('OEM', {}))

@app.route('/api/features', methods=['GET'])
@limiter.limit("60 per minute")
def get_features():
    """Expose feature flags the client cares about.

    Used by user.js to decide whether to render optional UI like the
    Bible verse panel toggle. Public endpoint — only returns booleans
    plus inert config (translation id), no secrets.
    """
    return jsonify({
        'bible_detection': {
            'enabled': bool(BIBLE_DETECTION_ENABLED and bible_detector is not None),
            'source_translation': S.BIBLE_SOURCE_TRANSLATION,
            'target_translation': BIBLE_TARGET_TRANSLATION,
        },
    })

_VALID_TRANS_RE = re.compile(r'^[A-Za-z0-9_-]{1,20}$')

@app.route('/api/bible/lookup', methods=['POST'])
@limiter.limit("120 per minute")
def bible_lookup():
    """Fetch verse text from PrayerPulse API for a list of refs.

    Body (JSON):
      {
        "refs": [{book, chapter, verse_start, verse_end, display}, ...],
        "source_translation": "WEB",   // bolls.life translation code
        "target_translation": "CUV"    // optional; "" to disable
      }

    Returns the same list with source/target verse text attached.
    Results are cached server-side so repeated requests are cheap.
    """
    if bible_detector is None:
        return jsonify({'error': 'Bible detection not enabled'}), 404

    payload = request.get_json(silent=True) or {}
    refs = payload.get('refs')
    if not refs or not isinstance(refs, list) or len(refs) > 20:
        return jsonify({'error': 'refs must be a list of 1-20 items'}), 400

    src = str(payload.get('source_translation') or S.BIBLE_SOURCE_TRANSLATION)[:20]
    tgt = str(payload.get('target_translation', BIBLE_TARGET_TRANSLATION) or '')[:20]

    # Validate translation codes (alphanumeric + dash/underscore)
    if not _VALID_TRANS_RE.match(src):
        return jsonify({'error': 'invalid source_translation'}), 400
    if tgt and not _VALID_TRANS_RE.match(tgt):
        return jsonify({'error': 'invalid target_translation'}), 400

    # Allow only the expected keys in each ref to prevent injection
    clean_refs = []
    for r in refs:
        if not isinstance(r, dict):
            continue
        book = r.get('book', '')
        chapter = r.get('chapter')
        if not isinstance(book, str) or not isinstance(chapter, int):
            continue
        clean_refs.append({
            'book': book[:50],
            'chapter': int(chapter),
            'verse_start': int(r['verse_start']) if isinstance(r.get('verse_start'), int) else None,
            'verse_end':   int(r['verse_end'])   if isinstance(r.get('verse_end'), int)   else None,
            'display': str(r.get('display', ''))[:80],
        })

    if not clean_refs:
        return jsonify([])

    try:
        results = bible_detector.lookup(clean_refs, source_translation=src, target_translation=tgt)
        return jsonify(results)
    except Exception as e:
        logger.warning(f"bible_lookup endpoint failed: {e}")
        return jsonify({'error': 'lookup failed'}), 500


# ── In-process cache for the language list (large, rarely changes) ──
S._bible_languages_cache: list = []
S._bible_languages_cached_at: float = 0.0
_BIBLE_LANGUAGES_TTL = 3600  # re-fetch once per hour

@app.route('/api/bible/languages', methods=['GET'])
@limiter.limit("20 per minute")
def bible_languages():
    """Return available Bible translations grouped by language from PrayerPulse API.

    Proxied and cached server-side (1-hour TTL) so the browser never has
    to hit an external host directly.  Shape:
      [{"language": "English", "translations": [{"short_name": "KJV", "full_name": "..."}, ...]}, ...]
    """
    import time as _time
    if bible_detector is None:
        return jsonify([]), 404
    now = _time.time()
    if not S._bible_languages_cache or (now - S._bible_languages_cached_at) > _BIBLE_LANGUAGES_TTL:
        data = bible_detector.fetch_languages()
        if data:
            S._bible_languages_cache = data
            S._bible_languages_cached_at = now
    return jsonify(S._bible_languages_cache)


@app.route('/api/bible/source-translation', methods=['GET'])
@limiter.limit("30 per minute")
def bible_source_translation_get():
    """Return the currently configured Bible source translation."""
    return jsonify({'source_translation': S.BIBLE_SOURCE_TRANSLATION})


@app.route('/api/bible/source-translation', methods=['POST'])
@limiter.limit("30 per minute")
@require_admin_auth
def bible_source_translation_post():
    """Update the Bible source translation live (admin only).

    POST body: {"source_translation": "KJV"}
    """

    payload = request.get_json(silent=True) or {}
    new_src = str(payload.get('source_translation') or '')[:20].strip()
    if not new_src or not _VALID_TRANS_RE.match(new_src):
        return jsonify({'error': 'invalid source_translation'}), 400

    S.BIBLE_SOURCE_TRANSLATION = new_src
    if bible_detector is not None:
        bible_detector.init(
            source_translation=S.BIBLE_SOURCE_TRANSLATION,
            target_translation=BIBLE_TARGET_TRANSLATION,
        )
    username = (request.user.get('username') if hasattr(request, 'user') else None) or 'admin'
    logger.info("%s updated source translation to: %s", username, S.BIBLE_SOURCE_TRANSLATION)
    return jsonify({'source_translation': S.BIBLE_SOURCE_TRANSLATION, 'updated': True})


# How surely a passage was found, strongest first. A passage that comes up
# twice is listed once, as the strongest of the ways it was found.
_MATCH_STRENGTH = {'reference': 4, 'wording': 3, 'cited': 2, 'offer': 1}


def _passage_key(ref: dict) -> str:
    """The passage itself, not the words it was found by: John 3:16 cited
    and John 3:16 recognised from its wording are one passage."""
    if ref.get('book'):
        return '|'.join(str(ref.get(k) if ref.get(k) is not None else '')
                        for k in ('book', 'chapter', 'verse_start', 'verse_end'))
    return str(ref.get('display') or '')


@app.route('/api/scripture', methods=['GET'])
@limiter.limit("60 per minute")
@require_api_token
def get_scripture():
    """Every passage this room's service has been through, once each.

    The listener's Scripture section used to be filled only by the lines it
    had loaded, which is the newest thirty: a passage read before them was
    missing from the one place meant to gather them all. This is the whole
    record, oldest first, each passage with every time it came up and the
    strongest way it was found.
    """
    room_id = normalize_room_id(request.args.get('room'))
    passages = {}
    for item in _room(room_id)['history']:
        for ref in item.get('bible_refs') or []:
            if not isinstance(ref, dict) or not ref.get('display'):
                continue
            ref = dict(ref, match=ref.get('match') or 'reference')
            key = _passage_key(ref)
            entry = passages.get(key)
            if entry is None:
                entry = passages[key] = dict(ref, times=[], ids=[])
            elif _MATCH_STRENGTH.get(ref['match'], 0) > _MATCH_STRENGTH.get(entry['match'], 0):
                entry.update({k: v for k, v in ref.items()})
            if item.get('timestamp') and item['timestamp'] not in entry['times']:
                entry['times'].append(item['timestamp'])
            entry['ids'].append(item.get('id'))
    return jsonify({'success': True, 'room_id': room_id, 'passages': list(passages.values())})


@app.route('/api/translations', methods=['GET'])
@limiter.limit("120 per minute")
@require_api_token
def get_translations():
    """
    Get translation history with pagination support
    
    Query parameters:
        offset (int): Starting index (default 0)
        limit (int): Number of items to return (default 100, max 1000)
    
    Response:
        {
            'translations': [...],
            'offset': 0,
            'limit': 100,
            'total': 1234,
            'has_more': true
        }
    """
    try:
        offset = int(request.args.get('offset', 0))
        limit = int(request.args.get('limit', 100))
    except (ValueError, TypeError):
        offset = 0
        limit = 100

    room_id = normalize_room_id(request.args.get('room'))
    history = _room(room_id)['history']

    # Validate parameters
    offset = max(0, min(offset, len(history)))
    limit = max(1, min(limit, 1000))  # Max 1000 items per request

    total = len(history)

    # Get slice of translations (newest first)
    start = max(0, total - offset - limit)
    end = max(0, total - offset)
    translations_slice = history[start:end]
    translations_slice = list(reversed(translations_slice))

    has_more = (offset + limit) < total

    return jsonify({
        'translations': translations_slice,
        'room_id': room_id,
        'offset': offset,
        'limit': limit,
        'total': total,
        'has_more': has_more
    })

@app.route('/api/translations/<int:translation_id>/translated', methods=['PATCH'])
@limiter.limit("300 per minute")
@require_api_token
def save_translated(translation_id):
    """
    Cache a client-side translation result back to the server so future clients
    skip the translate call for this item.

    Body: { "translated": "...", "lang": "zh" }
    """
    data = request.get_json(silent=True) or {}
    translated = data.get('translated', '').strip()
    lang = data.get('lang', '').strip()

    if not translated or not lang or len(translated) > 4000:
        return jsonify({'success': False, 'error': 'invalid'}), 400

    room_id = normalize_room_id(request.args.get('room') or (request.get_json(silent=True) or {}).get('room'))
    history = _room(room_id)['history']

    # Update in-memory history (scoped to room)
    for item in history:
        if item.get('id') == translation_id:
            if item.get('translated_lang') != lang:
                item['translated'] = translated
                item['translated_lang'] = lang
            break

    # Persist to DB
    if db is not None:
        db.update_translated(room_id, translation_id, translated, lang)

    return jsonify({'success': True})

@app.route('/api/translations/clear', methods=['POST'])
@limiter.limit("10 per minute")
@require_auth
@check_client_access
def clear_translations():
    """Clear translation history for the specified room (default room if omitted)."""
    room_id = normalize_room_id(request.args.get('room') or
                                (request.get_json(silent=True) or {}).get('room'))
    state = _room(room_id)
    state['history'].clear()
    # As the console's clear: off the screens, kept for the transcript.
    if db is not None:
        db.clear_live(room_id)
    socketio.emit('history_cleared', {'room_id': room_id}, room=f'room:{room_id}')
    socketio.emit('history_cleared', {'room_id': room_id}, room=f'admin:{room_id}')
    logger.info(f"Translation history cleared for room '{room_id}' by {request.user.get('username')}")
    return jsonify({'success': True, 'room_id': room_id})

@app.route('/favicon.ico', methods=['GET'])
def favicon():
    """The tab icon.

    This used to answer 204 to keep 404s out of the log, which worked and left
    every page in the app without an icon, the projection screen included.
    A configured file is redirected to; otherwise the brand icon is drawn, so a
    tab has something in it out of the box.
    """
    kind, value = favicon_from_oem(app.config.get('OEM'))
    if kind == 'path':
        return redirect(value, code=302)
    return Response(value, mimetype='image/svg+xml',
                    headers={'Cache-Control': 'public, max-age=86400'})

@app.route('/api/health', methods=['GET'])
@limiter.limit("120 per minute")
def health_check():
    """Health check endpoint. Accepts optional ?room= for room-scoped counts."""
    room_param = request.args.get('room')
    if room_param:
        room_id = normalize_room_id(room_param)
        room_state = _room(room_id)
        clients = len(room_state['listeners'])
        translations = len(room_state['history'])
    else:
        room_id = None
        clients = _all_listener_count()
        translations = _all_history_count()
    return jsonify({
        'status': 'healthy',
        'version': APP_VERSION,
        'timestamp': datetime.utcnow().isoformat(),
        'clients': clients,
        'peak_clients': S._peak_clients,
        'translations': translations,
        'rooms': len(_rooms),
        'room_id': room_id,
        'translation': get_translation_service().health_summary()['state'],
    })

@app.route('/api/history', methods=['GET'])
@limiter.limit("60 per minute")
@require_auth
def get_history():
    """Get all transcription history for the given room (default room if omitted)."""
    room_id = normalize_room_id(request.args.get('room'))
    history = _room(room_id)['history']
    return jsonify({
        'success': True,
        'room_id': room_id,
        'translations': history,
        'count': len(history),
    })
