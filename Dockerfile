# EzySpeech: both servers in one container, everything they write in one volume.
#
#   docker compose up -d          (see compose.yaml and install.sh)
#
# The listener page and the operator's console run as two processes that talk
# to each other over localhost, so they share a container rather than a network.

# Named in full: Podman on RHEL and its kin will not guess a registry for a
# short name when there is no one to ask, as in an install script.
FROM docker.io/library/python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    EZY_STATE=/var/lib/ezyspeech

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# The app reads and writes config/, data/, logs/, exports/ and app/static/oem/
# beside its code. Each becomes a link into the volume, so the code stays
# read-only and an upgrade replaces the image without touching an install.
# The shipped config.yaml is kept aside as the default a new install starts from.
RUN mkdir -p docker/defaults \
 && mv config/config.yaml docker/defaults/config.yaml \
 && rm -rf config data logs exports app/static/oem \
 && ln -s "$EZY_STATE/config"  config \
 && ln -s "$EZY_STATE/data"    data \
 && ln -s "$EZY_STATE/logs"    logs \
 && ln -s "$EZY_STATE/exports" exports \
 && ln -s "$EZY_STATE/oem"     app/static/oem \
 && useradd --system --uid 10001 --home-dir "$EZY_STATE" ezyspeech \
 && mkdir -p "$EZY_STATE" \
 && chown ezyspeech:ezyspeech "$EZY_STATE" \
 && install -m 0755 docker/entrypoint.sh /usr/local/bin/ezyspeech \
 # Readable whatever umask the checkout was made with: the servers do not run as root.
 && chmod -R a+rX /app

USER ezyspeech
VOLUME ["/var/lib/ezyspeech"]
EXPOSE 1915 1916

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "docker/healthcheck.py"]

ENTRYPOINT ["ezyspeech"]
CMD ["serve"]
