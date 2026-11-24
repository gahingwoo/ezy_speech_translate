"""ops/ezyspeech's concurrency setting: where each kind of install keeps it,
and the native units' Environment line."""
import importlib.machinery
import importlib.util
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parents[2] / 'ops' / 'ezyspeech'


@pytest.fixture(scope='module')
def ops():
    loader = importlib.machinery.SourceFileLoader('ezyspeech_tool', str(TOOL))
    spec = importlib.util.spec_from_loader('ezyspeech_tool', loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def native(**more):
    return {'mode': 'native', 'home': '/opt/ezyspeech', 'state': '/var/lib/ezyspeech',
            'user': 'ezyspeech', **more}


def test_native_units_say_eventlet_unless_told(ops):
    for body in ops.native_units(native()).values():
        assert 'Environment=EZY_CONCURRENCY=eventlet\n' in body
    for body in ops.native_units(native(concurrency='threading')).values():
        assert 'Environment=EZY_CONCURRENCY=threading\n' in body


def test_a_value_it_does_not_know_is_read_as_the_default(ops):
    assert ops.concurrency_of(native(concurrency='gevent')) == 'eventlet'


def test_docker_reads_and_writes_it_in_env(ops, tmp_path):
    conf = {'mode': 'docker', 'home': str(tmp_path)}
    (tmp_path / '.env').write_text('EZY_PORT=1915\n')
    assert ops.concurrency_of(conf) == 'eventlet'
    ops.set_concurrency(conf, 'threading')
    assert ops.concurrency_of(conf) == 'threading'
    assert 'EZY_PORT=1915' in (tmp_path / '.env').read_text()
    with pytest.raises(ops.Fail):
        ops.set_concurrency(conf, 'gevent')
