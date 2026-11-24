"""Everything the servers do at once, in one place.

Copyright (C) 2025-2026 Ga Hing Woo (Jiaxing Hu). AGPL-3.0-or-later; see LICENSE.

Step 1 of docs/EVENTLET_MIGRATION.md: the servers ask this module, not
eventlet, to start a task, wait, run several things together, run a blocking
call off the event loop, and serve. Underneath it is still eventlet, so
nothing behaves differently; moving to threads is then a change here, not in
twenty places. The monkey-patching itself stays at the top of the two
servers, because it has to happen before anything else is imported.
"""
from __future__ import annotations

from typing import Any, Callable, Iterable

import eventlet
import eventlet.wsgi
from eventlet import tpool

# What Flask-SocketIO is told to use.
ASYNC_MODE = 'eventlet'


def spawn(fn: Callable, *args: Any, **kwargs: Any):
    """Start fn in the background; returns a handle."""
    return eventlet.spawn(fn, *args, **kwargs)


def spawn_n(fn: Callable, *args: Any, **kwargs: Any) -> None:
    """Start fn in the background, with nothing kept to wait on."""
    eventlet.spawn_n(fn, *args, **kwargs)


def sleep(seconds: float) -> None:
    """Wait without holding up anything else."""
    eventlet.sleep(seconds)


def run_all(fn: Callable, items: Iterable, size: int) -> None:
    """fn(item) for every item, `size` at a time, returning when all are done."""
    pool = eventlet.GreenPool(size)
    for item in items:
        pool.spawn_n(fn, item)
    pool.waitall()


def run_blocking(fn: Callable, *args: Any):
    """A call that holds the CPU (a password hash), on a real thread, so the
    event loop goes on serving everyone else meanwhile."""
    return tpool.execute(fn, *args)


def serve(app, host: str, port: int, *, certfile: str | None = None,
          keyfile: str | None = None, backlog: int = 50, max_size: int = 1024) -> None:
    """Serve app on host:port until stopped, over TLS when given a
    certificate. `backlog` is how many connections may wait to be accepted
    (a room reconnecting at once); `max_size`, how many are served together.
    Raises what binding raises (PermissionError, OSError)."""
    sock = eventlet.listen((host, port), backlog=backlog)
    if certfile and keyfile:
        sock = eventlet.wrap_ssl(sock, certfile=certfile, keyfile=keyfile, server_side=True)
    eventlet.wsgi.server(sock, app, max_size=max_size)
