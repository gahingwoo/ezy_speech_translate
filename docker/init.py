"""Get the volume ready before either server starts.

Runs at every container start, and does only what is missing or what the
environment asks for:

  * the directories the app writes to, inside the volume;
  * config.yaml, copied from the shipped default the first time;
  * the ports, HTTPS, and public URL, when set in the environment;
  * the admin password and the two signing secrets, the first time;
  * a self-signed certificate, when HTTPS is on and none covers these names.

The secrets are made here rather than left to the servers because the two
servers start together and each would otherwise make its own: whichever wrote
last would win the file, and the other would sign logins with a key nobody
else holds. Left alone, a fresh install's admin password was admin123.

Copyright (C) 2025-2026 Ga Hing Woo (Jiaxing Hu)

This file is part of EzySpeech, and is free software under the GNU Affero
General Public License, version 3 or later. See LICENSE and TRADEMARK.md.
"""

import datetime
import importlib.util
import ipaddress
import json
import os
import secrets
import shutil
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP))

from cryptography import x509  # noqa: E402
from cryptography.fernet import Fernet  # noqa: E402
from cryptography.hazmat.primitives import hashes, serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import ec  # noqa: E402
from cryptography.x509.oid import NameOID  # noqa: E402

import yaml  # noqa: E402

# By path: importing it through app.core would run that package's __init__,
# which loads config.yaml, and on a new install there is none yet.
_spec = importlib.util.spec_from_file_location(
    'config_edit', APP / 'app' / 'core' / 'config_edit.py')
_config_edit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_config_edit)
write_in_place = _config_edit.write_in_place
from secure_loader import (  # noqa: E402
    _atomic_write_0600, _is_strong_secret, client_hash, make_verifier, is_verifier,
)

STATE = Path(os.environ.get('EZY_STATE', '/var/lib/ezyspeech'))
CONFIG = STATE / 'config' / 'config.yaml'
SECRETS = STATE / 'config' / 'secrets.key'
SSL = STATE / 'config' / 'ssl'
# The shipped config.yaml, set aside when the code is prepared to run: by the
# Dockerfile in the image, and by the ezyspeech command in a native release.
DEFAULT_CONFIG = next((p for p in (APP / 'docker' / 'defaults' / 'config.yaml',
                                   APP / 'config.dist' / 'config.yaml') if p.exists()),
                      APP / 'docker' / 'defaults' / 'config.yaml')

# No 0/O, 1/l/I: it gets read off a screen and typed on a phone.
_ALPHABET = 'abcdefghjkmnpqrstuvwxyz23456789'


def say(message=''):
    print(message, flush=True)


def readable_password():
    """Four groups of four: 80 bits, and it can be read aloud."""
    chars = ''.join(secrets.choice(_ALPHABET) for _ in range(16))
    return '-'.join(chars[i:i + 4] for i in range(0, 16, 4))


def env_flag(name):
    value = os.environ.get(name)
    if value is None or value.strip() == '':
        return None
    return value.strip().lower() in ('1', 'true', 'yes', 'on', 'self-signed')


# ── directories and config ───────────────────────────────────────────────────

def make_directories():
    for sub in ('config', 'config/ssl', 'data', 'logs', 'exports', 'oem'):
        (STATE / sub).mkdir(parents=True, exist_ok=True)


def seed_config():
    if CONFIG.exists():
        return False
    shutil.copyfile(DEFAULT_CONFIG, CONFIG)
    say(f'New install: config written to {CONFIG}')
    return True


def apply_environment():
    """What the environment sets, written into the file so the settings screen
    shows what is really running. Anything not set is left as the file has it."""
    changes = {
        # In a container the servers must listen beyond loopback; which
        # outside interfaces reach them is decided by the published ports.
        'server.host': '0.0.0.0',
        'admin_server.host': '0.0.0.0',
    }
    for env, key in (('EZY_PORT', 'server.port'), ('EZY_ADMIN_PORT', 'admin_server.port')):
        value = os.environ.get(env, '').strip()
        if value:
            if not value.isdigit() or not 0 < int(value) < 65536:
                raise SystemExit(f'{env}={value!r} is not a port number')
            changes[key] = int(value)
    https = env_flag('EZY_HTTPS')
    if https is not None:
        changes['server.use_https'] = https
        changes['admin_server.use_https'] = https
    url = os.environ.get('EZY_EXTERNAL_URL', '').strip().rstrip('/')
    if url:
        changes['server.external_url'] = None if url.lower() == 'none' else url

    text = CONFIG.read_text(encoding='utf-8')
    current = yaml.safe_load(text) or {}

    def now(path):
        node = current
        for part in path.split('.'):
            if not isinstance(node, dict):
                return object()
            node = node.get(part)
        return node

    pending = {k: v for k, v in changes.items() if now(k) != v}
    if not pending:
        return current
    updated = write_in_place(text, pending)
    if updated is None:
        raise SystemExit('config.yaml has been edited into a shape this cannot '
                         'update in place; set these in the file instead: '
                         + ', '.join(pending))
    CONFIG.write_text(updated, encoding='utf-8')
    say('Settings from the environment: '
        + ', '.join(f'{k}={v}' for k, v in pending.items()))
    return yaml.safe_load(updated) or {}


