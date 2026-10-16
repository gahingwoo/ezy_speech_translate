# Moving off eventlet: a plan

Status: planned, not started. Written October 2026, against 4.1.13.

## Why

Both servers run on eventlet: it monkey-patches the standard library into
green threads, serves HTTP with `eventlet.wsgi`, and is Flask-SocketIO's
`async_mode`. eventlet is in maintenance: its own documentation asks
projects to move away, new Python releases are supported late if at all,
and monkey-patching is the kind of thing that breaks quietly (an import
made before the patch leaves a lock or a socket un-greened, and nothing
says so until a deadlock under load).

It is not urgent. eventlet 0.40.3 was checked on Python 3.14 (Ubuntu
26.04's, and GitHub's `ubuntu-latest` from 19 October 2026): `monkey_patch`,
`wsgi.server`, `GreenPool` and `tpool` all work. The Docker and Podman images
pin Python 3.12. The move should be made before a Python release eventlet
does not support becomes what a supported distribution ships.

## What uses it

| Where | What | For |
|---|---|---|
| `app/user/server.py`, `app/admin/server.py` | `monkey_patch()`, `listen`, `wrap_ssl`, `wsgi.server` | serving HTTP(S) and WebSocket |
| `app/user/core.py` | `SocketIO(async_mode='eventlet')` | Socket.IO's transport |
| `app/user/core.py` `_push_translations` | `GreenPool(8)`, `spawn_n` | one line into every language at once |
| `app/user/sockets.py` | `spawn_n` ×3, `sleep` | translation off the event handler; the heartbeat sweep |
| `app/user/server.py` | `spawn` | starting the heartbeat sweep |
| `app/auth/passwords.py` | `tpool.execute` | PBKDF2 off the hub, so a sign-in does not stall everyone |

That is the whole of it: about twenty lines, in five files.

## Where to

**Flask-SocketIO's `threading` mode, with `simple-websocket`, served by
gunicorn's threaded worker** (`gunicorn -w 1 --threads 200`): real threads,
no patching, all maintained. One worker, as Socket.IO needs without sticky
sessions; a church's few hundred listeners are well within one process's
threads. gunicorn takes `--certfile`/`--keyfile` for the self-signed HTTPS
mode.

Considered and not chosen:

- **gevent**: maintained, and the smallest code change (the same calls under
  other names), but monkey-patching all the same, so the reason for moving
  stays.
- **asyncio (ASGI, python-socketio's async server, uvicorn)**: the most
  modern, but every handler and the translation service become `async`;
  a rewrite of both servers, for a load that does not need it.

## The real work: shared state under real threads

With green threads, code ran uninterrupted between I/O calls, so
`_rooms[...]['history'].append(...)` followed by a counter update was, in
practice, atomic. Real threads switch anywhere. Before switching, every
piece of shared mutable state needs a lock or a thread-safe structure:

- the rooms: history, listeners, reading languages, `next_id`
- `admin_sessions`, `sid_to_client_key`, the recording lock
- the rate-limiting and blocked-IP dicts, login attempt counts
- the counters on `S` (`S._total_words += ...` is a read-modify-write)
- caches: the Bible languages, the client-side translation metadata

The translation service already holds a `Lock` for its in-flight map. The
database layer (`app/db.py`) already serialises with `_lock`.

## Steps

Each is shipped on its own, with the Tests workflow (all three ways of
installing) passing.

1. **One place for concurrency.** `app/core/concurrency.py` with `spawn`,
   `sleep`, `pool(n)`, `run_blocking(fn, ...)` and `serve(app, host, port,
   ssl)`; the twenty lines above call it instead of eventlet. Behaviour is
   unchanged: it is eventlet underneath.
2. **Locks.** The audit above, one structure at a time, each with a test
   that hammers it from threads. Harmless under eventlet, needed after.
3. **A threading implementation** of the same module, chosen by
   `EZY_CONCURRENCY=threading` (eventlet stays the default). gunicorn and
   simple-websocket join requirements.txt; the systemd units, the container
   entrypoint and the Quadlet file start gunicorn when it is chosen.
4. **Both in CI.** The Tests matrix gains the concurrency mode, so every
   install way is exercised both ways; a load script (300 Socket.IO clients
   reading two languages, a line a second for ten minutes) is run against
   each, comparing memory, latency to the listener, and errors.
5. **Threading by default**, eventlet still selectable for one release.
6. **eventlet removed**, with the monkey-patching and its import-order rules.

## Done when

No `eventlet` import anywhere; the Tests workflow and the load script pass
on the oldest and newest Python the installer accepts; a service with the
church's usual number of listeners runs a full Sunday without a restart.
