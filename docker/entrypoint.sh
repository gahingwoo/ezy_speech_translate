#!/bin/bash
# EzySpeech container entrypoint.
#
#   ezyspeech serve              both servers (the default)
#   ezyspeech init               prepare the volume and exit
#   ezyspeech password [new]     set the admin password (a new one if not given)
#
# Copyright (C) 2025-2026 Ga Hing Woo (Jiaxing Hu)
# This file is part of EzySpeech, and is free software under the GNU Affero
# General Public License, version 3 or later. See LICENSE and TRADEMARK.md.
set -euo pipefail
cd /app

case "${1:-serve}" in
  init)
    exec python docker/init.py
    ;;
  password)
    shift
    exec python docker/init.py password "$@"
    ;;
  serve)
    python docker/init.py

    python app/user/server.py & user=$!
    python app/admin/server.py & admin=$!

    # Docker sends TERM to this script; pass it on, so a stop lets both
    # servers close their sockets instead of being killed ten seconds later.
    stop() { kill -TERM "$user" "$admin" 2>/dev/null || true; }
    trap stop TERM INT

    # Two servers, one container: if either goes down the container goes
    # down, and the restart policy brings back both. A console with no
    # transcript server behind it, or the reverse, is worse than a restart.
    status=0
    wait -n "$user" "$admin" || status=$?
    stop
    wait || true
    exit "$status"
    ;;
  *)
    exec "$@"
    ;;
esac
