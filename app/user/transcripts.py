"""The listener server: a service's transcript, after the service.

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

A service is a room's lines on one day. Its transcript is a page anyone with
its link can read, in any of the listener page's languages, and print or save
as a PDF from the browser; or a plain text file. The link carries a signature
of the room and the day, made with the server's secret, so it opens that one
service and no other, and needs no sign-in: it is meant to be passed to the
people who were not there. The console lists the services and gives out the
links; only the console can delete one.

Lines already translated during the service, for the screens that were
reading that language, are kept on the line; the rest are translated the
first time the transcript is opened in a language, and kept too.
"""

from app.user.core import *  # noqa: F401,F403  (one namespace, split by subject)

_DAY = re.compile(r'^\d{4}-\d{2}-\d{2}$')
# A new paragraph where the speaker stopped for this long, or after this many
# lines, so the page reads as text rather than as a list of captions.
_PAUSE = 20
_LINES_PER_PARAGRAPH = 6


def _share_key(room_id: str, day: str) -> str:
    msg = f'transcript|{room_id}|{day}'.encode()
    return hmac.new(secret_key.encode(), msg, hashlib.sha256).hexdigest()[:24]


def _key_ok(room_id: str, day: str, key: str) -> bool:
    return bool(key) and hmac.compare_digest(_share_key(room_id, day), key)


def _room_name(room_id: str) -> str:
    if db is not None:
        try:
            for r in db.list_rooms():
                if r.get('room_id') == room_id and r.get('display_name'):
                    return r['display_name']
        except Exception:
            pass
    return _room(room_id).get('display_name') or room_id


def _wanted(lang: str, source_lang: str) -> bool:
    """Whether a line needs translating to be read in `lang`."""
    return bool(lang) and _language_base(lang) != _language_base(source_lang or 'en')


def _fill_translations(room_id: str, lines: list, lang: str) -> None:
    """Translate the lines that have no translation into `lang` yet, or whose
    wording was corrected after it was made, and keep each on its line.

    A service is hundreds of lines, and the first reader in a new language
    asks for all of them: one request a line was enough to have Google's free
    endpoint refuse the server (429), live service and all. So the lines go
    six at a time, one per row of a single request, four requests at once;
    a group that does not come back as as many rows is asked again line by
    line, so nothing is put against the wrong line. A refusal stops the rest:
    the page shows those lines as said, marked, and the next reader's visit
    tries them again, rather than the server asking hundreds more times of a
    service that has said no."""
    service = get_translation_service()
    glossary = _get_glossary_for(room_id, lang)

    def keep(item, text, translated):
        item.setdefault('translations', {})[lang] = {'source': text, 'text': translated}
        if db is not None:
            db.save_line_translation(room_id, item['id'], lang, text, translated)

    refused = []
    done = []

    def ask(text):
        if refused:
            return None
        try:
            ok, translated, _ = service.translate(text, lang, glossary=glossary)
        except Exception as exc:
            logger.warning(f"Transcript translation to {lang} failed: {exc}")
            ok, translated = False, None
        if not ok or not translated:
            refused.append(True)
            return None
        return translated

    def group(items):
        texts = [(it.get('corrected') or it.get('original') or '').replace('\n', ' ') for it in items]
        translated = ask('\n'.join(texts))
        if translated is None:
            return
        rows = [r.strip() for r in translated.split('\n')]
        if len(rows) == len(items) and all(rows):
            for it, row in zip(items, rows):
                keep(it, it.get('corrected') or it.get('original') or '', row)
            done.extend(items)
            return
        for it, text in zip(items, texts):      # the rows did not line up
            one = ask(text)
            if one is None:
                return
            keep(it, it.get('corrected') or it.get('original') or '', one)
            done.append(it)

    todo = []
    for item in lines:
        text = item.get('corrected') or item.get('original') or ''
        have = (item.get('translations') or {}).get(lang) or {}
        if text and _wanted(lang, item.get('source_language')) and have.get('source') != text:
            todo.append(item)
    if todo:
        pool = eventlet.GreenPool(4)
        for k in range(0, len(todo), _LINES_PER_PARAGRAPH):
            pool.spawn_n(group, todo[k:k + _LINES_PER_PARAGRAPH])
        pool.waitall()
        logger.info(f"Transcript {room_id} {lines[0].get('at', '')[:10]}: translated "
                    f"{len(done)} of {len(todo)} line(s) into {lang}"
                    + (" (the translation service refused the rest)" if refused else ""))


# Chinese and Japanese put no space between sentences; everything else here does.
_CJK = re.compile(r'[\u3000-\u303f\u3040-\u30ff\u3400-\u9fff\uf900-\ufaff\uff00-\uffef]')


def _join(parts: list) -> list:
    """What goes before each part when they are run together as a paragraph."""
    seps, prev = [], ''
    for part in parts:
        part = part or ''
        no_space = not prev or _CJK.match(prev[-1:]) or _CJK.match(part[:1])
        seps.append('' if no_space else ' ')
        prev = part or prev
    return seps


