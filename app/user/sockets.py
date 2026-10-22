"""The listener server: the live events, and announcements.

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
# WebSocket Events with Security
# ──────────────────────────────────────────
@socketio.on('connect')
def handle_connect():
    """Handle client connection with validation"""
    # Priority: Get client_id from query params (sent by client), then cookies
    client_id = request.args.get('client_id')
    client_type = request.args.get('type', 'user')  # 'user' or 'admin'
    
    if not client_id:
        # Fallback to cookies if query param not provided
        if hasattr(request, 'cookies'):
            client_id = request.cookies.get('_client_id')
    
    # If still no client_id, generate one (fallback)
    if not client_id:
        client_id = f"browser_{secrets.token_hex(16)}"
        logger.warning(f"No client_id provided, generated fallback: {client_id}")

    # Validate client_type to a known whitelist; anything else is treated
    # as 'user'. Prevents callers from injecting arbitrary type strings
    # via the query string and ending up in unexpected branches.
    if client_type not in ('user', 'admin', 'caption'):
        logger.warning(f"Unknown client_type '{client_type}' from {client_id}, defaulting to 'user'")
        client_type = 'user'

    client_key = f"client:{client_id}"
    client_ip = get_real_ip()

    # Room scope for this client (validated; defaults to 'main')
    room_id = normalize_room_id(request.args.get('room'))
    room_state = _room(room_id)

    logger.info(f"Socket.IO connect attempt from {client_ip} (Client: {client_id}, Type: {client_type}, Room: {room_id}, SID: {request.sid})")

    if is_client_blocked(client_key):
        security_logger.warning(f"Blocked client attempted WebSocket: {client_key}")
        logger.error(f"Connection rejected: Client {client_key} is blocked")
        return False

    from flask_socketio import join_room as _join_room

    # Only count user-type clients as listeners (not admin)
    if client_type == 'user':
        # If this client_key already has an old SID anywhere, evict it (handles page refresh)
        for _rs in _rooms.values():
            old_sid = _rs['listeners'].get(client_key)
            if old_sid and old_sid != request.sid:
                logger.info(f"Evicting stale SID {old_sid} for {client_key} (replaced by {request.sid})")
                sid_to_client_key.pop(old_sid, None)
                connected_clients.discard(f"{client_key}:{old_sid}")
                _rs['listeners'].pop(client_key, None)

        client_id_full = f"{client_key}:{request.sid}"
        connected_clients.add(client_id_full)
        room_state['listeners'][client_key] = request.sid
        _join_room(f'room:{room_id}')
        logger.info(
            f"User client connected: {client_ip} (Client: {client_id}, Room: {room_id}, "
            f"SID: {request.sid}, Room listeners: {len(room_state['listeners'])}, "
            f"Total listeners: {_all_listener_count()})"
        )
    elif client_type == 'caption':
        # Caption overlay clients join the room so they receive broadcasts
        _join_room(f'room:{room_id}')
        logger.info(f"Caption client connected: {client_ip} (Client: {client_id}, Room: {room_id}, SID: {request.sid})")

    elif client_type == 'admin':
        # Admin clients still need to be tracked, but not as listeners
        client_id_full = f"{client_key}:{request.sid}"
        connected_clients.add(client_id_full)
        logger.info(f"Admin client connected: {client_ip} (Client: {client_id}, SID: {request.sid})")

    # Store mapping for reliable cleanup on disconnect (includes room_id)
    sid_to_client_key[request.sid] = (client_key, client_type, room_id)

    # Notify client that history is available via HTTP API (pagination)
    # Don't send all history via WebSocket - use HTTP API for better performance
    # Generate and send short-lived API session token for pagination
    api_token = create_api_token(request.sid)
    emit('ready', {
        'status': 'connected',
        'message': 'Use /api/translations to fetch paginated history',
        'api_token': api_token,
        'room_id': room_id,
        # Translations arrive as line_translated for the language announced
        # with reading_language.
        'server_translation': True,
    })

    # ── Feature 1: broadcast live viewer count to admins of this room ────
    if client_type == 'user':
        _sid_last_seen[request.sid] = datetime.now()   # start heartbeat tracking
        room_count = len(room_state['listeners'])
        total_count = _all_listener_count()
        if total_count > S._peak_clients:
            S._peak_clients = total_count
        payload = {'count': room_count, 'room_id': room_id, 'total': total_count}
        socketio.emit('clients_update', payload, room=f'admin:{room_id}')
        socketio.emit('clients_update', payload, room='admins')  # legacy compat

    return True

@socketio.on('disconnect')
def handle_disconnect(sid=None):
    """Handle client disconnection - find and clean up client info"""
    sid_used = sid if sid is not None else request.sid
    
    # Use stored mapping to find client_key and type reliably
    mapping = sid_to_client_key.pop(sid_used, None)
    
    if mapping:
        if len(mapping) >= 3:
            client_key, client_type, room_id = mapping[0], mapping[1], mapping[2]
        else:
            client_key, client_type = mapping[0], mapping[1]
            room_id = DEFAULT_ROOM_ID
        room_id = normalize_room_id(room_id)

        # Clean up only if it was a user (listener)
        if client_type == 'user':
            # Only remove from listener_clients if this SID is still the active one
            # (avoids removing a newer connection when a stale disconnect fires late)
            rs = _rooms.get(room_id)
            if rs is not None and rs['listeners'].get(client_key) == sid_used:
                del rs['listeners'][client_key]
            if rs is not None:
                rs.setdefault('reading', {}).pop(sid_used, None)
            logger.info(
                f"User client disconnected: SID {sid_used} from {client_key} "
                f"(Room: {room_id}, Total listeners: {_all_listener_count()})"
            )
        else:
            logger.info(f"Admin client disconnected: SID {sid_used} from {client_key}")
    else:
        logger.warning(f"Disconnect: Unknown client mapping for SID {sid_used}")
        client_type = None
        room_id = DEFAULT_ROOM_ID
    
    # Always try to remove from connected_clients
    connected_clients.discard(sid_used)
    for key in list(connected_clients):
        if key.endswith(f":{sid_used}"):
            connected_clients.discard(key)
            break
    
    admin_sessions.pop(sid_used, None)

    # Release recording lock if this disconnecting admin held it
    if client_type == 'admin':
        rs = _rooms.get(room_id)
        if rs and rs.get('recording') and rs['recording'].get('sid') == sid_used:
            rs['recording'] = None
            socketio.emit(
                'recording_state',
                {'room_id': room_id, 'recording': None},
                room=f'admin:{room_id}',
            )
            logger.info(f"[RECORDING] auto-released room '{room_id}' on admin disconnect")

    # Clean up API tokens associated with this SID
    tokens_to_remove = [t for t, info in api_session_tokens.items() if info['sid'] == sid_used]
    for token in tokens_to_remove:
        del api_session_tokens[token]

    # Remove heartbeat record
    _sid_last_seen.pop(sid_used, None)

    # ── Feature 1: broadcast updated viewer count to admins of the room ───
    if client_type == 'user':
        rs = _rooms.get(room_id)
        room_count = len(rs['listeners']) if rs else 0
        payload = {'count': room_count, 'room_id': room_id, 'total': _all_listener_count()}
        socketio.emit('clients_update', payload, room=f'admin:{room_id}')
        socketio.emit('clients_update', payload, room='admins')

@socketio.on('heartbeat')
def handle_heartbeat():
    """Client keepalive — update last-seen timestamp."""
    _sid_last_seen[request.sid] = datetime.now()


def _heartbeat_cleanup_loop():
    """Background greenlet: evict user clients that stopped sending heartbeats.

    A client is considered gone if no heartbeat arrived within
    HEARTBEAT_TIMEOUT seconds.  This catches browsers that close
    without triggering a clean WebSocket close (e.g. mobile sleep,
    Cloudflare Tunnel keepalive masking the real disconnect).
    """
    HEARTBEAT_TIMEOUT = 45   # seconds — 3× client interval (15 s)
    CHECK_INTERVAL   = 15   # how often we scan
    while True:
        eventlet.sleep(CHECK_INTERVAL)
        now = datetime.now()
        stale = [
            sid for sid, last in list(_sid_last_seen.items())
            if (now - last).total_seconds() > HEARTBEAT_TIMEOUT
        ]
        for sid in stale:
            _sid_last_seen.pop(sid, None)
            mapping = sid_to_client_key.get(sid)
            if mapping and mapping[1] == 'user':
                logger.info(f"[HEARTBEAT] Evicting stale user SID {sid} (no heartbeat for >{HEARTBEAT_TIMEOUT}s)")
                # Trigger the same cleanup path as a normal disconnect
                try:
                    handle_disconnect(sid)
                except Exception as _e:
                    logger.warning(f"[HEARTBEAT] Cleanup error for {sid}: {_e}")


@socketio.on('reading_language')
def handle_reading_language(data):
    """A screen says which language it reads in, or that it needs none
    (transcription mode, or reading the spoken language)."""
    from flask_socketio import join_room, leave_room
    sid = request.sid
    mapping = sid_to_client_key.get(sid)
    if not mapping or mapping[1] != 'user':
        return
    lang = (data or {}).get('lang') if isinstance(data, dict) else None
    lang = str(lang).strip().lower() if lang else None
    if lang and not _READING_LANG.match(lang):
        return
    room_id = _sid_room(sid)
    reading = _room(room_id).setdefault('reading', {})
    previous = reading.get(sid)
    if previous == lang:
        return
    if previous:
        leave_room(_reading_room(room_id, previous))
    if lang:
        reading[sid] = lang
        join_room(_reading_room(room_id, lang))
    else:
        reading.pop(sid, None)


@socketio.on('admin_connect')
def handle_admin_connect(data):
    """Handle admin connection with validation"""
    if not data or not isinstance(data, dict):
        emit('admin_connected', {'success': False, 'error': 'Invalid data'})
        return

    token = data.get('token')
    requested_room = normalize_room_id(data.get('room'))

    if not get_config('authentication', 'enabled', default=True):
        admin_sessions[request.sid] = {'username': 'admin', 'room_id': requested_room}
        from flask_socketio import join_room
        join_room('admins')
        join_room(f'admin:{requested_room}')
        # Send room-scoped history
        emit('history', _room(requested_room)['history'])
        emit('admin_connected', {
            'success': True, 'role': 'admin', 'channel': requested_room,
            'display_name': 'Admin', 'room_id': requested_room,
        })
        return

    if not token:
        emit('admin_connected', {'success': False, 'error': 'No token'})
        return

    decoded = validate_jwt_token(token)
    if decoded:
        # Prefer explicit room in payload; fall back to JWT channel; then default
        room_id = normalize_room_id(
            data.get('room') or decoded.get('channel') or DEFAULT_ROOM_ID
        )
        admin_sessions[request.sid] = {
            'username': decoded['username'],
            'room_id': room_id,
        }
        from flask_socketio import join_room
        join_room('admins')
        join_room(f'admin:{room_id}')
        # Send room-scoped history
        emit('history', _room(room_id)['history'])
        emit('translation_health', get_translation_service().health_summary())
        emit('admin_connected', {
            'success':      True,
            'role':         decoded.get('role', 'admin'),
            'channel':      room_id,
            'room_id':      room_id,
            'display_name': decoded.get('display_name', decoded['username']),
        })
        logger.info(f"Admin connected: {decoded['username']} ({decoded.get('role', 'admin')}/room={room_id}) from {get_real_ip()}")
    else:
        emit('admin_connected', {'success': False, 'error': 'Invalid token'})


@socketio.on('admin_switch_room')
def handle_admin_switch_room(data):
    """Allow an authenticated admin to switch the room they broadcast into."""
    if not is_admin(request.sid):
        emit('error', {'message': 'Unauthorized'})
        return
    if not data or not isinstance(data, dict):
        emit('error', {'message': 'Invalid data'})
        return
    new_room = normalize_room_id(data.get('room'))
    info = admin_sessions.get(request.sid)
    if not isinstance(info, dict):
        info = {'username': info or 'admin', 'room_id': DEFAULT_ROOM_ID}
    old_room = normalize_room_id(info.get('room_id'))
    if old_room == new_room:
        emit('room_switched', {'success': True, 'room_id': new_room, 'changed': False})
        return
    from flask_socketio import leave_room, join_room
    leave_room(f'admin:{old_room}')
    join_room(f'admin:{new_room}')
    info['room_id'] = new_room
    admin_sessions[request.sid] = info
    # Make sure target room state exists and send its history
    emit('history', _room(new_room)['history'])
    emit('room_switched', {'success': True, 'room_id': new_room, 'changed': True})
    logger.info(f"[ROOM-SWITCH] {_admin_username(request.sid)}: {old_room} -> {new_room}")


@socketio.on('new_transcription')
def handle_new_transcription(data):
    """Handle new transcription with validation
    
    Support two modes:
    - is_final=False: Send interim result for real-time display (no storing)
    - is_final=True: Send final result with translation (store in history)
    """
    if not is_admin(request.sid):
        emit('error', {'message': 'Unauthorized'})
        disconnect()
        return

    if not data or not isinstance(data, dict):
        emit('error', {'message': 'Invalid data'})
        return

    raw_text = sanitize_text(data.get('text', ''), max_length=5000)
    if not raw_text:
        return

    is_final = data.get('is_final', True)  # Default to final for backward compatibility
    temp_id = data.get('temp_id')  # Temporary ID to link interim->final results
    room_id = _admin_room(request.sid)

    if not is_final:
        interim_data = {
            'temp_id': temp_id,
            'text': raw_text,
            'timestamp': local_now().strftime('%H:%M:%S'),
            'source_language': data.get('language', 'en')[:10],
            'confidence': data.get('confidence'),
            'is_interim': True,
            'room_id': room_id,
        }
        # Broadcast to listeners in this room only
        socketio.emit('realtime_transcription', interim_data,
                      room=f'room:{room_id}', skip_sid=[request.sid])
        logger.debug(f"[INTERIM] room={room_id} {len(raw_text)} chars (temp_id: {temp_id})")
    else:
        translation_data = {
            'id': None,  # Will be assigned by add_translation()
            'temp_id': temp_id,
            'timestamp': local_now().strftime('%H:%M:%S'),
            'original': raw_text,
            'corrected': raw_text,
            'translated': data.get('translated'),
            'is_corrected': False,
            'source_language': data.get('language', 'en')[:10],
            'confidence': data.get('confidence'),
        }

        add_translation(translation_data, room_id=room_id)
        # Emit to listeners in this room only
        socketio.emit('new_translation', translation_data,
                      room=f'room:{room_id}', skip_sid=[request.sid])
        eventlet.spawn_n(_push_translations, room_id, translation_data)
        # Echo back to the sending admin for confirmation
        emit('transcription_confirmed', translation_data)
        logger.info(f"[FINAL] room={room_id} ID={translation_data.get('id')}")

def _translation_health_loop():
    """Tells the consoles how translation is going: when it changes, and every
    minute while it is not well, so one opened later hears of it too."""
    last_state, last_sent = 'ok', 0.0
    while True:
        eventlet.sleep(10)
        try:
            health = get_translation_service().health_summary()
        except Exception as exc:                # never the reason the server stops
            logger.warning(f"Translation health unavailable: {exc}")
            continue
        now = time.time()
        if health['state'] != last_state or (health['state'] != 'ok' and now - last_sent > 60):
            socketio.emit('translation_health', health, room='admins')
            last_state, last_sent = health['state'], now


@socketio.on('cancel_interim')
def handle_cancel_interim(data):
    """The console's recogniser let go of words it had sent as interim, with
    no final line to replace them (it stopped, or restarted on silence or a
    network blip): the screens showing them are told to take them off."""
    if not is_admin(request.sid):
        return
    temp_id = (data or {}).get('temp_id') if isinstance(data, dict) else None
    if not isinstance(temp_id, str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,80}', temp_id):
        return
    room_id = _admin_room(request.sid)
    socketio.emit('interim_cancelled', {'temp_id': temp_id, 'room_id': room_id},
                  room=f'room:{room_id}', skip_sid=[request.sid])


@socketio.on('correct_translation')
def handle_correct_translation(data):
    """Handle translation correction with validation"""
    if not is_admin(request.sid):
        emit('error', {'message': 'Unauthorized'})
        disconnect()
        return

    if not data or not isinstance(data, dict):
        emit('error', {'message': 'Invalid data'})
        return

    translation_id = data.get('id')
    corrected_text = sanitize_text(data.get('corrected_text', ''), max_length=5000)

    if not isinstance(translation_id, int) or translation_id < 0:
        emit('error', {'message': 'Invalid ID'})
        return

    if not corrected_text:
        emit('error', {'message': 'Empty correction'})
        return

    # Find translation by ID within the admin's room
    room_id = _admin_room(request.sid)
    history = _room(room_id)['history']
    target_item = None
    for item in history:
        if item['id'] == translation_id:
            target_item = item
            break

    if target_item is None:
        emit('error', {'message': 'Translation not found (may have been removed from history)'})
        return

    target_item['corrected'] = corrected_text
    target_item['is_corrected'] = True
    # Translations of the old wording are no longer this line's.
    target_item.pop('translations', None)

    # Re-detect Bible references in the corrected text so the panel updates
    # if the admin fixed a transcription error into a proper Bible citation.
    if bible_detector is not None:
        try:
            new_refs = bible_detector.detect_and_lookup(corrected_text)
            target_item['bible_refs'] = new_refs if new_refs else []
        except Exception:
            pass  # keep original refs on failure

    # Persist correction to DB
    if db is not None:
        db.update_correction(
            room_id, translation_id, corrected_text, True,
            bible_refs=target_item.get('bible_refs'),
            full_item=target_item,
        )

    socketio.emit('translation_corrected', target_item, room=f'room:{room_id}')
    socketio.emit('translation_corrected', target_item, room=f'admin:{room_id}')
    eventlet.spawn_n(_push_translations, room_id, target_item)
    logger.info(f"[CORRECTED] room={room_id} ID {translation_id}")
    emit('correction_success', {'id': translation_id})

@socketio.on('clear_history')
def handle_clear_history():
    """Handle clear history with authorization (scoped to admin's room)"""
    if not is_admin(request.sid):
        emit('error', {'message': 'Unauthorized'})
        disconnect()
        return

    room_id = _admin_room(request.sid)
    state = _room(room_id)
    state['history'].clear()
    # Off the live screens only: the lines stay in the database for the
    # transcript of the service they were said in, and the room goes on
    # numbering after them. Deleting a service is in the console's Services.
    if db is not None:
        db.clear_live(room_id)
    socketio.emit('history_cleared', {'room_id': room_id}, room=f'room:{room_id}')
    socketio.emit('history_cleared', {'room_id': room_id}, room=f'admin:{room_id}')
    logger.info(f"[CLEARED] room={room_id} by {_admin_username(request.sid)}")

@socketio.on('import_transcription')
def handle_import_transcription(data):
    """Handle import of transcriptions from JSON file"""
    if not is_admin(request.sid):
        emit('error', {'message': 'Unauthorized'})
        disconnect()
        return

    if not data or not isinstance(data, dict):
        emit('error', {'message': 'Invalid data'})
        return

    # Validate required fields
    required_fields = ['original', 'corrected']
    for field in required_fields:
        if field not in data:
            emit('error', {'message': f'Missing required field: {field}'})
            return

    # Sanitize and prepare import data
    translation_data = {
        'id': data.get('id'),  # Use provided ID if available
        'timestamp': data.get('timestamp', local_now().strftime('%H:%M:%S')),
        'original': sanitize_text(data.get('original', ''), max_length=5000),
        'corrected': sanitize_text(data.get('corrected', ''), max_length=5000),
        'translated': data.get('translated'),
        'is_corrected': data.get('is_corrected', False),
        'source_language': data.get('language', 'imported')[:10],
        'confidence': data.get('confidence', 0.95)
    }

    # Validate after sanitization
    if not translation_data['original'] or not translation_data['corrected']:
        emit('error', {'message': 'Original and corrected text cannot be empty'})
        return

    # Add to history (scoped to admin's room)
    room_id = _admin_room(request.sid)
    add_translation(translation_data, room_id=room_id)

    # Broadcast to clients in the admin's room
    socketio.emit('new_translation', translation_data, room=f'room:{room_id}')
    eventlet.spawn_n(_push_translations, room_id, translation_data)
    socketio.emit('new_translation', translation_data, room=f'admin:{room_id}')
    logger.info(f"[IMPORTED] room={room_id} ID={translation_data['id']} from {_admin_username(request.sid)}")

@socketio.on('delete_items')
def handle_delete_items(data):
    """Handle deletion of multiple items with authorization"""
    if not is_admin(request.sid):
        emit('error', {'message': 'Unauthorized'})
        disconnect()
        return

    if not data or not isinstance(data, dict):
        emit('error', {'message': 'Invalid data'})
        return

    item_ids = data.get('ids', [])
    if not isinstance(item_ids, list):
        emit('error', {'message': 'Invalid IDs format'})
        return

    if not item_ids:
        emit('error', {'message': 'No items to delete'})
        return

    # Scope deletion to the admin's own room
    room_id = _admin_room(request.sid)
    state = _room(room_id)
    original_count = len(state['history'])
    state['history'][:] = [item for item in state['history'] if item.get('id') not in item_ids]
    deleted_count = original_count - len(state['history'])

    # Persist deletion
    if db is not None:
        db.delete_ids(item_ids, room_id=room_id)

    # Broadcast deletion to all connected clients in this room
    socketio.emit('items_deleted', {'ids': item_ids, 'room_id': room_id}, room=f'room:{room_id}')
    socketio.emit('items_deleted', {'ids': item_ids, 'room_id': room_id}, room=f'admin:{room_id}')
    logger.info(f"[DELETED] room={room_id} {deleted_count} item(s) by {_admin_username(request.sid)}")
    emit('deletion_success', {'deleted_count': deleted_count})

# ──────────────────────────────────────────
# Feature 2: Announcement Broadcast
# ──────────────────────────────────────────
@socketio.on('send_announcement')
def handle_send_announcement(data):
    """Broadcast a short announcement to all connected user clients.

    Payload: {text: str, duration: int (ms, 0 = sticky), type: str}
    """
    if not is_admin(request.sid):
        emit('error', {'message': 'Unauthorized'})
        return

    if not data or not isinstance(data, dict):
        emit('error', {'message': 'Invalid data'})
        return

    raw_text = sanitize_text(data.get('text', ''), max_length=300)
    if not raw_text:
        emit('error', {'message': 'Announcement text is empty'})
        return

    duration = int(data.get('duration', 10000))
    # Clamp: 0 = sticky (no auto-dismiss), otherwise 3 s – 5 min
    if duration != 0:
        duration = max(3000, min(300000, duration))

    ann_type = data.get('type', 'info')
    if ann_type not in ('info', 'warning', 'success', 'danger'):
        ann_type = 'info'

    payload = {
        'text':      raw_text,
        'duration':  duration,
        'type':      ann_type,
        'sender':    _admin_username(request.sid),
        'timestamp': local_now().strftime('%H:%M:%S'),
    }
    # Broadcast to clients in the admin's room (skip the sender)
    room_id = _admin_room(request.sid)
    payload['room_id'] = room_id
    socketio.emit('announcement', payload, room=f'room:{room_id}', skip_sid=[request.sid])
    emit('announcement_sent', {'success': True, 'text': raw_text})
    logger.info(f"[ANNOUNCEMENT] room={room_id} '{raw_text[:60]}' by {_admin_username(request.sid)}")


@socketio.on_error_default
def default_error_handler(e):
    """Handle WebSocket errors"""
    security_logger.error(f"WebSocket error from {get_real_ip()}: {str(e)[:200]}")
    disconnect()
