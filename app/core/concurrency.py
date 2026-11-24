"""Everything the servers do at once, in one place.

Copyright (C) 2025-2026 Ga Hing Woo (Jiaxing Hu). AGPL-3.0-or-later; see LICENSE.

The servers ask this module, not eventlet or threading, to start a task,
wait, run several things together, run a blocking call off the event loop,
and serve. docs/EVENTLET_MIGRATION.md has the plan; this is steps 1 and 3.

Two ways underneath, chosen by EZY_CONCURRENCY:

  eventlet   (the default) green threads, the standard library monkey-patched
             at the top of each server, served by eventlet.wsgi. As every
             release before 4.2.13.
  threading  real threads, nothing patched, served by gunicorn's threaded
             worker in this same process, with simple-websocket for
             Socket.IO's WebSocket. The live state is locked for it (step 2).

The patching itself happens at the top of the two servers, before anything
else is imported, and reads EZY_CONCURRENCY the same way (mode_from below):
importing this module first would import the config, and with it half the
standard library, unpatched.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Callable, Iterable

_log = logging.getLogger(__name__)

MODES = ('eventlet', 'threading')


def mode_from(environ=os.environ) -> str:
    """EZY_CONCURRENCY, or eventlet when it is not set."""
    return (environ.get('EZY_CONCURRENCY') or 'eventlet').strip().lower()


MODE = mode_from()
if MODE not in MODES:
    raise SystemExit(f"EZY_CONCURRENCY is {MODE!r}; it can be {' or '.join(MODES)}")

# What Flask-SocketIO is told to use.
ASYNC_MODE = MODE

if MODE == 'eventlet':
    import eventlet
    import eventlet.wsgi
    from eventlet import tpool
else:
    import threading
    import time
    from concurrent.futures import ThreadPoolExecutor

# gunicorn runs the app in a worker process forked from this one, and threads
# do not cross a fork: a task started before serving would be left behind in
# the parent. So under threading, tasks started before serve() wait for the
# worker and start there.
_waiting: list = []
_serving = MODE == 'eventlet'


def spawn(fn: Callable, *args: Any, **kwargs: Any):
    """Start fn in the background; returns a handle (None under threading
    until the server is serving)."""
    if MODE == 'eventlet':
        return eventlet.spawn(fn, *args, **kwargs)
    if not _serving:
        _waiting.append((fn, args, kwargs))
        return None
    thread = threading.Thread(target=fn, args=args, kwargs=kwargs, daemon=True)
    thread.start()
    return thread


def spawn_n(fn: Callable, *args: Any, **kwargs: Any) -> None:
    """Start fn in the background, with nothing kept to wait on."""
    if MODE == 'eventlet':
        eventlet.spawn_n(fn, *args, **kwargs)
    else:
        spawn(fn, *args, **kwargs)


def sleep(seconds: float) -> None:
    """Wait without holding up anything else."""
    if MODE == 'eventlet':
        eventlet.sleep(seconds)
    else:
        time.sleep(seconds)


def run_all(fn: Callable, items: Iterable, size: int) -> None:
    """fn(item) for every item, `size` at a time, returning when all are done.
    An item that fails is logged; the others go on."""
    if MODE == 'eventlet':
        pool = eventlet.GreenPool(size)
        for item in items:
            pool.spawn_n(fn, item)
        pool.waitall()
        return
    with ThreadPoolExecutor(max_workers=size, thread_name_prefix='run_all') as pool:
        for future in [pool.submit(fn, item) for item in items]:
            exc = future.exception()
            if exc is not None:
                _log.warning('run_all: %s failed: %r', getattr(fn, '__name__', fn), exc)


def run_blocking(fn: Callable, *args: Any):
    """A call that holds the CPU (a password hash) without holding up the
    others: on a real thread under eventlet; under threading it already is."""
    if MODE == 'eventlet':
        return tpool.execute(fn, *args)
    return fn(*args)


def _start_waiting() -> None:
    global _serving
    _serving = True
    while _waiting:
        fn, args, kwargs = _waiting.pop(0)
        spawn(fn, *args, **kwargs)


def serve(app, host: str, port: int, *, certfile: str | None = None,
          keyfile: str | None = None, backlog: int = 50, max_size: int = 1024) -> None:
    """Serve app on host:port until stopped, over TLS when given a
    certificate. `backlog` is how many connections may wait to be accepted
    (a room reconnecting at once); `max_size`, how many are served together.
    Raises what binding raises (PermissionError, OSError)."""
    if MODE == 'eventlet':
        sock = eventlet.listen((host, port), backlog=backlog)
        if certfile and keyfile:
            sock = eventlet.wrap_ssl(sock, certfile=certfile, keyfile=keyfile, server_side=True)
        eventlet.wsgi.server(sock, app, max_size=max_size)
        return
    _gunicorn(app, host, port, certfile=certfile, keyfile=keyfile,
              backlog=backlog, max_size=max_size)


def _gunicorn(app, host, port, *, certfile, keyfile, backlog, max_size) -> None:
    import socket
    from gunicorn.app.base import BaseApplication

    # gunicorn says a port in use only in its log and then exits; this
    # server's callers expect the OSError, as eventlet raises it.
    probe = socket.socket(socket.AF_INET6 if ':' in host else socket.AF_INET)
    try:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        probe.bind((host, port))
    finally:
        probe.close()

    # One worker: Socket.IO keeps each client's session in the process that
    # has it, and with no sticky sessions a second worker would not. In it,
    # a thread for each connection served at once, since a WebSocket holds
    # its thread for as long as the page is open.
    options = {
        'bind': f'[{host}]:{port}' if ':' in host else f'{host}:{port}',
        'workers': 1,
        'worker_class': 'gthread',
        'threads': max_size,
        # More than threads, or gunicorn keeps no connection alive between
        # requests (a page's assets, each on a connection of its own).
        'worker_connections': max_size + 1024,
        'backlog': backlog,
        # The worker tells the parent it is alive from its own main loop,
        # which a long request does not hold up; this is for a worker that
        # has truly hung.
        'timeout': 120,
        # On a stop, how long requests in hand get to finish. An open
        # WebSocket never finishes, so this is how long a stop takes while a
        # phone is listening; the phones reconnect to the new server by
        # themselves. Within Podman's ten seconds and Docker's fifteen.
        # (gunicorn then logs that it killed the worker, "Perhaps out of
        # memory?": it is not.)
        'graceful_timeout': 3,
        'keepalive': 5,
        'accesslog': '-',
        'errorlog': '-',
        'post_worker_init': lambda worker: _start_waiting(),
    }
    if certfile and keyfile:
        options.update(certfile=certfile, keyfile=keyfile)

    class _Server(BaseApplication):
        def load_config(self):
            for key, value in options.items():
                self.cfg.set(key, value)

        def load(self):
            return app

    _log.info('Serving with real threads (gunicorn gthread, up to %d at once) on %s:%d',
              max_size, host, port)
    _Server().run()