def _paragraphs(lines: list, lang: str) -> list:
    """The lines as paragraphs: [{'at': '09:31', 'said': [...], 'read': [...],
    'read_sep': [...], 'said_text': '...'}], a None in `read` being a line the
    translation service did not answer for."""
    out, last = [], None
    for item in lines:
        text = item.get('corrected') or item.get('original') or ''
        if not text:
            continue
        at = item.get('at') or ''
        try:
            when = datetime.fromisoformat(at)
        except ValueError:
            when = None
        tr = (item.get('translations') or {}).get(lang) or {}
        read = tr.get('text') if tr.get('source') == text else None
        if not _wanted(lang, item.get('source_language')):
            read = text
        if (not out or len(out[-1]['said']) >= _LINES_PER_PARAGRAPH
                or (when and last and (when - last).total_seconds() > _PAUSE)):
            out.append({'at': when.strftime('%H:%M') if when else '', 'said': [], 'read': []})
        out[-1]['said'].append(text)
        out[-1]['read'].append(read)
        last = when or last
    for p in out:
        p['read_sep'] = _join([r or s for r, s in zip(p['read'], p['said'])])
        p['said_text'] = ''.join(sep + s for sep, s in zip(_join(p['said']), p['said']))
    return out


def _service_or_404(room_id: str, day: str):
    room_id = normalize_room_id(room_id)
    if not _DAY.match(day or ''):
        return room_id, None
    lines = db.service_lines(room_id, day) if db is not None else []
    return room_id, lines or None


def _lang_arg() -> str:
    lang = (request.args.get('lang') or '').strip().lower()
    return lang if _READING_LANG.match(lang) else ''


@app.route('/transcript/<room_id>/<day>', methods=['GET'])
@limiter.limit("30 per minute")
def transcript_page(room_id, day):
    """A service's transcript, for reading, printing, or saving as a PDF."""
    room_id, lines = _service_or_404(room_id, day)
    key = request.args.get('k', '')
    if lines is None or not _key_ok(room_id, day, key):
        # One answer for both, so a link cannot be used to learn which days
        # a room has services on.
        return render_template('transcript.html', missing=True, room_name='', day=day,
                               lang='', paragraphs=[], key='', room_id=room_id), 404
    spoken = _language_base(lines[0].get('source_language') or 'en')
    lang = _lang_arg() or spoken
    _fill_translations(room_id, lines, lang)
    first = datetime.fromisoformat(lines[0]['at'])
    last = datetime.fromisoformat(lines[-1]['at'])
    return render_template(
        'transcript.html', missing=False, room_id=room_id, room_name=_room_name(room_id),
        day=day, date_iso=first.date().isoformat(),
        first=first.strftime('%H:%M'), last=last.strftime('%H:%M'),
        lang=lang, spoken=spoken, translated=(lang != spoken),
        paragraphs=_paragraphs(lines, lang), lines=len(lines), key=key)


@app.route('/transcript/<room_id>/<day>.txt', methods=['GET'])
@limiter.limit("30 per minute")
def transcript_text(room_id, day):
    """The same transcript as plain text: the translation, then, when it is
    one, what was said."""
    room_id, lines = _service_or_404(room_id, day)
    if lines is None or not _key_ok(room_id, day, request.args.get('k', '')):
        return Response('Not found\n', status=404, mimetype='text/plain')
    spoken = _language_base(lines[0].get('source_language') or 'en')
    lang = _lang_arg() or spoken
    _fill_translations(room_id, lines, lang)
    paras = _paragraphs(lines, lang)
    head = f"{_room_name(room_id)} - {day}\n\n"
    body = "\n\n".join(''.join(sep + (r or s) for sep, r, s in zip(p['read_sep'], p['read'], p['said']))
                       for p in paras)
    if lang != spoken:
        body += "\n\n---\n\n" + "\n\n".join(p['said_text'] for p in paras)
    name = f"transcript-{room_id}-{day}-{lang}.txt"
    return Response(head + body + "\n", mimetype='text/plain; charset=utf-8',
                    headers={'Content-Disposition': f'attachment; filename="{name}"'})


@app.route('/api/transcripts', methods=['GET'])
@limiter.limit("60 per minute")
@require_admin_auth
def list_transcripts():
    """The services the console can share: room, day, from when to when, and
    the link (a path on this server) that opens each."""
    out = []
    for s in (db.services() if db is not None else []):
        rid, day = s['room_id'], s['date']
        if not day or not _DAY.match(day):
            continue
        out.append({
            'room_id': rid, 'room_name': _room_name(rid), 'date': day,
            'lines': s['lines'],
            'first': (s['first'] or '')[11:16], 'last': (s['last'] or '')[11:16],
            'path': f'/transcript/{rid}/{day}?k={_share_key(rid, day)}',
        })
    return jsonify({'success': True, 'services': out})


@app.route('/api/transcripts/<room_id>/<day>', methods=['DELETE'])
@limiter.limit("20 per minute")
@require_admin_auth
def delete_transcript(room_id, day):
    """Delete a service for good: its transcript, and its lines from the live
    screens if they are still there."""
    room_id = normalize_room_id(room_id)
    if not _DAY.match(day or '') or db is None:
        return jsonify({'success': False, 'error': 'invalid'}), 400
    removed = db.delete_service(room_id, day)
    state = _room(room_id)
    gone = [it.get('id') for it in state['history'] if (it.get('at') or '')[:10] == day]
    if gone:
        state['history'][:] = [it for it in state['history'] if it.get('id') not in gone]
        socketio.emit('items_deleted', {'ids': gone, 'room_id': room_id}, room=f'room:{room_id}')
        socketio.emit('items_deleted', {'ids': gone, 'room_id': room_id}, room=f'admin:{room_id}')
    logger.info(f"[TRANSCRIPT DELETED] room={room_id} day={day} lines={removed} "
                f"by {request.user.get('username')}")
    return jsonify({'success': True, 'deleted': removed})
