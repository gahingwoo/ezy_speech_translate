#!/usr/bin/env python3
"""Smoke test: an installed EzySpeech, from the outside, as people use it.

    check.py live --password PW [--say TEXT]
        both servers healthy and on the version in VERSION; the listener page
        served; a wrong password refused and the right one taking; a line said
        on the console reaching a listener, translated. Translation is
        expected from the echo provider (EZY_TRANSLATION_PROVIDERS=echo):
        "[zh] TEXT", with nothing sent off the machine.

    check.py history --has TEXT [--has-not TEXT]
        what the transcript holds, as a listener's page loads it.

Needs requests and python-socketio's client, both in requirements.txt, so
the installed release's own Python runs it. Exits non-zero, saying what was
wrong, on the first thing that is.

Copyright (C) 2025-2026 Ga Hing Woo (Jiaxing Hu)
This file is part of EzySpeech, and is free software under the GNU Affero
General Public License, version 3 or later. See LICENSE and TRADEMARK.md.
"""

import argparse
import hashlib
import pathlib
import queue
import sys
import time

import requests
import socketio

ROOT = pathlib.Path(__file__).resolve().parents[2]


def fail(message):
    print(f'FAIL: {message}')
    sys.exit(1)


def ok(message):
    print(f'ok    {message}')


def wait_for(q, what, timeout=20, match=lambda d: True):
    """The next event on q that matches, or a failure naming it."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            data = q.get(timeout=max(0.1, deadline - time.time()))
        except queue.Empty:
            break
        if match(data):
            return data
    fail(f'no {what} within {timeout}s')


def listener(base, lang=None):
    """A listener's page: connected, reading lang, its events on queues."""
    events = {name: queue.Queue() for name in ('ready', 'new_translation', 'line_translated')}
    sio = socketio.Client(reconnection=False)
    for name, q in events.items():
        sio.on(name, lambda data, q=q: q.put(data))
    sio.connect(f'{base}:{ARGS.port}?type=user&client_id=smoke-{time.time_ns()}&room=main',
                transports=['websocket', 'polling'])
    ready = wait_for(events['ready'], 'ready from the listener server')
    if lang:
        sio.emit('reading_language', {'lang': lang})
    return sio, events, ready


