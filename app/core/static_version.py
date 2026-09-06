"""Cache-busting URLs for the files under app/static.

A stylesheet or a script edited in place is the one thing a browser will go on
serving from its cache long after the server has moved on, which is how an
operator ends up looking at last week's admin panel. Each URL built here
carries eight characters of a hash of that file's own contents, so a changed
file is a different URL and an unchanged one keeps being served from cache.

Templates use it in place of a hardcoded path:

    <link href="{{ static_url('css/admin.css') }}" rel="stylesheet">

The hash is computed once per file and remembered against the file's
modification time, so an edit is picked up without a restart during
development and costs one stat() per reference in production.

Nothing here changes how the app is served: it only decorates the URL.
"""
import hashlib
import pathlib


def make_static_url(static_dir, url_prefix="/static"):
    """Return a static_url(path) function bound to one static directory."""
    root = pathlib.Path(static_dir)
    cache = {}

    def static_url(path):
        path = str(path).lstrip("/")
        target = root / path
        try:
            stamp = target.stat().st_mtime_ns
        except OSError:
            # A path that does not exist is left alone rather than raising:
            # a missing file should show up as a 404 in the browser, not as a
            # server error on every page that mentions it.
            return "%s/%s" % (url_prefix, path)

        cached = cache.get(path)
        if cached is None or cached[0] != stamp:
            digest = hashlib.sha256(target.read_bytes()).hexdigest()[:8]
            cache[path] = (stamp, digest)
            cached = cache[path]
        return "%s/%s?v=%s" % (url_prefix, path, cached[1])

    return static_url
