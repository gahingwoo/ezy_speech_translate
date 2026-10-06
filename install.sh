#!/usr/bin/env bash
# EzySpeech one-step install, and update: run it again to upgrade.
#
#   curl -fsSL https://raw.githubusercontent.com/gahingwoo/ezy_speech_translate/main/install.sh | bash
#
# or from a copy of the code:   ./install.sh
#
# Options (each also settable as the environment variable in brackets):
#   --dir DIR             where the code goes        [EZY_DIR, default ~/ezyspeech]
#   --port N              listener page port         [EZY_PORT, default 1915]
#   --admin-port N        operator console port      [EZY_ADMIN_PORT, default 1916]
#   --https               self-signed HTTPS, so the console's microphone works
#                         from another computer      [EZY_HTTPS=self-signed]
#   --no-https            plain HTTP                 [EZY_HTTPS=off]
#   --external-url URL    public address, when a tunnel or proxy is in front
#   --yes                 ask nothing; take the defaults
#
# Runs on Linux and macOS, with Docker. On Linux it offers to install Docker
# if it is missing; on a Mac, install OrbStack or Docker Desktop first.
#
# Copyright (C) 2025-2026 Ga Hing Woo (Jiaxing Hu)
# This file is part of EzySpeech, and is free software under the GNU Affero
# General Public License, version 3 or later. See LICENSE and TRADEMARK.md.

# Everything is inside main(), called on the last line, so a download cut off
# half way through runs nothing at all.
main() {
set -euo pipefail

REPO="https://github.com/gahingwoo/ezy_speech_translate"
TARBALL="https://codeload.github.com/gahingwoo/ezy_speech_translate/tar.gz/refs/heads/main"
PROJECT="ezyspeech"
VOLUME="${PROJECT}_ezyspeech"

DIR="${EZY_DIR:-}"
PORT="${EZY_PORT:-}"
ADMIN_PORT="${EZY_ADMIN_PORT:-}"
HTTPS="${EZY_HTTPS:-}"
EXTERNAL_URL="${EZY_EXTERNAL_URL:-}"
ASSUME_YES="${EZY_YES:-}"

while [ $# -gt 0 ]; do
    case "$1" in
        --dir)          DIR="$2"; shift 2 ;;
        --port)         PORT="$2"; shift 2 ;;
        --admin-port)   ADMIN_PORT="$2"; shift 2 ;;
        --https)        HTTPS="self-signed"; shift ;;
        --no-https)     HTTPS="off"; shift ;;
        --external-url) EXTERNAL_URL="$2"; shift 2 ;;
        --yes|-y)       ASSUME_YES=1; shift ;;
        -h|--help)      sed -n '2,22p' "${BASH_SOURCE[0]:-/dev/null}" 2>/dev/null \
                            || echo "See the top of install.sh"; return 0 ;;
        *)              die "Unknown option: $1 (try --help)" ;;
    esac
done

for value in "$PORT" "$ADMIN_PORT"; do
    if [ -n "$value" ] && ! [[ "$value" =~ ^[0-9]+$ && "$value" -ge 1 && "$value" -le 65535 ]]; then
        die "Not a port number: $value"
    fi
done

say "EzySpeech installer"

# ── Docker ───────────────────────────────────────────────────────────────────
OS="$(uname -s)"
case "$OS" in
    Linux|Darwin) ;;
    *) die "This installer runs on Linux and macOS. On Windows, use Docker Desktop with WSL and run it inside WSL." ;;
esac

if ! command -v docker >/dev/null 2>&1; then
    if [ "$OS" = "Darwin" ]; then
        die "Docker is not installed. Install OrbStack (https://orbstack.dev) or Docker Desktop, start it, and run this again."
    fi
    if ask "Docker is not installed. Install it now with Docker's own script (get.docker.com)?" y; then
        need curl
        curl -fsSL https://get.docker.com | as_root sh
        as_root systemctl enable --now docker 2>/dev/null || true
    else
        die "Docker is needed. See https://docs.docker.com/engine/install/"
    fi
fi

DOCKER=(docker)
if ! docker info >/dev/null 2>&1; then
    if [ "$OS" = "Linux" ] && command -v sudo >/dev/null 2>&1 && sudo docker info >/dev/null 2>&1; then
        DOCKER=(sudo docker)
        note "Using sudo for Docker. To avoid it: sudo usermod -aG docker \$USER, then log in again."
    elif [ "$OS" = "Darwin" ]; then
        die "Docker is installed but not running. Start OrbStack or Docker Desktop, then run this again."
    else
        die "Docker is installed but not running: sudo systemctl start docker"
    fi