# ── secrets ──────────────────────────────────────────────────────────────────

def load_secrets():
    raw = {}
    if SECRETS.exists():
        try:
            raw = json.loads(SECRETS.read_text(encoding='utf-8')) or {}
        except Exception:
            raise SystemExit(f'{SECRETS} is not readable; move it aside to start over')
    if not raw.get('fernet_key'):
        raw['fernet_key'] = Fernet.generate_key().decode()
    return raw, Fernet(raw['fernet_key'].encode())


def stored(raw, fernet, field):
    token = raw.get(field) or ''
    if not token:
        return None
    try:
        return fernet.decrypt(token.encode()).decode()
    except Exception:
        return None


def ensure_secrets(new_password=None):
    """Signing secrets if missing, and the admin password if missing or if a
    new one is given. Returns the password when it was set by this call."""
    raw, fernet = load_secrets()
    changed = False
    for field in ('jwt_secret', 'server_secret_key'):
        if not _is_strong_secret(stored(raw, fernet, field)):
            raw[field] = fernet.encrypt(secrets.token_urlsafe(48).encode()).decode()
            changed = True

    # Kept as a hash only. An older install's encrypted password counts as
    # set: the servers convert it on their first start.
    password = None
    has_password = is_verifier(raw.get('admin_password_hash')) \
        or stored(raw, fernet, 'admin_password') is not None
    if new_password is not None or not has_password:
        password = new_password or os.environ.get('EZY_ADMIN_PASSWORD', '').strip() \
            or readable_password()
        if len(password) < 8:
            raise SystemExit('The admin password must be at least 8 characters')
        raw['admin_password_hash'] = make_verifier(client_hash(password))
        raw.pop('admin_password', None)
        changed = True

    if changed:
        _atomic_write_0600(SECRETS, json.dumps(raw, indent=2))
    return password


def announce(password, config):
    user = (config.get('authentication') or {}).get('admin_username') or 'admin'
    port = (config.get('admin_server') or {}).get('port', 1916)
    scheme = 'https' if (config.get('admin_server') or {}).get('use_https') else 'http'
    line = '=' * 60
    say(line)
    say('  EzySpeech admin sign-in')
    say(f'  Console:   {scheme}://<this machine>:{port}/')
    say(f'  Username:  {user}')
    say(f'  Password:  {password}')
    say('  Shown this once. To set another:  ezyspeech password')
    say(line)


# ── certificate ──────────────────────────────────────────────────────────────

def wanted_names():
    # Not the container's own hostname: it changes whenever the container is
    # recreated, and every upgrade would make a new certificate for everyone
    # to accept again.
    names = {'localhost', '127.0.0.1'}
    for name in os.environ.get('EZY_HOSTNAMES', '').replace(' ', ',').split(','):
        if name.strip():
            names.add(name.strip())
    return names


def covered_names(cert):
    try:
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    except x509.ExtensionNotFound:
        return set()
    return {str(v) for v in san.get_values_for_type(x509.DNSName)} | \
           {str(v) for v in san.get_values_for_type(x509.IPAddress)}


def ensure_certificate(config):
    if not ((config.get('server') or {}).get('use_https')
            or (config.get('admin_server') or {}).get('use_https')):
        return
    cert_path, key_path = SSL / 'cert.pem', SSL / 'key.pem'
    names = wanted_names()
    if cert_path.exists() and key_path.exists():
        cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
        issuer_is_us = cert.issuer == cert.subject
        expires = cert.not_valid_after_tzinfo if hasattr(cert, 'not_valid_after_tzinfo') \
            else cert.not_valid_after.replace(tzinfo=datetime.timezone.utc)
        fresh = expires - datetime.datetime.now(datetime.timezone.utc) > datetime.timedelta(days=30)
        # A certificate someone put here themselves is theirs to renew.
        if not issuer_is_us or (fresh and names <= covered_names(cert)):
            return

    key = ec.generate_private_key(ec.SECP256R1())
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'EzySpeech')])
    alt = []
    for name in sorted(names):
        try:
            alt.append(x509.IPAddress(ipaddress.ip_address(name)))
        except ValueError:
            alt.append(x509.DNSName(name))
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder()
            .subject_name(subject).issuer_name(subject)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(minutes=5))
            .not_valid_after(now + datetime.timedelta(days=825))
            .add_extension(x509.SubjectAlternativeName(alt), critical=False)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .sign(key, hashes.SHA256()))
    _atomic_write_0600(key_path, key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption()).decode())
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    say('Self-signed certificate made for: ' + ', '.join(sorted(names)))


def main(argv):
    make_directories()
    seed_config()
    config = apply_environment()
    if argv[:1] == ['password']:
        password = ensure_secrets(new_password=(argv[1] if len(argv) > 1 else '') or readable_password())
        announce(password, config)
        say('Restart for it to take effect:  docker compose restart')
        return
    password = ensure_secrets()
    if password:
        announce(password, config)
    ensure_certificate(config)


if __name__ == '__main__':
    main(sys.argv[1:])
