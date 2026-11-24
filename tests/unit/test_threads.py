"""The live state, hammered from real threads: what step 2 of
docs/EVENTLET_MIGRATION.md makes safe before the servers stop running on
green threads.

Under eventlet, code ran uninterrupted between one wait and the next, so a
line's number and its place in the room were in practice set together. Real
threads switch anywhere; these tests switch them as often as Python allows
and check that nothing is lost, doubled or left half-done.

They import the listener server's state in a plain process, with no
monkey-patching, so threading here is real threads, as it will be."""
import sys
import threading
from contextlib import contextmanager

import pytest

from app.user import core

THREADS = 8


@contextmanager
def switching_often():
    before = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    try:
        yield
    finally:
        sys.setswitchinterval(before)


def together(fn, n=THREADS):
    """fn(k) on n threads, started at the same moment; re-raises the first
    exception any of them met."""
    start, errors = threading.Barrier(n), []

    def run(k):
        try:
            start.wait()
            fn(k)
        except BaseException as exc:          # noqa: BLE001 - reported below
            errors.append(exc)

    threads = [threading.Thread(target=run, args=(k,)) for k in range(n)]
    with switching_often():
        for t in threads:
            t.start()
        for t in threads:
            t.join()
    if errors:
        raise errors[0]


@pytest.fixture
def room(request):
    """A room of its own for each test, and analytics counted from nought."""
    rid = 'hammer_' + request.node.name.replace('[', '_').replace(']', '')[:40]
    for name in ('_total_words', '_session_lines', '_total_bible_refs', '_total_translations'):
        setattr(core.S, name, 0)
    yield rid
    core._rooms.pop(rid, None)


def test_every_line_has_its_own_number_and_place(room):
    per_thread = 300

    def say(k):
        for n in range(per_thread):
            core.add_translation({'original': f'{k} {n}', 'corrected': f'{k} {n}'}, room)

    together(say)
    history = core.history_snapshot(room)
    ids = [item['id'] for item in history]
    total = THREADS * per_thread
    expected = min(total, core.MAX_HISTORY_SIZE)
    assert len(ids) == len(set(ids)) == expected
    assert core._room(room)['next_id'] == total
    # The newest lines are the ones kept, in the order they were numbered.
    assert ids == sorted(ids) and ids[-1] == total - 1
    if core.ANALYTICS_ENABLED:
        assert core.S._session_lines == total
        assert core.S._total_words == total * 2


def test_counting_a_translation_loses_none():
    core.S._total_translations = 0

    def count(_k):
        for _ in range(2000):
            core.count_translation()

    together(count)
    assert core.S._total_translations == THREADS * 2000


def test_reading_the_rooms_while_they_are_made(room):
    def make(k):
        for n in range(200):
            core._room(f'{room}_{k}_{n}')

    def count(_k):
        for _ in range(400):
            core._all_listener_count()
            core._all_history_count()
            core.rooms_snapshot()

    try:
        together(lambda k: make(k) if k % 2 else count(k))
    finally:
        for rid in [r for r in list(core._rooms) if r.startswith(room)]:
            core._rooms.pop(rid, None)


def test_failed_sign_ins_block_at_the_limit_exactly():
    key = 'client:hammer-logins'
    core.failed_login_attempts.pop(key, None)
    core.blocked_clients.discard(key)
    blocked = []

    def fail(_k):
        for _ in range(50):
            if core.record_failed_login(key):
                blocked.append(1)

    try:
        together(fail)
        assert core.is_client_blocked(key)
        # Every attempt counted, in the window, none lost.
        assert len(core.failed_login_attempts[key]) == THREADS * 50
    finally:
        core.failed_login_attempts.pop(key, None)
        core.blocked_clients.discard(key)
        core.blocked_since.pop(key, None)


def test_rate_violations_and_suspicious_activity_are_all_counted():
    key = 'client:hammer-rate'

    def violate(_k):
        for _ in range(500):
            core.record_rate_violation(key)
            core.record_suspicious_activity('hammer', key)

    try:
        together(violate)
        assert core.rate_limit_violations[key] == THREADS * 500
        assert core.suspicious_patterns[key] == THREADS * 500
    finally:
        for table in (core.rate_limit_violations, core.suspicious_patterns, core.blocked_since):
            table.pop(key, None)
        core.blocked_clients.discard(key)


def test_api_tokens_made_checked_and_dropped_together():
    def churn(k):
        for n in range(300):
            sid = f'hammer-sid-{k}-{n}'
            token = core.create_api_token(sid)
            assert core.validate_api_token(token)['sid'] == sid
            core.drop_api_tokens(sid)
            assert core.validate_api_token(token) is None

    together(churn)


def test_listeners_joining_and_leaving_add_up(room):
    per_thread = 200

    def come_and_go(k):
        for n in range(per_thread):
            sid = f'{room}-{k}-{n}'
            core.listener_joined(room, f'client:{k}-{n}', sid, 'user')
            core.set_reading(sid, room, 'zh' if n % 2 else 'yue')
            core.heartbeat(sid)
            core._all_listener_count()
            if n % 3:
                core.client_left(sid)

    together(come_and_go)
    state = core._room(room)
    stayed = sum(1 for n in range(per_thread) if not n % 3) * THREADS
    assert len(state['listeners']) == stayed
    assert len(state['reading']) == stayed
    assert {sid for sid in state['listeners'].values()} == set(state['reading'])
    for sid in list(state['listeners'].values()):
        core.client_left(sid)
    assert not state['listeners'] and not state['reading']


def test_a_listener_reconnecting_on_two_sockets_at_once_is_counted_once(room):
    key = 'client:the-same-phone'

    def reconnect(k):
        for n in range(200):
            core.listener_joined(room, key, f'{room}-sid-{k}-{n}', 'user')

    together(reconnect)
    state = core._room(room)
    assert list(state['listeners']) == [key]
    live = state['listeners'][key]
    # Only the socket the room counts is still known; the rest were evicted.
    known = [sid for sid, m in core.sid_to_client_key.items() if m[0] == key]
    assert known == [live]
    core.client_left(live)


def test_a_heartbeat_sweep_while_listeners_come_and_go(room):
    def come_and_go(k):
        for n in range(300):
            sid = f'{room}-hb-{k}-{n}'
            core.listener_joined(room, f'client:hb-{k}-{n}', sid, 'user')
            core.heartbeat(sid)
            core.client_left(sid)

    def sweep(_k):
        for _ in range(300):
            core.stale_sids(timeout=-1)

    together(lambda k: come_and_go(k) if k % 2 else sweep(k))
    assert not core._room(room)['listeners']


def test_only_one_console_gets_the_microphone(room):
    winners = []

    def claim(k):
        if core.claim_recording(room, f'operator{k}', f'sid{k}') is not None:
            winners.append(k)

    together(claim)
    assert len(winners) == 1
    assert core._room(room)['recording']['username'] == f'operator{winners[0]}'


def test_deleting_lines_while_lines_are_said(room):
    def say(_k):
        for n in range(200):
            core.add_translation({'original': f'line {n}'}, room)

    def delete(_k):
        for _ in range(200):
            ids = [item['id'] for item in core.history_snapshot(room)[:3]]
            core.remove_lines(room, ids)

    together(lambda k: say(k) if k % 2 else delete(k))
    ids = [item['id'] for item in core.history_snapshot(room)]
    assert len(ids) == len(set(ids))