fi
"${DOCKER[@]}" compose version >/dev/null 2>&1 \
    || die "Docker Compose v2 is needed (the 'docker compose' command). Update Docker, or install the compose plugin."

# ── The code ─────────────────────────────────────────────────────────────────
HERE=""
if [ -n "${BASH_SOURCE[0]:-}" ] && [ -f "${BASH_SOURCE[0]}" ]; then
    HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi
if [ -z "$DIR" ] && [ -n "$HERE" ] && [ -f "$HERE/compose.yaml" ] && [ -f "$HERE/Dockerfile" ]; then
    DIR="$HERE"
    say "Using the code in $DIR"
else
    DIR="${DIR:-$HOME/ezyspeech}"
    if [ -d "$DIR/.git" ]; then
        say "Updating the code in $DIR"
        git -C "$DIR" pull --ff-only
    elif [ -f "$DIR/compose.yaml" ]; then
        say "Updating the code in $DIR"
        fetch_tarball "$DIR"
    elif command -v git >/dev/null 2>&1; then
        say "Downloading EzySpeech into $DIR"
        git clone --depth 1 "$REPO" "$DIR"
    else
        say "Downloading EzySpeech into $DIR"
        fetch_tarball "$DIR"
    fi
fi
cd "$DIR"

# ── Settings (.env) ──────────────────────────────────────────────────────────
FIRST_INSTALL=1
"${DOCKER[@]}" volume inspect "$VOLUME" >/dev/null 2>&1 && FIRST_INSTALL=0
touch .env

if [ "$FIRST_INSTALL" = 1 ] && [ -z "$HTTPS" ] && [ -z "$EXTERNAL_URL" ]; then
    HTTPS="off"
    if interactive; then
        say ""
        say "The operator's console listens to the speaker through the browser, and"
        say "browsers only allow the microphone over HTTPS, or on the machine itself."
        if ask "Will the console be opened on a different computer from this one?" n; then
            HTTPS="self-signed"
        fi
    fi
fi

IP="$(lan_ip)"
[ -n "$PORT" ]         && set_env EZY_PORT "$PORT"
[ -n "$ADMIN_PORT" ]   && set_env EZY_ADMIN_PORT "$ADMIN_PORT"
[ -n "$HTTPS" ]        && set_env EZY_HTTPS "$HTTPS"
[ -n "$EXTERNAL_URL" ] && set_env EZY_EXTERNAL_URL "$EXTERNAL_URL"
if [ "$(get_env EZY_HTTPS)" = "self-signed" ]; then
    names="$(hostname 2>/dev/null || true)"
    [ -n "$IP" ] && names="$IP,$names"
    case "$names" in *.local*|"") ;; *) names="$names,$(hostname -s 2>/dev/null || hostname).local" ;; esac
    set_env EZY_HOSTNAMES "$names"
fi
[ -z "$(get_env TZ)" ] && [ -n "$(host_tz)" ] && set_env TZ "$(host_tz)"

PORT="$(get_env EZY_PORT)"; PORT="${PORT:-1915}"
ADMIN_PORT="$(get_env EZY_ADMIN_PORT)"; ADMIN_PORT="${ADMIN_PORT:-1916}"
SCHEME="http"; [ "$(get_env EZY_HTTPS)" = "self-signed" ] && SCHEME="https"

# ── Build and start ──────────────────────────────────────────────────────────
say ""
say "Building the image (a minute or two the first time)..."
"${DOCKER[@]}" compose build --pull

SIGN_IN=""
if [ "$FIRST_INSTALL" = 1 ]; then
    # The volume is prepared, and the admin password made, before the servers
    # start; it is printed once, here.
    SIGN_IN="$("${DOCKER[@]}" compose run --rm --no-deps ezyspeech init 2>&1)" \
        || { echo "$SIGN_IN"; die "Setting up the new install failed."; }
fi

"${DOCKER[@]}" compose up -d --remove-orphans

say "Waiting for it to start..."
container="$("${DOCKER[@]}" compose ps -q ezyspeech)"
status=""
for _ in $(seq 1 60); do
    status="$("${DOCKER[@]}" inspect --format '{{.State.Health.Status}}' "$container" 2>/dev/null || true)"
    [ "$status" = "healthy" ] && break
    sleep 2
done
if [ "$status" != "healthy" ]; then
    "${DOCKER[@]}" compose logs --tail 40 ezyspeech || true
    die "It did not come up healthy. The log is above; 'docker compose logs' in $DIR has the rest."
fi

