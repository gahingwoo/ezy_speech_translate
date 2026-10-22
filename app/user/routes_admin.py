"""The listener server, for the console: session figures, rooms, the glossary,
the recording lock, and config.yaml.

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
# Feature 9: Session Analytics API
# ──────────────────────────────────────────
@app.route('/api/analytics', methods=['GET'])
@limiter.limit("30 per minute")
@require_auth
def get_analytics():
    """Return per-session statistics for the admin dashboard."""
    now = datetime.now()
    elapsed = now - S._session_start_time
    elapsed_sec = int(elapsed.total_seconds())
    hours, rem = divmod(elapsed_sec, 3600)
    minutes, seconds = divmod(rem, 60)
    duration_str = f"{hours}h {minutes}m {seconds}s" if hours else f"{minutes}m {seconds}s"

    db_stats = db.get_stats() if db is not None else {'enabled': False, 'count': 0}

    return jsonify({
        'session_start':    S._session_start_time.isoformat(),
        'duration_seconds': elapsed_sec,
        'duration_display': duration_str,
        'current_clients':  _all_listener_count(),
        'peak_clients':     S._peak_clients,
        # This is the card headed "This service", so it is this service:
        # the lifetime row count sat in the same column as a word count
        # that resets on restart, and the two disagreed by hundreds.
        'total_transcriptions': S._session_lines,
        'all_time_transcriptions': _all_history_count(),
        'total_words':      S._total_words,
        'total_bible_refs': S._total_bible_refs,
        'total_translations': S._total_translations,
        'db':               db_stats,
        'rooms': [
            {
                'room_id': rid,
                'display_name': st['display_name'],
                'listeners': len(st['listeners']),
                'history': len(st['history']),
            }
            for rid, st in _rooms.items()
        ],
    })

@app.route('/api/analytics/reset', methods=['POST'])
@limiter.limit("5 per minute")
@require_admin_auth
def reset_analytics():
    """Reset session analytics counters (admin only)."""
    S._session_start_time = datetime.now()
    S._peak_clients = _all_listener_count()
    S._total_words = 0
    S._session_lines = 0
    S._total_bible_refs = 0
    S._total_translations = 0
    logger.info("Session analytics reset by %s", getattr(request, 'user', {}).get('username', 'unknown'))
    return jsonify({'success': True, 'reset_at': S._session_start_time.isoformat()})

@app.route('/api/export/<export_format>', methods=['GET'])
@limiter.limit("10 per minute")
@require_auth
@check_client_access
def export_translations(export_format):
    """Export translations with validation"""
    allowed_formats = ['json', 'txt', 'csv', 'srt']

    if export_format not in allowed_formats:
        return jsonify({'error': f'Unsupported format'}), 400

    # Limit export size (scoped to the requested room, default room if omitted)
    room_id = normalize_room_id(request.args.get('room'))
    max_export = 5000
    export_data = _room(room_id)['history'][-max_export:]

    # The console can export the lines the operator ticked rather than the
    # whole service. Filtering here rather than in the browser keeps one
    # implementation of each format; an id that is not in this room is simply
    # not found, which is also the access check.
    wanted = (request.args.get('ids') or '').strip()
    if wanted:
        try:
            ids = {int(part) for part in wanted.split(',') if part.strip()}
        except ValueError:
            return jsonify({'error': 'Bad ids'}), 400
        if len(ids) > max_export:
            return jsonify({'error': 'Too many ids'}), 400
        export_data = [item for item in export_data if item.get('id') in ids]

    if export_format == 'json':
        import json as json_module
        output = json_module.dumps({'translations': export_data}, indent=2, ensure_ascii=False)
        return output, 200, {
            'Content-Type': 'application/json; charset=utf-8',
            'Content-Disposition': 'attachment; filename="transcriptions.json"'
        }

    elif export_format == 'txt':
        output = f"EzySpeechTranslate Export\nGenerated: {local_now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        output += "=" * 60 + "\n\n"

        for item in export_data:
            output += f"[{item['id']}] {item['timestamp']}\n"
            output += f"Original: {sanitize_text(item['original'], 500)}\n"
            output += f"Corrected: {sanitize_text(item['corrected'], 500)}\n"
            output += "-" * 60 + "\n\n"

        # Add UTF-8 BOM to ensure Windows/Excel correctly identifies encoding
        output = '\ufeff' + output
        return output, 200, {
            'Content-Type': 'text/plain; charset=utf-8',
            'Content-Disposition': 'attachment; filename="transcriptions.txt"'
        }

    elif export_format == 'csv':
        output = "ID,Timestamp,Original,Corrected,Is_Corrected\n"

        for item in export_data:
            row = [
                str(item['id']),
                item['timestamp'],
                f'"{sanitize_text(item["original"], 500).replace(chr(34), chr(34)*2)}"',
                f'"{sanitize_text(item["corrected"], 500).replace(chr(34), chr(34)*2)}"',
                'Yes' if item['is_corrected'] else 'No'
            ]
            output += ','.join(row) + '\n'

        # Add UTF-8 BOM to ensure Windows/Excel correctly identifies encoding
        output = '\ufeff' + output
        return output, 200, {
            'Content-Type': 'text/csv; charset=utf-8',
            'Content-Disposition': 'attachment; filename="transcriptions.csv"'
        }

    elif export_format == 'srt':
        output = ""
        for i, item in enumerate(export_data, 1):
            start_seconds = (i - 1) * 5
            end_seconds = i * 5

            start_time = f"00:{start_seconds // 60:02d}:{start_seconds % 60:02d},000"
            end_time = f"00:{end_seconds // 60:02d}:{end_seconds % 60:02d},000"

            output += f"{i}\n"
            output += f"{start_time} --> {end_time}\n"
            output += f"{sanitize_text(item['corrected'], 500)}\n\n"

        # Add UTF-8 BOM to ensure Windows/Excel correctly identifies encoding
        output = '\ufeff' + output
        return output, 200, {
            'Content-Type': 'text/plain; charset=utf-8',
            'Content-Disposition': 'attachment; filename="transcriptions.srt"'
        }


# ──────────────────────────────────────────
# Rooms API (multi-room support)
# ──────────────────────────────────────────
@app.route('/api/rooms', methods=['GET'])
@limiter.limit("60 per minute")
def list_rooms():
    """Public list of active rooms — used by the user picker overlay."""
    db_rooms = []
    if db is not None:
        try:
            db_rooms = db.list_rooms()
        except Exception as exc:
            logger.warning(f"db.list_rooms failed: {exc}")
    # Merge with in-memory rooms (ensures default 'main' always shows)
    by_id = {r['room_id']: dict(r) for r in db_rooms if r.get('is_active', True)}
    for rid, st in _rooms.items():
        entry = by_id.get(rid, {
            'room_id': rid,
            'display_name': st.get('display_name') or rid,
            'is_active': True,
        })
        entry['listeners'] = len(st['listeners'])
        by_id[rid] = entry
    # Sort: default first, then alphabetical
    rooms_list = sorted(
        by_id.values(),
        key=lambda r: (0 if r['room_id'] == DEFAULT_ROOM_ID else 1, r['room_id']),
    )
    return jsonify({'success': True, 'rooms': rooms_list, 'default': DEFAULT_ROOM_ID})


@app.route('/api/rooms', methods=['POST'])
@limiter.limit("20 per minute")
@require_admin_auth
def create_room():
    """Create or update a room (admin only)."""
    data = request.get_json(silent=True) or {}
    room_id = (data.get('room_id') or '').strip()
    display_name = sanitize_text(data.get('display_name', '') or room_id, max_length=120)
    if not _VALID_ROOM_RE.match(room_id):
        return jsonify({'success': False, 'error': 'Invalid room_id'}), 400
    if db is not None:
        try:
            db.upsert_room(room_id, display_name=display_name,
                           created_by=request.user.get('username'))
        except Exception as exc:
            logger.warning(f"db.upsert_room failed: {exc}")
            return jsonify({'success': False, 'error': 'DB error'}), 500
    # Ensure in-memory state exists
    state = _room(room_id)
    state['display_name'] = display_name
    logger.info(f"[ROOM] Created/updated '{room_id}' by {request.user.get('username')}")
    return jsonify({'success': True, 'room_id': room_id, 'display_name': display_name})


@app.route('/api/rooms/<room_id>', methods=['DELETE'])
@limiter.limit("20 per minute")
@require_admin_auth
def delete_room(room_id):
    """Soft-delete a room (admin only). Default room is protected."""
    room_id = (room_id or '').strip()
    if not _VALID_ROOM_RE.match(room_id):
        return jsonify({'success': False, 'error': 'Invalid room_id'}), 400
    if room_id == DEFAULT_ROOM_ID:
        return jsonify({'success': False, 'error': 'Cannot delete default room'}), 400
    if db is not None:
        try:
            db.delete_room(room_id)
        except Exception as exc:
            logger.warning(f"db.delete_room failed: {exc}")
            return jsonify({'success': False, 'error': 'DB error'}), 500
    # Notify any listeners still in the room
    socketio.emit('room_deleted', {'room_id': room_id}, room=f'room:{room_id}')
    socketio.emit('room_deleted', {'room_id': room_id}, room=f'admin:{room_id}')
    # Drop in-memory state
    _rooms.pop(room_id, None)
    logger.info(f"[ROOM] Deleted '{room_id}' by {request.user.get('username')}")
    return jsonify({'success': True, 'room_id': room_id})


# ──────────────────────────────────────────
# Glossary API (forced translations)
# ──────────────────────────────────────────
@app.route('/api/glossary', methods=['GET'])
@limiter.limit("60 per minute")
@require_auth
def get_glossary():
    """List glossary entries (optionally filtered by room and/or language)."""
    if db is None:
        return jsonify({'success': True, 'entries': []})
    room_param = request.args.get('room')
    room_id = normalize_room_id(room_param) if room_param else None
    include_global = request.args.get('include_global', 'true').lower() != 'false'
    try:
        entries = db.glossary_list(room_id=room_id, include_global=include_global)
    except Exception as exc:
        logger.warning(f"db.glossary_list failed: {exc}")
        return jsonify({'success': False, 'error': 'DB error'}), 500
    lang_filter = (request.args.get('target_lang') or '').lower()
    if lang_filter:
        entries = [e for e in entries if (e.get('target_lang') or '').lower() == lang_filter]
    return jsonify({'success': True, 'entries': entries, 'count': len(entries)})


@app.route('/api/glossary', methods=['POST'])
@limiter.limit("60 per minute")
@require_admin_auth
def add_glossary():
    """Create a new glossary entry."""
    if db is None:
        return jsonify({'success': False, 'error': 'Database disabled'}), 400
    data = request.get_json(silent=True) or {}
    source_term = sanitize_text(data.get('source_term', ''), max_length=200).strip()
    target_lang = sanitize_text(data.get('target_lang', ''), max_length=20).strip()
    translation = sanitize_text(data.get('translation', ''), max_length=500).strip()
    case_sensitive = bool(data.get('case_sensitive', False))
    enabled = bool(data.get('enabled', True))
    room_param = data.get('room')
    room_id = None  # None = global
    if room_param:
        if not _VALID_ROOM_RE.match(str(room_param).strip()):
            return jsonify({'success': False, 'error': 'Invalid room_id'}), 400
        room_id = str(room_param).strip()
        # Verify room actually exists (avoid orphan glossary entries)
        try:
            active_ids = {r['room_id'] for r in db.list_rooms()}
        except Exception:
            active_ids = set()
        if room_id != DEFAULT_ROOM_ID and room_id not in active_ids:
            return jsonify({'success': False, 'error': f"Room '{room_id}' does not exist"}), 400
    if not source_term or not target_lang or not translation:
        return jsonify({'success': False, 'error': 'Missing required fields'}), 400
    try:
        entry_id = db.glossary_add(
            source_term=source_term, target_lang=target_lang, translation=translation,
            room_id=room_id, case_sensitive=case_sensitive, enabled=enabled,
            created_by=request.user.get('username'),
        )
    except Exception as exc:
        logger.warning(f"db.glossary_add failed: {exc}")
        return jsonify({'success': False, 'error': 'DB error'}), 500
    # Bust translation cache so changes take effect immediately
    try:
        get_translation_service().clear_cache()
    except Exception:
        pass
    logger.info(f"[GLOSSARY] Added '{source_term}''{translation}' ({target_lang}, room={room_id}) "
                f"by {request.user.get('username')}")
    return jsonify({'success': True, 'id': entry_id})


@app.route('/api/glossary/<int:entry_id>', methods=['PUT'])
@limiter.limit("60 per minute")
@require_admin_auth
def update_glossary(entry_id):
    """Update an existing glossary entry."""
    if db is None:
        return jsonify({'success': False, 'error': 'Database disabled'}), 400
    data = request.get_json(silent=True) or {}
    fields = {}
    if 'source_term' in data:
        fields['source_term'] = sanitize_text(data['source_term'], max_length=200)
    if 'target_lang' in data:
        fields['target_lang'] = sanitize_text(data['target_lang'], max_length=20)
    if 'translation' in data:
        fields['translation'] = sanitize_text(data['translation'], max_length=500)
    if 'case_sensitive' in data:
        fields['case_sensitive'] = bool(data['case_sensitive'])
    if 'enabled' in data:
        fields['enabled'] = bool(data['enabled'])
    if not fields:
        return jsonify({'success': False, 'error': 'Nothing to update'}), 400
    try:
        ok = db.glossary_update(entry_id, **fields)
    except Exception as exc:
        logger.warning(f"db.glossary_update failed: {exc}")
        return jsonify({'success': False, 'error': 'DB error'}), 500
    try:
        get_translation_service().clear_cache()
    except Exception:
        pass
    return jsonify({'success': ok, 'id': entry_id})


@app.route('/api/glossary/<int:entry_id>', methods=['DELETE'])
@limiter.limit("60 per minute")
@require_admin_auth
def remove_glossary(entry_id):
    """Delete a glossary entry."""
    if db is None:
        return jsonify({'success': False, 'error': 'Database disabled'}), 400
    try:
        ok = db.glossary_delete(entry_id)
    except Exception as exc:
        logger.warning(f"db.glossary_delete failed: {exc}")
        return jsonify({'success': False, 'error': 'DB error'}), 500
    try:
        get_translation_service().clear_cache()
    except Exception:
        pass
    return jsonify({'success': ok, 'id': entry_id})


# ──────────────────────────────────────────
# Recording lock (per-room) — prevents two admins from recording the same
# room simultaneously. A force-stop requires re-verifying the admin password.
# ──────────────────────────────────────────

def _recording_owner_dict(state):
    rec = state.get('recording')
    if not rec:
        return None
    # Hide internal sid from public callers
    return {'username': rec.get('username'), 'started_at': rec.get('started_at')}


@app.route('/api/recording/state', methods=['GET'])
@limiter.limit("120 per minute")
@require_auth
def get_recording_state():
    """Report who (if anyone) is currently recording in a given room."""
    rid = normalize_room_id(request.args.get('room'))
    state = _room(rid)
    owner = _recording_owner_dict(state)
    return jsonify({'success': True, 'room_id': rid, 'recording': owner})


@app.route('/api/recording/acquire', methods=['POST'])
@limiter.limit("60 per minute")
@require_admin_auth
def acquire_recording():
    """Acquire the per-room recording lock.

    Returns 200 on success. If another admin holds the lock, returns 423 with
    owner info. To take over, pass {force: true, password_hash: <sha256>}.
    """
    data = request.get_json(silent=True) or {}
    rid = normalize_room_id(data.get('room'))
    state = _room(rid)
    username = (request.user.get('username') if request.user else '') or 'admin'
    sid = data.get('sid')  # optional Socket.IO sid of this admin tab

    current = state.get('recording')
    if current and current.get('username') != username:
        # Lock held by someone else
        if not data.get('force'):
            return jsonify({
                'success': False, 'error': 'locked',
                'owner': _recording_owner_dict(state),
            }), 423
        # Force-takeover requires password re-verification
        password_hash = data.get('password_hash', '')
        account = _accounts.get(username)
        if not account or not _verify_password(password_hash, account['verifier']):
            security_logger.warning(
                f"Force-recording rejected: bad password from {username} for room '{rid}'"
            )
            return jsonify({'success': False, 'error': 'invalid_password'}), 401
        # Notify the displaced owner so their browser stops recognition
        evicted = current.get('username')
        evicted_sid = current.get('sid')
        socketio.emit(
            'recording_force_stopped',
            {'room_id': rid, 'by': username, 'reason': 'admin_takeover'},
            room=evicted_sid if evicted_sid else f'admin:{rid}',
        )
        logger.warning(
            f"[RECORDING] {username} force-stopped {evicted} in room '{rid}'"
        )

    state['recording'] = {
        'username': username,
        'sid': sid,
        'started_at': datetime.utcnow().isoformat() + 'Z',
    }
    socketio.emit(
        'recording_state',
        {'room_id': rid, 'recording': _recording_owner_dict(state)},
        room=f'admin:{rid}',
    )
    logger.info(f"[RECORDING] {username} acquired room '{rid}'")
    return jsonify({'success': True, 'room_id': rid, 'recording': _recording_owner_dict(state)})


@app.route('/api/recording/release', methods=['POST'])
@limiter.limit("60 per minute")
@require_admin_auth
def release_recording():
    """Release the recording lock for a room.

    Only the current owner (or no-op if no owner) can release.
    """
    data = request.get_json(silent=True) or {}
    rid = normalize_room_id(data.get('room'))
    state = _room(rid)
    username = (request.user.get('username') if request.user else '') or 'admin'
    current = state.get('recording')
    if current and current.get('username') != username:
        return jsonify({'success': False, 'error': 'not_owner',
                        'owner': _recording_owner_dict(state)}), 403
    state['recording'] = None
    socketio.emit(
        'recording_state',
        {'room_id': rid, 'recording': None},
        room=f'admin:{rid}',
    )
    logger.info(f"[RECORDING] {username} released room '{rid}'")
    return jsonify({'success': True, 'room_id': rid})


# ──────────────────────────────────────────
# Editable config.yaml (admin only)
# Sensitive keys are masked on read and ignored on write — they are
# managed via the encrypted secrets.key file, not the YAML config.
# ──────────────────────────────────────────

_CONFIG_FILE_PATH = os.path.join(BASE_DIR, 'config', 'config.yaml') \
    if 'BASE_DIR' in globals() else os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'config.yaml')
_SENSITIVE_CONFIG_KEYS = (
    'admin_password', 'admin_password_hash', 'password', 'password_hash',
    'jwt_secret', 'server_secret_key',
    'secret_key', 'encryption_key',
)


def _is_sensitive(key) -> bool:
    """A secret, by its name: the ones above, and every *_api_key (a
    translation service's, which costs money in the wrong hands)."""
    return key in _SENSITIVE_CONFIG_KEYS or str(key).endswith('_api_key')


def _mask_sensitive(obj):
    """Recursively replace values for known sensitive keys with '***'."""
    if isinstance(obj, dict):
        return {
            k: ('***' if _is_sensitive(k) and v else _mask_sensitive(v))
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_mask_sensitive(v) for v in obj]
    return obj


def _strip_masked(new_obj, existing_obj):
    """Where new_obj contains '***' for sensitive keys, restore the value from existing_obj."""
    if isinstance(new_obj, dict) and isinstance(existing_obj, dict):
        out = {}
        for k, v in new_obj.items():
            if _is_sensitive(k) and v == '***':
                if k in existing_obj:
                    out[k] = existing_obj[k]
                # else: drop the masked placeholder
            else:
                out[k] = _strip_masked(v, existing_obj.get(k) if isinstance(existing_obj, dict) else None)
        return out
    if isinstance(new_obj, list):
        return [_strip_masked(v, None) for v in new_obj]
    return new_obj


@app.route('/api/config/raw', methods=['GET'])
@limiter.limit("30 per minute")
@require_admin_auth
def get_raw_config():
    """Return the current config.yaml as YAML text (sensitive values masked)."""
    try:
        import yaml  # PyYAML; already a transitive dep via config loader
        if not os.path.exists(_CONFIG_FILE_PATH):
            return jsonify({'success': False, 'error': 'config.yaml not found'}), 404
        with open(_CONFIG_FILE_PATH, 'r', encoding='utf-8') as f:
            raw = f.read()
        parsed = yaml.safe_load(raw) or {}
        masked = _mask_sensitive(parsed)
        return jsonify({
            'success': True,
            'yaml': yaml.safe_dump(masked, allow_unicode=True, sort_keys=False),
            'path': _CONFIG_FILE_PATH,
        })
    except Exception as exc:
        logger.warning(f"get_raw_config error: {exc}")
        return jsonify({'success': False, 'error': str(exc)}), 500


@app.route('/api/config/raw', methods=['POST'])
@limiter.limit("10 per minute")
@require_admin_auth
def save_raw_config():
    """Validate and write config.yaml. Sensitive keys with '***' are preserved
    from the existing file. Caller is warned that some changes require a server
    restart to take effect."""
    try:
        import yaml
        data = request.get_json(silent=True) or {}
        new_text = data.get('yaml', '')
        if not isinstance(new_text, str) or not new_text.strip():
            return jsonify({'success': False, 'error': 'Empty YAML'}), 400
        if len(new_text) > 200_000:
            return jsonify({'success': False, 'error': 'Config too large'}), 400
        try:
            parsed_new = yaml.safe_load(new_text)
        except yaml.YAMLError as exc:
            return jsonify({'success': False, 'error': f'YAML parse error: {exc}'}), 400
        if not isinstance(parsed_new, dict):
            return jsonify({'success': False, 'error': 'Top-level YAML must be a mapping'}), 400

        # Load existing to restore masked sensitive values
        existing = {}
        if os.path.exists(_CONFIG_FILE_PATH):
            with open(_CONFIG_FILE_PATH, 'r', encoding='utf-8') as f:
                existing = yaml.safe_load(f.read()) or {}

        merged = _strip_masked(parsed_new, existing)

        # Atomic write: write to .tmp then rename
        tmp_path = _CONFIG_FILE_PATH + '.tmp'
        with open(tmp_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(merged, f, allow_unicode=True, sort_keys=False)
        os.replace(tmp_path, _CONFIG_FILE_PATH)
        username = (request.user.get('username') if request.user else 'admin') or 'admin'
        logger.warning(f"[CONFIG] config.yaml updated by {username}")
        return jsonify({
            'success': True,
            'message': 'Saved. Restart the server for changes to take effect.',
        })
    except Exception as exc:
        logger.error(f"save_raw_config error: {exc}")
        return jsonify({'success': False, 'error': str(exc)}), 500


# ── config.yaml, field by field ───────────────────────────────────────────
# The YAML editor above hands the whole document back from the browser, so a
# key the page did not render is a key that gets dropped. These two take named
# scalar fields instead: a path that is not already in the file is refused, and
# so is any path ending in a sensitive key, so the settings page can never
# reach a secret or lose a setting it does not know about.

_CONFIG_PATH_SEGMENT = re.compile(r'^[A-Za-z0-9_]{1,64}$')
_CONFIG_MAX_DEPTH = 6
_CONFIG_MAX_CHANGES = 200


def _config_scalar(value):
    return value is None or isinstance(value, (str, int, float, bool))


def _config_lookup(root, parts):
    """The container holding the leaf, and the leaf's current value."""
    node = root
    for part in parts[:-1]:
        if not isinstance(node, dict) or part not in node:
            return None, None
        node = node[part]
    if not isinstance(node, dict) or parts[-1] not in node:
        return None, None
    return node, node[parts[-1]]


def _config_coerce(current, value):
    """Fit the incoming value to the type already in the file. Raises ValueError."""
    if isinstance(current, bool):
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.lower() in ('true', 'false'):
            return value.lower() == 'true'
        raise ValueError('expected true or false')
    if isinstance(current, int):
        if isinstance(value, bool):
            raise ValueError('expected a number')
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.strip().lstrip('-').isdigit():
            return int(value)
        raise ValueError('expected a whole number')
    if isinstance(current, float):
        if isinstance(value, bool) or not isinstance(value, (int, float, str)):
            raise ValueError('expected a number')
        try:
            return float(value)
        except (TypeError, ValueError):
            raise ValueError('expected a number')
    if current is None:
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        if _config_scalar(value):
            return value
        raise ValueError('expected a single value')
    if isinstance(current, str):
        if value is None:
            return ''
        if isinstance(value, (str, int, float)) and not isinstance(value, bool):
            return str(value)
        raise ValueError('expected text')
    raise ValueError('this setting is not a single value')


# Rewriting single values without losing the file's comments lives beside the
# config loader, so the container's first-run setup writes the file the same way.
from app.core.config_edit import write_in_place as _config_write_in_place  # noqa: E402


@app.route('/api/config/fields', methods=['GET'])
@limiter.limit("30 per minute")
@require_admin_auth
def get_config_fields():
    """The current config.yaml as JSON, sensitive values masked."""
    try:
        import yaml
        if not os.path.exists(_CONFIG_FILE_PATH):
            return jsonify({'success': False, 'error': 'config.yaml not found'}), 404
        with open(_CONFIG_FILE_PATH, 'r', encoding='utf-8') as f:
            parsed = yaml.safe_load(f.read()) or {}
        return jsonify({
            'success': True,
            'config': _mask_sensitive(parsed),
            'path': _CONFIG_FILE_PATH,
        })
    except Exception as exc:
        logger.warning(f"get_config_fields error: {exc}")
        return jsonify({'success': False, 'error': str(exc)}), 500


@app.route('/api/config/fields', methods=['POST'])
@limiter.limit("10 per minute")
@require_admin_auth
def save_config_fields():
    """Apply named scalar fields to config.yaml.

    Body: {"changes": {"server.port": 1915, "features.dark_mode": true}}.
    Every path must already exist in the file and already hold a single value;
    the new value is fitted to the type that is there. Nothing else in the file
    is touched, and the write is atomic.
    """
    try:
        import yaml
        body = request.get_json(silent=True) or {}
        changes = body.get('changes')
        if not isinstance(changes, dict) or not changes:
            return jsonify({'success': False, 'error': 'No changes given'}), 400
        if len(changes) > _CONFIG_MAX_CHANGES:
            return jsonify({'success': False, 'error': 'Too many changes at once'}), 400
        if not os.path.exists(_CONFIG_FILE_PATH):
            return jsonify({'success': False, 'error': 'config.yaml not found'}), 404

        with open(_CONFIG_FILE_PATH, 'r', encoding='utf-8') as f:
            raw = f.read()
        config = yaml.safe_load(raw) or {}

        applied, errors = {}, {}
        for path, value in changes.items():
            parts = str(path).split('.')
            if not (1 <= len(parts) <= _CONFIG_MAX_DEPTH) or \
                    not all(_CONFIG_PATH_SEGMENT.match(p) for p in parts):
                errors[path] = 'not a setting name'
                continue
            if _is_sensitive(parts[-1]):
                errors[path] = 'secrets are not editable here'
                continue
            holder, current = _config_lookup(config, parts)
            if holder is None:
                errors[path] = 'no such setting'
                continue
            if not _config_scalar(current):
                errors[path] = 'not a single value'
                continue
            try:
                holder[parts[-1]] = _config_coerce(current, value)
            except ValueError as exc:
                errors[path] = str(exc)
                continue
            applied[path] = holder[parts[-1]]

        if errors:
            return jsonify({'success': False, 'error': 'Some settings were refused',
                            'errors': errors}), 400

        # Rewrite the changed lines where the file allows it, so the comments
        # and the layout survive. Anything unexpected falls back to dumping the
        # document, and either way the result has to parse back to what was
        # intended before it is written.
        new_text = _config_write_in_place(raw, applied)
        if new_text is not None and yaml.safe_load(new_text) != config:
            new_text = None
        if new_text is None:
            new_text = yaml.safe_dump(config, allow_unicode=True, sort_keys=False)

        tmp_path = _CONFIG_FILE_PATH + '.tmp'
        with open(tmp_path, 'w', encoding='utf-8') as f:
            f.write(new_text)
        os.replace(tmp_path, _CONFIG_FILE_PATH)
        username = (request.user.get('username') if request.user else 'admin') or 'admin'
        logger.warning(f"[CONFIG] {len(applied)} setting(s) updated by {username}: "
                       + ', '.join(sorted(applied)))
        return jsonify({
            'success': True,
            'applied': applied,
            'message': 'Saved. Restart the server for changes to take effect.',
        })
    except Exception as exc:
        logger.error(f"save_config_fields error: {exc}")
        return jsonify({'success': False, 'error': str(exc)}), 500
