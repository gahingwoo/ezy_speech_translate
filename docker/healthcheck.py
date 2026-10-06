"""Healthy when both servers answer. The image has no curl; Python is there.

Copyright (C) 2025-2026 Ga Hing Woo (Jiaxing Hu)
This file is part of EzySpeech, and is free software under the GNU Affero
General Public License, version 3 or later. See LICENSE and TRADEMARK.md.
"""
import os
import ssl
import sys
import urllib.request

import yaml

config_path = os.path.join(os.environ.get('EZY_STATE', '/var/lib/ezyspeech'),
                           'config', 'config.yaml')
with open(config_path, encoding='utf-8') as f:
    config = yaml.safe_load(f) or {}

# The certificate may be self-signed; this asks whether the server is up,
# not whether it is trusted.
insecure = ssl.create_default_context()
insecure.check_hostname = False
insecure.verify_mode = ssl.CERT_NONE

for section, default_port, path in (('server', 1915, '/api/health'),
                                    ('admin_server', 1916, '/health')):
    conf = config.get(section) or {}
    scheme = 'https' if conf.get('use_https') else 'http'
    url = f"{scheme}://127.0.0.1:{conf.get('port', default_port)}{path}"
    try:
        urllib.request.urlopen(url, timeout=4, context=insecure).read()
    except Exception as exc:
        print(f'{url}: {exc}')
        sys.exit(1)
