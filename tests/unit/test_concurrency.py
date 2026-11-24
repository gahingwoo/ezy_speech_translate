"""app/core/concurrency.py, each way, in a process of its own (the mode is
read once, at import): what it runs, and that threading needs no eventlet."""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def run(mode, code):
    env = {**os.environ, 'PYTHONPATH': str(ROOT)}
    env.pop('EZY_CONCURRENCY', None)
    if mode is not None:
        env['EZY_CONCURRENCY'] = mode
    r = subprocess.run([sys.executable, '-c', code], env=env, cwd=ROOT,
                       capture_output=True, text=True, timeout=60)
    # Only the lines the code printed (importing the config prints its own)
    r.said = [line[2:] for line in r.stdout.splitlines() if line.startswith('@ ')]
    return r


EXERCISE = """
import sys, threading
from app.core import concurrency as c
say = lambda *a: print('@', *a)
say(c.MODE, c.ASYNC_MODE)
done = []
c.run_all(lambda n: done.append(n * n), range(20), 4)
say(sorted(done) == [n * n for n in range(20)])
say(c.run_blocking(lambda a, b: a + b, 2, 3))
c.run_all(lambda n: 1 / n, [1, 0, 2], 2)        # one fails, the others run
c.sleep(0.01)
"""


def test_eventlet_is_the_default():
    r = run(None, EXERCISE)
    assert r.returncode == 0, r.stderr
    assert r.said == ['eventlet eventlet', 'True', '5']


def test_threading_runs_the_same_without_eventlet():
    r = run('threading', EXERCISE + "say('eventlet' in sys.modules)\n")
    assert r.returncode == 0, r.stderr
    assert r.said == ['threading threading', 'True', '5', 'False']


def test_under_threading_a_task_started_before_serving_waits_for_the_worker():
    r = run('threading', """
import threading
from app.core import concurrency as c
say = lambda *a: print('@', *a)
ran = threading.Event()
c.spawn(ran.set)
say(ran.wait(0.2))
c._start_waiting()                  # what gunicorn's worker does on starting
say(ran.wait(5))
later = threading.Event()
c.spawn_n(later.set)                # once serving, at once
say(later.wait(5))
""")
    assert r.returncode == 0, r.stderr
    assert r.said == ['False', 'True', 'True']


def test_a_mode_it_does_not_know_is_refused():
    r = run('gevent', 'from app.core import concurrency')
    assert r.returncode != 0 and 'EZY_CONCURRENCY' in r.stderr
