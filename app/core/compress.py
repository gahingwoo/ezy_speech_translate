"""Gzip for what the servers send as text.

Nothing compressed anything. A listener opening the page for the first time
was sent 2.2MB of stylesheet and script, 1.5MB of it PatternFly's stylesheet,
and gzipped the same files are a seventh of that. It matters most at the
worst moment: the start of a service, when the room scans the code together
and every phone fetches it at once over the same Wi-Fi.

Static files are compressed once and kept, keyed by their modification time,
so an edited file is compressed again and an unchanged one never is. Pages
and API answers are compressed as they go out. Socket.IO is left alone.

Copyright (C) 2025-2026 Ga Hing Woo (Jiaxing Hu)

This file is part of EzySpeech, and is free software under the GNU Affero
General Public License, version 3 or later. See LICENSE and TRADEMARK.md.
"""

import gzip
import os

from flask import request
from werkzeug.security import safe_join

COMPRESSIBLE = {
    'text/html', 'text/css', 'text/plain', 'text/javascript',
    'application/javascript', 'application/json', 'image/svg+xml',
}

# Below this the headers cost about as much as the saving.
MIN_BYTES = 1024

_static_cache = {}      # absolute path -> (mtime_ns, size, gzipped bytes)


def _wants_gzip():
    return 'gzip' in request.headers.get('Accept-Encoding', '').lower()


def _mark(response, body):
    response.set_data(body)
    response.headers['Content-Encoding'] = 'gzip'
    # Another encoding of the same thing, which is what a weak tag says; it
    # still answers a revalidation of either form with a 304.
    etag, _ = response.get_etag()
    if etag:
        response.set_etag(etag, weak=True)


def install(app):
    """Compress this app's static files and text responses."""
    static_view = app.view_functions.get('static')

    if static_view is not None:
        def static_gzip(**kwargs):
            response = static_view(**kwargs)
            filename = kwargs.get('filename', '')
            response.vary.add('Accept-Encoding')
            if (response.status_code != 200 or not _wants_gzip()
                    or response.mimetype not in COMPRESSIBLE):
                return response
            path = safe_join(app.static_folder, filename)
            if not path or not os.path.isfile(path):
                return response
            stat = os.stat(path)
            hit = _static_cache.get(path)
            if hit is None or hit[0] != stat.st_mtime_ns or hit[1] != stat.st_size:
                with open(path, 'rb') as f:
                    data = f.read()
                if len(data) < MIN_BYTES:
                    return response
                hit = (stat.st_mtime_ns, stat.st_size, gzip.compress(data, 9, mtime=0))
                _static_cache[path] = hit
            # The file the static view opened is not going to be sent.
            if hasattr(response.response, 'close'):
                response.response.close()
            response.direct_passthrough = False
            _mark(response, hit[2])
            return response

        app.view_functions['static'] = static_gzip

    @app.after_request
    def gzip_response(response):
        if (response.direct_passthrough or response.is_streamed
                or response.status_code != 200
                or 'Content-Encoding' in response.headers
                or response.mimetype not in COMPRESSIBLE
                or request.path.startswith('/socket.io')):
            return response
        response.vary.add('Accept-Encoding')
        if not _wants_gzip():
            return response
        body = response.get_data()
        if len(body) < MIN_BYTES:
            return response
        _mark(response, gzip.compress(body, 6))
        return response