# ── Done ─────────────────────────────────────────────────────────────────────
host="${IP:-localhost}"
external="$(get_env EZY_EXTERNAL_URL)"
say ""
say "============================================================"
say "  EzySpeech is running."
say ""
if [ -n "$external" ] && [ "$external" != "none" ]; then
    say "  Listeners:   $external"
else
    say "  Listeners:   $SCHEME://$host:$PORT"
fi
say "  Projection:  $SCHEME://$host:$PORT/projection"
say "  Console:     $SCHEME://$host:$ADMIN_PORT"
if [ -n "$SIGN_IN" ]; then
    user="$(printf '%s\n' "$SIGN_IN" | sed -n 's/.*Username:  *//p' | head -1)"
    pass="$(printf '%s\n' "$SIGN_IN" | sed -n 's/.*Password:  *//p' | head -1)"
    say ""
    say "  Sign in as:  ${user:-admin}"
    say "  Password:    ${pass:-(see: docker compose logs ezyspeech)}"
    say "  Write it down: it is not shown again."
fi
if [ "$SCHEME" = "https" ]; then
    say ""
    say "  The certificate is self-signed, so each browser warns the first time."
    say "  On the console's computer, open both addresses above once and accept."
elif [ -z "$external" ] || [ "$external" = "none" ]; then
    say ""
    say "  The console's microphone works when it is opened on this machine"
    say "  (http://localhost:$ADMIN_PORT). From another computer, run again with --https."
fi
say ""
say "  In $DIR:"
say "    update             ./install.sh"
say "    new password       docker compose exec ezyspeech ezyspeech password"
say "                       docker compose restart"
say "    logs               docker compose logs -f"
say "    stop / start       docker compose stop / docker compose start"
say "  Everything it keeps is in the Docker volume $VOLUME."
say "============================================================"
}

# ── helpers ──────────────────────────────────────────────────────────────────
say()  { printf '%s\n' "$*"; }
note() { printf '  %s\n' "$*"; }
die()  { printf '\nError: %s\n' "$*" >&2; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || die "$1 is needed and is not installed."; }

as_root() {
    if [ "$(id -u)" = 0 ]; then "$@"
    elif command -v sudo >/dev/null 2>&1; then sudo "$@"
    else die "This step needs root, and sudo is not available."
    fi
}

# Questions come from the terminal even when the script itself arrives on a
# pipe; with no terminal, or with --yes, the default is taken.
interactive() {
    [ -z "${ASSUME_YES:-}" ] && { : </dev/tty; } 2>/dev/null
}

ask() {
    local question="$1" default="$2" reply hint="[y/N]"
    [ "$default" = y ] && hint="[Y/n]"
    if ! interactive; then
        [ "$default" = y ]; return
    fi
    printf '%s %s ' "$question" "$hint" >/dev/tty
    read -r reply </dev/tty || reply=""
    reply="${reply:-$default}"
    [[ "$reply" =~ ^[Yy] ]]
}

get_env() { sed -n "s/^$1=//p" .env 2>/dev/null | tail -1; }

set_env() {
    local key="$1" value="$2" tmp
    tmp="$(mktemp)"
    grep -v "^$key=" .env > "$tmp" 2>/dev/null || true
    printf '%s=%s\n' "$key" "$value" >> "$tmp"
    cat "$tmp" > .env
    rm -f "$tmp"
}

fetch_tarball() {
    local dest="$1" tmp
    need curl; need tar
    tmp="$(mktemp -d)"
    curl -fsSL "$TARBALL" | tar -xz -C "$tmp" --strip-components 1
    mkdir -p "$dest"
    # Over the top of an existing copy; its .env, the only thing it adds, stays.
    cp -R "$tmp"/. "$dest"/
    rm -rf "$tmp"
}

lan_ip() {
    local ip="" iface
    if [ "$(uname -s)" = "Darwin" ]; then
        iface="$(route -n get default 2>/dev/null | awk '/interface:/ {print $2}')"
        [ -n "$iface" ] && ip="$(ipconfig getifaddr "$iface" 2>/dev/null || true)"
    else
        ip="$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for (i = 1; i < NF; i++) if ($i == "src") {print $(i + 1); exit}}')"
        [ -z "$ip" ] && ip="$(hostname -I 2>/dev/null | awk '{print $1}')"
    fi
    printf '%s' "$ip"
}

host_tz() {
    local tz=""
    if command -v timedatectl >/dev/null 2>&1; then
        tz="$(timedatectl show -p Timezone --value 2>/dev/null || true)"
    fi
    if [ -z "$tz" ] && [ -L /etc/localtime ]; then
        tz="$(readlink /etc/localtime | sed 's|.*/zoneinfo/||')"
    fi
    printf '%s' "$tz"
}

main "$@"