def live():
    base = ARGS.base
    version = (ROOT / 'VERSION').read_text().strip()

    for port, path, name in ((ARGS.port, '/api/health', 'listener server'),
                             (ARGS.admin_port, '/health', 'console server')):
        try:
            r = requests.get(f'{base}:{port}{path}', timeout=5, verify=False)  # nosec B501
        except requests.RequestException as exc:
            fail(f'{name} not answering: {exc}')
        if r.status_code != 200:
            fail(f'{name} health is {r.status_code}')
        got = r.json().get('version')
        if got != version:
            fail(f'{name} is on {got}, expected {version}')
        ok(f'{name} healthy, {version}')

    r = requests.get(f'{base}:{ARGS.port}/', timeout=5, verify=False)  # nosec B501
    if r.status_code != 200 or f'data-version="{version}"' not in r.text:
        fail(f'listener page: {r.status_code}, version {"found" if version in r.text else "missing"}')
    ok('listener page served')

    def login(password):
        return requests.post(f'{base}:{ARGS.admin_port}/api/login', timeout=10, verify=False,  # nosec B501
                             json={'username': ARGS.user,
                                   'password_hash': hashlib.sha256(password.encode()).hexdigest()})

    r = login(ARGS.password + '-wrong')
    if r.status_code != 401:
        fail(f'a wrong password gave {r.status_code}, not 401')
    ok('wrong password refused')
    r = login(ARGS.password)
    if r.status_code != 200 or not r.json().get('token'):
        fail(f'the right password gave {r.status_code}: {r.text[:200]}')
    token = r.json()['token']
    ok('admin signed in')

    reader, events, _ = listener(base, lang='zh')

    admin_events = queue.Queue()
    admin = socketio.Client(reconnection=False)
    admin.on('admin_connected', lambda d: admin_events.put(d))
    admin.connect(f'{base}:{ARGS.port}?type=admin&client_id=smoke-admin',
                  transports=['websocket', 'polling'])
    admin.emit('admin_connect', {'token': token, 'room': 'main'})
    got = wait_for(admin_events, 'admin_connected')
    if not got.get('success'):
        fail(f'the console was refused: {got}')
    ok('console connected')

    admin.emit('new_transcription', {'text': ARGS.say, 'is_final': True, 'language': 'en-US',
                                     'temp_id': 'smoke'})
    line = wait_for(events['new_translation'], 'the line at the listener',
                    match=lambda d: d.get('original') == ARGS.say)
    ok(f'listener got the line (id {line.get("id")})')
    done = wait_for(events['line_translated'], 'its translation', timeout=40,
                    match=lambda d: d.get('source') == ARGS.say)
    expected = f'[zh] {ARGS.say}'
    if done.get('translated') != expected:
        fail(f'translated {done.get("translated")!r}, expected {expected!r}')
    ok('listener got its translation')

    # The service's transcript: listed for the console, opened by its link,
    # with the translation the listener was sent, and not without the link.
    r = requests.get(f'{base}:{ARGS.port}/api/transcripts', timeout=10, verify=False,  # nosec B501
                     headers={'Authorization': 'Bearer ' + token})
    services = r.json().get('services', []) if r.status_code == 200 else []
    service = next((s for s in services if s.get('room_id') == 'main'), None)
    if not service:
        fail(f'no transcript for the service: {r.status_code} {r.text[:200]}')
    page = requests.get(f'{base}:{ARGS.port}{service["path"]}&lang=zh', timeout=30,
                        verify=False)  # nosec B501
    if page.status_code != 200 or expected not in page.text:
        fail(f'the transcript page: {page.status_code}, line {"found" if expected in page.text else "missing"}')
    ok(f'transcript of {service["date"]} opens by its link, translated')
    wrong = requests.get(f'{base}:{ARGS.port}/transcript/main/{service["date"]}?k=0', timeout=10,
                         verify=False)  # nosec B501
    if wrong.status_code != 404:
        fail(f'a transcript opened with a wrong link: {wrong.status_code}')
    ok('transcript refused without its link')

    admin.disconnect()
    reader.disconnect()


def history():
    reader, _, ready = listener(ARGS.base)
    r = requests.get(f'{ARGS.base}:{ARGS.port}/api/translations', timeout=10, verify=False,  # nosec B501
                     params={'room': 'main', 'limit': 1000},
                     headers={'Authorization': 'Bearer ' + ready['api_token']})
    reader.disconnect()
    if r.status_code != 200:
        fail(f'history: {r.status_code}')
    texts = {t.get('original') for t in r.json().get('translations', [])}
    for t in ARGS.has:
        if t not in texts:
            fail(f'history is missing {t!r}')
        ok(f'history has {t!r}')
    for t in ARGS.has_not:
        if t in texts:
            fail(f'history still has {t!r}')
        ok(f'history no longer has {t!r}')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    p.add_argument('--base', default='http://127.0.0.1')
    p.add_argument('--port', type=int, default=1915)
    p.add_argument('--admin-port', type=int, default=1916)
    sub = p.add_subparsers(dest='what', required=True)
    s = sub.add_parser('live')
    s.add_argument('--user', default='admin')
    s.add_argument('--password', required=True)
    s.add_argument('--say', default='Grace and peace to you')
    s = sub.add_parser('history')
    s.add_argument('--has', action='append', default=[])
    s.add_argument('--has-not', action='append', default=[])
    ARGS = p.parse_args()
    requests.packages.urllib3.disable_warnings()
    {'live': live, 'history': history}[ARGS.what]()
    print('passed')
