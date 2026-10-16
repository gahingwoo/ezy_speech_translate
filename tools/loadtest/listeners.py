"""Load test: N listeners reading two languages, a speaker talking.

Copyright (C) 2025-2026 Ga Hing Woo (Jiaxing Hu). AGPL-3.0-or-later; see LICENSE.

Run it from another machine against a test install whose translation
provider is "echo", so it measures EzySpeech and not the provider:

  python3 -m venv /tmp/lt && /tmp/lt/bin/pip install "python-socketio[asyncio_client]" aiohttp
  ulimit -n 20000
  /tmp/lt/bin/python tools/loadtest/listeners.py http://HOST ADMIN_PASSWORD "300:600,1000:120"

usage: listeners.py BASE PASSWORD PLAN
  PLAN  "300:600,600:120"  = grow to 300 listeners and hold 600 s, then 600 for 120 s
Speaker: every 3 s a line, three interim updates 0.4 s apart, then final.
Measures, per phase: time from the speaker sending to a listener receiving
(interim and translated line), lines a listener never got, disconnects.
"""
import asyncio, hashlib, json, sys, time
import aiohttp, socketio

BASE, PASSWORD, PLAN = sys.argv[1], sys.argv[2], sys.argv[3]
LANGS = ['zh', 'es']
now_ms = lambda: time.time() * 1000


class Stats:
    def __init__(self):
        self.reset()

    def reset(self):
        self.interim, self.line = [], []
        self.disconnects = self.connect_fail = 0
        self.finals = 0
        self.got = {}                        # client -> lines received this phase


stats = Stats()
clients = []


async def listener(i, session):
    sio = socketio.AsyncClient(reconnection=True, http_session=session)
    lang = LANGS[i % len(LANGS)]
    cid = f'lt{i}'

    @sio.on('realtime_transcription')
    async def _interim(d):
        try:
            stats.interim.append(now_ms() - float(d['text'].rsplit('t=', 1)[1]))
        except Exception:
            pass

    @sio.on('line_translated')
    async def _line(d):
        try:
            sent = float((d.get('source') or '').rsplit('t=', 1)[1])
        except Exception:
            return
        if d.get('translated'):
            stats.line.append(now_ms() - sent)
            stats.got[cid] = stats.got.get(cid, 0) + 1

    @sio.on('disconnect')
    async def _gone(*_):
        stats.disconnects += 1

    @sio.on('connect')
    async def _hello():
        await sio.emit('reading_language', {'lang': lang})

    try:
        await sio.connect(f'{BASE}:1915?type=user&client_id={cid}&room=main', transports=['websocket'],
                          wait_timeout=20)
    except Exception:
        stats.connect_fail += 1
        return
    clients.append(sio)
    while True:                              # as the page does
        await asyncio.sleep(15)
        if sio.connected:
            try:
                await sio.emit('heartbeat')
            except Exception:
                pass


async def speaker(session):
    async with session.post(f'{BASE}:1916/api/login', json={
            'username': 'admin', 'password_hash': hashlib.sha256(PASSWORD.encode()).hexdigest()}) as r:
        tok = (await r.json())['token']
    sio = socketio.AsyncClient(http_session=session)
    await sio.connect(f'{BASE}:1915?type=admin&client_id=lt-speaker', transports=['websocket'])
    await sio.emit('admin_connect', {'token': tok, 'room': 'main'})
    await asyncio.sleep(1)
    n = 0
    while True:
        n += 1
        words = f'Line {n} of the sermon, about grace and peace to you all'.split()
        for k in (3, 6, 9):
            await sio.emit('new_transcription', {'text': ' '.join(words[:k]) + f' t={now_ms():.0f}',
                                                 'is_final': False, 'language': 'en-US', 'temp_id': f'l{n}'})
            await asyncio.sleep(0.4)
        await sio.emit('new_transcription', {'text': ' '.join(words) + f' t={now_ms():.0f}',
                                             'is_final': True, 'language': 'en-US', 'temp_id': f'l{n}'})
        stats.finals += 1
        await asyncio.sleep(1.8)


def pct(xs, p):
    if not xs:
        return None
    xs = sorted(xs)
    return round(xs[min(len(xs) - 1, int(len(xs) * p))])


async def main():
    conn = aiohttp.TCPConnector(limit=0)
    session = aiohttp.ClientSession(connector=conn)
    tasks = [asyncio.create_task(speaker(session))]
    made = 0
    for phase in PLAN.split(','):
        target, secs = (int(x) for x in phase.split(':'))
        t0 = time.time()
        while made < target:                 # join at about 50 a second
            tasks.append(asyncio.create_task(listener(made, session)))
            made += 1
            if made % 10 == 0:
                await asyncio.sleep(0.2)
        await asyncio.sleep(8)               # let them settle before measuring
        stats.reset()
        await asyncio.sleep(secs)
        connected = sum(1 for c in clients if c.connected)
        expected = stats.finals * connected
        received = sum(stats.got.values())
        print(json.dumps({
            'listeners': target, 'connected': connected, 'held_s': secs,
            'join_s': round(time.time() - t0 - secs - 8, 1),
            'lines_sent': stats.finals,
            'lines_missed_pct': round(100 * (1 - received / expected), 2) if expected else None,
            'interim_ms_p50_p95_p99_max': [pct(stats.interim, p) for p in (.5, .95, .99)] + [round(max(stats.interim)) if stats.interim else None],
            'line_ms_p50_p95_p99_max': [pct(stats.line, p) for p in (.5, .95, .99)] + [round(max(stats.line)) if stats.line else None],
            'disconnects': stats.disconnects, 'connect_fail': stats.connect_fail,
        }), flush=True)
    for t in tasks:
        t.cancel()
    await session.close()

asyncio.run(main())
