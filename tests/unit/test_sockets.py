"""The listener server's sockets, through Flask-SocketIO's own test client:
a listener counted while connected and forgotten when it goes, a reload
counted once, and a console's microphone freed when the console goes."""
import pytest

from app.user import core
from app.user import sockets  # noqa: F401  (the handlers)


def connect(kind, client_id, room='main'):
    return core.socketio.test_client(
        core.app, query_string=f'type={kind}&client_id={client_id}&room={room}')


@pytest.fixture
def room():
    rid = 'sockets_test'
    yield rid
    core._rooms.pop(rid, None)


def test_a_listener_is_forgotten_when_it_goes(room):
    phone = connect('user', 'phone-1', room)
    assert phone.is_connected()
    assert len(core._room(room)['listeners']) == 1
    phone.disconnect()
    assert core._room(room)['listeners'] == {}
    assert not [m for m in core.sid_to_client_key.values() if m[0] == 'client:phone-1']


def test_a_reload_counts_once_and_its_old_socket_going_leaves_the_new(room):
    first = connect('user', 'phone-2', room)
    second = connect('user', 'phone-2', room)
    assert len(core._room(room)['listeners']) == 1
    first.disconnect()
    assert len(core._room(room)['listeners']) == 1
    second.disconnect()
    assert core._room(room)['listeners'] == {}


def test_a_console_going_frees_its_microphone(room):
    console = connect('admin', 'console-1', room)
    sid = next(s for s, m in core.sid_to_client_key.items() if m[0] == 'client:console-1')
    assert core.claim_recording(room, 'operator', sid) == {}
    console.disconnect()
    assert core._room(room)['recording'] is None
    assert sid not in core.sid_to_client_key
